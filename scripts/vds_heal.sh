#!/usr/bin/env bash
# One-shot repair: Telegram bot + Mini App HTTPS + nginx on VDS.
# Run on server as root: bash /opt/onehunt/scripts/vds_heal.sh
set -Eeuo pipefail

IP="${1:-104.128.137.117}"
ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
BRANCH="${ONEHUNT_BRANCH:-cursor/fix-all-vds-2866}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

if [[ -d "${ROOT}/.git" ]]; then
  cd "${ROOT}"
  git fetch origin "${BRANCH}" 2>/dev/null || true
  git checkout -B "${BRANCH}" "origin/${BRANCH}" 2>/dev/null || git checkout -B "${BRANCH}" FETCH_HEAD 2>/dev/null || true
fi

echo "== 1/4 Telegram API =="
bash "${ROOT}/scripts/fix_vds_telegram.sh"

echo "== 2/4 nginx upstream =="
bash "${ROOT}/scripts/refresh_nginx_upstream.sh"

echo "== 3/4 HTTPS Mini App tunnel =="
bash "${ROOT}/scripts/vds_https_tunnel.sh" "${IP}"

echo "== 4/4 Status =="
grep -E '^(MINIAPP_URL|TELEGRAM_API_BASE)=' "${ROOT}/.env" || true
docker compose -f "${ROOT}/docker-compose.prod.yml" ps
docker compose -f "${ROOT}/docker-compose.prod.yml" logs --tail=5 bot
URL="$(grep '^MINIAPP_URL=' "${ROOT}/.env" | cut -d= -f2-)"
if [[ -n "${URL}" ]]; then
  curl -fsS -o /dev/null --max-time 20 "${URL}" && echo "Mini App OK: ${URL}" || echo "Mini App check failed: ${URL}"
fi
echo "Done. Test @Onehuntbot /start"
