#!/usr/bin/env bash
# Fix Telegram Bot API connectivity on VDS (IPv6 DNS / blocked DC / dead proxy tunnel).
set -Eeuo pipefail

ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
TELEGRAM_IPV4="${TELEGRAM_API_IPV4:-149.154.167.220}"
HOSTS_LINE="${TELEGRAM_IPV4} api.telegram.org"
HOSTS_FILE="/etc/hosts"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

echo "== Fix api.telegram.org -> ${TELEGRAM_IPV4} =="
if grep -qE '^[0-9.]+\s+api\.telegram\.org' "${HOSTS_FILE}"; then
  sed -i -E "s|^[0-9.]+\s+api\.telegram\.org.*|${HOSTS_LINE}|" "${HOSTS_FILE}"
else
  echo "${HOSTS_LINE}" >> "${HOSTS_FILE}"
fi

if [[ -f "${ROOT}/.env" ]]; then
  if grep -q '^TELEGRAM_API_BASE=' "${ROOT}/.env"; then
    sed -i 's|^TELEGRAM_API_BASE=.*|TELEGRAM_API_BASE=|' "${ROOT}/.env"
  fi
fi

echo "== Verify Telegram API =="
if ! timeout 10 curl -fsS -o /dev/null "https://api.telegram.org/"; then
  echo "WARNING: host curl still failed; docker extra_hosts should cover the bot container."
fi

if [[ -d "${ROOT}" && -f "${ROOT}/docker-compose.prod.yml" && "${TELEGRAM_SKIP_RESTART:-}" != "1" ]]; then
  cd "${ROOT}"
  docker compose -f docker-compose.prod.yml up -d --build bot
  sleep 4
  docker compose -f docker-compose.prod.yml logs --tail=12 bot
fi

echo "Done."
