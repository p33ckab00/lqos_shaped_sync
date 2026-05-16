#!/usr/bin/env bash
set -euo pipefail

# LQoSync GitHub source installer for bare-metal/systemd deployments.
# Does not require GitHub CLI (gh). It only needs plain git.
# Can safely handle fresh installs and existing installs from ZIP/manual/Git/Docker leftovers.

REPO_URL="${LQOSYNC_REPO_URL:-https://github.com/p33ckab00/lqos_shaped_sync.git}"
BRANCH="${LQOSYNC_BRANCH:-main}"
INSTALL_DIR="${LQOSYNC_INSTALL_DIR:-/opt/lqosync}"
SERVICE_NAME="${LQOSYNC_SERVICE_NAME:-lqos_shaped_sync}"
INIT_POLICY="${LQOSYNC_INIT_POLICY:-preserve_existing}"
LIBREQOS_SRC="${LIBREQOS_SRC:-/opt/libreqos/src}"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_ROOT="${LQOSYNC_BACKUP_ROOT:-/root/lqosync_git_install_backups}"
BACKUP_DIR="$BACKUP_ROOT/$TS"
EXISTING_INSTALL_ACTION="${EXISTING_INSTALL_ACTION:-auto}"

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "Run as root: sudo bash install-from-github.sh"
  exit 1
fi

log() { echo "[LQoSync Git Install] $*"; }
warn() { echo "[LQoSync Git Install] WARNING: $*"; }
fail() { echo "[LQoSync Git Install] ERROR: $*" >&2; exit 1; }

is_interactive() { [ -t 0 ] && [ -t 1 ]; }

install_packages() {
  apt-get update -qq
  apt-get install -y git rsync sudo acl python3 python3-venv python3-pip
}

is_git_managed() { [ -d "$INSTALL_DIR/.git" ]; }
existing_install_detected() {
  [ -e "$INSTALL_DIR" ] || \
  systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}.service" || \
  [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ] || \
  [ -f "/etc/sudoers.d/lqosync" ] || \
  [ -f "/etc/sudoers.d/lqos_shaped_sync" ]
}

backup_operator_files() {
  mkdir -p "$BACKUP_DIR"
  log "Creating safety backup: $BACKUP_DIR"

  # LQoSync operator-owned/runtime files.
  if [ -d "$INSTALL_DIR" ]; then
    cp -a "$INSTALL_DIR/users.json" "$BACKUP_DIR/users.json" 2>/dev/null || true
    cp -a "$INSTALL_DIR/.env" "$BACKUP_DIR/.env" 2>/dev/null || true
    cp -a "$INSTALL_DIR/state" "$BACKUP_DIR/state" 2>/dev/null || true
    cp -a "$INSTALL_DIR/logs" "$BACKUP_DIR/logs" 2>/dev/null || true
    cp -a "$INSTALL_DIR/backups" "$BACKUP_DIR/lqosync_backups" 2>/dev/null || true
  fi

  # Live LibreQoS files must never be destroyed by default.
  mkdir -p "$BACKUP_DIR/libreqos_src"
  cp -a "$LIBREQOS_SRC/config.json" "$BACKUP_DIR/libreqos_src/config.json" 2>/dev/null || true
  cp -a "$LIBREQOS_SRC/ShapedDevices.csv" "$BACKUP_DIR/libreqos_src/ShapedDevices.csv" 2>/dev/null || true
  cp -a "$LIBREQOS_SRC/network.json" "$BACKUP_DIR/libreqos_src/network.json" 2>/dev/null || true

  # Service/sudoers backup.
  cp -a "/etc/systemd/system/${SERVICE_NAME}.service" "$BACKUP_DIR/${SERVICE_NAME}.service" 2>/dev/null || true
  cp -a "/etc/sudoers.d/lqosync" "$BACKUP_DIR/sudoers.lqosync" 2>/dev/null || true
  cp -a "/etc/sudoers.d/lqos_shaped_sync" "$BACKUP_DIR/sudoers.lqos_shaped_sync" 2>/dev/null || true
}

