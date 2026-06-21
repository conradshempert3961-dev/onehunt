#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOGS_DIR="$ROOT/logs"
DATA_DIR="$ROOT/data"
mkdir -p "$LOGS_DIR" "$DATA_DIR"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  echo "Python 3 is required. Install from https://www.python.org/downloads/"
  exit 1
fi

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.local.example" "$ROOT/.env"
  echo "Created .env from .env.local.example"
fi

while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%%#*}"
  line="$(echo "$line" | xargs)"
  [[ -z "$line" || "$line" != *"="* ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  export "$key=$value"
done < "$ROOT/.env"

DB_PATH="${DATA_DIR}/onehunt_local.db"
export DATABASE_URL="sqlite+aiosqlite:///${DB_PATH//\\//}"
export USE_REDIS_FSM="${USE_REDIS_FSM:-false}"
export QUESTIONS_FILE="${QUESTIONS_FILE:-$ROOT/questions.json}"
export EXPORT_DIR="${EXPORT_DIR:-$DATA_DIR}"
export ANIMAL_CARDS_FILE="${ANIMAL_CARDS_FILE:-$DATA_DIR/animal_cards.json}"
export QUOTES_FILE="${QUOTES_FILE:-$DATA_DIR/quotes.json}"
export FREE_MODE="${FREE_MODE:-true}"
export BOT_SHELL_MODE="${BOT_SHELL_MODE:-true}"
export MINIAPP_BROWSER_DEMO="${MINIAPP_BROWSER_DEMO:-true}"
export MINIAPP_BROWSER_DEMO_HOSTS="${MINIAPP_BROWSER_DEMO_HOSTS:-localhost,127.0.0.1,::1}"
export MINIAPP_DEV_USER_ID="${MINIAPP_DEV_USER_ID:-6467055041}"
export MINIAPP_HOST="${MINIAPP_HOST:-0.0.0.0}"
export MINIAPP_PORT="${MINIAPP_PORT:-8080}"
export MINIAPP_URL="${MINIAPP_URL:-http://127.0.0.1:${MINIAPP_PORT}/}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-dummy}"
export OPENAI_API_BASE="${OPENAI_API_BASE:-http://127.0.0.1:18632/v1}"
export OPENAI_MODEL="${OPENAI_MODEL:-deepseek-chat}"
export AI_REQUEST_TIMEOUT="${AI_REQUEST_TIMEOUT:-90}"

"$PYTHON" -m pip install -q -r "$ROOT/requirements.txt"
"$PYTHON" "$ROOT/scripts/load_questions.py"

DEEPSEEK_DIR="${DEEPSEEK_API_DIR:-$ROOT/tools/deepseek-free-api}"
DEEPSEEK_PORT="${DEEPSEEK_PORT:-18632}"

deepseek_running() {
  curl -sf "http://127.0.0.1:${DEEPSEEK_PORT}/v1/models" >/dev/null 2>&1
}

miniapp_running() {
  curl -sf "http://127.0.0.1:${MINIAPP_PORT}/health" >/dev/null 2>&1
}

start_deepseek() {
  if deepseek_running; then
    echo "DeepSeek proxy: already running on port ${DEEPSEEK_PORT}"
    return 0
  fi

  if [[ ! -d "$DEEPSEEK_DIR" ]]; then
    echo "DeepSeek proxy not found — bootstrapping..."
    bash "$ROOT/scripts/bootstrap_deepseek_proxy.sh" || return 1
  fi

  if ! command -v node >/dev/null 2>&1; then
    echo "Node.js 18+ is required for DeepSeek proxy. Install from https://nodejs.org"
    return 1
  fi

  pushd "$DEEPSEEK_DIR" >/dev/null
  if [[ -f package.json && ! -d node_modules ]]; then
    npm install
  fi
  if [[ ! -f server.mjs && -f "$ROOT/scripts/deepseek_server.mjs" ]]; then
    cp "$ROOT/scripts/deepseek_server.mjs" server.mjs
  fi

  if [[ -f server.mjs ]]; then
    if [[ ! -f deepseek-auth.json && ! -f .session && ! -f session.json && ! -f .auth ]]; then
      echo "First login: browser window will open for chat.deepseek.com"
      echo "  cd \"$DEEPSEEK_DIR\" && node server.mjs --login"
      node server.mjs --login || true
    fi
    PORT="${DEEPSEEK_PORT}" nohup node server.mjs > "$LOGS_DIR/deepseek.stdout.log" 2> "$LOGS_DIR/deepseek.stderr.log" &
  elif [[ -f server.js ]]; then
    if [[ ! -f auth.json ]]; then
      echo "First login: run npm run auth in $DEEPSEEK_DIR"
      npm run auth
    fi
    nohup node server.js > "$LOGS_DIR/deepseek.stdout.log" 2> "$LOGS_DIR/deepseek.stderr.log" &
  else
    echo "No server.mjs or server.js found in $DEEPSEEK_DIR"
    popd >/dev/null
    return 1
  fi

  echo $! > "$LOGS_DIR/deepseek.pid"
  popd >/dev/null
  sleep 2

  if deepseek_running; then
    echo "DeepSeek proxy: started on port ${DEEPSEEK_PORT}"
  else
    echo "DeepSeek proxy failed to start. Check $LOGS_DIR/deepseek.stderr.log"
    return 1
  fi
}

start_miniapp() {
  if miniapp_running; then
    echo "ONEHUNT: already running on port ${MINIAPP_PORT}"
    return 0
  fi

  nohup "$PYTHON" "$ROOT/miniapp_server.py" > "$LOGS_DIR/miniapp.stdout.log" 2> "$LOGS_DIR/miniapp.stderr.log" &
  echo $! > "$LOGS_DIR/miniapp.pid"
  sleep 2

  if miniapp_running; then
    echo "ONEHUNT: started on port ${MINIAPP_PORT}"
  else
    echo "ONEHUNT failed to start. Check $LOGS_DIR/miniapp.stderr.log"
    exit 1
  fi
}

start_deepseek || true
start_miniapp

echo ""
echo "Local ONEHUNT is running."
echo "Main site: http://127.0.0.1:${MINIAPP_PORT}/"
echo "Mini App:  http://127.0.0.1:${MINIAPP_PORT}/app"
echo "Promo hub: http://127.0.0.1:${MINIAPP_PORT}/promo/"
echo "Estate:    http://127.0.0.1:${MINIAPP_PORT}/estate/"
echo ""
echo "Stop everything: bash scripts/stop_all_mac.sh"

if [[ "$(uname -s)" == "Darwin" ]]; then
  open "http://127.0.0.1:${MINIAPP_PORT}/app"
fi
