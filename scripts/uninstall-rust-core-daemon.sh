#!/usr/bin/env bash
set -euo pipefail
systemctl disable --now lqosync-core.service 2>/dev/null || true
rm -f /etc/systemd/system/lqosync-core.service
rm -f /run/lqosync-core.sock
systemctl daemon-reload
echo "Removed lqosync-core daemon service."
