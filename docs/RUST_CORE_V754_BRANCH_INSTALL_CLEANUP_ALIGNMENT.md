# v7.5.4 Branch Installation + Cleanup Alignment Guide

This guide is the canonical operator flow for the `lqosync-in-rust` branch during the final Rust production series.

## Canonical locations

| Item | Canonical value |
|---|---|
| GitHub branch | `lqosync-in-rust` |
| Application source/runtime | `/opt/LQoSync` |
| Rust core binary | `/usr/local/bin/lqosync-core` |
| Rust core service | `lqosync-core.service` |
| Rust core socket | `/run/lqosync-core.sock` |
| LibreQoS source path | `/opt/libreqos/src` |
| Cleanup archive root | `/opt/LQoSync-archive/<timestamp>` |

Do not use `/home/pi/lqosync_docker` as the final production source path. That path is treated as a legacy working tree and may be archived after `/opt/LQoSync` is verified.

## Fresh install from the Rust branch

```bash
sudo apt update
sudo apt install -y git curl build-essential pkg-config libssl-dev unzip

# Rust toolchain, if not installed yet
curl https://sh.rustup.rs -sSf | sh -s -- -y
source "$HOME/.cargo/env"

# Preserve any old canonical install first
if [ -d /opt/LQoSync ]; then
  sudo mv /opt/LQoSync "/opt/LQoSync.backup.$(date +%Y%m%d-%H%M%S)"
fi

sudo git clone --branch lqosync-in-rust --single-branch \
  https://github.com/p33ckab00/LQoSync.git /opt/LQoSync
sudo chown -R root:root /opt/LQoSync
cd /opt/LQoSync

bash scripts/repair-script-permissions.sh
bash scripts/verify-installation-docs-alignment.sh
bash scripts/verify-branch-cleanup-installation-alignment.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

Expected current production-series indicators:

```text
cargo tests: pass
self-test ok: true
operation_count >= 83
build-full-rust-backend-steady-state-guard advertised
build-full-rust-backend-production-drift-monitor advertised
```

## Update existing `/opt/LQoSync` from branch

```bash
cd /opt/LQoSync
sudo git fetch origin
sudo git checkout lqosync-in-rust
sudo git pull --ff-only origin lqosync-in-rust

bash scripts/repair-script-permissions.sh
bash scripts/verify-installation-docs-alignment.sh
bash scripts/verify-branch-cleanup-installation-alignment.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

## Cleanup flow after `/opt/LQoSync` is verified

Run inventory and dry-run first:

```bash
cd /opt/LQoSync
bash scripts/stale-codebase-inventory.sh
bash scripts/stale-codebase-cleanup-dry-run.sh
bash scripts/stale-codebase-cleanup-execution-plan.sh
```

Archive old duplicate working trees only after reviewing the plan:

```bash
export CONFIRM_STALE_CODEBASE_CLEANUP_EXECUTION=CONFIRM_STALE_CODEBASE_CLEANUP_EXECUTION
export LQOSYNC_CANONICAL_VERIFIED=1
export LQOSYNC_CORE_SELF_TEST_OK=1
sudo -E bash scripts/stale-codebase-cleanup-execute-guard.sh --execute
```

Verify after cleanup:

```bash
bash scripts/stale-codebase-post-cleanup-verify.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

## What cleanup may archive

Only these duplicate/legacy working trees are eligible for guarded archive:

```text
/home/pi/lqosync_docker
/home/pi/lqosync
/opt/lqosync
```

## What cleanup must never archive

```text
/opt/LQoSync
/opt/libreqos
/usr/local/bin/lqosync-core
/etc/systemd/system/lqosync-core.service
/run/lqosync-core.sock
/opt/lqosync-website
```

`/opt/lqosync-website` is inspect-only because it may be a separate public/showcase website service. Do not treat it as the Rust backend source tree.

## Restore from archive

```bash
export CONFIRM_STALE_CODEBASE_RESTORE=CONFIRM_STALE_CODEBASE_RESTORE
sudo -E bash scripts/stale-codebase-restore-from-archive.sh \
  /opt/LQoSync-archive/<timestamp> \
  lqosync_docker \
  /home/pi/lqosync_docker
```

## Production rule

If `bash scripts/build-rust-core.sh` fails, do not install. Keep the currently active daemon and fix the source first.
