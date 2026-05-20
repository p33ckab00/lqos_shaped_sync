#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/app"
DATA_DIR="/opt/LQoSync"
LIBREQOS_SRC_DIR="/opt/libreqos/src"
CONFIG_PATH="${CONFIG_PATH:-$LIBREQOS_SRC_DIR/config.json}"
SHAPED_DEVICES_PATH="${SHAPED_DEVICES_PATH:-$LIBREQOS_SRC_DIR/ShapedDevices.csv}"
NETWORK_JSON_PATH="${NETWORK_JSON_PATH:-$LIBREQOS_SRC_DIR/network.json}"
INIT_POLICY="${LQOSYNC_INIT_POLICY:-smart_confirm}"
PORT="${PORT:-9202}"
HOST="${HOST:-0.0.0.0}"

case "$INIT_POLICY" in
  smart_confirm|overwrite_with_backup|preserve_existing|create_missing_only) ;;
  *)
    echo "[LQoSync Docker] Invalid LQOSYNC_INIT_POLICY=$INIT_POLICY"
    echo "Allowed: smart_confirm | overwrite_with_backup | preserve_existing | create_missing_only"
    exit 1
    ;;
esac

mkdir -p "$DATA_DIR/backups" "$DATA_DIR/logs" "$DATA_DIR/state" "$DATA_DIR/config_backups" "$DATA_DIR/install_backups" "$LIBREQOS_SRC_DIR"
INIT_MARKER="$DATA_DIR/state/docker_initialized"
FORCE_INIT="${LQOSYNC_FORCE_INIT:-false}"

TS="$(date +%Y%m%d_%H%M%S)"
INSTALL_BACKUP_DIR="$DATA_DIR/install_backups/$TS"
BACKUP_CREATED=0
FRESH_MANAGED_FILES=0

resolve_init_policy() {
  local existing_count=0
  local files=("$CONFIG_PATH" "$SHAPED_DEVICES_PATH" "$NETWORK_JSON_PATH")

  for f in "${files[@]}"; do
    if [ -f "$f" ]; then
      existing_count=$((existing_count + 1))
    fi
  done

  if [ "$INIT_POLICY" != "smart_confirm" ]; then
    echo "[LQoSync Docker] Explicit init policy selected: $INIT_POLICY"
    return 0
  fi

  if [ "$existing_count" -eq 0 ]; then
    INIT_POLICY="create_missing_only"
    FRESH_MANAGED_FILES=1
    echo "[LQoSync Docker] Fresh LibreQoS file set detected. Missing managed files will be created from templates."
  else
    INIT_POLICY="preserve_existing"
    echo "[LQoSync Docker] Existing LibreQoS-managed files detected. Preserving existing files by default."
    echo "[LQoSync Docker] To overwrite explicitly, set LQOSYNC_INIT_POLICY=overwrite_with_backup."
  fi

  echo "[LQoSync Docker] Final init policy: $INIT_POLICY"
}


print_mikrotik_setup_notice() {
  echo
  echo "[LQoSync Docker] IMPORTANT NOTICE: MikroTik API setup requirement"
  echo "[LQoSync Docker] Create a dedicated read-only RouterOS API user before enabling live sync:"
  echo "  /user group add name=API_READ policy=\"read,sensitive,api,!policy,!local,!telnet,!ssh,!ftp,!reboot,!write,!test,!winbox,!password,!web,!sniff,!romon\""
  echo "  /user add name=\"libreqosyncAPI\" group=API_READ password=\"<Strong Password>\" address=\"<LibreQoS IP Address>\" disabled=no"
  echo "[LQoSync Docker] Then update router username/password in /opt/libreqos/src/config.json or Config Center."
}

