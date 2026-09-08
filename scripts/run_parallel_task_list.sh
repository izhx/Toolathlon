#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  bash scripts/run_parallel_task_list.sh \
    [--attempts N] \
    [--deploy-before-attempt] \
    [--tasks-folder <name>] \
    [--task-list <task-list-file>] \
    <dump-path> \
    [model-name] [provider] [workers] [image-name] [config-file] \
    [runner] [runmode] [agent-framework]

Defaults match scripts/run_parallel.sh. --tasks-folder is relative to the
repository's tasks directory and defaults to finalpool. Without --task-list,
all tasks under the selected tasks folder are evaluated. Relative task-list
and dump paths are resolved from the repository root. Without --attempts,
dump-path keeps its existing meaning as the exact output directory. With
--attempts, dump-path is the experiment root. A full run is written to:

  <dump-path>/<model-name>__run<attempt>/

A filtered run is written to:

  <dump-path>/<model-name>__run<attempt>/<task-list-basename>/

Slashes in model-name are replaced with underscores in the directory name.

With --deploy-before-attempt, global_preparation/deploy_containers.sh is run
before every attempt. Deployment failure stops the remaining attempts. The
option is explicit; it is not enabled automatically for any task-list name.
EOF
}

ATTEMPTS=1
MULTI_ATTEMPT_LAYOUT=false
DEPLOY_BEFORE_ATTEMPT=false
TASKS_FOLDER="finalpool"
TASK_LIST_FILE=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        --attempts)
            if [ "$#" -lt 2 ]; then
                echo "Error: --attempts requires a positive integer" >&2
                usage >&2
                exit 2
            fi
            ATTEMPTS=$2
            MULTI_ATTEMPT_LAYOUT=true
            shift 2
            ;;
        --deploy-before-attempt)
            DEPLOY_BEFORE_ATTEMPT=true
            shift
            ;;
        --task-list)
            if [ "$#" -lt 2 ] || [[ "$2" == --* ]]; then
                echo "Error: --task-list requires a file path" >&2
                usage >&2
                exit 2
            fi
            TASK_LIST_FILE=$2
            shift 2
            ;;
        --tasks-folder)
            if [ "$#" -lt 2 ] || [[ "$2" == --* ]]; then
                echo "Error: --tasks-folder requires a directory name" >&2
                usage >&2
                exit 2
            fi
            TASKS_FOLDER=$2
            shift 2
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "Error: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
        *)
            break
            ;;
    esac
done

if [ "$#" -lt 1 ] || [ "$#" -gt 9 ]; then
    usage >&2
    exit 2
fi

