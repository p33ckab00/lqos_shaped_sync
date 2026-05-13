# LQoSync In-App About Module and Operator Guide

## AI-Assisted Development Disclosure and Acknowledgement

LQoSync was developed and refined through an AI-assisted development workflow.

A significant portion of the system planning, code generation, documentation, UI/UX refinement, troubleshooting logic, release structuring, and implementation guidance was assisted by **GPT-5.5 Thinking by OpenAI**, working interactively with the project owner/operator.

The project owner/operator provided the real-world ISP requirements, LibreQoS and MikroTik deployment context, feature direction, testing feedback, operational decisions, and final approval for changes.

This acknowledgement is included to recognize the role of AI-assisted engineering in accelerating the development of LQoSync while preserving the importance of human validation, operational judgment, and production responsibility.

Because LQoSync may interact with live network infrastructure, LibreQoS files, MikroTik routers, scheduler behavior, and service-level automation, all AI-assisted code, configuration, documentation, and operational behavior should be reviewed, tested, and validated by a qualified human operator before production use.

AI assistance does not replace human review, security auditing, backup verification, configuration validation, or production testing.


---


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

## v2.46 Smart Insights note

LQoSync v2.46 adds Smart Insights on top of the Smart Policy Center. The dashboard and dry-run pages now summarize data quality, backup readiness, fallback-speed usage, anomaly detection, recommendations, and Why/Fix/Next explanations. These insights are rule-based and operator-facing: they do not replace the policy engine, but explain what happened, why it matters, and the safest next action.



## v2.47 Smart Lifecycle note

LQoSync v2.47 adds Smart Lifecycle tracking. The system now records bounded client lifecycle state, cleanup queue history, cleanup decision history, confirmation history, source lifecycle snapshots, per-client event timelines, and returned-client detection. The new Lifecycle Center shows active, stale, queued, removed, and returned clients so operators can understand not only what the policy engine decided, but what happened to each client across sync runs.


## v2.48 Smart Setup / Repair Center

LQoSync v2.48 adds a Smart Setup / Repair Center at `/setup-repair`. It provides a guided first-install checklist, health check report, readiness score, safe repair commands, policy preset setup, MikroTik connection-test guidance, Git/adoption guidance, and LibreQoS path/permission checks. The center is read-only by default and gives SSH commands instead of blindly modifying the server from the browser.


## v2.49 Policy Settings Integration FULL

LQoSync v2.49 makes Smart Policy Center a real operator settings surface. Policies are no longer hidden or only visible as raw JSON. Operators can edit policy behavior in the WebUI, save it to `config.json -> policies`, compare the current policy against Conservative/Balanced/Aggressive presets, and run Dry Run to preview the effect before scheduler/auto-apply.

### Key behavior

- Policy Center settings are saved to `config.json -> policies`.
- Manual edits switch `policies.mode` to `custom`.
- Preset buttons apply Conservative, Balanced, or Aggressive defaults.
- Config Center includes a Policy Center module for core policy settings and links to the full Policy Center.
- `engine/policy_schema.py` is the schema source for labels, descriptions, choices, defaults, risk labels, preset comparison, and form parsing.
- Setup & Repair focuses on diagnostics/repair actions and links to Documentation rather than duplicating the full manual.

### Source of truth

```text
config.json -> policies        operator intent
engine/policy_schema.py        policy setting metadata
engine/policy_defaults.py      default/preset values
engine/policy_engine.py        runtime decision maker
policy_state.json              pending confirmations and cleanup queue
docs/content/*.md              documentation source blocks
```


## v2.50 Policy-Aware Cleanup Intelligence

LQoSync v2.50 adds optional source-aware stale lifecycle behavior, risk-aware LibreQoS auto-apply, and policy decision trace entries. Grace is disabled by default per source and should only be enabled for stable identities. DHCP environments with randomized MAC addresses should usually keep grace disabled to avoid temporary ghost rows. Risk-aware auto-apply allows low-risk changes to apply automatically while holding medium/high/critical risk changes pending for operator review by default.


## v2.51 Config Schema + Policy Simulation Engine

LQoSync v2.51 adds a Config Center simulation layer. Operators can preview unsaved settings before saving `config.json`. The simulator validates schema health, detects important changes, explains policy impact, computes risk level, and recommends the next action.

New files:

```text
engine/config_schema.py
engine/config_diff.py
engine/config_simulator.py
engine/policy_simulator.py
docs/content/config_schema_policy_simulation.md
```

Config Center now includes a Config Health / Simulation card with a Preview Impact button. This is read-only and does not write config.json or generated LibreQoS files.


## v2.52 Smart Reports + Operator Audit

LQoSync v2.52 adds a Smart Reports center at `/reports`. It summarizes the last 24 hours of sync, dry-run, policy blocked, cleanup confirmation, LibreQoS apply, config change, and audit activity. The page also displays the latest policy decision report, cleanup report, client change report, smart recommendations, and config/operator audit trail. Reports can be exported as JSON, CSV, or Markdown and can be printed from the browser. The reporting engine is read-only and does not change config, generated files, policy state, or LibreQoS.


## v2.53 Client Lifecycle Timeline

LQoSync v2.53 expands the Lifecycle Center into a client timeline and cleanup-state investigation tool. It adds status/source/search filters, selected-client focus, source lifecycle summaries, cleanup queue visibility, pending confirmations, cleanup and confirmation history, recommendations, and JSON/CSV/Markdown exports. Privacy Mode redacts visible client names, parent nodes, IPs, and MACs in lifecycle tables and timelines.


