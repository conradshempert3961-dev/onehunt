#!/usr/bin/env bash
# Deploy Cloudflare Worker proxy for Groq (bypasses datacenter IP blocks on VDS).
# Requires: npm/npx, CLOUDFLARE_API_TOKEN with Workers edit permission.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/workers/groq-proxy"

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  echo "Set CLOUDFLARE_API_TOKEN (https://dash.cloudflare.com/profile/api-tokens)"
  exit 1
fi

if [[ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  echo "Set CLOUDFLARE_ACCOUNT_ID (Cloudflare dashboard → Workers)"
  exit 1
fi

npx --yes wrangler@3 deploy

echo ""
echo "Worker deployed. On VDS set in /opt/onehunt/.env:"
echo "  OPENAI_API_BASE=https://onehunt-groq-proxy.<your-subdomain>.workers.dev/openai/v1"
echo "  OPENAI_API_KEY=gsk_..."
echo "  OPENAI_MODEL=groq/compound-mini"
echo ""
echo "Then: cd /opt/onehunt && docker compose -f docker-compose.prod.yml up -d --build miniapp"
