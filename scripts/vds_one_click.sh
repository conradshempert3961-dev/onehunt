#!/usr/bin/env bash
# One-click VDS setup — paste in VNC console on 104.128.137.117 as root.
# Usage:
#   DEEPSEEK_USER_TOKEN='your_token' curl -fsSL https://raw.githubusercontent.com/conradshempert3961-dev/onehunt/cursor/improve-styling-fix-errors-2866/scripts/vds_one_click.sh | bash
set -Eeuo pipefail

IP="${ONEHUNT_IP:-104.128.137.117}"
ROOT=/opt/onehunt
TOKEN="${DEEPSEEK_USER_TOKEN:-}"

mkdir -p "${ROOT}"
if [[ -n "${TOKEN}" ]]; then
  printf 'DEEPSEEK_USER_TOKEN=%s\n' "${TOKEN}" > "${ROOT}/.env.deepseek"
  chmod 600 "${ROOT}/.env.deepseek"
fi

if [[ ! -d "${ROOT}/.git" ]]; then
  git clone --depth 1 -b main https://github.com/conradshempert3961-dev/onehunt.git "${ROOT}"
fi

cd "${ROOT}"
git fetch --depth 1 origin main
git checkout main
git pull origin main
bash scripts/deploy_vds_full.sh "${IP}"
