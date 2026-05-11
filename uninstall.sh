#!/usr/bin/env bash
set -euo pipefail

# LQoSync bare-metal uninstall helper.
# Defaults are safe: stop/remove service + sudoers, restore LibreQoS ACL/ownership
# for managed files, and keep /opt/lqosync as a backup source unless REMOVE_RUNTIME=true.

INSTALL_DIR="${INSTALL_DIR:-/opt/lqosync}"
SERVICE_NAME="${SERVICE_NAME:-lqos_shaped_sync}"
RESTORE_LIBREQOS_PERMS="${RESTORE_LIBREQOS_PERMS:-true}"
RESTORE_MODE="${RESTORE_MODE:-managed}" # managed or full
REMOVE_RUNTIME="${REMOVE_RUNTIME:-false}"
REMOVE_USER="${REMOVE_USER:-false}"
LQOSYNC_USER="${LQOSYNC_USER:-lqosync}"

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root. Use sudo." >&2
  exit 1
fi

echo "[LQoSync] Stopping and disabling $SERVICE_NAME..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true

rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload || true
systemctl reset-failed || true

rm -f /etc/sudoers.d/lqosync /etc/sudoers.d/lqos_shaped_sync

if [[ "$RESTORE_LIBREQOS_PERMS" == "true" ]]; then
  if [[ -x "$INSTALL_DIR/scripts/restore_libreqos_permissions.sh" ]]; then
    if [[ "$RESTORE_MODE" == "full" ]]; then
      bash "$INSTALL_DIR/scripts/restore_libreqos_permissions.sh" --full
    else
      bash "$INSTALL_DIR/scripts/restore_libreqos_permissions.sh" --managed
    fi
  else
    echo "[LQoSync] restore_libreqos_permissions.sh not found. Running inline managed restore."
    LIBREQOS_SRC_DIR="${LIBREQOS_SRC_DIR:-/opt/libreqos/src}"
    if command -v setfacl >/dev/null 2>&1; then
      setfacl -x "u:$LQOSYNC_USER" "$LIBREQOS_SRC_DIR" 2>/dev/null || true
      setfacl -d -x "u:$LQOSYNC_USER" "$LIBREQOS_SRC_DIR" 2>/dev/null || true
      for f in config.json ShapedDevices.csv network.json; do
        [[ -e "$LIBREQOS_SRC_DIR/$f" ]] && setfacl -x "u:$LQOSYNC_USER" "$LIBREQOS_SRC_DIR/$f" 2>/dev/null || true
      done
    fi
    chown root:root "$LIBREQOS_SRC_DIR" 2>/dev/null || true
    for f in config.json ShapedDevices.csv network.json; do
      [[ -e "$LIBREQOS_SRC_DIR/$f" ]] && chown root:root "$LIBREQOS_SRC_DIR/$f" || true
    done
    [[ -e "$LIBREQOS_SRC_DIR/config.json" ]] && chmod 600 "$LIBREQOS_SRC_DIR/config.json" || true
    [[ -e "$LIBREQOS_SRC_DIR/ShapedDevices.csv" ]] && chmod 644 "$LIBREQOS_SRC_DIR/ShapedDevices.csv" || true
    [[ -e "$LIBREQOS_SRC_DIR/network.json" ]] && chmod 644 "$LIBREQOS_SRC_DIR/network.json" || true
    chmod 755 "$LIBREQOS_SRC_DIR" 2>/dev/null || true
  fi
fi

if [[ -d "$INSTALL_DIR" ]]; then
  BACKUP="/root/lqosync_uninstall_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
  tar -czf "$BACKUP" "$INSTALL_DIR" 2>/dev/null || true
  echo "[LQoSync] Runtime backup saved to: $BACKUP"
  if [[ "$REMOVE_RUNTIME" == "true" ]]; then
    rm -rf "$INSTALL_DIR"
    echo "[LQoSync] Removed $INSTALL_DIR"
  else
    echo "[LQoSync] Kept $INSTALL_DIR. To remove it, run: sudo REMOVE_RUNTIME=true bash uninstall.sh"
  fi
fi

rm -f /var/log/lqos_shaped_sync.log 2>/dev/null || true

if [[ "$REMOVE_USER" == "true" ]]; then
  userdel "$LQOSYNC_USER" 2>/dev/null || true
  rm -rf "/home/$LQOSYNC_USER" 2>/dev/null || true
  echo "[LQoSync] Removed user $LQOSYNC_USER"
fi

echo "[LQoSync] Uninstall complete."
