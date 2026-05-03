#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="${1:-huntexam.online}"
ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
COMPOSE_FILE="${ROOT}/docker-compose.prod.yml"
NGINX_CONF="/etc/nginx/sites-available/${DOMAIN}"
TRACKED_ENV_TEMPLATE="${ROOT}/deploy/env/${DOMAIN}.env.example"

set_env() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" .env; then
        sed -i "s#^${key}=.*#${key}=${value}#" .env
    else
        printf '%s=%s\n' "${key}" "${value}" >> .env
    fi
}

echo "== ONEHUNT bot + Mini App domain deploy =="
echo "Domain: ${DOMAIN}"
echo "Root: ${ROOT}"

cd "${ROOT}"

if [ ! -f .env ]; then
    if [ -f "${TRACKED_ENV_TEMPLATE}" ]; then
        cp "${TRACKED_ENV_TEMPLATE}" .env
    else
        cp .env.example .env
    fi
fi

git pull --ff-only

set_env "MINIAPP_URL" "https://${DOMAIN}/app"
set_env "MINIAPP_BROWSER_DEMO" "true"
set_env "MINIAPP_BROWSER_DEMO_HOSTS" "${DOMAIN},www.${DOMAIN},localhost,127.0.0.1"
set_env "USE_REDIS_FSM" "false"
set_env "FREE_MODE" "false"

BOT_TOKEN_VALUE="$(grep '^BOT_TOKEN=' .env | cut -d= -f2- || true)"
if [ -z "${BOT_TOKEN_VALUE}" ] || [ "${BOT_TOKEN_VALUE}" = "your_telegram_bot_token" ]; then
    echo "BOT_TOKEN is empty or still set to the example placeholder in ${ROOT}/.env"
    echo "Set the real bot token and rerun this script."
    exit 1
fi

for required_key in CRYPTO_PAY_API_TOKEN YOOMONEY_WALLET YOOMONEY_ACCESS_TOKEN YOOMONEY_NOTIFICATION_SECRET; do
    required_value="$(grep "^${required_key}=" .env | cut -d= -f2- || true)"
    if [ -z "${required_value}" ]; then
        echo "${required_key} is empty in ${ROOT}/.env"
        echo "Fill the real value and rerun this script."
        exit 1
    fi
done

echo "== Stop services that are not needed on this VDS =="
docker compose -f "${COMPOSE_FILE}" stop site || true
docker compose -f "${COMPOSE_FILE}" rm -f site || true

echo "== Clean safe Docker cache =="
docker system prune -f || true
docker builder prune -f || true

echo "== Start bot + Mini App stack =="
docker compose -f "${COMPOSE_FILE}" up -d --build postgres redis miniapp bot

echo "== Load questions into Mini App database =="
docker compose -f "${COMPOSE_FILE}" run --rm miniapp python scripts/load_questions.py

echo "== Apply nginx config =="
install -m 0644 "${ROOT}/deploy/nginx/huntexam.online-miniapp-only.conf" "${NGINX_CONF}"
ln -sf "${NGINX_CONF}" "/etc/nginx/sites-enabled/${DOMAIN}"
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl reload nginx

if command -v certbot >/dev/null 2>&1; then
    echo "== Try SSL certificate =="
    certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --register-unsafely-without-email || true
fi

echo "== Checks =="
docker compose -f "${COMPOSE_FILE}" ps
printf 'local miniapp: '
curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' --max-time 10 http://127.0.0.1:8080/
printf 'nginx host: '
curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' --max-time 10 -H "Host: ${DOMAIN}" http://127.0.0.1/
printf 'domain http: '
curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' --max-time 15 "http://${DOMAIN}/" || true
printf 'domain https: '
curl -k -sS -o /dev/null -w '%{http_code} %{content_type}\n' --max-time 15 "https://${DOMAIN}/" || true
printf 'domain app https: '
curl -k -sS -o /dev/null -w '%{http_code} %{content_type}\n' --max-time 15 "https://${DOMAIN}/app" || true
printf 'bot logs: \n'
docker compose -f "${COMPOSE_FILE}" logs --tail=30 bot || true
df -h /

echo "== Done =="
