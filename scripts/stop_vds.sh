#!/usr/bin/env bash
# Stop ONEHUNT on VDS (Docker + nginx). Run on server as root.
set -Eeuo pipefail

ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
COMPOSE_FILE="${ROOT}/docker-compose.prod.yml"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

echo "== Stop ONEHUNT containers =="
if [[ -f "${COMPOSE_FILE}" ]]; then
  cd "${ROOT}"
  docker compose -f "${COMPOSE_FILE}" down --remove-orphans 2>/dev/null || true
fi

for name in onehunt_miniapp onehunt_postgres onehunt_redis onehunt_deepseek onehunt_bot onehunt_site; do
  if docker ps -a --format '{{.Names}}' | grep -qx "${name}"; then
    docker rm -f "${name}" 2>/dev/null || true
    echo "Removed ${name}"
  fi
done

echo "== Disable nginx site =="
if [[ -L /etc/nginx/sites-enabled/onehunt ]]; then
  rm -f /etc/nginx/sites-enabled/onehunt
fi
if nginx -t 2>/dev/null; then
  systemctl reload nginx 2>/dev/null || true
fi

echo "Done. ONEHUNT stopped on this server."
echo "Site http://$(curl -sf ifconfig.me 2>/dev/null || echo 'this-host')/ should no longer serve the app."
echo "Start again: cd ${ROOT} && bash scripts/deploy_ip_only.sh <ip>"