if ! [[ "$ATTEMPTS" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: --attempts must be a positive integer" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TASKS_ROOT="$(realpath "$PROJECT_ROOT/tasks")"

if [[ "$TASKS_FOLDER" == /* ]]; then
    echo "Error: --tasks-folder must be relative to $TASKS_ROOT" >&2
    exit 2
fi

TASKS_FOLDER_PATH="$(realpath -m "$TASKS_ROOT/$TASKS_FOLDER")"
case "$TASKS_FOLDER_PATH" in
    "$TASKS_ROOT"/*) ;;
    *)
        echo "Error: --tasks-folder must stay under $TASKS_ROOT" >&2
        exit 2
        ;;
esac

if [ ! -d "$TASKS_FOLDER_PATH" ]; then
    echo "Error: tasks folder does not exist: $TASKS_FOLDER_PATH" >&2
    exit 2
fi
TASKS_FOLDER="${TASKS_FOLDER_PATH#"$TASKS_ROOT"/}"

DUMP_ROOT=$1
MODEL_NAME=${2:-glm-5.2}
MODEL_PROVIDER=${3:-unified}
WORKERS=${4:-10}
IMAGE_NAME=${5:-lockon0927/toolathlon-task-image:1016beta}
CONFIG_FILE=${6:-}
RUNNER=${7:-containerized}
RUNMODE=${8:-normal}
AGENT_FRAMEWORK=${9:-}
STORED_MODEL_SHORT_NAME=${MODEL_NAME//\//_}

case "$DUMP_ROOT" in
    /*) ;;
    *) DUMP_ROOT="$PROJECT_ROOT/$DUMP_ROOT" ;;
esac

if [ -f "$DUMP_ROOT" ] || [[ "$DUMP_ROOT" == *.txt ]]; then
    echo "Error: task-list is no longer a positional argument; use --task-list <file> before <dump-path>" >&2
    exit 2
fi

if [ -n "$TASK_LIST_FILE" ]; then
    case "$TASK_LIST_FILE" in
        /*) ;;
        *) TASK_LIST_FILE="$PROJECT_ROOT/$TASK_LIST_FILE" ;;
    esac

    if [ ! -f "$TASK_LIST_FILE" ]; then
        echo "Error: task-list file does not exist: $TASK_LIST_FILE" >&2
        exit 2
    fi

    if ! grep -Eq '^[[:space:]]*[^#[:space:]]' "$TASK_LIST_FILE"; then
        echo "Error: task-list file contains no tasks: $TASK_LIST_FILE" >&2
        exit 2
    fi
fi

mkdir -p "$DUMP_ROOT"
if [ -n "$TASK_LIST_FILE" ]; then
    TASK_LIST_BASENAME="$(basename "$TASK_LIST_FILE")"
    GROUP_NAME="${TASK_LIST_BASENAME%.txt}"
    TASK_LIST_LABEL="$TASK_LIST_FILE"
else
    GROUP_NAME="all-tasks"
    TASK_LIST_LABEL="all tasks (tasks/$TASKS_FOLDER)"
fi

if [ "$MULTI_ATTEMPT_LAYOUT" = true ]; then
    LOCK_DIR="$DUMP_ROOT/.run_parallel_task_list_locks"
    mkdir -p "$LOCK_DIR"
    LOCK_PATH="$LOCK_DIR/$GROUP_NAME.lock"
else
    LOCK_PATH="$DUMP_ROOT/.run_parallel_task_list.lock"
fi

exec 9>"$LOCK_PATH"
if ! flock -n 9; then
    echo "Error: another grouped evaluation is using this output: $DUMP_ROOT ($GROUP_NAME)" >&2
    exit 2
fi

echo "Task list: $TASK_LIST_LABEL"
echo "Tasks folder: tasks/$TASKS_FOLDER"
echo "Dump root: $DUMP_ROOT"
echo "Attempts: $ATTEMPTS"
echo "Deploy before each attempt: $DEPLOY_BEFORE_ATTEMPT"

cd "$PROJECT_ROOT"
for ((attempt = 1; attempt <= ATTEMPTS; attempt++)); do
    if [ "$MULTI_ATTEMPT_LAYOUT" = true ]; then
        RUN_DUMP_PATH="$DUMP_ROOT/${STORED_MODEL_SHORT_NAME}__run${attempt}"
        if [ -n "$TASK_LIST_FILE" ]; then
            RUN_DUMP_PATH="$RUN_DUMP_PATH/$GROUP_NAME"
        fi
    else
        RUN_DUMP_PATH="$DUMP_ROOT"
    fi

    echo
    echo "Attempt: $attempt/$ATTEMPTS"
    echo "Dump path: $RUN_DUMP_PATH"

    if [ "$DEPLOY_BEFORE_ATTEMPT" = true ]; then
        echo "Deploying local infrastructure before attempt $attempt/$ATTEMPTS..."
        bash global_preparation/deploy_containers.sh
    fi

    if [ -n "$TASK_LIST_FILE" ]; then
        TASKS_FOLDER="$TASKS_FOLDER" TASK_LIST="$TASK_LIST_FILE" bash -o pipefail scripts/run_parallel.sh \
            "$MODEL_NAME" \
            "$RUN_DUMP_PATH" \
            "$MODEL_PROVIDER" \
            "$WORKERS" \
            "$IMAGE_NAME" \
            "$CONFIG_FILE" \
            "$RUNNER" \
            "$RUNMODE" \
            "$AGENT_FRAMEWORK"
    else
        env -u TASK_LIST TASKS_FOLDER="$TASKS_FOLDER" bash -o pipefail scripts/run_parallel.sh \
            "$MODEL_NAME" \
            "$RUN_DUMP_PATH" \
            "$MODEL_PROVIDER" \
            "$WORKERS" \
            "$IMAGE_NAME" \
            "$CONFIG_FILE" \
            "$RUNNER" \
            "$RUNMODE" \
            "$AGENT_FRAMEWORK"
    fi
done
