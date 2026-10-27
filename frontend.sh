#!/usr/bin/env bash
set -euo pipefail

PORT=5173
API_PORT=8001
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --api-port) API_PORT="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/Frontend"
cd "$FRONTEND_DIR"
[[ -d node_modules ]] || npm install
export VITE_API_TARGET="http://127.0.0.1:$API_PORT"
exec npm run dev -- --port "$PORT"
