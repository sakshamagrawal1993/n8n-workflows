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

FORCE=()
if [[ "$MODE" == "apply-force" ]]; then
  MODE="apply"
  FORCE=(--force)
fi

if [[ "$MODE" == "apply" ]]; then
  if ((${#FORCE[@]} > 0)); then
    "$ROOT_DIR/tools/n8n-cli/n8n-cli" apply "${FORCE[@]}" -d "$ROOT_DIR/definitions"
  else
    "$ROOT_DIR/tools/n8n-cli/n8n-cli" apply -d "$ROOT_DIR/definitions"
  fi
  echo "Apply completed."
else
  "$ROOT_DIR/tools/n8n-cli/n8n-cli" apply --dry-run -d "$ROOT_DIR/definitions"
  echo "Dry-run completed."
fi
