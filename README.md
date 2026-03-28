# n8n Workflows Repo

This repository is the source of truth for workflows in your self-hosted n8n instance.

## 1) One-time setup

1. Copy env template:
   - `cp .env.example .env`
2. Edit `.env` and add:
   - `N8N_API_URL`
   - `N8N_API_KEY`

## 2) Build n8n-cli (one-time)

```bash
git clone https://github.com/ubie-oss/n8n-cli.git tools/n8n-cli
cd tools/n8n-cli
~/.bun/bin/bun install
make build
cd ../..
chmod +x scripts/import-all.sh scripts/apply.sh
```

## 3) Import workflows from n8n

```bash
./scripts/import-all.sh
```

## 4) Deploy workflows

Dry-run:

```bash
./scripts/apply.sh
```

Apply:

```bash
./scripts/apply.sh apply
```

## Notes

- Keep `.env` private. It must not be committed.
- Always run dry-run before apply.
