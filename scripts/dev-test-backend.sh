#!/usr/bin/env bash
set -euo pipefail

TEST_ROOT="${SECRETBASE_TEST_DATA_ROOT:-/tmp/secretbase-test-runtime}"
TEST_PORT="${SECRETBASE_TEST_PORT:-10014}"
TEST_PASSWORD="${SECRETBASE_TEST_PASSWORD:-SecretBase-Test-123456!}"
RESET=0

usage() {
    cat <<EOF
Usage: scripts/dev-test-backend.sh [--reset]

Starts an isolated SecretBase test backend for manual API testing.

Environment overrides:
  SECRETBASE_TEST_DATA_ROOT  Default: /tmp/secretbase-test-runtime
  SECRETBASE_TEST_PORT       Default: 10014
  SECRETBASE_TEST_PASSWORD   Default: SecretBase-Test-123456!
  PYTHON                     Default: venv/bin/python if present, otherwise python3

The test backend stores vault, settings, backups, logs, and secure AI settings
under SECRETBASE_TEST_DATA_ROOT. It does not use the repository runtime data.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --reset)
            RESET=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TEST_ROOT="$(python3 -c 'import pathlib, sys; print(pathlib.Path(sys.argv[1]).expanduser().resolve())' "$TEST_ROOT")"

if [ "$TEST_ROOT" = "/" ] || [ -z "$TEST_ROOT" ]; then
    echo "Refusing to use unsafe SECRETBASE_TEST_DATA_ROOT: $TEST_ROOT" >&2
    exit 2
fi

if [ "$RESET" -eq 1 ]; then
    rm -rf "$TEST_ROOT"
fi

mkdir -p "$TEST_ROOT/data/backups" "$TEST_ROOT/logs"
chmod 700 "$TEST_ROOT" "$TEST_ROOT/data" "$TEST_ROOT/logs"

if [ -n "${PYTHON:-}" ]; then
    PYTHON_BIN="$PYTHON"
elif [ -x "$PROJECT_ROOT/venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
else
    PYTHON_BIN="python3"
fi

export SECRETBASE_MODE=desktop
export HOST=127.0.0.1
export PORT="$TEST_PORT"
export DATA_DIR="$TEST_ROOT/data"
export VAULT_PATH="$TEST_ROOT/data/secretbase.enc"
export BACKUP_DIR="$TEST_ROOT/data/backups"
export LOG_DIR="$TEST_ROOT/logs"
export SETTINGS_PATH="$TEST_ROOT/settings.json"
export CORS_ORIGINS="*"

unset DEEPSEEK_API_KEY
unset AI_API_KEY
unset AI_MODEL
unset AI_API_URL

cat <<EOF
SecretBase isolated test backend
URL: http://127.0.0.1:$TEST_PORT
Data root: $TEST_ROOT
Test password: $TEST_PASSWORD

Initialize if needed:
curl -sS -X POST http://127.0.0.1:$TEST_PORT/api/auth/init \\
  -H 'Content-Type: application/json' \\
  -d '{"password":"$TEST_PASSWORD"}'

Unlock:
curl -sS -X POST http://127.0.0.1:$TEST_PORT/api/auth/unlock \\
  -H 'Content-Type: application/json' \\
  -d '{"password":"$TEST_PASSWORD"}'

EOF

cd "$PROJECT_ROOT/backend"
exec "$PYTHON_BIN" -m uvicorn main:app --host 127.0.0.1 --port "$TEST_PORT"
