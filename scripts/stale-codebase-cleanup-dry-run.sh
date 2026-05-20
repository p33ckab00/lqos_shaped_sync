#!/usr/bin/env bash
set -u

echo "== LQoSync stale codebase cleanup dry run =="
echo "No changes will be made."
echo

archive_root="/opt/LQoSync-archive/$(date +%Y%m%d-%H%M%S)"
echo "proposed_archive_root=$archive_root"
echo

classify_path() {
  local p="$1"
  if [ ! -e "$p" ]; then
    echo "missing|$p|no action"
    return
  fi
  case "$p" in
    /opt/LQoSync)
      echo "keep|$p|canonical app path"
      ;;
    /opt/libreqos|/opt/libreqos/*)
      echo "never-delete|$p|LibreQoS path"
      ;;
    /usr/local/bin/lqosync-core)
      echo "keep|$p|active Rust core binary"
      ;;
    /home/pi/lqosync_docker|/home/pi/lqosync|/opt/lqosync)
      echo "archive-candidate|$p|duplicate or legacy working tree; archive only after /opt/LQoSync is verified"
      ;;
    /opt/lqosync-website)
      echo "inspect|$p|separate website/service; do not archive unless intentionally retired"
      ;;
    *)
      echo "inspect|$p|unknown related path"
      ;;
  esac
}

echo "== Path classification =="
for p in /opt/LQoSync /opt/lqosync /home/pi/lqosync_docker /home/pi/lqosync /opt/lqosync-website /opt/libreqos /usr/local/bin/lqosync-core; do
  classify_path "$p"
done

echo
echo "== Service classification =="
for svc in lqosync-core.service lqosync-website.service nginx.service docker.service; do
  if systemctl list-unit-files "$svc" >/dev/null 2>&1; then
    state=$(systemctl is-enabled "$svc" 2>/dev/null || true)
    active=$(systemctl is-active "$svc" 2>/dev/null || true)
    case "$svc" in
      lqosync-core.service) note="keep: Rust daemon" ;;
      lqosync-website.service) note="inspect: separate Python/Django website, not necessarily stale" ;;
      nginx.service) note="keep/inspect: reverse proxy may serve WebUI" ;;
      docker.service) note="keep/inspect: may host Dockhand or sync containers" ;;
    esac
    echo "$svc|enabled=$state|active=$active|$note"
  fi
done

echo
echo "== Archive command preview =="
echo "# Review before running. This is NOT executed here."
for p in /home/pi/lqosync_docker /home/pi/lqosync /opt/lqosync; do
  if [ -e "$p" ]; then
    base=$(basename "$p")
    echo "mkdir -p '$archive_root' && mv '$p' '$archive_root/$base'"
  fi
done

echo
echo "To execute guarded archive only after review:"
echo "export CONFIRM_STALE_CODEBASE_ARCHIVE=CONFIRM_STALE_CODEBASE_ARCHIVE"
echo "sudo -E bash scripts/stale-codebase-archive-executor-guard.sh --execute"
