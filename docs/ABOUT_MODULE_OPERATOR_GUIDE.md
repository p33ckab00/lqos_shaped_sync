# LQoSync In-App About Module and Operator Guide

This document mirrors the information now shown inside the LQoSync web UI under **About LQoSync**. The About module is intended to be the built-in operator manual. Every meaningful project change should update this document, the repository manuals, release notes, and `templates/about.html` together.

## Project description

LQoSync is a standalone, database-free LibreQoS companion dashboard for syncing live MikroTik PPPoE, DHCP, and Hotspot data into `ShapedDevices.csv` and `network.json`.

It is not a billing system, CRM, ISP Manager, or subscriber database. Its role is intentionally narrow:

1. Read live MikroTik subscriber/session data using a restricted RouterOS API user.
2. Read operator rules from `/opt/libreqos/src/config.json`.
3. Generate LibreQoS-compatible `ShapedDevices.csv` and `network.json`.
4. Write files atomically only when generated output changes.
5. Run `LibreQoS.py --updateonly` from `/opt/libreqos/src` when changes happen or when a previous apply failed and must be retried.
6. Show the whole process through a safe operator UI.

## Core safety model

- No database.
- MikroTik is read-only.
- `config.json` is the local rule source.
- `ShapedDevices.csv` and `network.json` are generated outputs.
- LibreQoS remains the actual shaper/apply engine.
- Dry-run never writes generated files and never runs LibreQoS.
- Non-dry-run applies immediately when changed files are written.
- Failed LibreQoS applies are retried when `retry_if_last_apply_failed=true`.
- Bare-metal installs use direct execution, not `nsenter`.

## Process workflow

1. Load `/opt/libreqos/src/config.json`, existing `ShapedDevices.csv`, and existing `network.json`.
2. Read MikroTik through the RouterOS API.
3. Process PPPoE, DHCP, and Hotspot sources.
4. Resolve names, MAC/IP, min/max speeds, parent nodes, node aggregation, source labels, and speed sources.
5. Build proposed `ShapedDevices.csv` and `network.json`.
6. Run preflight checks and compare generated output against current files.
7. If dry-run, show preview only.
8. If non-dry-run and files changed, write generated files using atomic temp-file writes.
9. Run LibreQoS apply from `/opt/libreqos/src`.
10. Record stdout, stderr, exit code, elapsed time, audit events, and last sync timeline.

## Required LibreQoS apply config

The live config should include:

```json
"libreqos": {
  "cmd": "/opt/libreqos/src/LibreQoS.py",
  "args": ["--updateonly"],
  "working_dir": "/opt/libreqos/src",
  "run_mode": "direct",
  "sudo": true,
  "run_only_when_files_changed": true,
  "retry_if_last_apply_failed": true,
  "timeout_seconds": 300
}
```

`working_dir` is critical because LibreQoS reads relative files such as `ShapedDevices.csv` and `ShapedDevices.lastLoaded.csv`.

## Fresh installation

Recommended GitHub-source install:

```bash
sudo apt update
sudo apt install -y git
cd /opt
sudo git clone https://github.com/p33ckab00/lqos_shaped_sync.git lqosync
cd /opt/lqosync
sudo bash install.sh
```

One-command bootstrap:

```bash
curl -fsSL https://raw.githubusercontent.com/p33ckab00/lqos_shaped_sync/main/install-from-github.sh -o /tmp/install-lqosync.sh
sudo bash /tmp/install-lqosync.sh
```

Fresh install behavior:

- Missing `config.json`, `ShapedDevices.csv`, or `network.json` are created from templates.
- Existing LibreQoS files are preserved by default.
- Interactive installs ask the operator what to do when existing files are detected.
- Non-interactive installs preserve existing files by default.

## Existing installation adoption

If `/opt/lqosync` already exists, the installer should not delete it blindly. It should detect the existing install and offer options:

```text
Existing LQoSync installation detected.

Choose action:
[1] Adopt and update existing install  (recommended)
[2] Update code only, preserve all data
[3] Repair install, preserve all data
[4] Backup and replace app files
[5] Remove existing LQoSync then fresh install
[6] Abort
```

Recommended adoption command:

```bash
cd /opt
curl -fsSL https://raw.githubusercontent.com/p33ckab00/lqos_shaped_sync/main/install-from-github.sh -o /tmp/install-lqosync.sh
sudo EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh
```

Preserved by default:

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

## GitHub update flow

Default production update:

```bash
cd /opt/lqosync
sudo bash upgrade.sh
```

Default policy is `preserve_and_migrate`.

Available update policies:

