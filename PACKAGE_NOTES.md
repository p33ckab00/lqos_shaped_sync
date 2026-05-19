## v2.100.0-rc1 Package Notes - Rust Core v3.0 RouterOS Authentication Plan

This package adds the RouterOS auth-plan bridge with safe defaults: no password emission, no authentication attempts, no socket use, and no collector authority migration.

## v2.99.0-rc1 Package Notes - Rust Core v2.9 RouterOS TCP Connectivity Pilot

This package adds the `run-routeros-tcp-connectivity-pilot` operation and `/api/rust-core/routeros-tcp-connectivity-pilot` endpoint.

The feature is disabled by default. It is intended to test TCP reachability only when explicitly enabled. It does not authenticate, send RouterOS API words, read replies, or replace the Python collectors.

## v2.92.1-rc1 Package Notes — RouterOS Transport Redaction Test Hotfix
## v2.95.1-rc1 - Rust Core v2.5.1 RouterOS API Codec Redaction Hotfix

- Fixes the RouterOS API sentence codec test that failed when the result metadata exposed dropped sensitive field names such as `api-key`.
- Keeps `/ppp/secret` as a valid RouterOS resource path while preventing actual sensitive `.proplist` field names from being emitted in the result payload.
- Replaces explicit dropped sensitive field names with `dropped_sensitive_field_count` and `dropped_sensitive_fields_redacted=true`.
- Removes an unused helper from `routeros_api_codec.rs` so the Rust build stays warning-clean.


- Fixes a false-positive Rust test failure in `routeros_transport.rs`.
- The failed assertion checked for the word `secret`, but the JSON output legitimately includes RouterOS resource paths such as `/ppp/secret`.
- The test now checks for the exact password value and the raw `password` key instead.
- Runtime behavior is unchanged; transport remains non-network and rehearsal-only.

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

## v2.77.0-rc1 Rust Core v0.7 Sync Plan Shadow

Adds `evaluate-sync-plan`, Dry Run sync-plan visibility, and documentation. Python remains authoritative.


## v2.78.0-rc1 - Rust Core v0.8 Authority Gates

- Added opt-in `rust_core.enforce_sync_plan` authority gate.
- Added `rust_core.authority_mode` with `shadow` and `enforce_blockers`.
- Added fail-closed behavior when enforced Rust core is unavailable.
- Dry Run remains preview-only; Python remains default authority unless enforcement is enabled.
- Added documentation: `docs/RUST_CORE_V08_AUTHORITY_GATES.md`.


## v2.79.0-rc1 Package Notes

Rust core advances to v0.9.0 with a transaction-style apply manifest preview. No generated file write/apply behavior is moved to Rust in this package.


## Rust Core v1.0 Apply Transaction Executor

This package adds the optional `execute-apply-transaction` Rust operation. It rehearses transactions by default and only writes files when explicit Rust transaction flags are enabled. Python remains authoritative for normal production sync/apply behavior.



## v2.81.1-rc1 Package Notes

This package fixes the Rust Core v1.1 self-test build failure and hardens Rust binary/daemon install behavior. The self-test no-change manifest check now uses apply mode, the build helper removes stale release binaries before tests/builds, and the daemon installer restarts an active service after binary updates.

Read: `docs/RUST_CORE_V11_SELF_TEST.md`.

## v2.81.0-rc1 Package Notes

This package adds a safe Rust core `self-test` operation and `/api/rust-core/self-test` endpoint. It also routes `execute-apply-transaction` through the CLI/daemon protocol and centralizes advertised Rust operations so future operation-list mismatches are easier to catch before enabling authority flags.

Read: `docs/RUST_CORE_V11_SELF_TEST.md`.

## v2.82.0-rc1 Package Notes

Adds Rust Core v1.2 transaction journal and rollback manifest previews. This is documentation/diagnostic/safety plumbing only; Python remains authoritative and no new Rust write/apply authority is enabled by default.

## v2.83.0-rc1 package notes

Adds Rust Core v1.3 transaction journal persistence preview/write path. Defaults remain non-mutating unless transaction journal write flags are explicitly enabled.


## Rust Core v1.4 Transaction History and Rollback Plan Viewer

This package adds read-only Rust operations `read-transaction-journal` and `build-rollback-from-journal`, plus WebUI API endpoints for transaction history and rollback plan preview. Rollback execution remains unsupported/disabled.


