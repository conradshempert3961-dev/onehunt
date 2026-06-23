#!/usr/bin/env bash
# Quick HTTPS tunnel for ONEHUNT on VDS without a domain (Cloudflare TryCloudflare).
set -Eeuo pipefail

IP="${1:-104.128.137.117}"
ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
UPSTREAM="${TUNNEL_UPSTREAM:-http://127.0.0.1:80}"
LOG="/var/log/onehunt-https-tunnel.log"
UNIT="/etc/systemd/system/onehunt-https-tunnel.service"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    -o /usr/local/bin/cloudflared
  chmod +x /usr/local/bin/cloudflared
fi

cat > "${UNIT}" <<EOF
[Unit]
Description=ONEHUNT HTTPS tunnel (no domain)
After=network-online.target nginx.service docker.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate --protocol http2 --url ${UPSTREAM}
Restart=always
RestartSec=5
StandardOutput=append:${LOG}
StandardError=append:${LOG}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable onehunt-https-tunnel
systemctl restart onehunt-https-tunnel

echo "Waiting for tunnel URL in ${LOG}..."
PUBLIC_URL=""
for _ in $(seq 1 30); do
  PUBLIC_URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "${LOG}" | tail -1 || true)"
  if [[ -n "${PUBLIC_URL}" ]]; then
    break
  fi
  sleep 2
done

if [[ -z "${PUBLIC_URL}" ]]; then
  echo "Tunnel URL not found yet. Check: journalctl -u onehunt-https-tunnel -f"
  exit 1
fi

set_kv() {
  local k="$1" v="$2"
  if grep -q "^${k}=" "${ROOT}/.env"; then
    sed -i "s|^${k}=.*|${k}=${v}|" "${ROOT}/.env"
  else
    echo "${k}=${v}" >> "${ROOT}/.env"
  fi
}

set_kv MINIAPP_URL "${PUBLIC_URL}/app"

cd "${ROOT}"
docker compose -f docker-compose.prod.yml up -d --build bot miniapp

echo ""
echo "HTTPS (no domain): ${PUBLIC_URL}"
echo "Mini App: ${PUBLIC_URL}/app"
echo "Web + registration: ${PUBLIC_URL}/"
echo "IP fallback: http://${IP}/"
