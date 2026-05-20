#!/usr/bin/env bash
set -euo pipefail

# Guarded stale codebase cleanup executor.
# Archive-only. No delete. No service mutation. No WebUI/static asset mutation.

if [ "${1:-}" != "--execute" ]; then
  echo "Dry-run guard: no changes made."
  echo "Usage: CONFIRM_STALE_CODEBASE_CLEANUP_EXECUTION=CONFIRM_STALE_CODEBASE_CLEANUP_EXECUTION LQOSYNC_CANONICAL_VERIFIED=1 LQOSYNC_CORE_SELF_TEST_OK=1 sudo -E bash $0 --execute"
  exit 0
fi

if [ "${CONFIRM_STALE_CODEBASE_CLEANUP_EXECUTION:-}" != "CONFIRM_STALE_CODEBASE_CLEANUP_EXECUTION" ]; then
  echo "ERROR: missing confirmation token."
  exit 2
fi

if [ "${LQOSYNC_CANONICAL_VERIFIED:-}" != "1" ]; then
  echo "ERROR: LQOSYNC_CANONICAL_VERIFIED=1 is required."
  exit 3
fi

if [ "${LQOSYNC_CORE_SELF_TEST_OK:-}" != "1" ]; then
  echo "ERROR: LQOSYNC_CORE_SELF_TEST_OK=1 is required."
  exit 4
fi

canonical_app="/opt/LQoSync"
rust_bin="/usr/local/bin/lqosync-core"
rust_service="lqosync-core.service"
archive_root="${LQOSYNC_STALE_ARCHIVE_ROOT:-/opt/LQoSync-archive/$(date +%Y%m%d-%H%M%S)}"
manifest="$archive_root/cleanup-manifest.tsv"

if [ ! -d "$canonical_app" ]; then
  echo "ERROR: canonical app path $canonical_app not found."
  exit 5
fi

if [ ! -x "$rust_bin" ]; then
  echo "ERROR: Rust binary $rust_bin not executable."
  exit 6
fi

if ! systemctl is-active --quiet "$rust_service"; then
  echo "ERROR: $rust_service is not active."
  exit 7
fi

self_test_tmp=$(mktemp)
if ! printf '{"version":"1","op":"self-test","payload":{}}' | "$rust_bin" > "$self_test_tmp" 2>/dev/null; then
  echo "ERROR: lqosync-core self-test command failed."
  rm -f "$self_test_tmp"
  exit 8
fi

if ! python3 - "$self_test_tmp" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
ops = set((data.get("result") or {}).get("operations") or [])
required = {
    "build-full-rust-backend-steady-state-guard",
    "build-full-rust-backend-production-drift-monitor",
}
if not data.get("ok"):
    raise SystemExit(1)
if not required.issubset(ops):
    raise SystemExit(2)
PY
then
  echo "ERROR: self-test did not confirm final production guard/drift operations."
  rm -f "$self_test_tmp"
  exit 9
fi
rm -f "$self_test_tmp"

mkdir -p "$archive_root"
printf 'timestamp\tsource\tdestination\tstatus\tnote\n' > "$manifest"

protect_resolved_path() {
  local p="$1"
  local rp
  rp=$(readlink -f "$p" 2>/dev/null || true)
  case "$rp" in
    /opt/LQoSync|/opt/LQoSync/*|/opt/lqosync-website|/opt/lqosync-website/*|/opt/libreqos|/opt/libreqos/*|/usr/local/bin/lqosync-core|/etc/systemd/system/lqosync-core.service|/run/lqosync-core.sock)
      echo "ERROR: refusing protected path: $p -> $rp" >&2
      return 1
      ;;
  esac
  return 0
}

archive_path() {
  local p="$1"
  local base dest
  if [ ! -e "$p" ]; then
    printf '%s\t%s\t%s\t%s\t%s\n' "$(date -Is)" "$p" "" "skipped" "missing" >> "$manifest"
    echo "skip missing: $p"
    return
  fi
  protect_resolved_path "$p"
  base=$(basename "$p")
  dest="$archive_root/$base"
  if [ -e "$dest" ]; then
    dest="$archive_root/${base}.$(date +%s)"
  fi
  echo "archiving: $p -> $dest"
  mv "$p" "$dest"
  printf '%s\t%s\t%s\t%s\t%s\n' "$(date -Is)" "$p" "$dest" "archived" "archive-only cleanup" >> "$manifest"
}

# Only these duplicate/legacy working trees are eligible for automatic archive.
archive_path "/home/pi/lqosync_docker"
archive_path "/home/pi/lqosync"
archive_path "/opt/lqosync"

cat > "$archive_root/RESTORE.md" <<RESTORE
# LQoSync stale codebase archive restore

Archive root: $archive_root
Manifest: $manifest

Restore a path manually after review, for example:

    sudo mv '$archive_root/lqosync_docker' /home/pi/lqosync_docker

Or use:

    sudo bash /opt/LQoSync/scripts/stale-codebase-restore-from-archive.sh '$archive_root' lqosync_docker /home/pi/lqosync_docker

RESTORE

echo "Archive complete: $archive_root"
echo "Manifest: $manifest"
echo "Run: bash /opt/LQoSync/scripts/stale-codebase-post-cleanup-verify.sh"
