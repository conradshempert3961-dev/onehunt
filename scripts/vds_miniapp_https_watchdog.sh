#!/usr/bin/env bash
# Restart HTTPS tunnel when MINIAPP_URL is dead (trycloudflare URLs expire).
set -Eeuo pipefail

ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
ENV_FILE="${ROOT}/.env"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  exit 0
fi

MINIAPP_URL="$(grep '^MINIAPP_URL=' "${ENV_FILE}" | cut -d= -f2- || true)"
if [[ -z "${MINIAPP_URL}" ]]; then
  bash "${ROOT}/scripts/vds_https_tunnel.sh"
  exit 0
fi

if curl -fsS -o /dev/null --max-time 15 "${MINIAPP_URL}"; then
  exit 0
fi

echo "MINIAPP_URL is down (${MINIAPP_URL}), restarting HTTPS tunnel..."
bash "${ROOT}/scripts/vds_https_tunnel.sh"
