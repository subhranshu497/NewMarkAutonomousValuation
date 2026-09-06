#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

cd "$FRONTEND_DIR"

if [ ! -d node_modules ]; then
  echo "node_modules not found, running npm install..." >&2
  npm install
fi

exec npm run dev