restore_operator_files() {
  # Restore only local app runtime files. LibreQoS live files stay in /opt/libreqos/src and are not overwritten here.
  cp -a "$BACKUP_DIR/users.json" "$INSTALL_DIR/users.json" 2>/dev/null || true
  cp -a "$BACKUP_DIR/.env" "$INSTALL_DIR/.env" 2>/dev/null || true
  cp -a "$BACKUP_DIR/state" "$INSTALL_DIR/state" 2>/dev/null || true
  cp -a "$BACKUP_DIR/logs" "$INSTALL_DIR/logs" 2>/dev/null || true
  cp -a "$BACKUP_DIR/lqosync_backups" "$INSTALL_DIR/backups" 2>/dev/null || true
}

stop_service_if_present() {
  if systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}.service"; then
    log "Stopping existing $SERVICE_NAME service..."
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
  fi
}

clone_to_temp() {
  local tmp="/tmp/lqosync_git_clone_$TS"
  rm -rf "$tmp"
  git clone --branch "$BRANCH" "$REPO_URL" "$tmp"
  echo "$tmp"
}

pull_or_clone_source() {
  if is_git_managed; then
    log "Git-managed install detected. Pulling latest code..."
    git -C "$INSTALL_DIR" config --global --add safe.directory "$INSTALL_DIR" 2>/dev/null || true
    git -C "$INSTALL_DIR" fetch origin "$BRANCH"
    git -C "$INSTALL_DIR" checkout "$BRANCH"
    git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
  else
    local tmp
    tmp="$(clone_to_temp)"
    log "Converting existing install directory into Git-managed source while preserving runtime files."
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
      "$tmp/" "$INSTALL_DIR/"
    rm -rf "$tmp"
  fi
}

fresh_clone() {
  local tmp
  tmp="$(clone_to_temp)"
  mkdir -p "$(dirname "$INSTALL_DIR")"
  rm -rf "$INSTALL_DIR"
  mv "$tmp" "$INSTALL_DIR"
}

choose_action() {
  if ! existing_install_detected; then
    echo "fresh"
    return
  fi

  case "$EXISTING_INSTALL_ACTION" in
    adopt|code_only|repair|replace_app|remove_fresh|abort)
      echo "$EXISTING_INSTALL_ACTION"
      return
      ;;
    auto)
      if is_interactive; then
        echo "prompt"
      else
        echo "adopt"
      fi
      return
      ;;
    *)
      fail "Invalid EXISTING_INSTALL_ACTION=$EXISTING_INSTALL_ACTION. Allowed: auto, adopt, code_only, repair, replace_app, remove_fresh, abort"
      ;;
  esac
}

prompt_action() {
  echo
  echo "Existing LQoSync installation detected at or around: $INSTALL_DIR"
  echo
  echo "Choose action:"
  echo "  [1] Adopt and update existing install  (recommended)"
  echo "      Convert ZIP/manual installs to Git-managed source, preserve config/users/logs/state."
  echo "  [2] Update code only"
  echo "      Pull/replace app source and restart; avoid config migration."
  echo "  [3] Repair install, preserve all data"
  echo "      Recreate service/sudoers/permissions/migrations without replacing app source unless needed."
  echo "  [4] Backup and replace app files"
  echo "      Clean source refresh from GitHub; restore users/.env/state/logs."
  echo "  [5] Remove existing LQoSync then fresh install"
  echo "      Backup old install first; preserve LibreQoS live files by default."
  echo "  [6] Abort"
  echo
  read -r -p "Select [1-6]: " ans
  case "$ans" in
    1) echo "adopt" ;;
    2) echo "code_only" ;;
    3) echo "repair" ;;
    4) echo "replace_app" ;;
    5) echo "remove_fresh" ;;
    6) echo "abort" ;;
    *) fail "Invalid selection." ;;
  esac
}

run_install_preserve() {
  log "Running production-safe installer from Git source..."
  cd "$INSTALL_DIR"
  LQOSYNC_INIT_POLICY="$INIT_POLICY" LQOSYNC_INSTALL_MODE=baremetal bash install.sh
}

