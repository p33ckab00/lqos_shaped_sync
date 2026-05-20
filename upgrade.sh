#!/usr/bin/env bash
set -euo pipefail

# Smart Git updater for LQoSync bare-metal installs.
# Does not require GitHub CLI (gh). Uses plain git.

INSTALL_DIR="${LQOSYNC_INSTALL_DIR:-/opt/LQoSync}"
REPO_URL="${LQOSYNC_REPO_URL:-https://github.com/p33ckab00/LQoSync.git}"
BRANCH="${LQOSYNC_BRANCH:-lqosync-in-rust}"
SERVICE_NAME="${LQOSYNC_SERVICE_NAME:-lqosync}"
OLD_SERVICE_NAME="${LQOSYNC_OLD_SERVICE_NAME:-lqos_shaped_sync}"
POLICY="${UPDATE_POLICY:-preserve_and_migrate}"
BACKUP_ROOT="${LQOSYNC_BACKUP_ROOT:-/opt/LQoSync/backups/upgrades}"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$TS"
LIBREQOS_SRC="${LIBREQOS_SRC:-/opt/libreqos/src}"

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "Run as root: sudo bash upgrade.sh"
  exit 1
fi

case "$POLICY" in
  pull_only|code_only|preserve_and_migrate|refresh_with_backup|factory_reset) ;;
  *)
    echo "[LQoSync Upgrade] Invalid UPDATE_POLICY=$POLICY"
    echo "Allowed: pull_only | code_only | preserve_and_migrate | refresh_with_backup | factory_reset"
    exit 1
    ;;
esac

log() { echo "[LQoSync Upgrade] $*"; }

mkdir -p "$BACKUP_DIR"
LOCK_FILE="${INSTALL_DIR}/state/upgrade.lock"
mkdir -p "${INSTALL_DIR}/state" 2>/dev/null || true

if [ -f "$LOCK_FILE" ]; then
  log "Upgrade lock exists: $LOCK_FILE"
  log "Remove it only if no upgrade is running."
  exit 1
fi
trap 'rm -f "$LOCK_FILE"' EXIT
date -Is > "$LOCK_FILE"

log "Policy:     $POLICY"
log "Repository: $REPO_URL"
log "Branch:     $BRANCH"
log "Install:    $INSTALL_DIR"
log "Backup:     $BACKUP_DIR"

apt-get update -qq
apt-get install -y git rsync sudo acl python3 python3-venv python3-pip

# Backup operator-owned and LibreQoS-owned runtime files before touching source.
cp -a "$LIBREQOS_SRC/config.json" "$BACKUP_DIR/config.json" 2>/dev/null || true
cp -a "$LIBREQOS_SRC/ShapedDevices.csv" "$BACKUP_DIR/ShapedDevices.csv" 2>/dev/null || true
cp -a "$LIBREQOS_SRC/network.json" "$BACKUP_DIR/network.json" 2>/dev/null || true
cp -a "$INSTALL_DIR/users.json" "$BACKUP_DIR/users.json" 2>/dev/null || true
cp -a "$INSTALL_DIR/.env" "$BACKUP_DIR/.env" 2>/dev/null || true
cp -a "$INSTALL_DIR/state" "$BACKUP_DIR/state" 2>/dev/null || true
cp -a "/etc/systemd/system/${SERVICE_NAME}.service" "$BACKUP_DIR/${SERVICE_NAME}.service" 2>/dev/null || true
cp -a "/etc/sudoers.d/lqosync" "$BACKUP_DIR/sudoers.lqosync" 2>/dev/null || true

OLD_COMMIT="none"
if [ -d "$INSTALL_DIR/.git" ]; then
  OLD_COMMIT="$(git -C "$INSTALL_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
fi

