# v7.5.5 Production-Safe Install Wrapper

Adds a conservative live-system install wrapper and optional service start policy controls.

## Added files

- `install-production-safe.sh`
- `docs/PRODUCTION_SAFE_INSTALL.md`
- `docs/RUST_CORE_V755_PRODUCTION_SAFE_INSTALL_WRAPPER.md`

## Installer behavior preserved

`install.sh` still defaults to historical behavior:

```bash
LQOSYNC_SERVICE_START_POLICY=restart
```

Existing automation that runs `sudo bash install.sh` continues to enable and restart `lqosync`.

## New install controls

`install.sh`, `install-from-github.sh`, and `upgrade.sh` now support:

```bash
LQOSYNC_SERVICE_START_POLICY=restart|enable_only|leave_stopped
```

The production wrapper defaults to:

```bash
LQOSYNC_INIT_POLICY=preserve_existing
LQOSYNC_SERVICE_START_POLICY=enable_only
```

This allows installation/update on a live LibreQoS host without immediately starting scheduler-capable runtime.

## Rust core remains opt-in

The wrapper does not build or install Rust core unless requested:

```bash
INSTALL_RUST_CORE=true
INSTALL_RUST_CORE_DAEMON=true
```

This avoids cargo/toolchain surprises on production machines.

## Safety intent

The change is intentionally additive and conservative:

- no WebUI/UX template changes;
- no collector/runtime logic changes;
- no default overwrite of live `config.json`, `ShapedDevices.csv`, or `network.json`;
- no mandatory Rust build step;
- existing `install.sh` default behavior is preserved.
