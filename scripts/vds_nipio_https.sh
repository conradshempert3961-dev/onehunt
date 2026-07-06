#!/usr/bin/env bash
# Permanent HTTPS via nip.io (no trycloudflare, no Cloudflare account).
# URL: https://104.128.137.117.nip.io/app — stable while VDS IP is unchanged.
set -Eeuo pipefail

IP="${1:-104.128.137.117}"
ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
DOMAIN="${ONEHUNT_NIPIO_DOMAIN:-${IP}.nip.io}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

RESOLVED="$(getent ahosts "${DOMAIN}" 2>/dev/null | awk '/STREAM/ {print $1; exit}')"
if [[ -z "${RESOLVED}" || "${RESOLVED}" != "${IP}" ]]; then
  echo "nip.io DNS check failed for ${DOMAIN} (got ${RESOLVED:-none})"
  exit 1
fi

# Stop ephemeral trycloudflare tunnel — we use real TLS on nip.io now.
systemctl stop onehunt-https-tunnel 2>/dev/null || true
systemctl disable onehunt-https-tunnel 2>/dev/null || true

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq certbot python3-certbot-nginx nginx

MINIAPP_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' onehunt_miniapp 2>/dev/null || true)"
if [[ -z "${MINIAPP_IP}" ]]; then
  echo "onehunt_miniapp container not running"
  exit 1
fi

bash "${ROOT}/scripts/refresh_nginx_upstream.sh" 2>/dev/null || true
MINIAPP_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' onehunt_miniapp)"

cat > /etc/nginx/sites-available/onehunt <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${DOMAIN} ${IP} _;

    location / {
        proxy_pass http://${MINIAPP_IP}:8080;
        proxy_http_version 1.1;
        proxy_read_timeout 300;
        proxy_connect_timeout 60;
        proxy_send_timeout 300;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf /etc/nginx/sites-available/onehunt /etc/nginx/sites-enabled/onehunt
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

EMAIL="${ONEHUNT_CERTBOT_EMAIL:-admin@onehunt.app}"
if [[ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
  certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${EMAIL}" \
    --cert-name onehunt-nipio --redirect
else
  certbot renew --nginx --quiet || certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${EMAIL}" --cert-name onehunt-nipio --redirect
fi

echo "Permanent HTTPS: https://${DOMAIN}/app"
echo "BotFather /setdomain → @Onehuntbot → ${DOMAIN}"
