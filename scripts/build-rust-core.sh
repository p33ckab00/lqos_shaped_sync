#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_DIR="$ROOT_DIR/rust/lqosync-core"
if ! command -v cargo >/dev/null 2>&1; then
  echo "ERROR: cargo is not installed. Install Rust toolchain first: https://rustup.rs" >&2
  exit 1
fi
cd "$CORE_DIR"
# Prevent a failed test/build from leaving a stale release binary that could be installed accidentally.
rm -f "$CORE_DIR/target/release/lqosync-core"
cargo test
cargo build --release
echo "Built: $CORE_DIR/target/release/lqosync-core"
