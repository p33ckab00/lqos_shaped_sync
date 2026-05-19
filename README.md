# LQoSync

> **Canonical path:** LQoSync installs and runs from `/opt/lqosync`. LibreQoS remains under `/opt/libreqos`. Do not use a user-home directory as the documented install base.


LQoSync is a standalone WebUI and scheduler that syncs live MikroTik PPPoE, DHCP, and Hotspot data into LibreQoS input files.

```text
MikroTik RouterOS API → LQoSync → ShapedDevices.csv + network.json → LibreQoS.py --updateonly
```

LQoSync is inspired by the LibreQoS operating model. It exists to make MikroTik-to-LibreQoS synchronization easier to operate, safer to update, and more visible for ISP operators who need to understand what is happening behind the system.

## Table of Contents

1. [What LQoSync Is](#what-lqosync-is)
2. [What LQoSync Is Not](#what-lqosync-is-not)
3. [Why It Exists](#why-it-exists)
4. [System Workflow](#system-workflow)
5. [Fresh Install Safety](#fresh-install-safety)
6. [Safe Update Behavior](#safe-update-behavior)
7. [Standard Paths](#standard-paths)
8. [Core Modules](#core-modules)
9. [Operator Workflow](#operator-workflow)
10. [Dashboard Areas](#dashboard-areas)
11. [ShapedDevices.csv Handling](#shapeddevicescsv-handling)
12. [network.json Handling](#networkjson-handling)
13. [Glossary](#glossary)
14. [Appendices](#appendices)

## What LQoSync Is

- A focused MikroTik-to-LibreQoS sync companion.
- A WebUI for dry-run preview, source health, policies, config, backups, reports, and operations visibility.
- A safety layer for generating LibreQoS `ShapedDevices.csv` and `network.json`.
- A scheduler that can run collection, build proposed outputs, validate impact, and optionally apply LibreQoS updates.

## What LQoSync Is Not

- Not a billing system.
- Not an ISP CRM.
- Not a replacement for LibreQoS.
- Not a replacement for operator validation, backups, and production testing.

## Why It Exists

LibreQoS is powerful, but operators still need clean input files and clear visibility into how subscribers map into shaping. LQoSync helps by showing the chain from router data collection to generated LibreQoS files, policy decisions, dry-run impact, backups, and apply results.

## System Workflow

```text
1. Collect from MikroTik sources
2. Normalize PPPoE / DHCP / Hotspot records
3. Resolve speed and identity rules
4. Build ShapedDevices.csv rows
5. Build network.json topology nodes
6. Validate duplicates, missing parent nodes, and policy conflicts
7. Show Dry Run impact
8. Backup live files
9. Write generated files
10. Run LibreQoS apply/update when allowed
11. Store logs, audit events, and apply history
```

## Fresh Install Safety

If a fresh install finds existing production files, LQoSync backs them up first and preserves them by default:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

Missing files are created from templates. Existing files are not overwritten unless the operator explicitly chooses overwrite-with-backup.

## Safe Update Behavior

A normal update should update app code and safe missing defaults only. These operator-owned files are preserved:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
/opt/lqosync/users.json
/opt/lqosync/.env
/opt/lqosync/state/
/opt/lqosync/logs/
/opt/lqosync/backups/
```

Recommended GitHub install/update command after repository rename:

```bash
cd /opt
curl -fsSL https://raw.githubusercontent.com/p33ckab00/LQoSync/main/install-from-github.sh -o /tmp/install-lqosync.sh
sudo EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh
```

If the GitHub repository has not yet been renamed, temporarily use:

```bash
sudo LQOSYNC_REPO_URL=https://github.com/p33ckab00/LQoSync.git EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh
```


## GitHub Repository Rename

Target repository name:

```text
p33ckab00/LQoSync
```

Rename with GitHub CLI:

```bash
gh repo edit p33ckab00/LQoSync --name LQoSync
```

Then update every local checkout:

```bash
git remote set-url origin https://github.com/p33ckab00/LQoSync.git
git remote -v
git fetch origin main
```

See [Repository Rename Guide](docs/REPOSITORY_RENAME.md).

## Standard Paths

```text
/opt/libreqos/                     # LibreQoS application folder
/opt/libreqos/src/config.json       # LQoSync runtime config consumed by the engine
/opt/libreqos/src/ShapedDevices.csv # generated LibreQoS shaped-device output
/opt/libreqos/src/network.json      # generated LibreQoS topology output
/opt/lqosync/                       # LQoSync app/runtime folder
/opt/lqosync/state/                 # runtime, policy, lifecycle, notification state
/opt/lqosync/logs/                  # audit and apply logs
/opt/lqosync/backups/               # pre-apply and restore backups
```

Compatibility note: the systemd service can remain `lqosync` even after the GitHub repository/product name is LQoSync.


### LQoSync-in-Rust v0.2 Trust/Diff Guard

The `lqosync-in-rust` branch now includes an optional Rust v0.2 safety layer: collector output trust validation and Rust diff operations. The collector trust guard protects cleanup from silent empty/partial RouterOS results, while the Rust diff report is surfaced in Dry Run under `rust_core_diff`. Python remains the primary runtime and fallback remains active when the Rust binary is not built.

## Core Modules

| Module | Purpose |
|---|---|
| Dashboard | Live health, source status, production readiness, and apply warnings |
| Config Center | Router/source settings, policies, notifications, scheduler, and Advanced JSON |
| Dry Run | Preview generated changes before writing live LibreQoS files |
| Shaped Devices | Inspect generated subscriber/circuit rows |
| Network Layout | Inspect or adjust LibreQoS topology nodes |
| Operations Center | Services, journals, app logs, audit, backups, restore preview, and apply history |
| Update Center | Installed version, GitHub status, latest fetched changes, and safe SSH update commands |
| Documentation Center | Searchable local operator documentation |

## Operator Workflow

```text
Install / update safely
→ Configure routers and sources
→ Choose policy preset
→ Run Dry Run
→ Review generated rows and node tree
→ Confirm backups are ready
→ Enable scheduler only when production-ready
→ Monitor Operations Center and Dashboard
```

## Dashboard Areas

- **Dashboard** shows live status and go-live confidence.
- **Config Center** owns settings and policy controls.
- **Update Center** owns version/update visibility.
- **About** owns project identity only; it does not display release updates.
- **Operations Center** owns logs, services, backups, and apply history.

## ShapedDevices.csv Handling

LQoSync builds `ShapedDevices.csv` from normalized source records. The important questions are:

- Which source created this row?
- Which speed rule resolved its bandwidth?
- Which parent node will LibreQoS use?
- Is the IP/MAC duplicated?
- Is the row active, stale, excluded, locked, or policy-held?

## network.json Handling

LQoSync builds the LibreQoS node tree from router, source, DHCP server, plan, and topology rules. A generated subscriber row should point to a valid parent node. Dry Run and validation help detect missing parent nodes before apply.

## Glossary

- **LibreQoS** — the shaping system that consumes `ShapedDevices.csv` and `network.json`.
- **ShapedDevices.csv** — LibreQoS subscriber/circuit input file.
- **network.json** — LibreQoS topology tree file.
- **Dry Run** — preview mode that calculates impact without writing live files.
- **Apply** — writing generated outputs and optionally running LibreQoS update.
- **Policy preset** — Conservative, Balanced, or Aggressive behavior template.
- **Custom policy** — a policy state created when preset-derived values are manually changed.
- **Source** — MikroTik PPPoE, DHCP, Hotspot, or static source used to generate rows.
- **Parent Node** — the LibreQoS node where a shaped device is attached.



## LQoSync-in-Rust branch plan

The `lqosync-in-rust` branch keeps the Python Flask WebUI as the operator interface while adding an optional Rust core for deterministic safety-critical backend work.

```text
Python = WebUI, auth, templates, scheduler controls, docs, reports
Rust   = protocol, validation, parsing, diff, collector trust, atomic state/file writes
```

The migration preserves the existing no-database model and keeps `config.json`, `runtime_state.json`, `policy_state.json`, `collector_cache.json`, `audit.jsonl`, `ShapedDevices.csv`, and `network.json` as file-based state.

This package now includes the first optional Rust core scaffold under `rust/lqosync-core` plus the Python wrapper `engine/rust_core.py`. Rust validation is non-blocking by default and Python fallback remains active when the binary is not built or installed.

Build the optional Rust core with:

```bash
scripts/build-rust-core.sh
sudo scripts/install-rust-core.sh
```

Documentation:

- [LQoSync-in-Rust Core Migration Plan](docs/RUST_CORE_MIGRATION.md)
- [Rust Core Protocol](docs/RUST_CORE_PROTOCOL.md)
- [Collector Output Contract](docs/COLLECTOR_OUTPUT_CONTRACT.md)
- [Autosave and Atomic State Model](docs/AUTOSAVE_AND_ATOMIC_STATE.md)
- [Commit and Push Guide](docs/COMMIT_AND_PUSH_GUIDE.md)

## Appendices

- [Full Documentation](FULL_DOCUMENTATION.md)
- [Documentation Index](docs/DOCUMENTATION_INDEX.md)
- [Upgrade Guide](docs/UPGRADE_GUIDE.md)
- [Command Reference](docs/COMMANDS.md)
- [AI-Assisted Development Disclosure](docs/AI_ASSISTED_DEVELOPMENT.md)

## Rust Core v0.3 Atomic State/File Engine

The `lqosync-in-rust` branch now includes Rust protocol operations for atomic JSON state writes, generated file writes, and audit JSONL appends. Python remains the default writer, with optional Rust-backed writes enabled by `LQOSYNC_RUST_ATOMIC_WRITES=1`. See `docs/RUST_CORE_V03_ATOMIC_STATE.md`.

Build hotfix `v2.73.1-rc1` updates the Rust CSV writer to use `csv::Terminator::Any(b'\n')` for compatibility with the current `csv` crate while preserving LF line endings.

## Safety Note

LQoSync can write LibreQoS input files and trigger LibreQoS apply behavior. Always verify backups, policies, dry-run output, and apply results before using it in production.


### Rust Core v0.4 daemon mode

The optional Rust safety core now supports a Unix socket daemon. The daemon uses the same JSON protocol as the CLI and can be installed with `sudo scripts/install-rust-core-daemon.sh` after building/installing the Rust binary. Python falls back to subprocess or Python fallback when the daemon is unavailable.

## Rust Core v0.5 Policy Shadow

The `lqosync-in-rust` branch now includes an optional Rust `evaluate-policy` operation. It runs in shadow mode beside Python policy decisions, reports risk/verdict/parity in Dry Run, and remains non-authoritative until parity is proven.



## Rust Core v0.6 Circuit Shadow

The `lqosync-in-rust` branch now includes an optional Rust `normalize-circuits` operation. It runs in shadow mode beside the Python collectors/builders, reports normalized row counts and diagnostics in Dry Run, and prepares the next migration step toward a Rust circuit builder without changing live behavior.

### Rust Core v0.7 Sync Plan Shadow

The `lqosync-in-rust` branch now includes `evaluate-sync-plan`, a shadow-only end-to-end Rust planner that composes collector trust, Rust diff, Rust circuit shadow, Rust validation, Rust policy shadow, Python preflight, and cleanup stats. Python remains authoritative for writes and LibreQoS apply.


## v2.78.0-rc1 - Rust Core v0.8 Authority Gates

- Added opt-in `rust_core.enforce_sync_plan` authority gate.
- Added `rust_core.authority_mode` with `shadow` and `enforce_blockers`.
- Added fail-closed behavior when enforced Rust core is unavailable.
- Dry Run remains preview-only; Python remains default authority unless enforcement is enabled.
- Added documentation: `docs/RUST_CORE_V08_AUTHORITY_GATES.md`.


## Rust Core v0.9 Apply Manifest Preview

The `lqosync-in-rust` branch now includes a non-destructive Rust apply manifest that previews the backup/write/pending-apply/LibreQoS apply transaction before Python executes it. Python remains authoritative by default.


## Rust Core v1.0 Apply Transaction Executor

This package adds the optional `execute-apply-transaction` Rust operation. It rehearses transactions by default and only writes files when explicit Rust transaction flags are enabled. Python remains authoritative for normal production sync/apply behavior.


## Rust Core v1.1 Runtime Self-Test

This package adds a safe Rust core `self-test` operation and `/api/rust-core/self-test` endpoint. It also routes `execute-apply-transaction` through the CLI/daemon protocol and centralizes advertised Rust operations so future operation-list mismatches are easier to catch before enabling authority flags.

Read: `docs/RUST_CORE_V11_SELF_TEST.md`.


### Rust Core v1.1.1 self-test build hotfix

The v1.1.1 package fixes the self-test no-change manifest assertion and hardens Rust install helpers so a failed build cannot accidentally install a stale release binary. The daemon installer now restarts an already-running `lqosync-core.service` after updating `/usr/local/bin/lqosync-core`.


### Rust Core v1.2 transaction journal and rollback preview

Rust Core v1.2 adds `build-transaction-journal` and `build-rollback-manifest` operations. These are preview-only by default and make future Rust file-write authority auditable and rollback-aware. Read: `docs/RUST_CORE_V12_TRANSACTION_JOURNAL.md`.

### Rust Core v1.3 Transaction Journal Persistence

The `lqosync-in-rust` branch now includes `append-transaction-journal`, an opt-in operation for persisting Rust apply transaction journal events to `/opt/lqosync/logs/transaction_journal.jsonl`. It is disabled by default and remains rehearsal-only unless explicitly enabled.


## Rust Core v1.4 Transaction History and Rollback Plan Viewer

This package adds read-only Rust operations `read-transaction-journal` and `build-rollback-from-journal`, plus WebUI API endpoints for transaction history and rollback plan preview. Rollback execution remains unsupported/disabled.


## Rust Core v1.5 Rollback Execution Rehearsal

This package adds `execute-rollback`, a gated rollback executor. It rehearses rollback by default and only restores files when rollback authority, file-write permission, and `CONFIRM_ROLLBACK` confirmation are explicitly provided. Python remains authoritative by default.


## Rust Core v1.6 Authority Readiness Report

- Adds `evaluate-authority-readiness` to score whether Rust authority flags are safe to pilot.
- Adds `/api/rust-core/authority-readiness` for read-only operator visibility.
- Keeps Python authoritative by default and treats partial authority flags as blockers.
- Documents readiness verdicts before sync-plan enforcement, file-write authority, journal persistence, or rollback authority are enabled.

### Rust Core v1.7 Full Backend Readiness

The `lqosync-in-rust` branch now includes read-only full backend readiness and authority pilot planning. This confirms the current system is still a hybrid architecture: Python remains authoritative for the WebUI, scheduler, RouterOS collectors, and default run cycle, while Rust provides validation, planning, transactions, journaling, rollback, and optional authority gates.

New operations:

```text
evaluate-full-rust-readiness
build-authority-pilot-plan
```

New read-only APIs:

```text
/api/rust-core/full-backend-readiness
/api/rust-core/authority-pilot-plan
```

## Rust Core v1.8 Collector Bundle Shadow Builder

This package adds `build-collector-circuit-bundle`, a non-authoritative Rust operation that accepts raw Python collector snapshots and returns ShapedDevices-compatible rows in shadow mode. Python RouterOS collection remains authoritative.


## Rust Core v1.9 Collector Bundle Parity Report

Adds `compare-collector-bundle-parity`, a diagnostic operation and API endpoint for comparing Python-authoritative rows with Rust-shadow collector bundle rows before any collector authority migration.


## Rust Core v2.0 RouterOS Collector Plan

This package adds `build-routeros-collector-plan`, a read-only Rust operation that derives the RouterOS resource/field plan for enabled PPPoE, DHCP, and Hotspot sources. It does not connect to MikroTik and does not replace Python collectors. It is a bridge toward a future Rust RouterOS transport while keeping Python authoritative by default.

New API:

```text
GET /api/rust-core/routeros-collector-plan
POST /api/rust-core/routeros-collector-plan
```


## Rust Core v2.0.1 Script Permission Hotfix

If a ZIP/manual copy loses executable bits and `scripts/build-rust-core.sh` returns `Permission denied`, run:

```bash
bash scripts/repair-script-permissions.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
```

A valid v2.0+ self-test must advertise `build-routeros-collector-plan`.


## Rust Core v2.1 RouterOS Read Result Contract

This package adds `validate-routeros-read-results`, a Rust trust contract that validates Python-executed RouterOS read results against the deterministic collector plan. It is diagnostic by default and does not replace Python live RouterOS collectors.


## Rust Core v2.2.1 RouterOS Transport Session Rehearsal Hotfix

This package fixes a false-positive redaction test while keeping the v2.2 transport session behavior unchanged. RouterOS transport remains non-network, credentials stay redacted, and Python collectors remain authoritative.

## Rust Core v2.2 RouterOS Transport Session Rehearsal

Adds `build-routeros-transport-session`, a non-network RouterOS transport rehearsal that redacts credentials, reports planned sessions, blocks live Rust RouterOS transport attempts, and keeps Python live collectors authoritative.


## Rust Core v2.3 RouterOS Live Read Pilot Gate

LQoSync 2.93.0-rc1 / lqosync-core 2.3.0 adds `build-routeros-live-read-pilot`, a gated non-network contract for a future read-only Rust RouterOS transport adapter. Python collectors remain authoritative and Rust still does not open MikroTik sockets.


## Rust Core v2.4 RouterOS Read Pilot Fixture Adapter

Adds `run-routeros-read-pilot`, an offline fixture adapter that exercises the RouterOS read-pilot execution contract without opening MikroTik sockets or replacing Python collectors.

### Rust Core v2.5 RouterOS API Sentence Codec

The `lqosync-in-rust` branch now includes `build-routeros-api-sentence`, an offline RouterOS API word/proplist encoder for future read-only Rust transport. It does not connect to MikroTik and does not replace Python collectors.


### Rust Core v2.5.1 RouterOS API Codec Redaction Hotfix

`lqosync-core` v2.5.1 keeps the offline RouterOS API codec warning-clean and redacts dropped sensitive `.proplist` field names from result payloads. Valid RouterOS resource paths such as `/ppp/secret` remain allowed, but dropped fields such as `password` or `api-key` are reported only by count.


## Rust Core v2.6 RouterOS API Reply Codec

Adds `decode-routeros-api-reply`, an offline RouterOS API reply parser that decodes already-captured `!re`/`!trap`/`!done` words into sanitized rows/traps while keeping Rust RouterOS live transport disabled by default.

### Rust Core v2.7 RouterOS API Frame Codec

Adds `codec-routeros-api-frame`, an offline RouterOS API binary frame encoder/decoder. This is transport preparation only: no live MikroTik sockets, no credential use, and Python collectors remain authoritative.


## Rust Core v2.8 RouterOS Offline Session Pipeline

Adds `run-routeros-offline-session`, an end-to-end offline RouterOS API session rehearsal. It composes sentence encoding, frame encoding/decoding, and reply decoding using fixtures only. It performs zero live connections, consumes no MikroTik credentials, and keeps Python collectors authoritative.


## Rust Core v2.9 RouterOS TCP Connectivity Pilot

The `lqosync-in-rust` branch now includes a gated RouterOS TCP reachability pilot through `run-routeros-tcp-connectivity-pilot`. This remains a transport bridge, not a full Rust backend. Python collectors remain authoritative by default.


## Rust Core v3.0 RouterOS Authentication Plan

Adds `build-routeros-auth-plan`, a redacted RouterOS authentication planning bridge. It verifies whether router metadata is ready for a future authentication adapter without emitting credentials, opening sockets, or replacing Python collectors.


## Rust Core v3.1 RouterOS Auth Handshake Fixture

Adds `run-routeros-auth-handshake`, an offline fixture operation that models RouterOS authentication reply handling without opening sockets, emitting credentials, or replacing Python collectors.


## Rust Core v3.2 RouterOS Auth Session Contract

Adds `build-routeros-auth-session-contract`, a redacted authenticated-session contract built from fixture auth replies. It performs zero socket/auth attempts, emits no credentials or tokens, and keeps Python collectors authoritative.
