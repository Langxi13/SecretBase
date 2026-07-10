#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
REQUIREMENTS="$PROJECT_ROOT/backend/requirements.txt"
STAMP_FILE="$VENV_DIR/.secretbase-requirements.sha256"
PYTHON_COMMAND="${PYTHON_COMMAND:-python3}"

if ! command -v "$PYTHON_COMMAND" >/dev/null 2>&1; then
    echo "未找到 Python 3，请先安装 Python 3.10 或更高版本。" >&2
    exit 1
fi

if ! "$PYTHON_COMMAND" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "SecretBase 需要 Python 3.10 或更高版本。" >&2
    exit 1
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "正在创建本地虚拟环境..."
    "$PYTHON_COMMAND" -m venv "$VENV_DIR"
fi

if command -v sha256sum >/dev/null 2>&1; then
    REQUIREMENTS_HASH="$(sha256sum "$REQUIREMENTS" | awk '{print $1}')"
else
    REQUIREMENTS_HASH="$(shasum -a 256 "$REQUIREMENTS" | awk '{print $1}')"
fi

INSTALLED_HASH=""
if [ -f "$STAMP_FILE" ]; then
    INSTALLED_HASH="$(tr -d '\r\n' < "$STAMP_FILE")"
fi

if [ "$REQUIREMENTS_HASH" != "$INSTALLED_HASH" ]; then
    echo "正在安装或更新 SecretBase 依赖..."
    "$VENV_DIR/bin/python" -m pip install --disable-pip-version-check --upgrade pip
    "$VENV_DIR/bin/python" -m pip install --disable-pip-version-check -r "$REQUIREMENTS"
    printf '%s' "$REQUIREMENTS_HASH" > "$STAMP_FILE"
fi

exec "$VENV_DIR/bin/python" "$PROJECT_ROOT/desktop/launcher.py" "$@"
