#!/usr/bin/env bash
# Delete duplicate "TradingAgents - *" workflows on n8n, keeping the canonical
# IDs referenced by TradingAgents_Supervisor.json (and Recon webhook).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "Missing .env. Copy .env.example to .env and fill values."
  exit 1
fi

set -a
source "$ROOT_DIR/.env"
set +a

CLI="$ROOT_DIR/tools/n8n-cli/n8n-cli"

echo "Listing TradingAgents workflows from n8n…"
TMP_IDS="$(mktemp)"
trap 'rm -f "$TMP_IDS"' EXIT

"$CLI" -o json workflow list | node -e "
const fs = require('fs');
const raw = fs.readFileSync(0, 'utf8');
const keep = new Set([
  'UDRkHgYzqs3GBaat','YeGEiKF7ZndLF8YN','TIJbwjW9wXs7Nz0f','qXgHkMpiqmOJqDqv','bREGC66gC2ppRSio',
  'AUTiS5Q4Eh5r2KXQ','IgQ0ooBfvg4oPsST','DXp8YLaipORggHwr','53Li8sbHz5IsPyNr','sqhpR7pc8WqFXOUY',
]);
const arr = JSON.parse(raw);
const del = arr.filter((w) => /TradingAgents/i.test(w.name || '') && !keep.has(w.id)).map((w) => w.id);
process.stdout.write(del.join('\n'));
" > "$TMP_IDS"

if [[ ! -s "$TMP_IDS" ]]; then
  echo "No duplicate TradingAgents workflows to delete."
  exit 0
fi

N=$(grep -c . "$TMP_IDS" || true)
echo "Deleting ${N} duplicate workflow(s)…"
xargs -n 20 "$CLI" workflow delete --force < "$TMP_IDS"
echo "Done. Re-sync: ./scripts/apply.sh apply-force"
