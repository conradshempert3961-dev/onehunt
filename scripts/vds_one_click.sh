#!/usr/bin/env bash
# One-click VDS setup — paste in VNC/SSH console on 104.128.137.117 as root.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/conradshempert3961-dev/onehunt/cursor/fix-all-vds-2866/scripts/vds_one_click.sh | bash
set -Eeuo pipefail

IP="${ONEHUNT_IP:-104.128.137.117}"
ROOT=/opt/onehunt
BRANCH=cursor/fix-all-vds-2866

mkdir -p "${ROOT}"
if [[ ! -d "${ROOT}/.git" ]]; then
  git clone --depth 1 -b "${BRANCH}" \
    https://github.com/conradshempert3961-dev/onehunt.git "${ROOT}"
fi

cd "${ROOT}"
git fetch --depth 1 origin "${BRANCH}"
git checkout -B "${BRANCH}" "origin/${BRANCH}" 2>/dev/null || git checkout -B "${BRANCH}" FETCH_HEAD
ONEHUNT_BRANCH="${BRANCH}" bash scripts/deploy_vds_full.sh "${IP}"
