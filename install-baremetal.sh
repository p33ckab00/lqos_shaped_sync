#!/usr/bin/env bash
# Convenience wrapper for bare-metal Ubuntu/Debian installation.
# Equivalent to: sudo bash install.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/install.sh" "$@"
