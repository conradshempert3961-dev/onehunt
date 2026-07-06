#!/usr/bin/env bash
# Pick the best stable HTTPS URL for Telegram Mini App (no ephemeral trycloudflare when possible).
set -Eeuo pipefail

ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
ENV_FILE="${ROOT}/.env"
IP="${1:-104.128.137.117}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

[[ -f "${ENV_FILE}" ]] || cp "${ROOT}/.env.example" "${ENV_FILE}"

set_kv() {
  local k="$1" v="$2"
  if grep -q "^${k}=" "${ENV_FILE}"; then
    sed -i "s|^${k}=.*|${k}=${v}|" "${ENV_FILE}"
  else
    echo "${k}=${v}" >> "${ENV_FILE}"
  fi
}

miniapp_url_ok() {
  local url="$1"
  [[ -n "${url}" && "${url}" == https://* ]] || return 1
  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "${url}" 2>/dev/null || echo 000)"
  [[ "${code}" == "200" ]]
}

apply_miniapp_url() {
  local url="$1"
  local host
  host="$(echo "${url}" | sed -E 's#^https?://([^/]+)/?.*#\1#')"
  set_kv MINIAPP_URL "${url}"
  set_kv MINIAPP_BROWSER_DEMO "true"
  set_kv MINIAPP_BROWSER_DEMO_HOSTS "${IP},localhost,127.0.0.1,${host}"
  cd "${ROOT}"
  docker compose -f docker-compose.prod.yml up -d --build bot miniapp
  echo "MINIAPP_URL=${url}"
  echo "BotFather /setdomain → @Onehuntbot → ${host}"
}

# 1) Custom domain with Let's Encrypt (permanent when DNS points to this VDS).
if [[ -n "${ONEHUNT_DOMAIN:-}" ]]; then
  if bash "${ROOT}/scripts/vds_https_certbot.sh" "${ONEHUNT_DOMAIN}" "${IP}"; then
    if miniapp_url_ok "https://${ONEHUNT_DOMAIN}/app"; then
      apply_miniapp_url "https://${ONEHUNT_DOMAIN}/app"
      exit 0
    fi
  fi
fi

# 2) Cloudflare Named Tunnel (permanent hostname from your Cloudflare account).
if [[ -f "${ENV_FILE}" ]] && grep -q '^CLOUDFLARE_TUNNEL_TOKEN=.\+' "${ENV_FILE}" 2>/dev/null; then
  if bash "${ROOT}/scripts/vds_cloudflare_named_tunnel.sh"; then
    TUNNEL_HOST="$(grep '^ONEHUNT_TUNNEL_HOSTNAME=' "${ENV_FILE}" | cut -d= -f2- || true)"
    if [[ -n "${TUNNEL_HOST}" ]] && miniapp_url_ok "https://${TUNNEL_HOST}/app"; then
      apply_miniapp_url "https://${TUNNEL_HOST}/app"
      exit 0
    fi
  fi
fi

# 3) Cloudflare Worker proxy (stable workers.dev URL).
WORKER_BASE="${ONEHUNT_MINIAPP_WORKER_URL:-}"
if [[ -z "${WORKER_BASE}" && -f "${ROOT}/.miniapp_worker_url" ]]; then
  WORKER_BASE="$(tr -d '\r\n' < "${ROOT}/.miniapp_worker_url")"
fi
if [[ -n "${WORKER_BASE}" ]]; then
  WORKER_URL="${WORKER_BASE%/}/app"
  if miniapp_url_ok "${WORKER_URL}"; then
    apply_miniapp_url "${WORKER_URL}"
    exit 0
  fi
  echo "Worker URL not ready yet: ${WORKER_URL}"
fi

# 4) Permanent nip.io + Let's Encrypt (stable URL, no trycloudflare).
USE_NIPIO="${ONEHUNT_USE_NIPIO:-true}"
if [[ "${USE_NIPIO}" == "true" ]]; then
  NIPIO_DOMAIN="${ONEHUNT_NIPIO_DOMAIN:-${IP}.nip.io}"
  if bash "${ROOT}/scripts/vds_nipio_https.sh" "${IP}"; then
    if miniapp_url_ok "https://${NIPIO_DOMAIN}/app"; then
      apply_miniapp_url "https://${NIPIO_DOMAIN}/app"
      exit 0
    fi
    echo "nip.io HTTPS issued but /app not 200 yet — check nginx upstream"
  else
    echo "nip.io HTTPS setup failed, falling back..."
  fi
fi

# 5) Ephemeral trycloudflare tunnel (last resort; URL changes on restart).
echo "WARNING: using temporary trycloudflare tunnel — set ONEHUNT_USE_NIPIO=true or add CLOUDFLARE_TUNNEL_TOKEN for permanent URL"
bash "${ROOT}/scripts/vds_https_tunnel.sh" "${IP}"
