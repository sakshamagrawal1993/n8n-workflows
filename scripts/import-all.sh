#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "Missing .env. Copy .env.example to .env and fill values."
  exit 1
fi

set -a
source "$ROOT_DIR/.env"
set +a

"$ROOT_DIR/tools/n8n-cli/n8n-cli" import -d "$ROOT_DIR/definitions"
echo "Import completed."
