#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND="$ROOT/Frontend"
PORT="${PORT:-5173}"
API_PORT="${API_PORT:-8001}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --api-port) API_PORT="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

command -v node >/dev/null 2>&1 || { echo "Node.js 18+ is required." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required." >&2; exit 1; }

if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 2 "http://127.0.0.1:$PORT" | grep -q 'FedUPI'; then
  echo "FedUPI frontend is already running on http://127.0.0.1:$PORT"
  exit 0
fi

cd "$FRONTEND"
if [[ ! -d node_modules ]]; then
  echo "Installing frontend dependencies..."
  npm ci --no-audit --no-fund
fi

export VITE_API_TARGET="http://127.0.0.1:$API_PORT"
echo "Frontend: http://127.0.0.1:$PORT  (API: $VITE_API_TARGET)"
exec npm run dev -- --host 127.0.0.1 --port "$PORT" --strictPort
