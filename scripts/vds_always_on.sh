#!/usr/bin/env bash
# Install always-on watchdogs on VDS (run as root after deploy).
set -Eeuo pipefail

ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

HEAL_UNIT="/etc/systemd/system/onehunt-heal.service"
HEAL_TIMER="/etc/systemd/system/onehunt-heal.timer"

cat > "${HEAL_UNIT}" <<EOF
[Unit]
Description=ONEHUNT heal (bot + miniapp)
After=network-online.target docker.service

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'certbot renew --quiet 2>/dev/null || true; bash ${ROOT}/scripts/vds_miniapp_https_watchdog.sh; bash ${ROOT}/scripts/vds_bot_health.sh; bash ${ROOT}/scripts/refresh_nginx_upstream.sh'
EOF

cat > "${HEAL_TIMER}" <<EOF
[Unit]
Description=ONEHUNT heal every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable onehunt-heal.timer
systemctl start onehunt-heal.timer

# Faster HTTPS watchdog cron (backup)
cat > /etc/cron.d/onehunt-https-watchdog <<'CRON'
*/5 * * * * root /opt/onehunt/scripts/vds_miniapp_https_watchdog.sh >> /var/log/onehunt-https-watchdog.log 2>&1
CRON
chmod 644 /etc/cron.d/onehunt-https-watchdog

echo "Always-on timers enabled:"
systemctl list-timers onehunt-heal.timer --no-pager
