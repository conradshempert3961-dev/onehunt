#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS_DIR="$ROOT/logs"

stop_pid_file() {
  local name="$1"
  local pid_file="$LOGS_DIR/${name}.pid"
  if [[ ! -f "$pid_file" ]]; then
    return 0
  fi
  local pid
  pid="$(tr -d '[:space:]' < "$pid_file")"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    echo "$name stopped: PID $pid"
  fi
  rm -f "$pid_file"
}

stop_pid_file "miniapp"
echo "Local ONEHUNT processes stopped."