## v2.54 First Run Setup Wizard

LQoSync v2.54 adds a guided First Run Setup Wizard. The wizard computes readiness from config, runtime state, setup/repair checks, source configuration, Network Layout mode, Smart Policy preset, Dry Run status, and scheduler state. It gives the operator a clean onboarding path: confirm LibreQoS paths, configure MikroTik routers, enable PPPoE/DHCP/Hotspot sources, choose Network Layout, choose policy preset, run Dry Run, and enable scheduler only after results are clean and expected.

The wizard is read-only while loading. It does not contact routers or write generated LibreQoS files automatically. Policy preset and layout-mode changes are explicit form actions and are followed by a reminder to run Dry Run.


## v2.54.1 Smart Reports route hotfix

This hotfix restores the missing Flask route wiring for Smart Reports in `app.py`. The v2.54 package already included `engine/reports.py`, `templates/reports.html`, and the navigation link, but `/reports` returned `404 Not Found` because the route handler was not registered. v2.54.1 adds `/reports`, `/api/reports/operator`, and `/reports/export/<fmt>` so Smart Reports works cumulatively with the First Run Setup Wizard release.


## v2.54.2 Policy Center Setup Guidelines

Policy Center now includes atomic setup guidance for every visible setting. Each field explains what it controls, recommended setup, risk note, config path, recommended value, and risk level. The detailed guide is available at `docs/content/policy_center_settings_guidelines.md`.

This update also normalizes stale lifecycle PPPoE policy naming to the canonical `pppoe` key while accepting the older `ppoe` alias from previous schema builds, preventing false missing-policy warnings after upgrades or fresh installs.


## v2.54.3 Network Layout Drag-and-Drop

Network Layout now supports desktop drag-and-drop. Operators can drag a node card or topology tree item onto another node to move it under that parent, or drop it on the root drop zone to move it to root level. The UI prevents unsafe moves such as moving a node under itself, moving it under its own descendant, creating duplicate child names, or dropping to the same parent as a no-op. Drag changes are preview-only until **Save topology** is clicked and backend network.json validation still applies. On mobile/touch devices, use the Node Inspector Move control.


## v2.54.5 Privacy icon polish

The Privacy Mode topbar control now uses an incognito-style icon to better represent screenshot-safe masking/redaction. Privacy OFF keeps the slash overlay, while Privacy ON highlights the incognito icon and continues to replace visible sensitive values with stable labels such as `Client-001`, `Node-001`, `IP-001`, and `MAC-001`. This is a UI-only polish change.


## v2.55 Package Quality + Environment Doctor

LQoSync v2.55 adds package integrity checks and a built-in Environment Doctor to make releases safer. It detects missing Flask routes for navigation links, missing templates, missing feature engine files, incomplete config defaults, and missing policy defaults before publishing or after updating. Setup & Repair also includes a Smart Defaults Repair button that backs up `config.json`, deep-merges missing safe defaults, preserves operator values, and validates the result.

Commands:

```bash
cd /opt/lqosync
python3 scripts/release_check.py
sudo CONFIG_PATH=/opt/libreqos/src/config.json bash scripts/lqosync-doctor.sh
```


## v2.56 Policy UX + Conflict Intelligence

LQoSync v2.56 adds read-only Policy Conflict Resolver checks, improved current-vs-preset comparison, and Client Identity Handling guidance inside Smart Policy Center.

The conflict resolver explains risky combinations such as immediate cleanup combined with permissive zero-result handling, collector-failed cleanup that could delete rows, source-disabled immediate cleanup, high/critical risk auto-apply, disabled apply guards, and grace enabled for mixed/unstable identity sources.

Client Identity Handling explains that PPPoE usernames are usually stable, DHCP server+MAC is mixed because of private/random MAC behavior, Hotspot is stable only when username/voucher based, and Static/manual rows are operator-controlled.


## v2.57 Source Health + Performance Trends

LQoSync v2.57 adds a read-only Health Trends center. It summarizes PPPoE/DHCP/Hotspot source health, RouterOS API timing, full sync timing, LibreQoS apply health, and internal notification candidates. The goal is to make operational health visible before problems become production-impacting. Telegram delivery is planned separately so credentials, testing, and alert rules can be handled safely.


## v2.57.1 Dashboard Health Consolidation

Source Health and Performance Trends are now shown directly on the Dashboard instead of a separate sidebar page. This avoids duplicate monitoring surfaces and keeps the Dashboard as the single operator landing page for source health, RouterOS API timing, LibreQoS apply health, and internal notification candidates. The `/api/health/trends` endpoint remains available for JSON diagnostics, and `/health` redirects to the Dashboard health section for compatibility.


## v2.58 Telegram Notifications

LQoSync v2.58 adds optional Telegram delivery for internal notification candidates generated by source health, performance trends, LibreQoS apply health, and policy/confirmation workflows. Telegram is disabled by default and can be configured from the new Notifications page. Operators can save bot token/chat ID, choose notification levels, use digest delivery, test Telegram delivery, and send current Dashboard health alerts.

Telegram delivery includes minimum interval and dedupe-window controls to reduce noise. Bot tokens are secrets stored in `config.json`, so protect file permissions and avoid sharing raw config screenshots.
