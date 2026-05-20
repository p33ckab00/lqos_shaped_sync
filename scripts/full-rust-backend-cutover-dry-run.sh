#!/usr/bin/env bash
set -euo pipefail
TOKEN="${1:-}"
if [[ "$TOKEN" != "CONFIRM_FULL_RUST_BACKEND_PRODUCTION_CUTOVER" ]]; then
  echo "Refusing: pass CONFIRM_FULL_RUST_BACKEND_PRODUCTION_CUTOVER as first argument." >&2
  exit 2
fi
printf '%s
' "Dry-run only: validate Rust backend service, WebUI static assets, rollback backup, and API parity before any service switch."
printf '%s
' "No Python service is stopped by this dry-run script."
