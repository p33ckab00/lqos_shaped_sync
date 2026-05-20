# Production-Safe Install Wrapper

This package includes `install-production-safe.sh` for live LibreQoS machines where the operator wants the safest install/update path.

The wrapper is additive. It does not replace `install.sh`, `install-from-github.sh`, or `upgrade.sh`.

## Default behavior

```bash
sudo bash install-production-safe.sh
```

Default safety behavior:

- backs up live LibreQoS files before installer actions:
  - `/opt/libreqos/src/config.json`
  - `/opt/libreqos/src/ShapedDevices.csv`
  - `/opt/libreqos/src/network.json`
- preserves existing live LibreQoS files using `LQOSYNC_INIT_POLICY=preserve_existing`;
- runs non-mutating package prechecks before install;
- installs and enables the `lqosync` systemd unit but does not start/restart it by default;
- skips Rust core build/install unless explicitly requested;
- writes a timestamped install summary under `/root/lqosync_production_install_backups/<timestamp>/`.

## Why the service is not started by default

A live machine may already have `scheduler.enabled=true` in its preserved config. Starting the dashboard service can also start scheduler-capable runtime. The production-safe wrapper therefore defaults to:

```bash
LQOSYNC_SERVICE_START_POLICY=enable_only
```

After reviewing config and running a dry-run, start manually:

```bash
sudo systemctl start lqosync
sudo systemctl status lqosync --no-pager
```

## Service start policy options

The underlying `install.sh` now supports:

| Policy | Effect |
|---|---|
| `restart` | Historical behavior: enable and restart `lqosync`. |
| `enable_only` | Enable the unit but do not start/restart it. Production-safe wrapper default. |
| `leave_stopped` | Stop and disable the unit after install. Useful for offline staging. |

Examples:

```bash
sudo LQOSYNC_SERVICE_START_POLICY=restart bash install-production-safe.sh
sudo LQOSYNC_SERVICE_START_POLICY=leave_stopped bash install-production-safe.sh
```

## Optional Rust core install

Rust core install remains opt-in:

```bash
sudo INSTALL_RUST_CORE=true bash install-production-safe.sh
```

Install the Rust daemon too:

```bash
sudo INSTALL_RUST_CORE=true INSTALL_RUST_CORE_DAEMON=true bash install-production-safe.sh
```

If `cargo` is not installed, the wrapper warns and continues by default. To fail hard when Rust is requested but unavailable:

```bash
sudo INSTALL_RUST_CORE=true STRICT_RUST=true bash install-production-safe.sh
```

## Custom paths

The wrapper and `install.sh` support path overrides while preserving old defaults:

```bash
sudo LQOSYNC_INSTALL_DIR=/opt/LQoSync \
     LIBREQOS_SRC=/opt/libreqos/src \
     bash install-production-safe.sh
```

## Recommended live flow

```bash
cd /path/to/LQoSync
sudo bash install-production-safe.sh

# review generated backups and config
sudo ls -lah /root/lqosync_production_install_backups
sudo python3 /opt/LQoSync/scripts/doctor.py /opt/libreqos/src/config.json

# run a Dry Run from the UI before enabling scheduler/live apply
sudo systemctl start lqosync
sudo journalctl -u lqosync -n 100 --no-pager
```

## What this does not do

The wrapper does not automatically enable scheduler, does not overwrite existing live LibreQoS files by default, and does not build/install Rust core unless requested.
