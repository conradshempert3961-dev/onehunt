#!/usr/bin/env bash
# Connect ONEHUNT AI to DeepSeek using browser userToken (.env.deepseek).
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CREDS="${ROOT}/.env.deepseek"
PROXY_URL="${DEEPSEEK_PROXY_URL:-http://127.0.0.1:8000}"

cd "${ROOT}"

if [[ ! -f "${CREDS}" ]]; then
  cat <<'EOF'
Create .env.deepseek with your browser token:
  chat.deepseek.com → F12 → Application → Local Storage → userToken → value

Example:
  DEEPSEEK_USER_TOKEN=your_token_here
EOF
  exit 1
fi

# shellcheck disable=SC1090
source "${CREDS}"

if [[ -z "${DEEPSEEK_USER_TOKEN:-}" ]]; then
  echo "Set DEEPSEEK_USER_TOKEN in ${CREDS}"
  exit 1
fi

if ! curl -sf "${PROXY_URL}/health" >/dev/null 2>&1; then
  echo "Starting DeepSeek proxy (Docker)..."
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker not found. Install Docker Desktop or start proxy manually on ${PROXY_URL}"
    exit 1
  fi
  docker compose -f docker-compose.prod.yml up -d --build deepseek
  for _ in $(seq 1 30); do
    curl -sf "${PROXY_URL}/health" >/dev/null 2>&1 && break
    sleep 2
  done
fi

python3 "${ROOT}/scripts/deepseek_token_import.py" \
  --token "${DEEPSEEK_USER_TOKEN}" \
  --proxy "${PROXY_URL}"

set_kv() {
  local k="$1" v="$2"
  local env_file="${ROOT}/.env"
  [[ -f "${env_file}" ]] || cp "${ROOT}/.env.local.example" "${env_file}"
  if grep -q "^${k}=" "${env_file}"; then
    sed -i.bak "s|^${k}=.*|${k}=${v}|" "${env_file}" && rm -f "${env_file}.bak"
  else
    echo "${k}=${v}" >> "${env_file}"
  fi
}

set_kv OPENAI_API_KEY "sk-dummy"
set_kv OPENAI_API_BASE "http://127.0.0.1:8000/v1"
set_kv OPENAI_MODEL "deepseek-chat"
set_kv AI_REQUEST_TIMEOUT "90"

echo ""
echo "DeepSeek AI configured for local ONEHUNT."
echo "Start app: bash scripts/run_all_mac.sh"
echo "Check AI tab — status should show: Живой AI · DeepSeek"
