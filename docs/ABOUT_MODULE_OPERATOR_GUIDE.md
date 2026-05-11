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
