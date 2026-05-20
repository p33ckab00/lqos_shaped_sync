#!/usr/bin/env bash
set -euo pipefail

# LQoSync stale codebase cleanup execution plan
# This script is read-only. It prints a concrete archive plan and preflight status.

echo "== LQoSync stale codebase cleanup execution plan =="
echo "timestamp=$(date -Is)"
echo "hostname=$(hostname)"
echo

canonical_app="/opt/LQoSync"
rust_bin="/usr/local/bin/lqosync-core"
rust_service="lqosync-core.service"
archive_root="${LQOSYNC_STALE_ARCHIVE_ROOT:-/opt/LQoSync-archive/$(date +%Y%m%d-%H%M%S)}"

candidate_paths=(
  "/home/pi/lqosync_docker"
  "/home/pi/lqosync"
  "/opt/lqosync"
)

inspect_paths=(
  "/opt/lqosync-website"
  "/opt/LQoSync-archive"
  "/opt/LQoSync.backup"
)

critical_paths=(
  "/opt/LQoSync"
  "/opt/libreqos"
  "/usr/local/bin/lqosync-core"
  "/etc/systemd/system/lqosync-core.service"
  "/run/lqosync-core.sock"
)

self_test_ok="unknown"
operation_count="unknown"
has_drift_monitor="unknown"
has_steady_state_guard="unknown"

if command -v "$rust_bin" >/dev/null 2>&1; then
  tmp=$(mktemp)
  if printf '{"version":"1","op":"self-test","payload":{}}' | "$rust_bin" > "$tmp" 2>/dev/null; then
    read -r self_test_ok operation_count has_drift_monitor has_steady_state_guard < <(python3 - "$tmp" <<'PY'
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    result = data.get("result", {})
    ops = set(result.get("operations") or [])
    print(
        str(bool(data.get("ok"))).lower(),
        result.get("operation_count", "unknown"),
        str("build-full-rust-backend-production-drift-monitor" in ops).lower(),
        str("build-full-rust-backend-steady-state-guard" in ops).lower(),
    )
except Exception:
    print("false unknown false false")
PY
)
  else
    self_test_ok="false"
    operation_count="unknown"
    has_drift_monitor="false"
    has_steady_state_guard="false"
  fi
  rm -f "$tmp"
else
  self_test_ok="false"
  operation_count="missing-binary"
  has_drift_monitor="false"
  has_steady_state_guard="false"
fi

cat <<REPORT
== Preconditions ==
canonical_app_exists=$([ -d "$canonical_app" ] && echo true || echo false)
rust_binary_exists=$([ -x "$rust_bin" ] && echo true || echo false)
rust_service_active=$(systemctl is-active "$rust_service" 2>/dev/null || echo unknown)
self_test_ok=$self_test_ok
operation_count=$operation_count
has_steady_state_guard=$has_steady_state_guard
has_production_drift_monitor=$has_drift_monitor
archive_root=$archive_root
REPORT

echo
echo "== Critical paths protected =="
for p in "${critical_paths[@]}"; do
  echo "protect|$p|$([ -e "$p" ] && echo exists || echo missing)"
done

echo
echo "== Archive candidates =="
for p in "${candidate_paths[@]}"; do
  if [ -e "$p" ]; then
    if [ -d "$p/.git" ]; then
      branch=$(cd "$p" && git branch --show-current 2>/dev/null || true)
      head=$(cd "$p" && git rev-parse --short HEAD 2>/dev/null || true)
      dirty=$(cd "$p" && git status --short 2>/dev/null | wc -l | tr -d ' ')
      echo "archive-candidate|$p|git_branch=$branch|git_head=$head|dirty_count=$dirty"
    else
      echo "archive-candidate|$p|not-a-git-working-tree"
    fi
  else
    echo "missing|$p|no action"
  fi
done

echo
echo "== Inspect only, not archived by executor =="
for p in "${inspect_paths[@]}"; do
  echo "inspect|$p|$([ -e "$p" ] && echo exists || echo missing)"
done

echo
echo "== Canonical install/cleanup guide =="
echo "docs/BRANCH_INSTALL_AND_CLEANUP_GUIDE.md"
echo
echo "== Execution command, after review =="
echo "export CONFIRM_STALE_CODEBASE_CLEANUP_EXECUTION=CONFIRM_STALE_CODEBASE_CLEANUP_EXECUTION"
echo "export LQOSYNC_CANONICAL_VERIFIED=1"
echo "export LQOSYNC_CORE_SELF_TEST_OK=1"
echo "sudo -E bash scripts/stale-codebase-cleanup-execute-guard.sh --execute"