pull_or_clone() {
  if [ -d "$INSTALL_DIR/.git" ]; then
    log "Git-managed install detected. Pulling latest code..."
    git -C "$INSTALL_DIR" config --global --add safe.directory "$INSTALL_DIR" 2>/dev/null || true
    git -C "$INSTALL_DIR" fetch origin "$BRANCH"
    git -C "$INSTALL_DIR" checkout "$BRANCH"
    git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
  else
    log "Install directory is not Git-managed. Converting it using clone + rsync."
    TMP_CLONE="/tmp/lqosync_upgrade_clone_$TS"
    rm -rf "$TMP_CLONE"
    git clone --branch "$BRANCH" "$REPO_URL" "$TMP_CLONE"
    mkdir -p "$INSTALL_DIR"
    rsync -a --delete \
      --exclude 'venv' \
      --exclude 'users.json' \
      --exclude '.env' \
      --exclude 'state' \
      --exclude 'logs' \
      --exclude 'backups' \
      --exclude 'install_backups' \
      --exclude 'config_backups' \
      "$TMP_CLONE/" "$INSTALL_DIR/"
    rm -rf "$TMP_CLONE"
  fi
}

if [ "$POLICY" = "factory_reset" ] && [ "${CONFIRM_FACTORY_RESET:-no}" != "yes" ]; then
  log "factory_reset requires CONFIRM_FACTORY_RESET=yes"
  exit 1
fi

if systemctl is-active --quiet "$SERVICE_NAME"; then
  log "Stopping $SERVICE_NAME before update..."
  systemctl stop "$SERVICE_NAME"
fi

pull_or_clone

if [ -f "$INSTALL_DIR/scripts/cleanup_stale_files.py" ]; then
  log "Removing known stale files from older ZIP/manual installs..."
  python3 "$INSTALL_DIR/scripts/cleanup_stale_files.py" --apply || true
fi

NEW_COMMIT="$(git -C "$INSTALL_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
log "Commit: $OLD_COMMIT -> $NEW_COMMIT"

case "$POLICY" in
  pull_only)
    log "Pull-only policy selected. Not installing dependencies, migrating config, or restarting service."
    ;;

  code_only)
    log "Code-only policy selected. Preserving config/users/generated files; updating dependencies and restarting service."
    python3 -m venv "$INSTALL_DIR/venv"
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
    chown -R lqosync:lqosync "$INSTALL_DIR" 2>/dev/null || true
    systemctl daemon-reload
    systemctl start "$SERVICE_NAME"
    ;;

  preserve_and_migrate|refresh_with_backup)
    log "Production-safe policy selected. Preserving live config/users/generated files and applying safe migration."
    cd "$INSTALL_DIR"
    LQOSYNC_INIT_POLICY=preserve_existing LQOSYNC_INSTALL_MODE=baremetal bash install.sh
    ;;

  factory_reset)
    log "Factory reset selected. Existing files were backed up; templates may replace managed files."
    cd "$INSTALL_DIR"
    LQOSYNC_INIT_POLICY=overwrite_with_backup LQOSYNC_INSTALL_MODE=baremetal bash install.sh
    ;;
esac

SUMMARY="$BACKUP_DIR/upgrade_summary.json"
cat > "$SUMMARY" <<JSON
{
  "started_at": "$TS",
  "policy": "$POLICY",
  "repo_url": "$REPO_URL",
  "branch": "$BRANCH",
  "old_commit": "$OLD_COMMIT",
  "new_commit": "$NEW_COMMIT",
  "install_dir": "$INSTALL_DIR",
  "backup_dir": "$BACKUP_DIR",
  "preserved_config": true,
  "preserved_users": true,
  "preserved_generated_files": true
}
JSON

if [ "$POLICY" != "pull_only" ]; then
  if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "Service is active after update."
  else
    log "WARNING: Service is not active after update. Check: journalctl -u $SERVICE_NAME -n 100 --no-pager"
    exit 1
  fi
fi

log "Upgrade complete. Summary: $SUMMARY"
