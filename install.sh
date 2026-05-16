#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/lqosync"
LIBREQOS_SRC_DIR="/opt/libreqos/src"
CONFIG_PATH="$LIBREQOS_SRC_DIR/config.json"
SHAPED_DEVICES_PATH="$LIBREQOS_SRC_DIR/ShapedDevices.csv"
NETWORK_JSON_PATH="$LIBREQOS_SRC_DIR/network.json"
SERVICE_NAME="lqos_shaped_sync"
USER_NAME="lqosync"
PORT="${PORT:-9202}"

# Smart default: fresh LibreQoS installs get missing files created automatically.
# If managed files already exist, interactive installs ask what to do; non-interactive
# installs preserve existing files unless an explicit policy is provided.
# Allowed: smart_confirm | overwrite_with_backup | preserve_existing | create_missing_only
INIT_POLICY="${LQOSYNC_INIT_POLICY:-smart_confirm}"

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "Run as root: sudo bash install.sh"
  exit 1
fi

case "$INIT_POLICY" in
  smart_confirm|overwrite_with_backup|preserve_existing|create_missing_only) ;;
  *)
    echo "[LQoSync] Invalid LQOSYNC_INIT_POLICY=$INIT_POLICY"
    echo "Allowed: smart_confirm | overwrite_with_backup | preserve_existing | create_missing_only"
    exit 1
    ;;
esac

TS="$(date +%Y%m%d_%H%M%S)"
INSTALL_BACKUP_DIR="$INSTALL_DIR/install_backups/$TS"
BACKUP_CREATED=0
FRESH_MANAGED_FILES=0

resolve_init_policy() {
  local existing_count=0
  local missing_count=0
  local files=("$CONFIG_PATH" "$SHAPED_DEVICES_PATH" "$NETWORK_JSON_PATH")

  for f in "${files[@]}"; do
    if [ -f "$f" ]; then
      existing_count=$((existing_count + 1))
    else
      missing_count=$((missing_count + 1))
    fi
  done

  if [ "$INIT_POLICY" != "smart_confirm" ]; then
    echo "[LQoSync] Explicit init policy selected: $INIT_POLICY"
    return 0
  fi

  if [ "$existing_count" -eq 0 ]; then
    INIT_POLICY="create_missing_only"
    FRESH_MANAGED_FILES=1
    echo "[LQoSync] Fresh LibreQoS file set detected: config.json, ShapedDevices.csv, and network.json are missing."
    echo "[LQoSync] Init policy auto-selected: create_missing_only"
    return 0
  fi

  echo "[LQoSync] Existing LibreQoS-managed files detected:"
  for f in "${files[@]}"; do
    if [ -f "$f" ]; then
      ls -lah "$f" || true
    else
      echo "  MISSING: $f"
    fi
  done

  if [ -t 0 ]; then
    echo
    echo "Choose how LQoSync should initialize managed files:"
    echo "  [P] Preserve existing files and create only missing files  (recommended for live systems)"
    echo "  [O] Backup and overwrite existing files from LQoSync templates"
    echo "  [M] Create missing files only; do not touch existing files"
    echo "  [A] Abort install"
    printf "Selection [P/o/m/a]: "
    read -r answer
    case "${answer:-P}" in
      P|p) INIT_POLICY="preserve_existing" ;;
      O|o) INIT_POLICY="overwrite_with_backup" ;;
      M|m) INIT_POLICY="create_missing_only" ;;
      A|a) echo "[LQoSync] Install aborted by operator."; exit 1 ;;
      *) echo "[LQoSync] Unknown selection. Defaulting to preserve_existing."; INIT_POLICY="preserve_existing" ;;
    esac
  else
    INIT_POLICY="preserve_existing"
    echo "[LQoSync] Non-interactive install detected. Existing files will be preserved."
    echo "[LQoSync] To overwrite explicitly, run: sudo LQOSYNC_INIT_POLICY=overwrite_with_backup bash install.sh"
  fi

  echo "[LQoSync] Final init policy: $INIT_POLICY"
}

backup_existing() {
  local target="$1"
  if [ -f "$target" ]; then
    mkdir -p "$INSTALL_BACKUP_DIR"
    cp -a "$target" "$INSTALL_BACKUP_DIR/$(basename "$target")"
    BACKUP_CREATED=1
    echo "[LQoSync] Backed up existing $target -> $INSTALL_BACKUP_DIR/$(basename "$target")"
  fi
}


print_mikrotik_setup_notice() {
  echo
  echo "[LQoSync] IMPORTANT NOTICE: MikroTik API setup requirement"
  echo "[LQoSync] Create a dedicated read-only RouterOS API user before enabling live sync:"
  echo "  /user group add name=API_READ policy=\"read,sensitive,api,!policy,!local,!telnet,!ssh,!ftp,!reboot,!write,!test,!winbox,!password,!web,!sniff,!romon\""
  echo "  /user add name=\"libreqosyncAPI\" group=API_READ password=\"<Strong Password>\" address=\"<LibreQoS IP Address>\" disabled=no"
  echo "[LQoSync] Then update router username/password in /opt/libreqos/src/config.json or Config Center."
}

