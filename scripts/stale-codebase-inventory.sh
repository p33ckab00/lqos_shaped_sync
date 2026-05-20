#!/usr/bin/env bash
set -u

echo "== LQoSync stale codebase inventory =="
echo "timestamp=$(date -Is)"
echo "hostname=$(hostname)"
echo

echo "== Canonical expectations =="
echo "canonical_app=/opt/LQoSync"
echo "canonical_branch=lqosync-in-rust"
echo "rust_binary=/usr/local/bin/lqosync-core"
echo "rust_service=lqosync-core.service"
echo "rust_socket=/run/lqosync-core.sock"
echo

echo "== Running related services =="
systemctl list-units --type=service --state=running 2>/dev/null | grep -Ei 'lqos|lqosync|libreqos|python|flask|gunicorn|uvicorn|rust|nginx|docker|compose|supervisor' || true
echo

echo "== Related unit files =="
systemctl list-unit-files 2>/dev/null | grep -Ei 'lqos|lqosync|libreqos|python|flask|gunicorn|uvicorn|rust|nginx|docker|compose|supervisor' || true
echo

echo "== lqosync-core status =="
systemctl status lqosync-core.service --no-pager 2>/dev/null || true
echo

echo "== Related processes =="
ps auxww | grep -Ei 'lqos|lqosync|libreqos|python|flask|gunicorn|uvicorn|rust|lqosync-core|app.py|run_cycle' | grep -v grep || true
echo

echo "== Listening ports =="
if command -v ss >/dev/null 2>&1; then
  ss -ltnp 2>/dev/null | grep -Ei 'python|flask|gunicorn|uvicorn|nginx|lqosync|lqosync-core|docker|:80|:443|:5000|:8000|:8080|:8088|:9202|:9123' || true
fi
echo

echo "== Docker containers =="
if command -v docker >/dev/null 2>&1; then
  docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' | grep -Ei 'lqos|lqosync|libreqos|python|flask|nginx|rust|dockhand' || true
else
  echo "docker not installed"
fi
echo

echo "== Timers and crons =="
systemctl list-timers --all 2>/dev/null | grep -Ei 'lqos|lqosync|libreqos|python|sync' || true
crontab -l 2>/dev/null | grep -Ei 'lqos|lqosync|libreqos|python|sync' || true
sudo crontab -l 2>/dev/null | grep -Ei 'lqos|lqosync|libreqos|python|sync' || true
echo

echo "== Candidate directories =="
for p in /opt/LQoSync /opt/lqosync /home/pi/lqosync_docker /home/pi/lqosync /opt/lqosync-website /opt/libreqos; do
  if [ -e "$p" ]; then
    printf 'exists: %s\n' "$p"
    if [ -d "$p/.git" ]; then
      (cd "$p" && printf '  git_branch=' && git branch --show-current 2>/dev/null || true)
      (cd "$p" && printf '  git_head=' && git rev-parse --short HEAD 2>/dev/null || true)
      (cd "$p" && printf '  git_status=' && git status --short 2>/dev/null | wc -l)
    fi
  else
    printf 'missing: %s\n' "$p"
  fi
done
echo

echo "== Rust core self-test summary =="
if command -v lqosync-core >/dev/null 2>&1; then
  tmp=$(mktemp)
  if printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core > "$tmp" 2>/dev/null; then
    python3 - "$tmp" <<'PY'
import json,sys
try:
    data=json.load(open(sys.argv[1]))
    result=data.get('result',{})
    print('ok=', data.get('ok'))
    print('operation_count=', result.get('operation_count'))
    ops=result.get('operations') or []
    for op in ['build-full-rust-backend-production-drift-monitor','build-full-rust-backend-production-audit-sentinel','build-full-rust-backend-steady-state-guard']:
        print(f'{op}=', op in ops)
except Exception as e:
    print('unable to parse self-test:', e)
PY
  else
    echo "self-test command failed"
  fi
  rm -f "$tmp"
else
  echo "lqosync-core not found"
fi
