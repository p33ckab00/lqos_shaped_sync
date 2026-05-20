#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" != "--execute" ]; then
  echo "Dry-run guard: no changes made."
  echo "Usage: CONFIRM_STALE_CODEBASE_ARCHIVE=CONFIRM_STALE_CODEBASE_ARCHIVE sudo -E bash $0 --execute"
  exit 0
fi

if [ "${CONFIRM_STALE_CODEBASE_ARCHIVE:-}" != "CONFIRM_STALE_CODEBASE_ARCHIVE" ]; then
  echo "ERROR: missing confirmation token."
  echo "Set: export CONFIRM_STALE_CODEBASE_ARCHIVE=CONFIRM_STALE_CODEBASE_ARCHIVE"
  exit 2
fi

if [ ! -d /opt/LQoSync ]; then
  echo "ERROR: /opt/LQoSync canonical path not found. Aborting."
  exit 3
fi

if [ ! -x /usr/local/bin/lqosync-core ]; then
  echo "ERROR: /usr/local/bin/lqosync-core not found/executable. Aborting."
  exit 4
fi

archive_root="/opt/LQoSync-archive/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$archive_root"

archive_path() {
  local p="$1"
  local base
  if [ ! -e "$p" ]; then
    echo "skip missing: $p"
    return
  fi
  case "$p" in
    /opt/LQoSync|/opt/libreqos|/usr/local/bin/lqosync-core|/etc/systemd/system/lqosync-core.service)
      echo "refuse critical path: $p"
      return
      ;;
  esac
  base=$(basename "$p")
  echo "archiving: $p -> $archive_root/$base"
  mv "$p" "$archive_root/$base"
}

for p in /home/pi/lqosync_docker /home/pi/lqosync /opt/lqosync; do
  archive_path "$p"
done

echo "Archive complete: $archive_root"
echo "Run: bash /opt/LQoSync/scripts/stale-codebase-inventory.sh"
