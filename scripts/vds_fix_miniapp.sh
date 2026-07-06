#!/usr/bin/env bash
# Quick fix: Mini App HTTPS + nginx + bot restart on VDS.
# Run on server as root:
#   bash /opt/onehunt/scripts/vds_fix_miniapp.sh
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

echo "== nginx upstream =="
bash "${ROOT}/scripts/refresh_nginx_upstream.sh"

echo "== HTTPS tunnel + MINIAPP_URL =="
bash "${ROOT}/scripts/vds_https_tunnel.sh" "${IP}"

URL="$(grep '^MINIAPP_URL=' "${ROOT}/.env" | cut -d= -f2-)"
HOST="$(echo "${URL}" | sed -E 's#^https?://([^/]+)/?.*#\1#')"

echo ""
echo "============================================"
echo "Mini App URL: ${URL}"
echo ""
echo "ВАЖНО — в @BotFather выполни:"
echo "  /setdomain"
echo "  выбери @Onehuntbot"
echo "  введи домен БЕЗ https://:"
echo "  ${HOST}"
echo ""
echo "Потом в боте: /start → «Открыть ONEHUNT»"
echo "============================================"
