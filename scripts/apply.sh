#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-dry-run}"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "Missing .env. Copy .env.example to .env and fill values."
  exit 1
fi

set -a
source "$ROOT_DIR/.env"
set +a

if [[ "$MODE" == "apply" ]]; then
  "$ROOT_DIR/tools/n8n-cli/n8n-cli" apply -d "$ROOT_DIR/definitions"
  echo "Apply completed."
else
  "$ROOT_DIR/tools/n8n-cli/n8n-cli" apply --dry-run -d "$ROOT_DIR/definitions"
  echo "Dry-run completed."
fi