run_code_only() {
  log "Updating Python dependencies and restarting service without config migration."
  python3 -m venv "$INSTALL_DIR/venv"
  "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
  "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
  chown -R lqosync:lqosync "$INSTALL_DIR" 2>/dev/null || true
  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME" 2>/dev/null || true
  systemctl start "$SERVICE_NAME" 2>/dev/null || true
}

write_summary() {
  local action="$1"
  local status="$2"
  local summary="$BACKUP_DIR/install_summary.json"
  mkdir -p "$BACKUP_DIR"
  cat > "$summary" <<JSON
{
  "timestamp": "$TS",
  "action": "$action",
  "status": "$status",
  "repo_url": "$REPO_URL",
  "branch": "$BRANCH",
  "install_dir": "$INSTALL_DIR",
  "backup_dir": "$BACKUP_DIR",
  "preserved_config": true,
  "preserved_users": true,
  "preserved_generated_files": true,
  "preserved_logs": true,
  "preserved_state": true
}
JSON
  log "Summary: $summary"
}

log "Repository: $REPO_URL"
log "Branch:     $BRANCH"
log "Target:     $INSTALL_DIR"
log "Init policy:$INIT_POLICY"
log "Existing action request: $EXISTING_INSTALL_ACTION"

install_packages
mkdir -p "$BACKUP_ROOT" "$BACKUP_DIR"

action="$(choose_action)"
[ "$action" = "prompt" ] && action="$(prompt_action)"
log "Selected action: $action"

[ "$action" = "abort" ] && fail "Aborted by operator."

stop_service_if_present
backup_operator_files

case "$action" in
  fresh)
    log "No existing LQoSync install detected. Performing fresh GitHub install."
    fresh_clone
    run_install_preserve
    ;;

  adopt)
    log "Adopting/updating existing install while preserving operator data."
    pull_or_clone_source
    restore_operator_files
    run_install_preserve
    ;;

  code_only)
    log "Code-only update selected. Preserving config/users/generated files and skipping config migration."
    pull_or_clone_source
    restore_operator_files
    run_code_only
    ;;

  repair)
    log "Repair selected. Preserving source/data and reapplying install-time service, sudoers, ACL, and config migration."
    if [ ! -d "$INSTALL_DIR" ]; then
      warn "Install directory missing; cloning source first."
      fresh_clone
    fi
    run_install_preserve
    ;;

  replace_app)
    log "Replacing app source from GitHub while restoring operator runtime files."
    tmp="$(clone_to_temp)"
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
      "$tmp/" "$INSTALL_DIR/"
    rm -rf "$tmp"
    restore_operator_files
    run_install_preserve
    ;;

  remove_fresh)
    log "Remove/fresh selected. Moving old app directory aside; preserving LibreQoS live files by default."
    if [ -d "$INSTALL_DIR" ]; then
      mv "$INSTALL_DIR" "$BACKUP_DIR/old_lqosync_app"
    fi
    fresh_clone
    # Restore users/.env unless explicitly disabled; this keeps admin accounts intact even on fresh app source.
    if [ "${PRESERVE_USERS:-true}" = "true" ]; then
      cp -a "$BACKUP_DIR/old_lqosync_app/users.json" "$INSTALL_DIR/users.json" 2>/dev/null || true
    fi
    if [ "${PRESERVE_ENV:-true}" = "true" ]; then
      cp -a "$BACKUP_DIR/old_lqosync_app/.env" "$INSTALL_DIR/.env" 2>/dev/null || true
    fi
    run_install_preserve
    ;;

  *)
    fail "Unhandled action: $action"
    ;;
esac

if systemctl is-active --quiet "$SERVICE_NAME"; then
  log "$SERVICE_NAME is active."
else
  warn "$SERVICE_NAME is not active. Check: journalctl -u $SERVICE_NAME -n 100 --no-pager"
fi

write_summary "$action" "ok"
log "Install/update from GitHub complete. Backup: $BACKUP_DIR"
log "UI: http://$(hostname -I | awk '{print $1}'):9202"
