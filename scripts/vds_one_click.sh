#!/usr/bin/env bash
# One-click VDS setup — paste in VNC console on 104.128.137.117 as root.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/conradshempert3961-dev/onehunt/main/scripts/vds_one_click.sh | bash
set -Eeuo pipefail

IP="${ONEHUNT_IP:-104.128.137.117}"
ROOT=/opt/onehunt

mkdir -p "${ROOT}"

if [[ ! -d "${ROOT}/.git" ]]; then
  git clone --depth 1 -b main https://github.com/conradshempert3961-dev/onehunt.git "${ROOT}"
fi

cd "${ROOT}"
git fetch --depth 1 origin main
git checkout main
git pull origin main
bash scripts/deploy_vds_full.sh "${IP}"
