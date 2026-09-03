#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  bash scripts/run_parallel_task_list.sh \
    <task-list-file> <dump-path> \
    [model-name] [provider] [workers] [image-name] [config-file] \
    [runner] [runmode] [agent-framework]

Defaults match scripts/run_parallel.sh. Relative task-list and dump paths are
resolved from the repository root.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
    exit 0
fi

if [ "$#" -lt 2 ] || [ "$#" -gt 10 ]; then
    usage >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

TASK_LIST_FILE=$1
DUMP_PATH=$2
MODEL_NAME=${3:-gpt-5-mini}
MODEL_PROVIDER=${4:-unified}
WORKERS=${5:-10}
IMAGE_NAME=${6:-lockon0927/toolathlon-task-image:1016beta}
CONFIG_FILE=${7:-}
RUNNER=${8:-containerized}
RUNMODE=${9:-normal}
AGENT_FRAMEWORK=${10:-}

case "$TASK_LIST_FILE" in
    /*) ;;
    *) TASK_LIST_FILE="$PROJECT_ROOT/$TASK_LIST_FILE" ;;
esac
case "$DUMP_PATH" in
    /*) ;;
    *) DUMP_PATH="$PROJECT_ROOT/$DUMP_PATH" ;;
esac

if [ ! -f "$TASK_LIST_FILE" ]; then
    echo "Error: task-list file does not exist: $TASK_LIST_FILE" >&2
    exit 2
fi

if ! grep -Eq '^[[:space:]]*[^#[:space:]]' "$TASK_LIST_FILE"; then
    echo "Error: task-list file contains no tasks: $TASK_LIST_FILE" >&2
    exit 2
fi

mkdir -p "$DUMP_PATH"
exec 9>"$DUMP_PATH/.run_parallel_task_list.lock"
if ! flock -n 9; then
    echo "Error: another grouped evaluation is using dump path: $DUMP_PATH" >&2
    exit 2
fi

echo "Task list: $TASK_LIST_FILE"
echo "Dump path: $DUMP_PATH"

cd "$PROJECT_ROOT"
TASK_LIST="$TASK_LIST_FILE" bash -o pipefail scripts/run_parallel.sh \
    "$MODEL_NAME" \
    "$DUMP_PATH" \
    "$MODEL_PROVIDER" \
    "$WORKERS" \
    "$IMAGE_NAME" \
    "$CONFIG_FILE" \
    "$RUNNER" \
    "$RUNMODE" \
    "$AGENT_FRAMEWORK"
