#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/Backend"
PORT="${PORT:-8001}"
RELOAD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --reload) RELOAD=1; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

cd "$BACKEND"
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 PYTHONUNBUFFERED=1

if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 2 "http://127.0.0.1:$PORT/api/health" | grep -q '"status":"ok"'; then
  echo "FedUPI backend is already running on http://127.0.0.1:$PORT"
  exit 0
fi

PYTHON="$BACKEND/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  command -v python3 >/dev/null 2>&1 || { echo "Python 3.10+ is required." >&2; exit 1; }
  echo "Creating Backend/.venv..."
  python3 -m venv .venv
fi

if ! "$PYTHON" -c 'import fastapi, torch, sklearn, sqlalchemy, openpyxl, docx, reportlab' >/dev/null 2>&1; then
  echo "Installing backend dependencies..."
  "$PYTHON" -m pip install --upgrade pip
  "$PYTHON" -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
fi

if [[ ! -f artifacts/fedupi_model.pt ]]; then
  echo "No model artifact found; running bounded first-time training..."
  "$PYTHON" scripts/train.py --scale 0.5 --quick
fi

ARGS=(app.main:app --host 127.0.0.1 --port "$PORT")
if [[ "$RELOAD" -eq 1 ]]; then
  echo "WARNING: reload mode uses extra memory; do not combine it with training or tests." >&2
  ARGS+=(--reload --reload-dir app)
fi

echo "Backend: http://127.0.0.1:$PORT  (API docs: /docs)"
exec "$PYTHON" -m uvicorn "${ARGS[@]}"

