#!/usr/bin/env bash
set -euo pipefail

PORT=8001
RELOAD=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --reload) RELOAD=1; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/Backend"
PYTHON="$BACKEND_DIR/.venv/bin/python"
[[ -x "$PYTHON" ]] || python3 -m venv "$BACKEND_DIR/.venv"
"$PYTHON" -m pip install -q -r "$BACKEND_DIR/requirements.txt"
cd "$BACKEND_DIR"
if [[ "$RELOAD" -eq 1 ]]; then
  exec "$PYTHON" -m flask --app app.main run --host 127.0.0.1 --port "$PORT" --debug
fi
exec "$PYTHON" -m waitress --listen="127.0.0.1:$PORT" app.main:app
