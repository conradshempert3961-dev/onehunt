#!/usr/bin/env bash
# Bootstrap DeepSeek Free API proxy per ONEHUNT guide (.env.local.example).
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEEPSEEK_DIR="${DEEPSEEK_API_DIR:-$ROOT/tools/deepseek-free-api}"
DEEPSEEK_REPO="${DEEPSEEK_REPO:-https://github.com/ForgetMeAI/FreeDeepseekAPI.git}"
DEEPSEEK_PORT="${DEEPSEEK_PORT:-18632}"
SHIM="$ROOT/scripts/deepseek_server.mjs"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 18+ required: https://nodejs.org"
  exit 1
fi

if [[ ! -d "$DEEPSEEK_DIR/.git" ]]; then
  echo "Cloning DeepSeek proxy -> $DEEPSEEK_DIR"
  mkdir -p "$(dirname "$DEEPSEEK_DIR")"
  git clone --depth 1 "$DEEPSEEK_REPO" "$DEEPSEEK_DIR"
fi

pushd "$DEEPSEEK_DIR" >/dev/null
if [[ -f package.json && ! -d node_modules ]]; then
  npm install
fi
popd >/dev/null

cp "$SHIM" "$DEEPSEEK_DIR/server.mjs"
chmod +x "$DEEPSEEK_DIR/server.mjs" 2>/dev/null || true

echo ""
echo "DeepSeek proxy ready in: $DEEPSEEK_DIR"
echo ""
echo "Next steps (from ONEHUNT guide):"
echo "  1) cd \"$DEEPSEEK_DIR\" && node server.mjs --login"
echo "     (log in at https://chat.deepseek.com in the opened browser)"
echo "  2) node server.mjs   # listens on http://127.0.0.1:${DEEPSEEK_PORT}"
echo ""
echo "Alternative — import token from browser Local Storage (userToken → value):"
echo "  DEEPSEEK_TOKEN=\"<token>\" npm run auth:import -- --input /dev/stdin <<< '{\"token\":\"<token>\"}'"
echo ""
echo "Then start ONEHUNT: bash scripts/run_all_mac.sh"
