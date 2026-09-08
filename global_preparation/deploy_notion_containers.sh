#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: bash global_preparation/deploy_notion_containers.sh [--check | --dry-run] [true|false]

Prepare the local mail backend for finalpool/notion-find-job and notion-hr.
The other six tasks in configs/task_lists/finalpool/c-notion.txt do not
require Poste deployment.
Default: rebuild this instance's Poste container, DELETE its mail data, and
initialize accounts using deployment/poste/scripts/setup.sh start.
The optional true|false controls Dovecot configuration (default: true).

  --check    Only check the existing Poste container's published services.
  --dry-run  Show the setup command without reading credentials or deploying.

POSTE_READY_TIMEOUT_SECONDS sets the readiness wait (default: 180 seconds).
Notion credentials and remote pages are handled separately by setup/preprocess.
EOF
}

MODE=deploy
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    usage
    exit 0
fi
if [[ "${1:-}" == --check || "${1:-}" == --dry-run ]]; then
    MODE=${1#--}
    shift
fi
if (( $# > 1 )) || [[ "${1:-true}" != true && "${1:-true}" != false ]]; then
    usage >&2
    exit 2
fi
CONFIGURE_DOVECOT=${1:-true}
READY_TIMEOUT=${POSTE_READY_TIMEOUT_SECONDS:-180}
if ! [[ "$READY_TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: POSTE_READY_TIMEOUT_SECONDS must be a positive integer" >&2
    exit 2
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ "$MODE" == dry-run ]]; then
    echo "Working directory: $PROJECT_ROOT"
    echo "Rebuild Poste and clear deployment/poste/data and deployment/poste/configs:"
    echo "bash deployment/poste/scripts/setup.sh start $CONFIGURE_DOVECOT"
    echo "Then check Poste's published HTTP, IMAP, SMTP and submission ports."
    exit 0
fi

for dependency in uv curl timeout nc awk; do
    command -v "$dependency" >/dev/null || { echo "Missing command: $dependency" >&2; exit 1; }
done
SETTINGS=$(uv run python - <<'PY'
import yaml
from configs.global_configs import global_configs

with open("configs/ports_config.yaml") as stream:
    suffix = (yaml.safe_load(stream) or {}).get("instance_suffix", "") or ""
runtime = global_configs.podman_or_docker
if runtime not in ("docker", "podman"):
    raise ValueError("podman_or_docker must be docker or podman")
print(runtime)
print("poste" + suffix)
PY
)
mapfile -t SETTINGS_LINES <<< "$SETTINGS"
CTR=${SETTINGS_LINES[0]}
CONTAINER_NAME=${SETTINGS_LINES[1]}
command -v "$CTR" >/dev/null || { echo "Missing command: $CTR" >&2; exit 1; }

if [[ "$MODE" == deploy ]]; then
    command -v jq >/dev/null || { echo "Missing command: jq" >&2; exit 1; }
    echo "Rebuilding $CONTAINER_NAME; existing Poste mail data will be cleared."
    bash deployment/poste/scripts/setup.sh start "$CONFIGURE_DOVECOT"
    # The existing account initializer can exit zero after partial failures.
    jq -e '.statistics.users_failed == 0 and .statistics.users_created > 0' \
        deployment/poste/configs/created_accounts.json >/dev/null || {
        echo "Error: Poste account initialization is incomplete; inspect setup output." >&2
        exit 1
    }
fi

# Query actual published ports so apply_port_numbers.py needs no new entries.
published_port() {
    local port
    port=$("$CTR" port "$CONTAINER_NAME" "$1/tcp" | awk -F: 'NR == 1 {print $NF}')
    [[ "$port" =~ ^[0-9]+$ ]] || { echo "Missing published port: $1/tcp" >&2; return 1; }
    echo "$port"
}
WEB_PORT=$(published_port 80)
IMAP_PORT=$(published_port 143)
SMTP_PORT=$(published_port 25)
SUBMISSION_PORT=$(published_port 587)

probe_mail() {
    local code port
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost:$WEB_PORT/") || return 1
    [[ "$code" == 200 || "$code" == 302 ]] || return 1
    printf 'a1 CAPABILITY\r\na2 LOGOUT\r\n' \
        | timeout 5 nc -w 3 localhost "$IMAP_PORT" | grep -q 'IMAP4rev1' || return 1
    for port in "$SMTP_PORT" "$SUBMISSION_PORT"; do
        printf 'EHLO healthcheck\r\nQUIT\r\n' \
            | timeout 5 nc -w 3 localhost "$port" | grep -q 'ESMTP' || return 1
    done
}

echo "Checking $CONTAINER_NAME: HTTP=$WEB_PORT IMAP=$IMAP_PORT SMTP=$SMTP_PORT submission=$SUBMISSION_PORT"
deadline=$((SECONDS + READY_TIMEOUT))
while ! probe_mail; do
    if (( SECONDS >= deadline )); then
        echo "Error: Poste services did not become ready within ${READY_TIMEOUT}s." >&2
        echo "Inspect with: $CTR logs $CONTAINER_NAME" >&2
        exit 1
    fi
    sleep 2
done
echo "Poste service probes passed. Notion authorization and task execution were not checked."
