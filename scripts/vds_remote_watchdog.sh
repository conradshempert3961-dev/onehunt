#!/usr/bin/env bash
# Always fetch latest heal logic from GitHub (no stale scripts on disk).
set -Eeuo pipefail

BRANCH="${ONEHUNT_BRANCH:-cursor/fix-all-vds-2866}"
BASE="https://raw.githubusercontent.com/conradshempert3961-dev/onehunt/${BRANCH}/scripts"

export ONEHUNT_ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
export ONEHUNT_USE_NIPIO="${ONEHUNT_USE_NIPIO:-true}"

if [[ "$(id -u)" -ne 0 ]]; then
  exit 0
fi

mkdir -p "${ONEHUNT_ROOT}/scripts"
curl -fsSL "${BASE}/vds_miniapp_https_watchdog.sh" -o "${ONEHUNT_ROOT}/scripts/vds_miniapp_https_watchdog.sh"
curl -fsSL "${BASE}/vds_bot_health.sh" -o "${ONEHUNT_ROOT}/scripts/vds_bot_health.sh"
curl -fsSL "${BASE}/refresh_nginx_upstream.sh" -o "${ONEHUNT_ROOT}/scripts/refresh_nginx_upstream.sh"
chmod +x "${ONEHUNT_ROOT}/scripts/"*.sh 2>/dev/null || true

bash "${ONEHUNT_ROOT}/scripts/vds_miniapp_https_watchdog.sh"
bash "${ONEHUNT_ROOT}/scripts/vds_bot_health.sh"
bash "${ONEHUNT_ROOT}/scripts/refresh_nginx_upstream.sh"