```bash
sudo UPDATE_POLICY=pull_only bash upgrade.sh
sudo UPDATE_POLICY=code_only bash upgrade.sh
sudo UPDATE_POLICY=preserve_and_migrate bash upgrade.sh
sudo UPDATE_POLICY=refresh_with_backup bash upgrade.sh
sudo UPDATE_POLICY=factory_reset CONFIRM_FACTORY_RESET=yes bash upgrade.sh
```

Policy meanings:

- `pull_only`: fetch/pull code only; no migration or restart.
- `code_only`: update app source while preserving config/users/runtime files.
- `preserve_and_migrate`: production default; preserve operator files and add missing safe defaults.
- `refresh_with_backup`: backup first, refresh service files, dependencies, permissions, and migrations.
- `factory_reset`: dangerous lab/rebuild mode requiring explicit confirmation.

## Uninstall and permission restore

Standard uninstall:

```bash
cd /opt/lqosync
sudo bash uninstall.sh
```

Remove runtime too:

```bash
cd /opt/lqosync
sudo REMOVE_RUNTIME=true bash uninstall.sh
```

Full permission restore:

```bash
cd /opt/lqosync
sudo RESTORE_MODE=full bash uninstall.sh
```

Never delete LibreQoS operational files by default:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
/opt/libreqos/src/ShapedDevices.lastLoaded.csv
/opt/libreqos/src/lastGoodConfig.csv
/opt/libreqos/src/lastGoodConfig.json
/opt/libreqos/src/planner_state.json
```

## MikroTik setup requirement

Create a dedicated read-only API user:

```rsc
/user group add name=API_READ policy="read,sensitive,api,!policy,!local,!telnet,!ssh,!ftp,!reboot,!write,!test,!winbox,!password,!web,!sniff,!romon"
/user add name="libreqosyncAPI" group=API_READ password="<Strong Password>" address="<LibreQoS IP Address>" disabled=no
```

Use that user in the router section of `config.json`.

## Important paths

```text
/opt/lqosync                                  LQoSync app and Git source
/opt/libreqos/src/config.json                 LQoSync live config
/opt/libreqos/src/ShapedDevices.csv           generated LibreQoS CSV
/opt/libreqos/src/network.json                generated LibreQoS topology
/opt/lqosync/users.json                       UI users with bcrypt hashes
/opt/lqosync/logs/lqos_shaped_sync.log        LQoSync app log
/opt/lqosync/logs/audit.jsonl                 audit log
/opt/lqosync/logs/libreqos_apply/             LibreQoS apply stdout/stderr/metadata
/opt/lqosync/state/runtime_state.json         runtime state and last run summary
/opt/lqosync/backups/                         backups
```

## Troubleshooting guide with explanations and expectations

### FileNotFoundError: ShapedDevices.csv

Meaning: LibreQoS.py ran from the wrong working directory.

Check:

```bash
grep -A12 '"libreqos"' /opt/libreqos/src/config.json
```

Expected:

```text
"working_dir": "/opt/libreqos/src"
"run_mode": "direct"
```

Check apply metadata:

```bash
latest_json=$(sudo find /opt/lqosync/logs/libreqos_apply -name "*.json" -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
sudo cat "$latest_json"
```

Expected:

```text
"working_dir": "/opt/libreqos/src"
```

### nsenter permission denied

Meaning: Docker-only host namespace mode was used on bare-metal.

Check:

```bash
grep -E 'LQOSYNC_RUN_MODE|HOST_CONTROL_MODE|LQOSYNC_INSTALL_MODE|LQOSYNC_FORCE_DIRECT' /opt/lqosync/.env
```

Expected:

```text
LQOSYNC_INSTALL_MODE=baremetal
LQOSYNC_RUN_MODE=direct
HOST_CONTROL_MODE=direct
LQOSYNC_FORCE_DIRECT=true
```

### Permission denied: config.json.tmp

Meaning: LQoSync cannot create atomic temp files in `/opt/libreqos/src`.

Repair:

```bash
sudo apt update
sudo apt install -y acl
sudo setfacl -m u:lqosync:rwx /opt/libreqos/src
sudo setfacl -m u:lqosync:rw /opt/libreqos/src/config.json
sudo setfacl -m u:lqosync:rw /opt/libreqos/src/ShapedDevices.csv
sudo setfacl -m u:lqosync:rw /opt/libreqos/src/network.json
sudo setfacl -d -m u:lqosync:rwX /opt/libreqos/src
```

Smoke test:

```bash
sudo -u lqosync touch /opt/libreqos/src/config.json.tmp
sudo -u lqosync rm -f /opt/libreqos/src/config.json.tmp
```

Expected: no error.

### files_changed=False but previous apply failed

Meaning: the generated files are already written, so file diff is clean; LQoSync must retry the failed apply using pending apply state.

Expected config:

```json
"retry_if_last_apply_failed": true
```

### LibreQoS status false in UI but apply works

Check real service state:

```bash
systemctl is-active lqosd
systemctl is-active lqos_scheduler
systemctl status lqosd lqos_scheduler --no-pager
```

Expected: `lqosd` and `lqos_scheduler` are active. `lqos_node_manager` is legacy/optional.

### Blank /var/log/lqos_shaped_sync.log

Use the active app log path:

```bash
tail -n 100 /opt/lqosync/logs/lqos_shaped_sync.log
journalctl -u lqos_shaped_sync -n 100 --no-pager
```

### git pull does not work: not a git repository

Use adoption mode:

```bash
cd /opt
curl -fsSL https://raw.githubusercontent.com/p33ckab00/lqos_shaped_sync/main/install-from-github.sh -o /tmp/install-lqosync.sh
sudo EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh
```

### Port 9202 is already in use

Check:

```bash
sudo ss -tulpn | grep :9202
sudo systemctl status lqos_shaped_sync
```

### ShapedDevices/network validation fails

Check basic structure:

```bash
cd /opt/libreqos/src
head -1 ShapedDevices.csv
awk -F',' 'NR>1 && $5=="" {print NR ":" $0}' ShapedDevices.csv
python3 -m json.tool network.json
```

## Documentation update rule

Every feature or install behavior change should update:

```text
README.md
FULL_DOCUMENTATION.md
INSTALLATION.md
BARE_METAL_INSTALL.md
DOCKER_INSTALL.md
UNINSTALLATION.md
relevant files under docs/
RELEASE_NOTES.md
templates/about.html
```

The in-app About module should stay aligned with the latest repository documentation.


## v2.39 Operations Dashboard UX

The About module and Dashboard should now describe LQoSync as an operator cockpit, not only a counter page. The dashboard is designed to answer:

```text
Is the system healthy?
Why did LibreQoS run or skip?
Which MikroTik source changed?
Where did the last cycle spend time?
Was cleanup safe?
Who changed, what speed, and which node?
Is the Git-managed install up to date, behind, ahead, or diverged?
```

### Dashboard modules

- **System Health**: combines errors, warnings, and pending apply status.
- **Apply Decision**: explains `files_changed`, `retry_pending_failed_apply`, `force_apply`, `dry_run`, `auto_apply_disabled`, and `no_changes`.
- **Performance Breakdown**: splits elapsed time into MikroTik API, build/diff, file write, and LibreQoS apply.
- **Data Source Status**: shows PPPoE/DHCP/Hotspot counts, metadata reads, generated rows, and timing.
- **Cleanup Safety**: shows allowed cleanup sources and removed rows.
- **Recent Client Change Feed**: shows client, speed, parent node, and changed fields.
- **Generated Files and Drift Policy**: shows whether `ShapedDevices.csv` or `network.json` changed and which drift/backup policy applies.
- **Version / Git Status**: shows Git branch, commit, relation to upstream, and dirty worktree.


## LQoSync v2.40 Operator Experience Polish

This release improves the operator-facing UI/UX without changing the core LibreQoS-safe sync workflow. It focuses on making the dashboard explain decisions, risks, and next actions clearly.

### Added UI/UX behavior

- **Health Summary Banner** — shows whether the system is healthy, warning, pending apply, or action-needed.
- **What Changed Panel** — summarizes added, updated, removed, and total client changes from the last sync.
- **Apply Decision Explanation** — explains why LibreQoS ran or skipped, including no changes, dry-run, files changed, forced apply, or retry of a pending failed apply.
- **Config Change Preview** — Config Center previews important config changes before saving and encourages dry-run after major changes.
- **Safe Dry Run Report** — Dry Run Preview highlights duplicate IP, parent-node, speed validation, and confirms that dry-run never writes or applies.
- **Update Center** — shows Git/version state and recommended production-safe update/adoption commands without running arbitrary shell operations from the browser.
- **Mobile Shaped Devices Cards** — mobile users get compact device cards instead of relying only on a wide table.

### Operator principle

The UI should answer: what happened, why did LQoSync decide that, what changed, was cleanup safe, did LibreQoS apply successfully, where did time go, and what is the safest next action.

## LQoSync v2.41 — Topology UX and Privacy Mode

This release improves the Network Layout page into a safer topology builder and adds WebUI Privacy / Redaction Mode for screenshots and demos.

### Network Layout / Topology UX

The Network Layout page now behaves more like a production topology editor:

- layout mode cards for Simple Flat — No Parent, Simple Flat — Router Root, Normal Hierarchy, Deep Hierarchy, and Custom Hierarchy
- topology tree sidebar for quick node selection
- visual topology canvas with nested node cards
- right-side Node Inspector for editing name, type, bandwidth, virtual state, and parent placement
- promote, move, delete, and save topology actions
- impact preview showing affected clients, child count, virtual-node warnings, and selected path
- advanced JSON preview that reflects the in-browser topology state before save
- validation before save to block duplicate node names, invalid bandwidth, or missing Parent Node references

### Deep Hierarchy Concept

Normal hierarchy keeps each MikroTik router as a root with generated PPPoE/DHCP/Hotspot nodes under it. Deep hierarchy allows a router to be nested under another upstream/core/site node using `router.parent_node`.

Example:

```text
RB-Core
└─ RB5k9-Distro
   ├─ Tier-15M-RB5k9-Distro
   ├─ DHCP-LAN-RB5k9-Distro
   └─ DHCP-Wifi5Soft-RB5k9-Distro
```

The important rule is that generated child nodes stay under their owning router. If `RB5k9-Distro` is nested under `RB-Core`, the child nodes generated from `RB5k9-Distro` remain inside `RB5k9-Distro`, not directly under `RB-Core`.

### Virtual Nodes

Virtual/logical nodes are supported for organization and display. They are useful for grouping by area, PoP, region, or logical site. Operators should avoid name collisions because LibreQoS may promote children to the nearest non-virtual ancestor during shaping.

### WebUI Privacy / Redaction Mode

A mask icon is available in the top navigation. Privacy Mode:

- masks visible client names, node names, router names, IP addresses, MAC addresses, and IDs in the browser UI
- stores preference in browser local storage
- is intended for screenshots, demos, support requests, and documentation
- does not modify `config.json`, `ShapedDevices.csv`, `network.json`, logs, audit files, or any source data

This is a client-side display-only feature. Disable Privacy Mode before doing precise visual checks where real names/IPs must be visible.


## v2.42 Privacy UX + Topology Save Fix

The About module documents the improved privacy and topology-save behavior. Privacy Mode is intended for demos, public screenshots, and support screenshots. It masks visible UI values only and does not protect data from browser developer tools. Topology save now includes the CSRF token in JSON/AJAX requests; if saving is blocked with a security-token message, refresh the page and retry.


## v2.43 UI Polish and Git Update Detection

This release is a UI/UX polish update. It does not change the core sync engine.

### Privacy toggle

The topbar Privacy Mode control now uses an incognito-style icon. When privacy mode is disabled, the same icon is shown with a slash indicator. When privacy mode is enabled, the slash disappears and visible subscriber, node, IP, MAC, and ID values are replaced with stable redaction labels such as `Client-001`, `IP-001`, and `MAC-001`. This is browser-only redaction for screenshots and demos; source files are not modified.

### Services & Journals layout

The Services & Journals page now uses equal-height desktop panels for Journal Viewer and LibreQoS Apply Logs. The Journal Viewer output pane is larger, scrolls cleanly inside the card, and keeps controls aligned at the top. The apply log list uses a matching scroll area so the two panels feel balanced. On smaller screens, the panels stack vertically.

### Update Center detection

Update Center now performs a fresh `git fetch origin main` before comparing local and remote state. It compares local `HEAD` against the latest fetched `origin/main`, displays local and remote commits, reads the remote `VERSION` file using `git show origin/main:VERSION`, and shows whether an update is needed based on commit or version difference.

Update Center remains read-only. It displays safe SSH commands for updating, but it does not execute Git or upgrade actions from the browser.


## v2.44 UI polish note

LQoSync v2.44 refines the browser-only Privacy Mode icon and Services & Journals layout. Privacy Mode now uses a shield-and-eye redaction icon with a slash state when masking is disabled. Services & Journals now uses matching scroll-shell panels for Journal Viewer and LibreQoS Apply Logs so both areas line up visually and use the available card height consistently. These changes do not modify the core engine, generated files, or LibreQoS apply logic.

## v2.45 Smart Policy Center

LQoSync v2.45 adds a policy-driven safety layer before file writes and LibreQoS apply. The policy engine evaluates cleanup candidates, collector source health, preflight validation, backup readiness, and pending confirmations before allowing ShapedDevices.csv/network.json writes or `LibreQoS.py --updateonly`.

Key behavior:

- Config defines operator intent.
- Policies define how safely that intent is applied.
- The policy engine decides before write/apply.
- Dashboard and Dry Run explain every decision.

The Policy Center exposes policy mode, source cleanup behavior, pending cleanup confirmations, runtime policy state, apply guards, and collector guards. Normal inactive cleanup, source-disabled cleanup, collector failure, zero-result scans, and mass-removal events are treated differently so intentional operator actions are not confused with API failure or suspicious data loss.

Recommended production default is balanced mode. In balanced mode, collector failures preserve rows, enabled sources returning zero rows are protected, source-disabled cleanup can require confirmation, and dangerous validation failures block file writes and LibreQoS apply.
