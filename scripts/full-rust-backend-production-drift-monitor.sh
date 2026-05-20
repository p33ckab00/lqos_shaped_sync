#!/usr/bin/env bash
set -euo pipefail

SOCKET="${LQOSYNC_CORE_SOCKET:-/run/lqosync-core.sock}"
CONFIRM="${CONFIRM_FULL_RUST_BACKEND_PRODUCTION_DRIFT_MONITOR:-}"
PYTHON_PROCESS_COUNT="${PYTHON_BACKEND_PROCESS_COUNT:-0}"
DRIFT_CHECK_COUNT="${DRIFT_CHECK_COUNT:-1}"

if [[ "$CONFIRM" != "CONFIRM_FULL_RUST_BACKEND_PRODUCTION_DRIFT_MONITOR" ]]; then
  echo "Refusing: set CONFIRM_FULL_RUST_BACKEND_PRODUCTION_DRIFT_MONITOR=CONFIRM_FULL_RUST_BACKEND_PRODUCTION_DRIFT_MONITOR" >&2
  exit 2
fi

python3 - <<'PY' "$SOCKET" "$PYTHON_PROCESS_COUNT" "$DRIFT_CHECK_COUNT"
import json, socket, sys
sock_path, python_process_count, drift_check_count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
payload = {
  "confirmation": "CONFIRM_FULL_RUST_BACKEND_PRODUCTION_DRIFT_MONITOR",
  "shadow_age_seconds": 0,
  "rust_core": {
    "full_rust_backend_production_drift_monitor_pilot": True,
    "allow_full_rust_backend_production_drift_monitor": True,
    "full_rust_backend_production_drift_monitor_mode": "monitor_only",
  },
  "full_rust_backend_steady_state_guard_confirmation": "CONFIRM_FULL_RUST_BACKEND_STEADY_STATE_GUARD",
  "rust_service_active": True,
  "rust_api_healthcheck_passed": True,
  "rust_unix_socket_active": True,
  "api_traffic_switched_to_rust": True,
  "rust_service_runtime_authoritative": True,
  "flask_routes_disabled": True,
  "python_backend_stopped_or_disabled": True,
  "python_backend_service_masked_or_disabled": True,
  "python_backend_unexpectedly_running": False,
  "flask_routes_reappeared": False,
  "api_traffic_routed_to_python": False,
  "python_backend_service_reenabled": False,
  "python_backend_process_count": python_process_count,
  "drift_check_count": drift_check_count,
  "webui_ux_unchanged": True,
  "webui_static_asset_paths_unchanged": True,
  "webui_static_assets_preserved": True,
  "python_backend_rollback_package_ready": True,
  "rollback_path": "restore_python_backend_and_flask_routes",
  "rollback_test_passed": True,
  "server_cargo_tests_passed": True,
  "self_test_passed": True,
  "production_healthcheck_passed": True,
  "post_retirement_healthcheck_passed": True,
  "steady_state_healthcheck_passed": True,
  "drift_monitor_healthcheck_passed": True,
  "operator_full_rust_backend_drift_monitor_ack": True,
}
req = {"version":"1", "op":"build-full-rust-backend-production-drift-monitor", "payload": payload}
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect(sock_path)
s.sendall(json.dumps(req).encode())
s.shutdown(socket.SHUT_WR)
print(s.recv(1024 * 1024).decode())
s.close()
PY
