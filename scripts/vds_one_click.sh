#!/usr/bin/env bash
# One-click: bot + Mini App on VDS. Paste in VNC console as root.
# curl -fsSL https://raw.githubusercontent.com/conradshempert3961-dev/onehunt/cursor/fix-all-vds-2866/scripts/vds_one_click.sh | bash
set -Eeuo pipefail
exec bash -c "$(curl -fsSL https://raw.githubusercontent.com/conradshempert3961-dev/onehunt/cursor/fix-all-vds-2866/scripts/vds_heal.sh)"
