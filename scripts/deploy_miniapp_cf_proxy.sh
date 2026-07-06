#!/usr/bin/env bash
# Deploy stable HTTPS Mini App proxy (Cloudflare Worker → VDS IP).
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/workers/miniapp-proxy"

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  echo "Set CLOUDFLARE_API_TOKEN (Workers Edit permission)"
  exit 1
fi

if [[ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  echo "Set CLOUDFLARE_ACCOUNT_ID"
  exit 1
fi

npx --yes wrangler@3 deploy 2>&1 | tee /tmp/onehunt-miniapp-worker-deploy.log

WORKER_URL="$(grep -oE 'https://[a-zA-Z0-9._-]+\.workers\.dev' /tmp/onehunt-miniapp-worker-deploy.log | tail -1 || true)"
if [[ -z "${WORKER_URL}" ]]; then
  WORKER_URL="https://onehunt-miniapp-proxy.${CLOUDFLARE_ACCOUNT_ID}.workers.dev"
fi

echo ""
echo "Stable Mini App URL (set on VDS):"
echo "  echo '${WORKER_URL}' > /opt/onehunt/.miniapp_worker_url"
echo "  ONEHUNT_MINIAPP_WORKER_URL='${WORKER_URL}' bash /opt/onehunt/scripts/vds_heal.sh"
echo ""
echo "BotFather once: /setdomain → @Onehuntbot → ${WORKER_URL#https://}"
