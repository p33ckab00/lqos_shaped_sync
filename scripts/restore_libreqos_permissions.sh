#!/usr/bin/env bash
set -euo pipefail

# Restore /opt/libreqos/src permissions after removing LQoSync.
# Default mode restores only the files LQoSync manages. Use --full to chown
# the whole LibreQoS src tree back to root:root.

LIBREQOS_SRC_DIR="${LIBREQOS_SRC_DIR:-/opt/libreqos/src}"
LQOSYNC_USER="${LQOSYNC_USER:-lqosync}"
MODE="managed"

if [[ "${1:-}" == "--full" ]]; then
  MODE="full"
elif [[ "${1:-}" == "--managed" || -z "${1:-}" ]]; then
  MODE="managed"
else
  echo "Usage: sudo bash scripts/restore_libreqos_permissions.sh [--managed|--full]" >&2
  exit 2
fi

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root. Use sudo." >&2
  exit 1
fi

if [[ ! -d "$LIBREQOS_SRC_DIR" ]]; then
  echo "LibreQoS source directory not found: $LIBREQOS_SRC_DIR" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
ACL_BACKUP="/root/lqosync_libreqos_acl_backup_${STAMP}.acl"

if command -v getfacl >/dev/null 2>&1; then
  {
    getfacl -p "$LIBREQOS_SRC_DIR" 2>/dev/null || true
    for f in config.json ShapedDevices.csv network.json; do
      [[ -e "$LIBREQOS_SRC_DIR/$f" ]] && getfacl -p "$LIBREQOS_SRC_DIR/$f" 2>/dev/null || true
    done
  } > "$ACL_BACKUP" || true
  echo "[LQoSync] ACL backup saved to: $ACL_BACKUP"
fi

if command -v setfacl >/dev/null 2>&1; then
  echo "[LQoSync] Removing ACL entries for user: $LQOSYNC_USER"
  setfacl -x "u:$LQOSYNC_USER" "$LIBREQOS_SRC_DIR" 2>/dev/null || true
  setfacl -d -x "u:$LQOSYNC_USER" "$LIBREQOS_SRC_DIR" 2>/dev/null || true
  for f in config.json ShapedDevices.csv network.json; do
    [[ -e "$LIBREQOS_SRC_DIR/$f" ]] && setfacl -x "u:$LQOSYNC_USER" "$LIBREQOS_SRC_DIR/$f" 2>/dev/null || true
  done
fi

if [[ "$MODE" == "full" ]]; then
  echo "[LQoSync] Restoring root:root ownership recursively under $LIBREQOS_SRC_DIR"
  chown -R root:root "$LIBREQOS_SRC_DIR"
else
  echo "[LQoSync] Restoring root:root ownership on managed LibreQoS files only"
  chown root:root "$LIBREQOS_SRC_DIR" 2>/dev/null || true
  for f in config.json ShapedDevices.csv network.json; do
    [[ -e "$LIBREQOS_SRC_DIR/$f" ]] && chown root:root "$LIBREQOS_SRC_DIR/$f" || true
  done
fi

# Conservative permissions after LQoSync removal. LibreQoS/manual root commands can
# still read these files. config.json may contain router credentials.
[[ -e "$LIBREQOS_SRC_DIR/config.json" ]] && chmod 600 "$LIBREQOS_SRC_DIR/config.json" || true
[[ -e "$LIBREQOS_SRC_DIR/ShapedDevices.csv" ]] && chmod 644 "$LIBREQOS_SRC_DIR/ShapedDevices.csv" || true
[[ -e "$LIBREQOS_SRC_DIR/network.json" ]] && chmod 644 "$LIBREQOS_SRC_DIR/network.json" || true
chmod 755 "$LIBREQOS_SRC_DIR" || true

echo "[LQoSync] LibreQoS permission restore complete."
ls -ld "$LIBREQOS_SRC_DIR" || true
ls -lah "$LIBREQOS_SRC_DIR/config.json" "$LIBREQOS_SRC_DIR/ShapedDevices.csv" "$LIBREQOS_SRC_DIR/network.json" 2>/dev/null || true