## Rust Core v1.5 Rollback Execution Rehearsal

This package adds `execute-rollback`, a gated rollback executor. It rehearses rollback by default and only restores files when rollback authority, file-write permission, and `CONFIRM_ROLLBACK` confirmation are explicitly provided. Python remains authoritative by default.


## v2.86.0-rc1 Package Notes

- Adds `evaluate-authority-readiness` to score whether Rust authority flags are safe to pilot.
- Adds `/api/rust-core/authority-readiness` for read-only operator visibility.
- Keeps Python authoritative by default and treats partial authority flags as blockers.
- Documents readiness verdicts before sync-plan enforcement, file-write authority, journal persistence, or rollback authority are enabled.


## v2.87.0-rc1 Package Notes

Adds Rust Core v1.7 full backend readiness and authority pilot plan operations. No default live behavior changes; all new endpoints are read-only.

## v2.88.0-rc1 Package Notes

Includes Rust Core v1.8 collector-bundle shadow builder and documentation. No default production write/apply behavior changes.


## Rust Core v1.9 Collector Bundle Parity Report

Adds `compare-collector-bundle-parity`, a diagnostic operation and API endpoint for comparing Python-authoritative rows with Rust-shadow collector bundle rows before any collector authority migration.


## Rust Core v2.0 RouterOS Collector Plan

This package adds `build-routeros-collector-plan`, a read-only Rust operation that derives the RouterOS resource/field plan for enabled PPPoE, DHCP, and Hotspot sources. It does not connect to MikroTik and does not replace Python collectors. It is a bridge toward a future Rust RouterOS transport while keeping Python authoritative by default.

New API:

```text
GET /api/rust-core/routeros-collector-plan
POST /api/rust-core/routeros-collector-plan
```


## v2.90.1-rc1 package note

Packaging hotfix for script executable-bit loss during ZIP/manual deployment. Use `bash scripts/repair-script-permissions.sh` or call helpers through `bash`.


## Rust Core v2.1 RouterOS Read Result Contract

This package adds `validate-routeros-read-results`, a Rust trust contract that validates Python-executed RouterOS read results against the deterministic collector plan. It is diagnostic by default and does not replace Python live RouterOS collectors.


## Rust Core v2.2 RouterOS Transport Session Rehearsal

Adds `build-routeros-transport-session`, a non-network RouterOS transport rehearsal that redacts credentials, reports planned sessions, blocks live Rust RouterOS transport attempts, and keeps Python live collectors authoritative.


## Rust Core v2.3 RouterOS Live Read Pilot Gate

LQoSync 2.93.0-rc1 / lqosync-core 2.3.0 adds `build-routeros-live-read-pilot`, a gated non-network contract for a future read-only Rust RouterOS transport adapter. Python collectors remain authoritative and Rust still does not open MikroTik sockets.


## Rust Core v2.4 RouterOS Read Pilot Fixture Adapter

Adds `run-routeros-read-pilot`, an offline fixture adapter that exercises the RouterOS read-pilot execution contract without opening MikroTik sockets or replacing Python collectors.

## v2.95.0-rc1 package note

Adds the Rust RouterOS API sentence codec foundation for future read-only Rust transport. This package remains hybrid and safe by default.


## Rust Core v2.6 RouterOS API Reply Codec

Adds `decode-routeros-api-reply`, an offline RouterOS API reply parser that decodes already-captured `!re`/`!trap`/`!done` words into sanitized rows/traps while keeping Rust RouterOS live transport disabled by default.

## v2.97.0-rc1

- Added Rust Core v2.7 RouterOS API frame codec.
- Added `codec-routeros-api-frame` operation and API endpoint.
- No live RouterOS transport is enabled.


## Rust Core v2.8 RouterOS Offline Session Pipeline

Adds `run-routeros-offline-session`, an end-to-end offline RouterOS API session rehearsal. It composes sentence encoding, frame encoding/decoding, and reply decoding using fixtures only. It performs zero live connections, consumes no MikroTik credentials, and keeps Python collectors authoritative.


## Rust Core v3.1 RouterOS Auth Handshake Fixture

Adds `run-routeros-auth-handshake`, an offline fixture operation that models RouterOS authentication reply handling without opening sockets, emitting credentials, or replacing Python collectors.
