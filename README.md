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

## Safety Note

LQoSync can write LibreQoS input files and trigger LibreQoS apply behavior. Always verify backups, policies, dry-run output, and apply results before using it in production.
