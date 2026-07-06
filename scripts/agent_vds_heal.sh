#!/usr/bin/env bash
# Deploy/heal VDS from Cloud Agent (uses VDS_PASS from environment).
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${ONEHUNT_VDS_HOST:-104.128.137.117}"
USER="${ONEHUNT_VDS_USER:-root}"
PASS="${ONEHUNT_VDS_PASSWORD:-${VDS_PASS:-}}"

if [[ -z "${PASS}" ]]; then
  echo "Set VDS_PASS or ONEHUNT_VDS_PASSWORD"
  exit 1
fi

SSHPASS_BIN="${SSHPASS_BIN:-/tmp/sshpass-1.09/sshpass}"
if [[ ! -x "${SSHPASS_BIN}" ]]; then
  echo "sshpass not found at ${SSHPASS_BIN}"
  exit 1
fi

printf '%s' "${PASS}" > /tmp/onehunt_vds_pw.txt
chmod 600 /tmp/onehunt_vds_pw.txt

"${SSHPASS_BIN}" -f /tmp/onehunt_vds_pw.txt ssh \
  -o StrictHostKeyChecking=no \
  -o PreferredAuthentications=password \
  -o PubkeyAuthentication=no \
  -o ConnectTimeout=30 \
  "${USER}@${HOST}" bash -s <<'REMOTE'
set -Eeuo pipefail
export ONEHUNT_USE_NIPIO=true
curl -fsSL https://raw.githubusercontent.com/conradshempert3961-dev/onehunt/cursor/fix-all-vds-2866/scripts/vds_heal.sh | bash
REMOTE

echo "Done."
