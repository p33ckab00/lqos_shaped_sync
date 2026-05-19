#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_SRC="$ROOT_DIR/systemd/lqosync-core.service"
SERVICE_DEST="${LQOSYNC_CORE_SERVICE_DEST:-/etc/systemd/system/lqosync-core.service}"
BIN="${LQOSYNC_CORE_DEST:-/usr/local/bin/lqosync-core}"
if [ ! -x "$BIN" ]; then
  echo "Rust core binary not installed at $BIN. Run sudo bash scripts/install-rust-core.sh first." >&2
  exit 1
fi
install -m 0644 "$SERVICE_SRC" "$SERVICE_DEST"
systemctl daemon-reload
systemctl enable lqosync-core.service
if systemctl is-active --quiet lqosync-core.service; then
  systemctl restart lqosync-core.service
else
  systemctl start lqosync-core.service
fi
systemctl status lqosync-core.service --no-pager || true
echo "Installed and restarted lqosync-core daemon service."
