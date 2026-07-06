#!/usr/bin/env bash
set -Eeuo pipefail
AGENT_KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPqiJsBjAsv4KymedFcUR891X1lgC90DW8yMtjcHJ/p0 cursor-agent'
mkdir -p /root/.ssh && chmod 700 /root/.ssh
grep -qF "${AGENT_KEY}" /root/.ssh/authorized_keys 2>/dev/null || echo "${AGENT_KEY}" >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
curl -fsSL https://raw.githubusercontent.com/conradshempert3961-dev/onehunt/cursor/fix-all-vds-2866/scripts/vds_heal.sh | bash
