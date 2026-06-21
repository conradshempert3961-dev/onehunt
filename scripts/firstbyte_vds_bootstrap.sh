#!/usr/bin/env bash
# ONEHUNT bootstrap for FirstByte / Ubuntu VDS (1 GB RAM friendly)
set -Eeuo pipefail

DOMAIN="${1:-socialspur.ru}"
ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
BRANCH="${ONEHUNT_BRANCH:-main}"
REPO="${ONEHUNT_REPO:-https://github.com/conradshempert3961-dev/onehunt.git}"

echo "== ONEHUNT VDS bootstrap =="
echo "Domain: ${DOMAIN}"
echo "Root:   ${ROOT}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0 ${DOMAIN}"
  exit 1
fi

if ! swapon --show | grep -q .; then
  echo "== Add 2G swap (1 GB RAM) =="
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "== Install packages =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-plugin nginx certbot python3-certbot-nginx git curl
systemctl enable --now docker
systemctl enable --now nginx

echo "== Clone or update repo =="
if [[ ! -d "${ROOT}/.git" ]]; then
  git clone --depth 1 -b "${BRANCH}" "${REPO}" "${ROOT}"
else
  cd "${ROOT}"
  git fetch --depth 1 origin "${BRANCH}" || true
  git checkout "${BRANCH}" || true
  git pull --ff-only || true
fi

cd "${ROOT}"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

# Minimal production defaults
set_kv() {
  local key="$1" val="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s#^${key}=.*#${key}=${val}#" .env
  else
    printf '%s=%s\n' "${key}" "${val}" >> .env
  fi
}

set_kv "MINIAPP_URL" "https://${DOMAIN}/app"
set_kv "MINIAPP_BROWSER_DEMO" "false"
set_kv "USE_REDIS_FSM" "false"
set_kv "FREE_MODE" "false"
set_kv "MINIAPP_HOST" "0.0.0.0"

echo "== Docker stack (miniapp only) =="
bash deploy/scripts/run_standalone_domain.sh "${DOMAIN}"

echo "== Done =="
echo "Open: https://${DOMAIN}/"
echo "App:  https://${DOMAIN}/app"
echo "Edit: ${ROOT}/.env  (BOT_TOKEN, payments, AI)"
