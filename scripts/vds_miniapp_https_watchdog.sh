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

# Stable URLs — never switch back to trycloudflare.
if [[ "${MINIAPP_URL}" == *".workers.dev"* || "${MINIAPP_URL}" == *".nip.io"* || "${MINIAPP_URL}" == *".sslip.io"* ]]; then
  if curl -fsS -o /dev/null --max-time 15 "${MINIAPP_URL}"; then
    exit 0
  fi
  echo "Stable MINIAPP_URL down: ${MINIAPP_URL} — running heal"
  bash "${ROOT}/scripts/vds_stable_miniapp_url.sh" 2>/dev/null || bash "${ROOT}/scripts/refresh_nginx_upstream.sh"
  exit 0
fi

# Permanent custom domain (not trycloudflare).
if [[ "${MINIAPP_URL}" == https://* && "${MINIAPP_URL}" != *"trycloudflare.com"* ]]; then
  if curl -fsS -o /dev/null --max-time 15 "${MINIAPP_URL}"; then
    exit 0
  fi
  echo "HTTPS MINIAPP_URL down: ${MINIAPP_URL} — running stable URL setup"
  bash "${ROOT}/scripts/vds_stable_miniapp_url.sh" 2>/dev/null || true
  exit 0
fi

echo "MINIAPP_URL is down (${MINIAPP_URL}), restarting HTTPS tunnel..."
bash "${ROOT}/scripts/vds_https_tunnel.sh"