install_managed_file() {
  local source="$1"
  local target="$2"
  local label="$3"

  mkdir -p "$(dirname "$target")"

  if [ -f "$target" ]; then
    backup_existing "$target"
    case "$INIT_POLICY" in
      overwrite_with_backup)
        cp "$source" "$target"
        echo "[LQoSync] Existing $label overwritten from LQoSync template: $target"
        ;;
      preserve_existing|create_missing_only)
        echo "[LQoSync] Existing $label preserved: $target"
        ;;
    esac
  else
    cp "$source" "$target"
    echo "[LQoSync] Missing $label created: $target"
  fi
}

resolve_init_policy

echo "[LQoSync] Installing..."
echo "[LQoSync] Init policy: $INIT_POLICY"
apt-get update -qq
apt-get install -y python3 python3-venv python3-pip git sudo rsync acl

if ! id "$USER_NAME" >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "$USER_NAME"
fi
# Allow non-root LQoSync to read systemd journal where supported.
if getent group systemd-journal >/dev/null 2>&1; then
  usermod -aG systemd-journal "$USER_NAME" || true
fi

mkdir -p "$INSTALL_DIR" "$LIBREQOS_SRC_DIR"
rsync -a --delete   --exclude 'venv'   --exclude '.git'   --exclude 'backups'   --exclude 'install_backups'   --exclude 'state/runtime_state.json'   ./ "$INSTALL_DIR/" 2>/dev/null || cp -r . "$INSTALL_DIR/"

# Initialize/own the LibreQoS-managed files. These are the files LQoSync controls.
install_managed_file "$INSTALL_DIR/config.json.example" "$CONFIG_PATH" "config.json"
install_managed_file "$INSTALL_DIR/ShapedDevices.csv.example" "$SHAPED_DEVICES_PATH" "ShapedDevices.csv"
install_managed_file "$INSTALL_DIR/network.json.example" "$NETWORK_JSON_PATH" "network.json"

python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

if [ ! -f "$INSTALL_DIR/.env" ]; then
  SECRET=$(python3 - <<'PY2'
import secrets; print(secrets.token_hex(32))
PY2
)
  cat > "$INSTALL_DIR/.env" <<ENVEOF
SECRET_KEY=$SECRET
PORT=$PORT
HOST=0.0.0.0
CONFIG_PATH=$CONFIG_PATH
USERS_PATH=$INSTALL_DIR/users.json
ENVEOF
fi

set_env_var() {
  local key="$1"
  local value="$2"
  touch "$INSTALL_DIR/.env"
  if grep -q "^${key}=" "$INSTALL_DIR/.env"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$INSTALL_DIR/.env"
  else
    printf '%s=%s\n' "$key" "$value" >> "$INSTALL_DIR/.env"
  fi
}

# Bare-metal/systemd install is the priority deployment mode. Always normalize
# the runtime environment so old Docker/nsenter values cannot survive upgrades.
set_env_var PORT "$PORT"
set_env_var HOST "0.0.0.0"
set_env_var CONFIG_PATH "$CONFIG_PATH"
set_env_var USERS_PATH "$INSTALL_DIR/users.json"
set_env_var LQOSYNC_INSTALL_MODE "baremetal"
set_env_var LQOSYNC_RUN_MODE "direct"
set_env_var HOST_CONTROL_MODE "direct"
set_env_var LQOSYNC_FORCE_DIRECT "true"
set_env_var LQOSYNC_USE_SUDO "true"
set_env_var LQOSYNC_LIBREQOS_WORKING_DIR "$LIBREQOS_SRC_DIR"

mkdir -p "$INSTALL_DIR/backups" "$INSTALL_DIR/logs" "$INSTALL_DIR/state" "$INSTALL_DIR/config_backups" "$INSTALL_DIR/install_backups"
touch /var/log/lqos_shaped_sync.log || true

# Permissions
chown -R "$USER_NAME:$USER_NAME" "$INSTALL_DIR"
chown "$USER_NAME:$USER_NAME" /var/log/lqos_shaped_sync.log || true
chown "$USER_NAME:$USER_NAME" "$CONFIG_PATH" "$SHAPED_DEVICES_PATH" "$NETWORK_JSON_PATH" || true
chmod 600 "$CONFIG_PATH" || true
chmod 664 "$SHAPED_DEVICES_PATH" "$NETWORK_JSON_PATH" || true
chmod 600 "$INSTALL_DIR/users.json" 2>/dev/null || true
chmod 700 "$INSTALL_DIR/backups" "$INSTALL_DIR/state" "$INSTALL_DIR/config_backups" "$INSTALL_DIR/install_backups" || true

