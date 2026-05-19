# Package Notes

## v2.76.0-rc1 - Rust Core v0.6 Circuit Shadow Normalizer

Adds the Rust `normalize-circuits` operation and Dry Run circuit shadow panel. This release remains fallback-safe and does not move live circuit building authority away from Python. It also removes the harmless v0.5 Rust unused-mut warning.

## v2.73.1-rc1 Package Notes

- Rust Core v0.3 build hotfix for the `csv` crate line terminator API.
- Replaces `csv::Terminator::LF` with `csv::Terminator::Any(b'\n')` so `scripts/build-rust-core.sh` can compile on the current `csv` crate.
- No sync/apply behavior changes.

## v2.73.0-rc1 Package Notes

- Adds Rust protocol operations for `validate-json-state`, `write-json-state`, `write-text-file`, and `append-audit-jsonl`.
- Hardens Python fallback atomic writes with parent-directory fsync where supported.
- Moves `runtime_state.json`, `policy_state.json`, `collector_cache.json`, and audit JSONL writes onto shared safe writer helpers.
- Keeps Rust-backed writes opt-in via `LQOSYNC_RUST_ATOMIC_WRITES=1`; Python fallback remains default.

# LQoSync Runtime Canonical Package

This package canonicalizes LQoSync naming across repository references, operator documentation, runtime service names, Docker container naming, logs, config defaults, and WebUI guidance.

## Canonical names

```text
GitHub repo:      https://github.com/p33ckab00/LQoSync.git
Install path:     /opt/lqosync
Systemd service:  lqosync
Docker container: lqosync
App log:          /opt/lqosync/logs/lqosync.log
System log:       /var/log/lqosync.log
Sudoers file:     /etc/sudoers.d/lqosync
```


## Canonical installation path note

All operator-facing install/update examples should use `/opt` as the base path. The canonical app checkout is:

```text
/opt/lqosync
```

Do not document user-home based project folders as active install locations. Legacy cleanup references, when needed, should point to `/opt/lqosync` or `/opt/lqos_docker`.

## Update safety

The installer/updater keeps production safety behavior:

- backs up `/opt/libreqos/src/config.json`
- backs up `/opt/libreqos/src/ShapedDevices.csv`
- backs up `/opt/libreqos/src/network.json`
- preserves users, `.env`, state, logs, and backups
- creates missing files only by default
- normalizes Git remote to `p33ckab00/LQoSync`
- installs and starts the canonical `lqosync` runtime service

## Migration safety

The only remaining old runtime name references are internal migration variables in the install/update scripts. They are needed to safely stop/disable/remove the previous runtime unit during upgrade so the old and new services do not run at the same time.

After installation/update, operators should use only:

```bash
sudo systemctl status lqosync
sudo journalctl -u lqosync -n 100 --no-pager
sudo systemctl restart lqosync
```


## Rust branch scaffold package

This package includes documentation and the first optional Rust core scaffold for the `lqosync-in-rust` branch. Runtime sync/apply remains Python-first, and Rust validation is non-blocking by default.

Included docs:

```text
docs/RUST_CORE_MIGRATION.md
docs/RUST_CORE_PROTOCOL.md
docs/COLLECTOR_OUTPUT_CONTRACT.md
docs/AUTOSAVE_AND_ATOMIC_STATE.md
docs/COMMIT_AND_PUSH_GUIDE.md
docs/assets/lqosync_rust_migration_plan.svg
```

Recommended branch:

```bash
git checkout -b lqosync-in-rust
```

Recommended commit for this scaffold package:

```bash
git commit -m "rust(core): scaffold optional LQoSync safety core"
```

## v2.71.0-rc1 Rust core scaffold package

This package adds the first optional Rust core implementation for the `lqosync-in-rust` branch.

Included implementation files:

```text
rust/lqosync-core/
engine/rust_core.py
scripts/build-rust-core.sh
scripts/install-rust-core.sh
```

The existing Python runtime remains primary. Rust validation is exposed as an optional sidecar and is non-blocking by default.
## 2.72.0-rc1 package note

This package advances the `lqosync-in-rust` branch to Rust Core v0.2. It adds collector output trust guarding and Rust diff operations while keeping Python as the primary runtime. No database is introduced. `/opt/lqosync` and `/opt/libreqos` remain the canonical paths.



## v2.74.0-rc1

Includes optional Rust core daemon service support. Daemon mode is disabled by default and must be enabled with `rust_core.prefer_daemon=true`.

## v2.75.0-rc1 Rust Policy Shadow

Adds Rust Core v0.5 policy shadow evaluation, Dry Run parity visibility, and a non-authoritative `evaluate-policy` protocol operation.

