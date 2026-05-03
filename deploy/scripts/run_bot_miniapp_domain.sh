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

wait_for_health() {
    local container_name="$1"
    local label="$2"
    local max_attempts="${3:-60}"
    local attempt=1

    echo "== Wait for ${label} =="
    while [ "${attempt}" -le "${max_attempts}" ]; do
        local status
        status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_name}" 2>/dev/null || true)"
        if [ "${status}" = "healthy" ] || [ "${status}" = "running" ]; then
            echo "${label}: ${status}"
            return 0
        fi
        printf '%s attempt %s/%s: %s\n' "${label}" "${attempt}" "${max_attempts}" "${status:-missing}"
        sleep 2
        attempt=$((attempt + 1))
    done

    echo "${label} did not become ready in time."
    docker ps -a || true
    return 1
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

echo "== Start data services first =="
docker compose -f "${COMPOSE_FILE}" up -d postgres redis
wait_for_health "onehunt_postgres" "postgres"
wait_for_health "onehunt_redis" "redis"

echo "== Build bot + Mini App images =="
docker compose -f "${COMPOSE_FILE}" build miniapp bot

echo "== Load questions into Mini App database =="
docker compose -f "${COMPOSE_FILE}" run --rm miniapp python scripts/load_questions.py

echo "== Start bot + Mini App stack =="
docker compose -f "${COMPOSE_FILE}" up -d miniapp bot
sleep 8

echo "== Apply nginx config =="
install -m 0644 "${ROOT}/deploy/nginx/huntexam.online-miniapp-only.conf" "${NGINX_CONF}"
ln -sf "${NGINX_CONF}" "/etc/nginx/sites-enabled/${DOMAIN}"
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl reload nginx

if command -v certbot >/dev/null 2>&1; then
    if getent ahostsv4 "${DOMAIN}" >/dev/null 2>&1; then
        echo "== Try SSL certificate =="
        certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --register-unsafely-without-email || true
    else
        echo "== Skip SSL for now: ${DOMAIN} does not resolve yet =="
    fi
fi

echo "== Checks =="
docker compose -f "${COMPOSE_FILE}" ps
printf 'local health: '
curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' --max-time 10 http://127.0.0.1:8080/health || true
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
