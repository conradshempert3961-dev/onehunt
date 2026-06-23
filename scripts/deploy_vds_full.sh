#!/usr/bin/env bash
# Full ONEHUNT deploy on VDS: app + nginx.
# Run on server as root: bash scripts/deploy_vds_full.sh
set -Eeuo pipefail

IP="${1:-104.128.137.117}"
ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
BRANCH="${ONEHUNT_BRANCH:-main}"
REPO="${ONEHUNT_REPO:-https://github.com/conradshempert3961-dev/onehunt.git}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-v2 nginx git curl python3
systemctl enable --now docker nginx

if [[ ! -d "${ROOT}/.git" ]]; then
  git clone --depth 1 -b "${BRANCH}" "${REPO}" "${ROOT}"
fi

cd "${ROOT}"
git fetch --depth 1 origin "${BRANCH}" || true
git checkout "${BRANCH}" 2>/dev/null || git checkout -b "${BRANCH}" "origin/${BRANCH}" 2>/dev/null || true
git pull origin "${BRANCH}" || true

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

echo "== Start stack =="
docker rm -f onehunt_deepseek 2>/dev/null || true
docker compose -f docker-compose.prod.yml up -d --build postgres redis
sleep 5
docker compose -f docker-compose.prod.yml up -d --build miniapp huntdriver
docker compose -f docker-compose.prod.yml run --rm miniapp python scripts/load_questions.py 2>/dev/null || true

BOT_TOKEN_VALUE="$(grep '^BOT_TOKEN=' .env | cut -d= -f2- || true)"
if [[ -n "${BOT_TOKEN_VALUE}" && "${BOT_TOKEN_VALUE}" != "your_telegram_bot_token" ]]; then
  echo "== Start Telegram bot =="
  docker compose -f docker-compose.prod.yml up -d --build bot
else
  echo "== Skip bot: set real BOT_TOKEN from @BotFather in ${ROOT}/.env =="
fi

if ! grep -q '^OPENAI_API_KEY=.\+' .env 2>/dev/null; then
  set_kv OPENAI_API_KEY ""
fi

MINIAPP_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' onehunt_miniapp 2>/dev/null || true)"
if [[ -z "${MINIAPP_IP}" ]]; then
  echo "miniapp container not found"
  docker compose -f docker-compose.prod.yml ps
  exit 1
fi

# Refresh nginx upstream after container recreate (IP may change)
if [[ -f /etc/nginx/sites-available/onehunt ]]; then
  sed -i "s|proxy_pass http://[0-9.]*:8080|proxy_pass http://${MINIAPP_IP}:8080|" /etc/nginx/sites-available/onehunt
fi

cat > /etc/nginx/sites-available/onehunt <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location /assets/ {
        proxy_pass http://${MINIAPP_IP}:8080/assets/;
        proxy_http_version 1.1;
        add_header Cache-Control "no-store, no-cache, must-revalidate";
    }

    location /huntdriver/ {
        proxy_pass http://${MINIAPP_IP}:8080/huntdriver/;
        proxy_http_version 1.1;
        proxy_read_timeout 300;
        proxy_connect_timeout 60;
        proxy_send_timeout 300;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

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

echo ""
echo "OK: http://${IP}/"
echo "App: http://${IP}/app"
echo "HuntDriver: http://${IP}/huntdriver/"
docker compose -f docker-compose.prod.yml ps
