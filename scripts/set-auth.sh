#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

DEFAULT_URL="https://n8n.saksham-experiments.com"

echo "n8n authentication setup"
echo
read -r -p "n8n URL [$DEFAULT_URL]: " INPUT_URL
N8N_URL="${INPUT_URL:-$DEFAULT_URL}"

read -r -s -p "Paste your n8n API key: " N8N_KEY
echo

if [[ -z "$N8N_KEY" ]]; then
  echo "API key cannot be empty."
  exit 1
fi

cat > "$ENV_FILE" <<EOF
N8N_API_URL=$N8N_URL
N8N_API_KEY=$N8N_KEY
EOF

echo "Saved auth settings to $ENV_FILE"
