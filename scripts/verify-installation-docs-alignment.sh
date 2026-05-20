#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
fail=0
check_file() {
  local path="$1"
  if [ ! -f "$path" ]; then
    echo "MISSING: $path" >&2
    fail=1
  fi
}
check_file INSTALLATION.md
check_file GIT_INSTALL.md
check_file docs/GITHUB_INSTALL.md
check_file BARE_METAL_INSTALL.md
check_file DOCKER_INSTALL.md
check_file docs/RUST_CORE_V751_INSTALLATION_DOCS_ALIGNMENT.md
check_file scripts/build-rust-core.sh
check_file scripts/install-rust-core.sh
check_file scripts/install-rust-core-daemon.sh

echo "[alignment] canonical branch examples"
grep -R "lqosync-in-rust" INSTALLATION.md GIT_INSTALL.md docs/GITHUB_INSTALL.md BARE_METAL_INSTALL.md DOCKER_INSTALL.md README.md >/dev/null || {
  echo "No lqosync-in-rust references found in primary install docs" >&2
  fail=1
}

echo "[alignment] canonical path examples"
grep -R "/opt/LQoSync" INSTALLATION.md GIT_INSTALL.md docs/GITHUB_INSTALL.md BARE_METAL_INSTALL.md DOCKER_INSTALL.md README.md >/dev/null || {
  echo "No /opt/LQoSync references found in primary install docs" >&2
  fail=1
}

echo "[alignment] Rust daemon install flow"
grep -R "install-rust-core-daemon.sh" INSTALLATION.md GIT_INSTALL.md docs/GITHUB_INSTALL.md BARE_METAL_INSTALL.md README.md >/dev/null || {
  echo "Rust daemon install flow is missing from primary docs" >&2
  fail=1
}

echo "[alignment] install script defaults"
grep -q 'LQOSYNC_BRANCH:-lqosync-in-rust' install-from-github.sh || { echo "install-from-github.sh default branch is not lqosync-in-rust" >&2; fail=1; }
grep -q 'LQOSYNC_INSTALL_DIR:-/opt/LQoSync' install-from-github.sh || { echo "install-from-github.sh default install dir is not /opt/LQoSync" >&2; fail=1; }
grep -q 'LQOSYNC_BRANCH:-lqosync-in-rust' upgrade.sh || { echo "upgrade.sh default branch is not lqosync-in-rust" >&2; fail=1; }
grep -q 'LQOSYNC_INSTALL_DIR:-/opt/LQoSync' upgrade.sh || { echo "upgrade.sh default install dir is not /opt/LQoSync" >&2; fail=1; }

if [ "$fail" -ne 0 ]; then
  echo "[alignment] FAILED" >&2
  exit 1
fi
echo "[alignment] OK"
