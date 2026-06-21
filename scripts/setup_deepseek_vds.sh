#!/usr/bin/env bash
# Configure DeepSeek Free API proxy and wire ONEHUNT AI to it.
set -Eeuo pipefail

ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
COMPOSE_FILE="${ROOT}/docker-compose.prod.yml"
CREDS_FILE="${ROOT}/.env.deepseek"

cd "${ROOT}"

if [[ ! -f "${CREDS_FILE}" ]]; then
  cat > "${CREDS_FILE}" <<'EOF'
# DeepSeek web account (NOT committed to git)
DEEPSEEK_EMAIL=
DEEPSEEK_PASSWORD=
EOF
  chmod 600 "${CREDS_FILE}"
  echo "Created ${CREDS_FILE} — fill DEEPSEEK_EMAIL and DEEPSEEK_PASSWORD, then rerun."
  exit 1
fi

# shellcheck disable=SC1090
source "${CREDS_FILE}"

if [[ -z "${DEEPSEEK_EMAIL:-}" || -z "${DEEPSEEK_PASSWORD:-}" ]]; then
  echo "Set DEEPSEEK_EMAIL and DEEPSEEK_PASSWORD in ${CREDS_FILE}"
  exit 1
fi

echo "== Start DeepSeek proxy =="
docker compose -f "${COMPOSE_FILE}" up -d deepseek

for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "== Login to DeepSeek =="
LOGIN_RESULT=$(curl -sf -X POST http://127.0.0.1:8000/api/login \
  -H "Content-Type: application/json" \
  -d "{\"login_type\":\"email\",\"email\":\"${DEEPSEEK_EMAIL}\",\"password\":\"${DEEPSEEK_PASSWORD}\"}")

echo "${LOGIN_RESULT}" | python3 -c "import sys,json; d=json.load(sys.stdin); print('login ok' if d.get('ok') else d.get('error','failed'))"

if ! echo "${LOGIN_RESULT}" | python3 -c "import sys,json; sys.exit(0 if json.load(sys.stdin).get('ok') else 1)"; then
  exit 1
fi

set_kv() {
  local k="$1" v="$2"
  if grep -q "^${k}=" .env; then sed -i "s|^${k}=.*|${k}=${v}|" .env; else echo "${k}=${v}" >> .env; fi
}

set_kv OPENAI_API_KEY "sk-dummy"
set_kv OPENAI_API_BASE "http://deepseek:8000/v1"
set_kv OPENAI_MODEL "deepseek-chat"
set_kv AI_REQUEST_TIMEOUT "90"

echo "== Restart miniapp =="
docker compose -f "${COMPOSE_FILE}" up -d miniapp

sleep 3
curl -sf http://127.0.0.1:8080/health >/dev/null
echo "Done. AI should use DeepSeek via internal proxy."
