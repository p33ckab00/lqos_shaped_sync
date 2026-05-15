#!/usr/bin/env bash
set -euo pipefail

LQOSYNC_DIR="${LQOSYNC_DIR:-/opt/lqosync}"
CONFIG_PATH="${CONFIG_PATH:-/opt/libreqos/src/config.json}"

echo "LQoSync Environment Doctor"
echo "========================="
echo "LQoSync dir : ${LQOSYNC_DIR}"
echo "Config path : ${CONFIG_PATH}"
echo

if [[ ! -d "${LQOSYNC_DIR}" ]]; then
  echo "[FAIL] LQoSync directory not found: ${LQOSYNC_DIR}"
  exit 1
fi

cd "${LQOSYNC_DIR}"

echo "== Package integrity =="
python3 scripts/release_check.py || RELEASE_STATUS=$?
RELEASE_STATUS=${RELEASE_STATUS:-0}
echo

echo "== Regression suite =="
if [[ -x scripts/regression_check.py || -f scripts/regression_check.py ]]; then
  python3 scripts/regression_check.py || REGRESSION_STATUS=$?
else
  echo "[WARN] scripts/regression_check.py not found; skipping."
  REGRESSION_STATUS=0
fi
REGRESSION_STATUS=${REGRESSION_STATUS:-0}
echo

echo "== Config migration regression =="
if [[ -x scripts/config_migration_check.py || -f scripts/config_migration_check.py ]]; then
  python3 scripts/config_migration_check.py || MIGRATION_STATUS=$?
else
  echo "[WARN] scripts/config_migration_check.py not found; skipping."
  MIGRATION_STATUS=0
fi
MIGRATION_STATUS=${MIGRATION_STATUS:-0}
echo

echo "== Environment / config doctor =="
CONFIG_PATH="${CONFIG_PATH}" python3 scripts/doctor.py "${CONFIG_PATH}" "$@" || DOCTOR_STATUS=$?
DOCTOR_STATUS=${DOCTOR_STATUS:-0}
echo

if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
  echo "== Service status =="
  systemctl status lqos_shaped_sync --no-pager || true
else
  echo "== Service status =="
  echo "[INFO] systemd is not available in this environment; skipping service status."
fi

if [[ "${RELEASE_STATUS}" -ne 0 || "${REGRESSION_STATUS:-0}" -ne 0 || "${MIGRATION_STATUS:-0}" -ne 0 || "${DOCTOR_STATUS}" -ne 0 ]]; then
  echo
  echo "Doctor completed with issues. Review FAIL/WARN lines above."
  exit 1
fi

echo

echo "Doctor completed successfully."
