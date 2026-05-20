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

check_contains() {
  local path="$1" pattern="$2" label="$3"
  check_file "$path"
  if [ -f "$path" ] && ! grep -q "$pattern" "$path"; then
    echo "MISSING[$label]: $path lacks pattern: $pattern" >&2
    fail=1
  else
    echo "ok|$label|$path"
  fi
}

echo "[branch-cleanup-alignment] checking canonical branch/path docs"
for f in INSTALLATION.md GIT_INSTALL.md docs/GITHUB_INSTALL.md BARE_METAL_INSTALL.md DOCKER_INSTALL.md README.md docs/BRANCH_INSTALL_AND_CLEANUP_GUIDE.md docs/RUST_CORE_V754_BRANCH_INSTALL_CLEANUP_ALIGNMENT.md; do
  check_contains "$f" "lqosync-in-rust" "branch"
  check_contains "$f" "/opt/LQoSync" "canonical-path"
done

echo "[branch-cleanup-alignment] checking Rust daemon commands"
for f in INSTALLATION.md GIT_INSTALL.md docs/GITHUB_INSTALL.md README.md docs/BRANCH_INSTALL_AND_CLEANUP_GUIDE.md; do
  check_contains "$f" "build-rust-core.sh" "build-script"
  check_contains "$f" "install-rust-core-daemon.sh" "daemon-install"
  check_contains "$f" "self-test" "self-test"
done

echo "[branch-cleanup-alignment] checking cleanup runbook references"
for f in docs/STALE_CODEBASE_CLEANUP_POLICY.md docs/STALE_CODEBASE_CLEANUP_EXECUTION_RUNBOOK.md docs/BRANCH_INSTALL_AND_CLEANUP_GUIDE.md README.md FULL_DOCUMENTATION.md; do
  check_contains "$f" "stale-codebase-cleanup-execution-plan.sh" "cleanup-plan"
  check_contains "$f" "stale-codebase-cleanup-execute-guard.sh" "cleanup-execute"
  check_contains "$f" "/opt/LQoSync-archive" "archive-root"
done

echo "[branch-cleanup-alignment] checking installer defaults"
grep -q 'LQOSYNC_BRANCH:-lqosync-in-rust' install-from-github.sh || { echo "install-from-github.sh default branch is not lqosync-in-rust" >&2; fail=1; }
grep -q 'LQOSYNC_INSTALL_DIR:-/opt/LQoSync' install-from-github.sh || { echo "install-from-github.sh default dir is not /opt/LQoSync" >&2; fail=1; }
grep -q 'LQOSYNC_BRANCH:-lqosync-in-rust' upgrade.sh || { echo "upgrade.sh default branch is not lqosync-in-rust" >&2; fail=1; }
grep -q 'LQOSYNC_INSTALL_DIR:-/opt/LQoSync' upgrade.sh || { echo "upgrade.sh default dir is not /opt/LQoSync" >&2; fail=1; }

echo "[branch-cleanup-alignment] checking cleanup scripts exist and are shell-valid"
for f in \
  scripts/stale-codebase-inventory.sh \
  scripts/stale-codebase-cleanup-dry-run.sh \
  scripts/stale-codebase-cleanup-execution-plan.sh \
  scripts/stale-codebase-cleanup-execute-guard.sh \
  scripts/stale-codebase-post-cleanup-verify.sh \
  scripts/stale-codebase-restore-from-archive.sh; do
  check_file "$f"
  [ -f "$f" ] && bash -n "$f"
done

if [ "$fail" -ne 0 ]; then
  echo "[branch-cleanup-alignment] FAILED" >&2
  exit 1
fi

echo "[branch-cleanup-alignment] OK"
