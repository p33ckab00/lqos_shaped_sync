#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT_DIR/rust/lqosync-core/target/release/lqosync-core"
DEST="${LQOSYNC_CORE_DEST:-/usr/local/bin/lqosync-core}"
if [ ! -x "$BIN" ]; then
  echo "Rust core binary not found. Run scripts/build-rust-core.sh first." >&2
  exit 1
fi
install -m 0755 "$BIN" "$DEST"
echo "Installed: $DEST"
