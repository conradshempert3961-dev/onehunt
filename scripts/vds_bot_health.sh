#!/usr/bin/env bash
# Restart bot if Telegram API or polling is broken.
set -Eeuo pipefail

ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
ENV_FILE="${ROOT}/.env"

if [[ "$(id -u)" -ne 0 ]]; then
  exit 0
fi

[[ -f "${ENV_FILE}" ]] || exit 0
BOT_TOKEN="$(grep '^BOT_TOKEN=' "${ENV_FILE}" | cut -d= -f2- || true)"
[[ -n "${BOT_TOKEN}" && "${BOT_TOKEN}" != "your_telegram_bot_token" ]] || exit 0

if ! curl -fsS --max-time 12 "https://api.telegram.org/bot${BOT_TOKEN}/getMe" | grep -q '"ok":true'; then
  echo "bot getMe failed — running fix_vds_telegram.sh"
  bash "${ROOT}/scripts/fix_vds_telegram.sh"
  exit 0
fi

if ! docker ps --format '{{.Names}}' | grep -q '^onehunt_bot$'; then
  echo "bot container down — starting"
  cd "${ROOT}"
  docker compose -f docker-compose.prod.yml up -d bot
fi
