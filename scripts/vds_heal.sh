#!/usr/bin/env bash
# One-shot repair: bot + Mini App + nginx on VDS.
# VNC/SSH as root:
#   curl -fsSL https://raw.githubusercontent.com/conradshempert3961-dev/onehunt/cursor/fix-all-vds-2866/scripts/vds_heal.sh | bash
set -Eeuo pipefail

IP="${1:-104.128.137.117}"
ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
BRANCH="${ONEHUNT_BRANCH:-cursor/fix-all-vds-2866}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

mkdir -p "${ROOT}"
if [[ ! -d "${ROOT}/.git" ]]; then
  git clone --depth 1 -b "${BRANCH}" https://github.com/conradshempert3961-dev/onehunt.git "${ROOT}"
fi

cd "${ROOT}"
git fetch origin "${BRANCH}" 2>/dev/null || true
git checkout -B "${BRANCH}" "origin/${BRANCH}" 2>/dev/null || git checkout -B "${BRANCH}" FETCH_HEAD 2>/dev/null || true

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "WARNING: создан .env — добавьте BOT_TOKEN из @BotFather в ${ROOT}/.env"
fi

BOT_TOKEN="$(grep '^BOT_TOKEN=' .env | cut -d= -f2- || true)"
if [[ -z "${BOT_TOKEN}" || "${BOT_TOKEN}" == "your_telegram_bot_token" ]]; then
  echo "ERROR: BOT_TOKEN не задан в ${ROOT}/.env"
  echo "Откройте @BotFather → /mybots → @Onehuntbot → API Token"
  echo "На сервере: nano ${ROOT}/.env  →  BOT_TOKEN=..."
  exit 1
fi

echo "== 1/5 Docker stack =="
docker compose -f docker-compose.prod.yml up -d --build postgres redis
sleep 4
docker compose -f docker-compose.prod.yml up -d --build miniapp
docker compose -f docker-compose.prod.yml run --rm miniapp python scripts/load_questions.py 2>/dev/null || true

echo "== 2/5 Telegram API (bot polling) =="
TELEGRAM_SKIP_RESTART=1 bash scripts/fix_vds_telegram.sh

echo "== 3/5 nginx =="
MINIAPP_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' onehunt_miniapp 2>/dev/null || true)"
if [[ -z "${MINIAPP_IP}" ]]; then
  echo "ERROR: onehunt_miniapp not running"
  exit 1
fi
if [[ ! -f /etc/nginx/sites-available/onehunt ]]; then
  cat > /etc/nginx/sites-available/onehunt <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    location / {
        proxy_pass http://${MINIAPP_IP}:8080;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
  ln -sf /etc/nginx/sites-available/onehunt /etc/nginx/sites-enabled/onehunt
  rm -f /etc/nginx/sites-enabled/default
fi
bash scripts/refresh_nginx_upstream.sh

echo "== 4/5 HTTPS Mini App =="
bash scripts/vds_stable_miniapp_url.sh "${IP}"

echo "== 5/5 Bot restart + always-on =="
docker compose -f docker-compose.prod.yml up -d --build bot
bash "${ROOT}/scripts/vds_always_on.sh"
sleep 5

echo ""
echo "========== STATUS =========="
grep -E '^(MINIAPP_URL|TELEGRAM_API_BASE|BOT_TOKEN)=' .env | sed 's/BOT_TOKEN=.*/BOT_TOKEN=***/'
docker compose -f docker-compose.prod.yml ps

echo ""
echo "== Telegram getMe =="
if curl -fsS "https://api.telegram.org/bot${BOT_TOKEN}/getMe" | grep -q '"ok":true'; then
  echo "OK: бот доступен через Telegram API"
else
  echo "FAIL: getMe не прошёл — проверьте BOT_TOKEN и /etc/hosts"
fi

URL="$(grep '^MINIAPP_URL=' .env | cut -d= -f2-)"
if [[ -n "${URL}" ]]; then
  CODE="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "${URL}" 2>/dev/null || echo 000)"
  echo "Mini App ${URL} -> HTTP ${CODE}"
  HOST="$(echo "${URL}" | sed -E 's#^https?://([^/]+)/?.*#\1#')"
  echo ""
  echo "В @BotFather:"
  echo "  /setdomain"
  echo "  @Onehuntbot"
  echo "  ${HOST}"
fi

echo ""
docker compose -f docker-compose.prod.yml logs --tail=8 bot
echo ""
echo "Готово. Проверьте @Onehuntbot → /start"
