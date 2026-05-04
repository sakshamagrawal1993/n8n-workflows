#!/usr/bin/env bash
# Merge pinData from a local workflow JSON onto the remote workflow via PUT.
# n8n-cli `apply` intentionally omits pinData (public API); use this after apply when you need pinned samples on the server.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "Missing $ROOT_DIR/.env"
  exit 1
fi
set -a
source "$ROOT_DIR/.env"
set +a

DEF="${1:?usage: $0 <definitions/...json> <workflowId>}"
WF_ID="${2:?usage: $0 <definitions/...json> <workflowId>}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required"
  exit 1
fi

API="${N8N_API_URL%/}"
PIN="$(jq -c '.pinData // {}' "$DEF")"
if [[ "$PIN" == "{}" ]]; then
  echo "No pinData in $DEF"
  exit 1
fi

TMP="$(mktemp)"
curl -sS "$API/api/v1/workflows/$WF_ID" -H "X-N8N-API-KEY: $N8N_API_KEY" -o "$TMP"

jq --argjson pin "$PIN" '
  {
    name: .name,
    nodes: .nodes,
    connections: .connections,
    settings: { executionOrder: (.settings.executionOrder // "v1") },
    staticData: .staticData,
    pinData: $pin
  }
' "$TMP" >"${TMP}.put"

HTTP=$(curl -sS -o "${TMP}.resp" -w "%{http_code}" -X PUT "$API/api/v1/workflows/$WF_ID" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @"${TMP}.put")

rm -f "$TMP" "${TMP}.put"

if [[ "$HTTP" == "200" ]]; then
  echo "push-pindata: OK workflow $WF_ID (HTTP $HTTP)"
  rm -f "${TMP}.resp"
  exit 0
fi

echo "push-pindata: failed HTTP $HTTP"
cat "${TMP}.resp"
rm -f "${TMP}.resp"
exit 1
