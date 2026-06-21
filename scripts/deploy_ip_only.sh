#!/usr/bin/env bash
# Deploy ONEHUNT on VDS by IP only (no domain / no HTTPS)
set -Eeuo pipefail

IP="${1:?Usage: $0 <server-ip>}"
ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
BRANCH="${ONEHUNT_BRANCH:-cursor/improve-styling-fix-errors-2866}"
REPO="${ONEHUNT_REPO:-https://github.com/conradshempert3961-dev/onehunt.git}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-v2 nginx git curl

systemctl enable --now docker nginx

if [[ ! -d "${ROOT}/.git" ]]; then
  git clone --depth 1 -b "${BRANCH}" "${REPO}" "${ROOT}"
fi
cd "${ROOT}"

if [[ ! -f .env ]]; then cp .env.example .env; fi

set_kv() {
  local k="$1" v="$2"
  if grep -q "^${k}=" .env; then sed -i "s|^${k}=.*|${k}=${v}|" .env; else echo "${k}=${v}" >> .env; fi
}

set_kv MINIAPP_URL "http://${IP}/app"
set_kv MINIAPP_BROWSER_DEMO "false"
set_kv FREE_MODE "true"
set_kv USE_REDIS_FSM "false"
set_kv ADMIN_IDS "6467055041"
set_kv MINIAPP_DEV_USER_ID "6467055041"
set_kv MINIAPP_HOST "0.0.0.0"

docker compose -f docker-compose.prod.yml up -d --build postgres redis miniapp
docker compose -f docker-compose.prod.yml run --rm miniapp python scripts/load_questions.py

MINIAPP_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' onehunt_miniapp)"

cat > /etc/nginx/sites-available/onehunt <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

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

echo "OK: http://${IP}/"
echo "App: http://${IP}/app"
