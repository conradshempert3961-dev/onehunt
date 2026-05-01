#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
COMPOSE_FILE="${ROOT}/docker-compose.prod.yml"

echo "== ONEHUNT web-only mode =="
echo "Root: ${ROOT}"

cd "${ROOT}"

if [ ! -f .env ]; then
    cp .env.example .env
fi

git pull --ff-only || true

echo "== Stop and remove bot and old landing =="
docker compose -f "${COMPOSE_FILE}" stop bot || true
docker compose -f "${COMPOSE_FILE}" rm -f bot || true
docker compose -f "${COMPOSE_FILE}" stop site || true
docker compose -f "${COMPOSE_FILE}" rm -f site || true

echo "== Remove bot image if present =="
docker image rm onehunt-bot:latest 2>/dev/null || true

echo "== Start only standalone web services =="
docker compose -f "${COMPOSE_FILE}" up -d --build postgres redis miniapp

echo "== Safe cleanup =="
docker system prune -f || true
docker builder prune -f || true

echo "== Current services =="
docker compose -f "${COMPOSE_FILE}" ps

echo "== Local checks =="
printf 'miniapp: '
curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' --max-time 10 http://127.0.0.1:8080/ || true

echo "== Disk usage =="
df -h /

echo "== Done =="
