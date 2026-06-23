#!/usr/bin/env bash
# Deploy ONEHUNT to VDS from this machine (Cloud Agent / CI).
# Requires: sshpass, ONEHUNT_VDS_PASSWORD in env or .env.vds
set -Eeuo pipefail

HOST="${ONEHUNT_VDS_HOST:-104.128.137.117}"
USER="${ONEHUNT_VDS_USER:-root}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CREDS="${ROOT}/.env.vds"

if [[ -f "${CREDS}" ]]; then
  # shellcheck disable=SC1090
  source "${CREDS}"
fi

PASS="${ONEHUNT_VDS_PASSWORD:-}"
BOT_TOKEN_DEPLOY="${ONEHUNT_BOT_TOKEN:-${BOT_TOKEN:-}}"
if [[ -z "${PASS}" ]]; then
  echo "Set ONEHUNT_VDS_PASSWORD or create ${CREDS}:"
  echo "  ONEHUNT_VDS_PASSWORD=your_root_password"
  exit 1
fi

if ! command -v sshpass >/dev/null 2>&1; then
  echo "Install sshpass"
  exit 1
fi

SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=20)

echo "== Run full deploy on VDS =="
sshpass -p "${PASS}" ssh "${SSH_OPTS[@]}" "${USER}@${HOST}" bash -s <<REMOTE
set -Eeuo pipefail
ROOT=/opt/onehunt
mkdir -p "\$ROOT"
if [[ ! -d "\$ROOT/.git" ]]; then
  git clone --depth 1 -b main https://github.com/conradshempert3961-dev/onehunt.git "\$ROOT"
fi
cd "\$ROOT"
git fetch --depth 1 origin main
git reset --hard origin/main
if [[ -n "${BOT_TOKEN_DEPLOY}" ]]; then
  if grep -q '^BOT_TOKEN=' .env 2>/dev/null; then
    sed -i "s|^BOT_TOKEN=.*|BOT_TOKEN=${BOT_TOKEN_DEPLOY}|" .env
  else
    echo "BOT_TOKEN=${BOT_TOKEN_DEPLOY}" >> .env
  fi
fi
bash scripts/deploy_vds_full.sh 104.128.137.117
REMOTE

echo "Done: http://${HOST}/app"
