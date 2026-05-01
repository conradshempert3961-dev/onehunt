#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="${1:-huntexam.online}"
ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
COMPOSE_FILE="${ROOT}/docker-compose.prod.yml"
NGINX_CONF="/etc/nginx/sites-available/${DOMAIN}"

set_env() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" .env; then
        sed -i "s#^${key}=.*#${key}=${value}#" .env
    else
        printf '%s=%s\n' "${key}" "${value}" >> .env
    fi
}

echo "== ONEHUNT standalone site deploy =="
echo "Domain: ${DOMAIN}"
echo "Root: ${ROOT}"

cd "${ROOT}"

if [ ! -f .env ]; then
    cp .env.example .env
fi

git pull --ff-only

set_env "MINIAPP_URL" "https://${DOMAIN}/"
set_env "MINIAPP_BROWSER_DEMO" "false"
set_env "USE_REDIS_FSM" "false"
set_env "FREE_MODE" "false"

echo "== Stop deprecated services =="
docker compose -f "${COMPOSE_FILE}" stop bot site || true
docker compose -f "${COMPOSE_FILE}" rm -f bot site || true

echo "== Start standalone stack =="
docker compose -f "${COMPOSE_FILE}" up -d --build postgres redis miniapp

echo "== Load questions =="
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
printf 'standalone site: '
curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' --max-time 10 http://127.0.0.1:8080/ || true
printf 'domain https: '
curl -k -sS -o /dev/null -w '%{http_code} %{content_type}\n' --max-time 15 "https://${DOMAIN}/" || true
df -h /

echo "== Done =="