backup_existing() {
  local target="$1"
  if [ -f "$target" ]; then
    mkdir -p "$INSTALL_BACKUP_DIR"
    cp -a "$target" "$INSTALL_BACKUP_DIR/$(basename "$target")"
    BACKUP_CREATED=1
    echo "[LQoSync Docker] Backed up existing $target -> $INSTALL_BACKUP_DIR/$(basename "$target")"
  fi
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
        echo "[LQoSync Docker] Existing $label overwritten from template: $target"
        ;;
      preserve_existing|create_missing_only)
        echo "[LQoSync Docker] Existing $label preserved: $target"
        ;;
    esac
  else
    cp "$source" "$target"
    echo "[LQoSync Docker] Missing $label created: $target"
  fi
}

if [ ! -f "$INIT_MARKER" ] || [ "$FORCE_INIT" = "true" ]; then
  resolve_init_policy
  install_managed_file "$APP_DIR/config.json.example" "$CONFIG_PATH" "config.json"
  install_managed_file "$APP_DIR/ShapedDevices.csv.example" "$SHAPED_DEVICES_PATH" "ShapedDevices.csv"
  install_managed_file "$APP_DIR/network.json.example" "$NETWORK_JSON_PATH" "network.json"
  date -Is > "$INIT_MARKER"
else
  echo "[LQoSync Docker] Init already completed. Preserving existing managed files."
  echo "[LQoSync Docker] To re-run init policy, set LQOSYNC_FORCE_INIT=true."
fi

if [ ! -f "${USERS_PATH:-$DATA_DIR/users.json}" ]; then
  cp "$APP_DIR/users.json" "${USERS_PATH:-$DATA_DIR/users.json}" 2>/dev/null || true
fi

chmod 600 "$CONFIG_PATH" 2>/dev/null || true
chmod 664 "$SHAPED_DEVICES_PATH" "$NETWORK_JSON_PATH" 2>/dev/null || true
chmod 600 "${USERS_PATH:-$DATA_DIR/users.json}" 2>/dev/null || true

# Upgrade-time config migration. Even when existing managed files are preserved,
# new config defaults must be written into config.json so the UI and runner use
# the latest production-safe settings.
if CONFIG_PATH="$CONFIG_PATH" PYTHONPATH="$APP_DIR" LQOSYNC_INSTALL_MODE=docker python "$APP_DIR/scripts/migrate_config.py"; then
  echo "[LQoSync Docker] Existing config.json normalized with current defaults."
else
  echo "[LQoSync Docker] WARNING: config migration failed. Check permissions and JSON validity."
fi
chmod 600 "$CONFIG_PATH" 2>/dev/null || true
chmod 664 "$SHAPED_DEVICES_PATH" "$NETWORK_JSON_PATH" 2>/dev/null || true

if systemctl is-active --quiet updatecsv.service 2>/dev/null; then
  echo "[LQoSync Docker] WARNING: host updatecsv.service appears active. Disable it before enabling LQoSync scheduler."
  echo "sudo systemctl disable --now updatecsv.service"
fi

if [ "$BACKUP_CREATED" = "1" ]; then
  echo "[LQoSync Docker] Existing file backups saved in: $INSTALL_BACKUP_DIR"
fi
if [ "$FRESH_MANAGED_FILES" = "1" ]; then
  print_mikrotik_setup_notice
fi

echo "[LQoSync Docker] Starting LQoSync on $HOST:$PORT"
echo "[LQoSync Docker] CONFIG_PATH=$CONFIG_PATH"
echo "[LQoSync Docker] USERS_PATH=${USERS_PATH:-$DATA_DIR/users.json}"
echo "[LQoSync Docker] LQOSYNC_RUN_MODE=${LQOSYNC_RUN_MODE:-direct}"
echo "[LQoSync Docker] HOST_CONTROL_MODE=${HOST_CONTROL_MODE:-direct}"

exec gunicorn --workers "${GUNICORN_WORKERS:-1}" --threads "${GUNICORN_THREADS:-4}" --timeout "${GUNICORN_TIMEOUT:-300}" --bind "$HOST:$PORT" app:app
