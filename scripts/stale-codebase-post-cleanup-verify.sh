#!/usr/bin/env bash
set -euo pipefail

echo "== LQoSync stale codebase post-cleanup verification =="
echo "timestamp=$(date -Is)"
echo

fail=0

check_ok() {
  local name="$1" cmd="$2"
  if bash -c "$cmd"; then
    echo "ok|$name"
  else
    echo "fail|$name"
    fail=1
  fi
}

check_ok "canonical_path_exists" "test -d /opt/LQoSync"
check_ok "rust_binary_exists" "test -x /usr/local/bin/lqosync-core"
check_ok "rust_service_active" "systemctl is-active --quiet lqosync-core.service"

if command -v lqosync-core >/dev/null 2>&1; then
  tmp=$(mktemp)
  if printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core > "$tmp" 2>/dev/null; then
    python3 - "$tmp" <<'PY'
import json, sys
data=json.load(open(sys.argv[1]))
ops=set((data.get('result') or {}).get('operations') or [])
print('self_test_ok=', data.get('ok'))
print('operation_count=', (data.get('result') or {}).get('operation_count'))
print('has_steady_state_guard=', 'build-full-rust-backend-steady-state-guard' in ops)
print('has_drift_monitor=', 'build-full-rust-backend-production-drift-monitor' in ops)
PY
  else
    echo "fail|self_test_command"
    fail=1
  fi
  rm -f "$tmp"
else
  echo "fail|lqosync-core command missing"
  fail=1
fi


if [ -d /opt/LQoSync/.git ]; then
  echo
  echo "== Canonical git source =="
  echo "branch=$(cd /opt/LQoSync && git branch --show-current 2>/dev/null || true)"
  echo "head=$(cd /opt/LQoSync && git rev-parse --short HEAD 2>/dev/null || true)"
fi

echo
echo "== Candidate path status =="
for p in /home/pi/lqosync_docker /home/pi/lqosync /opt/lqosync; do
  if [ -e "$p" ]; then
    echo "still-present|$p|review manually"
  else
    echo "absent|$p|ok if archived intentionally"
  fi
done

echo
echo "== Archives =="
find /opt/LQoSync-archive -maxdepth 2 -type f -name 'cleanup-manifest.tsv' -print 2>/dev/null || true

exit "$fail"
