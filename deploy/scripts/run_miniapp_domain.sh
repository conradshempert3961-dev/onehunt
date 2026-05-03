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

git_pull_or_warn() {
    if [ "${ONEHUNT_SKIP_GIT_PULL:-}" = "1" ]; then
        echo "== Skip git pull: ONEHUNT_SKIP_GIT_PULL=1 =="
        return 0
    fi

    if git pull --ff-only; then
        return 0
    fi

    echo "== Warning: git pull failed, continue with current checkout =="
    return 0
}

resolve_container_ip() {
    local container_name="$1"
    local ip
    ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "${container_name}" 2>/dev/null || true)"
    if [ -z "${ip}" ]; then
        echo "Could not resolve IP for ${container_name}"
        docker ps -a || true
        return 1
    fi
    printf '%s\n' "${ip}"
}

write_miniapp_nginx_conf() {
    local domain="$1"
    local upstream_ip="$2"

    cat > "${NGINX_CONF}" <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${domain} www.${domain} _;

    location / {
        proxy_pass http://${upstream_ip}:8080;
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
}

echo "== ONEHUNT Mini App domain deploy =="
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

git_pull_or_warn

set_env "MINIAPP_URL" "https://${DOMAIN}/app"
set_env "MINIAPP_BROWSER_DEMO" "true"
set_env "MINIAPP_BROWSER_DEMO_HOSTS" "${DOMAIN},www.${DOMAIN},localhost,127.0.0.1"
set_env "USE_REDIS_FSM" "false"
set_env "FREE_MODE" "false"

echo "== Stop services that are not needed on this VDS =="
docker compose -f "${COMPOSE_FILE}" stop bot site || true
docker compose -f "${COMPOSE_FILE}" rm -f bot site || true

echo "== Clean safe Docker cache =="
docker system prune -f || true
docker builder prune -f || true

echo "== Start data services first =="
docker compose -f "${COMPOSE_FILE}" up -d postgres redis
wait_for_health "onehunt_postgres" "postgres"
wait_for_health "onehunt_redis" "redis"

echo "== Build Mini App image =="
docker compose -f "${COMPOSE_FILE}" build miniapp

echo "== Load questions into Mini App database =="
docker compose -f "${COMPOSE_FILE}" run --rm miniapp python scripts/load_questions.py

echo "== Start Mini App stack =="
docker compose -f "${COMPOSE_FILE}" up -d miniapp
sleep 8

echo "== Apply nginx config =="
MINIAPP_UPSTREAM_IP="$(resolve_container_ip "onehunt_miniapp")"
echo "Mini App upstream: ${MINIAPP_UPSTREAM_IP}:8080"
write_miniapp_nginx_conf "${DOMAIN}" "${MINIAPP_UPSTREAM_IP}"
ln -sf "${NGINX_CONF}" "/etc/nginx/sites-enabled/${DOMAIN}"
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl reload nginx

if command -v certbot >/dev/null 2>&1; then
    if getent ahostsv4 "${DOMAIN}" >/dev/null 2>&1; then
        echo "== Try SSL certificate =="
        CERTBOT_ARGS=(-d "${DOMAIN}")
        if getent ahostsv4 "www.${DOMAIN}" >/dev/null 2>&1; then
            CERTBOT_ARGS+=(-d "www.${DOMAIN}")
        fi
        certbot --nginx "${CERTBOT_ARGS[@]}" --non-interactive --agree-tos --register-unsafely-without-email || true
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
df -h /

echo "== Done =="
