#!/usr/bin/env bash
# Permanent Cloudflare Named Tunnel (URL never changes; set CLOUDFLARE_TUNNEL_TOKEN in .env).
# Create tunnel: https://one.dash.cloudflare.com → Networks → Tunnels → Create → copy token.
set -Eeuo pipefail

ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
ENV_FILE="${ROOT}/.env"
UPSTREAM="${TUNNEL_UPSTREAM:-http://127.0.0.1:80}"
UNIT="/etc/systemd/system/onehunt-cf-tunnel.service"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-}"
if [[ -z "${TOKEN}" && -f "${ENV_FILE}" ]]; then
  TOKEN="$(grep '^CLOUDFLARE_TUNNEL_TOKEN=' "${ENV_FILE}" | cut -d= -f2- || true)"
fi
if [[ -z "${TOKEN}" ]]; then
  echo "Set CLOUDFLARE_TUNNEL_TOKEN in ${ENV_FILE}"
  echo "Dashboard: one.dash.cloudflare.com → Networks → Tunnels → Create → Install connector"
  exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -o /usr/local/bin/cloudflared
  chmod +x /usr/local/bin/cloudflared
fi

systemctl stop onehunt-https-tunnel 2>/dev/null || true
systemctl disable onehunt-https-tunnel 2>/dev/null || true

cat > "${UNIT}" <<EOF
[Unit]
Description=ONEHUNT Cloudflare Named Tunnel (permanent)
After=network-online.target nginx.service docker.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate run --token ${TOKEN}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable onehunt-cf-tunnel
systemctl restart onehunt-cf-tunnel

HOSTNAME="${ONEHUNT_TUNNEL_HOSTNAME:-}"
if [[ -z "${HOSTNAME}" && -f "${ENV_FILE}" ]]; then
  HOSTNAME="$(grep '^ONEHUNT_TUNNEL_HOSTNAME=' "${ENV_FILE}" | cut -d= -f2- || true)"
fi

if [[ -n "${HOSTNAME}" ]]; then
  echo "Permanent Mini App: https://${HOSTNAME}/app"
  echo "BotFather /setdomain → @Onehuntbot → ${HOSTNAME}"
else
  echo "Named tunnel running. Set public hostname in Cloudflare dashboard, then:"
  echo "  ONEHUNT_TUNNEL_HOSTNAME=your-subdomain.example.com bash scripts/vds_heal.sh"
fi
