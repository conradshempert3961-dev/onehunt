#!/usr/bin/env bash
# Point nginx at the current miniapp container IP (changes after docker recreate).
set -Eeuo pipefail

ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
NGINX_SITE="/etc/nginx/sites-available/onehunt"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

MINIAPP_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' onehunt_miniapp 2>/dev/null || true)"
if [[ -z "${MINIAPP_IP}" ]]; then
  echo "onehunt_miniapp container not found"
  exit 1
fi

if [[ ! -f "${NGINX_SITE}" ]]; then
  echo "nginx site ${NGINX_SITE} not found; run deploy_vds_full.sh first"
  exit 1
fi

sed -i "s|proxy_pass http://[0-9.]*:8080|proxy_pass http://${MINIAPP_IP}:8080|g" "${NGINX_SITE}"
nginx -t
systemctl reload nginx
echo "nginx -> ${MINIAPP_IP}:8080"
