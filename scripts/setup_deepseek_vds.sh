#!/usr/bin/env bash
# Configure DeepSeek Free API on VDS and wire ONEHUNT AI to it.
#
# Recommended (works from datacenter IP — login from browser on your PC):
#   1. chat.deepseek.com → F12 → Application → Local Storage → userToken → copy "value"
#   2. Put in /opt/onehunt/.env.deepseek:
#        DEEPSEEK_USER_TOKEN=...
#   3. bash scripts/setup_deepseek_vds.sh
#
# Alternative: DEEPSEEK_CURL="curl ..." (Copy as cURL from Network tab)
# Fallback: DEEPSEEK_EMAIL + DEEPSEEK_PASSWORD (often blocked by WAF on VDS)
set -Eeuo pipefail

ROOT="${ONEHUNT_ROOT:-/opt/onehunt}"
COMPOSE_FILE="${ROOT}/docker-compose.prod.yml"
CREDS_FILE="${ROOT}/.env.deepseek"

cd "${ROOT}"

if [[ ! -f "${CREDS_FILE}" ]]; then
  cat > "${CREDS_FILE}" <<'EOF'
# DeepSeek auth (NOT committed to git)
# Recommended — token from browser after login at chat.deepseek.com:
# F12 → Application → Local Storage → userToken → value
DEEPSEEK_USER_TOKEN=

# Or paste "Copy as cURL" from Network → completion request:
# DEEPSEEK_CURL=

# Or email login (may fail on VDS due to AWS WAF):
DEEPSEEK_EMAIL=
DEEPSEEK_PASSWORD=
EOF
  chmod 600 "${CREDS_FILE}"
  echo "Created ${CREDS_FILE} — set DEEPSEEK_USER_TOKEN, then rerun."
  exit 1
fi

# shellcheck disable=SC1090
source "${CREDS_FILE}"

set_kv() {
  local k="$1" v="$2"
  if grep -q "^${k}=" .env; then
    sed -i "s|^${k}=.*|${k}=${v}|" .env
  else
    echo "${k}=${v}" >> .env
  fi
}

echo "== Start DeepSeek proxy =="
docker compose -f "${COMPOSE_FILE}" up -d --build deepseek

for _ in $(seq 1 45); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "DeepSeek proxy did not start. Check: docker logs onehunt_deepseek"
  exit 1
fi

IMPORT_OK=0

if [[ -n "${DEEPSEEK_USER_TOKEN:-}" ]]; then
  echo "== Import browser userToken =="
  if python3 "${ROOT}/scripts/deepseek_token_import.py" \
      --token "${DEEPSEEK_USER_TOKEN}" \
      --proxy "http://127.0.0.1:8000"; then
    IMPORT_OK=1
  else
    echo "Token import failed."
  fi
elif [[ -n "${DEEPSEEK_CURL:-}" ]]; then
  echo "== Import cURL from browser =="
  CURL_JSON=$(python3 -c "import json,sys; print(json.dumps({'curl': sys.stdin.read()}))" <<< "${DEEPSEEK_CURL}")
  RESULT=$(curl -sf -X POST http://127.0.0.1:8000/api/config \
    -H "Content-Type: application/json" \
    -d "${CURL_JSON}" || echo '{"ok":false}')
  echo "${RESULT}" | python3 -c "import sys,json; d=json.load(sys.stdin); print('import ok' if d.get('ok') else d.get('error','failed'))"
  if echo "${RESULT}" | python3 -c "import sys,json; sys.exit(0 if json.load(sys.stdin).get('ok') else 1)"; then
    IMPORT_OK=1
  fi
elif [[ -n "${DEEPSEEK_EMAIL:-}" && -n "${DEEPSEEK_PASSWORD:-}" ]]; then
  echo "== Email login (may be blocked on datacenter IP) =="
  LOGIN_RESULT=$(curl -sf -X POST http://127.0.0.1:8000/api/login \
    -H "Content-Type: application/json" \
    -d "{\"login_type\":\"email\",\"email\":\"${DEEPSEEK_EMAIL}\",\"password\":\"${DEEPSEEK_PASSWORD}\"}" \
    || echo '{"ok":false,"error":"login request failed"}')
  echo "${LOGIN_RESULT}" | python3 -c "import sys,json; d=json.load(sys.stdin); print('login ok' if d.get('ok') else d.get('error','failed'))"
  if echo "${LOGIN_RESULT}" | python3 -c "import sys,json; sys.exit(0 if json.load(sys.stdin).get('ok') else 1)"; then
    IMPORT_OK=1
  fi
else
  echo "Set DEEPSEEK_USER_TOKEN (recommended), DEEPSEEK_CURL, or DEEPSEEK_EMAIL/PASSWORD in ${CREDS_FILE}"
  exit 1
fi

if [[ "${IMPORT_OK}" -ne 1 ]]; then
  echo ""
  echo "Auth failed. Use browser token (see .env.local.example):"
  echo "  chat.deepseek.com → F12 → Application → userToken → value → DEEPSEEK_USER_TOKEN"
  exit 1
fi

echo "== Wire ONEHUNT miniapp to DeepSeek =="
set_kv OPENAI_API_KEY "sk-dummy"
set_kv OPENAI_API_BASE "http://deepseek:8000/v1"
set_kv OPENAI_MODEL "deepseek-chat"
set_kv AI_REQUEST_TIMEOUT "90"

echo "== Restart miniapp =="
docker compose -f "${COMPOSE_FILE}" up -d miniapp

sleep 3
curl -sf http://127.0.0.1:8080/health >/dev/null

echo ""
echo "Done. Live AI via DeepSeek proxy."
echo "Check: curl -s http://127.0.0.1:8080/api/bootstrap | python3 -m json.tool | grep -A3 '\"ai\"'"
