#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
chmod +x   "$ROOT_DIR/scripts/build-rust-core.sh"   "$ROOT_DIR/scripts/install-rust-core.sh"   "$ROOT_DIR/scripts/install-rust-core-daemon.sh"   "$ROOT_DIR/scripts/uninstall-rust-core-daemon.sh"   "$ROOT_DIR/install.sh"   "$ROOT_DIR/install-from-github.sh"   "$ROOT_DIR/uninstall.sh" 2>/dev/null || true
echo "Script permissions repaired. You can now run scripts/build-rust-core.sh directly."
