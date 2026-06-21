#!/usr/bin/env bash
# Install running-wolf loader video into ONEHUNT static assets.
# Usage: bash scripts/install_wolf_loader_video.sh /path/to/video.mp4
set -Eeuo pipefail

SOURCE="${1:-}"
TARGET="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/miniapp/static/wolf-loader.mp4"

if [[ -z "${SOURCE}" || ! -f "${SOURCE}" ]]; then
  echo "Usage: bash scripts/install_wolf_loader_video.sh /path/to/video.mp4"
  exit 1
fi

cp "${SOURCE}" "${TARGET}"
echo "Installed wolf loader video -> ${TARGET}"
echo "Redeploy miniapp to publish on VDS."