# Grant LQoSync the exact permissions needed for atomic writes in /opt/libreqos/src.
# Atomic writes create <file>.tmp first, so the service user needs write access to
# both the managed files AND the parent directory. This prevents errors such as:
#   Permission denied: '/opt/libreqos/src/config.json.tmp'
if command -v setfacl >/dev/null 2>&1; then
  setfacl -m "u:$USER_NAME:rwx" "$LIBREQOS_SRC_DIR" || true
  setfacl -m "u:$USER_NAME:rw" "$CONFIG_PATH" || true
  setfacl -m "u:$USER_NAME:rw" "$SHAPED_DEVICES_PATH" || true
  setfacl -m "u:$USER_NAME:rw" "$NETWORK_JSON_PATH" || true
  setfacl -d -m "u:$USER_NAME:rwX" "$LIBREQOS_SRC_DIR" || true
  echo "[LQoSync] ACL permissions applied for $USER_NAME on $LIBREQOS_SRC_DIR"
else
  echo "[LQoSync] WARNING: setfacl not available. Install acl if atomic writes fail."
fi

# Permission smoke test for config.json.tmp creation used by Config Center and DHCP discovery.
if sudo -u "$USER_NAME" sh -c "touch '$LIBREQOS_SRC_DIR/.lqosync_acl_test' && rm -f '$LIBREQOS_SRC_DIR/.lqosync_acl_test'"; then
  echo "[LQoSync] Permission test passed: $USER_NAME can create temp files in $LIBREQOS_SRC_DIR"
else
  echo "[LQoSync] WARNING: $USER_NAME cannot create temp files in $LIBREQOS_SRC_DIR"
  echo "[LQoSync] Run: sudo setfacl -m u:$USER_NAME:rwx $LIBREQOS_SRC_DIR"
fi

# Upgrade-time config migration. This is important when preserve_existing is used:
# the installer must keep the operator's live config, but still add new safe
# defaults such as libreqos.working_dir and retry_if_last_apply_failed.
if sudo -u "$USER_NAME" env CONFIG_PATH="$CONFIG_PATH" PYTHONPATH="$INSTALL_DIR" LQOSYNC_INSTALL_MODE=baremetal LQOSYNC_FORCE_DIRECT=true LQOSYNC_RUN_MODE=direct HOST_CONTROL_MODE=direct LQOSYNC_LIBREQOS_WORKING_DIR="$LIBREQOS_SRC_DIR" "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/scripts/migrate_config.py"; then
  echo "[LQoSync] Existing config.json normalized with current defaults."
else
  echo "[LQoSync] WARNING: config migration failed. Check permissions and JSON validity."
fi

# Re-apply ownership and permissions after migration/atomic write.
chown "$USER_NAME:$USER_NAME" "$CONFIG_PATH" "$SHAPED_DEVICES_PATH" "$NETWORK_JSON_PATH" || true
chmod 600 "$CONFIG_PATH" || true
chmod 664 "$SHAPED_DEVICES_PATH" "$NETWORK_JSON_PATH" || true

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF2
[Unit]
Description=LQoSync Dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/gunicorn --workers 1 --threads 4 --timeout 300 --bind 0.0.0.0:$PORT app:app
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF2

SYSTEMCTL_BIN="$(command -v systemctl || echo /bin/systemctl)"
PYTHON_BIN="$(command -v python3 || echo /usr/bin/python3)"
cat > /etc/sudoers.d/lqos_shaped_sync <<EOF2
$USER_NAME ALL=(ALL) NOPASSWD: $PYTHON_BIN /opt/libreqos/src/LibreQoS.py --updateonly
$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_BIN restart lqosd
$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_BIN restart lqos_scheduler
$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_BIN restart lqos_node_manager
$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_BIN restart lqos_shaped_sync
$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_BIN restart lqosd lqos_scheduler
$USER_NAME ALL=(ALL) NOPASSWD: $SYSTEMCTL_BIN restart lqosd lqos_scheduler lqos_node_manager
EOF2
chmod 440 /etc/sudoers.d/lqos_shaped_sync

if systemctl is-active --quiet updatecsv.service; then
  echo "[LQoSync] WARNING: updatecsv.service is active. Disable it before enabling LQoSync scheduler:"
  echo "sudo systemctl disable --now updatecsv.service"
fi

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "[LQoSync] Installed: http://$(hostname -I | awk '{print $1}'):$PORT"
echo "[LQoSync] Default login: admin / adminpass"
echo "[LQoSync] Managed files:"
echo "  config:        $CONFIG_PATH"
echo "  shaped CSV:    $SHAPED_DEVICES_PATH"
echo "  network JSON:  $NETWORK_JSON_PATH"
if [ "$BACKUP_CREATED" = "1" ]; then
  echo "[LQoSync] Existing file backups saved in: $INSTALL_BACKUP_DIR"
fi
if [ "$FRESH_MANAGED_FILES" = "1" ]; then
  print_mikrotik_setup_notice
fi
