#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

cd "$BACKEND_DIR"

if [ ! -f .env ]; then
  echo "Warning: backend/.env not found. Copy backend/.env.example to backend/.env and fill in values." >&2
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
RELOAD_FLAG="${RELOAD:---reload}"

exec uv run uvicorn app.main:app --host "$HOST" --port "$PORT" $RELOAD_FLAG
