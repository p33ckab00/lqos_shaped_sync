# LQoSync Full Documentation

## 1. Overview

**LQoSync** is a standalone, database-free dashboard and service for syncing live MikroTik subscriber/client/session data into LibreQoS.

Technical name:

```text
lqos_shaped_sync
```

Main purpose:

```text
Live QoS Subscriber Sync for LibreQoS
```

Core flow:



## Final path convention

LQoSync uses this final path layout:

```text
/opt/libreqos/                    # LibreQoS application folder
/opt/libreqos/src/config.json      # LQoSync config consumed by the engine
/opt/libreqos/src/ShapedDevices.csv# generated LibreQoS shaped devices output
/opt/libreqos/src/network.json     # generated LibreQoS network topology output
/opt/lqosync/                      # LQoSync app/runtime folder
/opt/lqosync/users.json            # UI users with bcrypt password hashes
/opt/lqosync/state/                # scheduler/runtime state and locks
/opt/lqosync/logs/                 # audit and LibreQoS apply logs
/opt/lqosync/backups/              # pre-apply and restore backups
```

The systemd service name and Docker container name remain `lqos_shaped_sync` for compatibility, but the application/runtime directory is now `/opt/lqosync`.

```text
MikroTik RouterOS API
    ↓ read-only
LQoSync Engine
    ↓ generates
ShapedDevices.csv + network.json
    ↓ applies
LibreQoS.py --updateonly
```

LQoSync is not a billing system, not an ISP Manager, and not a subscriber database. It is a web-controlled, production-ready version of the MikroTik-to-LibreQoS sync workflow.

---

## 2. Source of Truth

LQoSync has no database.

Source of truth:

```text
MikroTik live state + /opt/libreqos/src/config.json
```

Generated outputs:

```text
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

Runtime files:

```text
/opt/lqosync/users.json
/opt/lqosync/state/runtime_state.json
/opt/lqosync/backups/
/opt/lqosync/logs/
```

---

## 3. What LQoSync Reads From MikroTik

LQoSync is read-only to MikroTik.

Allowed RouterOS resources:

```text
/ppp/secret
/ppp/active
/ppp/profile
/ip/hotspot/active
/ip/dhcp-server/lease
/ip/dhcp-server      # discovery/config helper only
```

Recommended MikroTik API policy:

```text
read, api
```

Do not give write/reboot/policy permissions.

---

## 4. Core Engine Logic

The engine follows the original updatecsv.py workflow:

1. read config
2. read current CSV
3. read current network JSON
4. connect to routers
5. process PPPoE
6. process Hotspot
7. process DHCP
8. cleanup inactive non-static rows if router processing succeeded
9. render proposed files
10. compare current vs proposed files
11. backup existing files if changed
12. write files atomically
13. call LibreQoS only if files changed
14. update runtime state and logs

---

## 5. PPPoE Features

PPPoE mode reads:

```text
/ppp/secret
/ppp/active
/ppp/profile
```

Inclusion rule:

```text
PPP secret must exist
PPP active session must exist
secret disabled=false
secret inactive=false
```

Speed priority:

1. PPP secret comment
2. PPP active comment
3. PPP profile comment
4. PPP profile rate-limit
5. speed from PPP profile name
6. default PPPoE rate from config

Supported speed formats:

```text
Juan|15M/15M|0917
15M/15M
25M
Tier-15M
Business-50M
```

Node modes:

```text
per_plan_node=true  → Tier-15M-RB5k9-Distro, Tier-25M-RB5k9-Distro
per_plan_node=false → PPP-RB5k9-Distro
```

Factor rules are configurable in config.json and Config Center.

---

## 6. DHCP Features

DHCP mode reads:

```text
/ip/dhcp-server/lease
```

Each DHCP server can be included or excluded.

Example:

```json
{
  "name": "LAN",
  "enabled": true,
  "mode": "per_site",
  "default_plan_down_mbps": 15,
  "default_plan_up_mbps": 15,
  "download_factor": 0.3,
  "upload_factor": 0.3
}
```

If `enabled=false`:

```text
server is skipped
no leases processed
no node generated
no CSV rows generated
```

DHCP modes:

```text
per_site → one node per DHCP server
per_plan → group leases by plan parsed from lease comment
```

Per-site node example:

```text
DHCP-LAN-RB5k9-Distro
```

Per-plan node example:

```text
PLAN-DHCP-15M-RB5k9-Distro
```

---

## 7. Hotspot Features

Hotspot mode reads:

```text
/ip/hotspot/active
```

Configurable options:

```text
enabled
include_mac
download_limit_mbps
upload_limit_mbps
download_factor
upload_factor
node_name
node_type
```

Node example:

```text
HS-RB5k9-Distro
```

---

## 8. Network Layout

LQoSync uses router-as-root topology.

Example:

```text
RB5k9-Distro
 ├─ DHCP-LAN-RB5k9-Distro
 ├─ DHCP-LibreQoEMgt-RB5k9-Distro
 ├─ DHCP-Wifi5Soft-RB5k9-Distro
 ├─ Tier-15M-RB5k9-Distro
 ├─ Tier-25M-RB5k9-Distro
 └─ Tier-50M-RB5k9-Distro
```

Network Layout page features:

```text
router root card
node cards
source filters: All, PPPoE plan, DHCP site, Hotspot
bandwidth bars
math display: users × speed × factor
Advanced JSON View button
copy JSON button
```

---

## 9. Shaped Devices Page

Shows rows from `ShapedDevices.csv`.

Features:

```text
search
filters: All, PPP, DHCP, Hotspot, Static, Duplicate IP
sortable table
badges
row details
Speed source column
export CSV
```

CSV fields:

```text
Circuit ID
Circuit Name
Device ID
Device Name
Parent Node
MAC
IPv4
IPv6
Download Min Mbps
Upload Min Mbps
Download Max Mbps
Upload Max Mbps
Comment
```

Rows with comment `static` are preserved during cleanup.

---

## 10. Config Center

Config Center is a UI editor for `/opt/libreqos/src/config.json`.

Editable sections:

```text
App settings
Paths
LibreQoS runner
Scheduler
Defaults
Preflight policies
Routers
PPPoE settings
DHCP settings
Hotspot settings
Raw JSON advanced editor
```

Everything visible in Config Center maps back to config.json.

---

## 11. Scheduler

Scheduler can be enabled/disabled from UI.

Config values:

```text
active_interval_seconds
idle_interval_seconds
error_retry_interval_seconds
apply_cooldown_seconds
max_instances
```

Safety:

```text
no overlapping sync cycles
no overlapping LibreQoS update
skip run if already running
```

---

## 12. Dry Run Preview

Dry run performs a full scan and generation, but:

```text
does not write files
does not call LibreQoS
```

Shows:

```text
added circuits
updated circuits
removed circuits
added nodes
updated nodes
removed nodes
warnings/errors
whether CSV would change
whether network.json would change
whether LibreQoS would run
```

---

## 13. Backup and Restore

Before every apply, LQoSync backs up current files:

```text
/opt/lqosync/backups/<timestamp>/
 ├─ ShapedDevices.csv
 ├─ network.json
 └─ metadata.json
```

Installer also backs up existing files before initial overwrite:

```text
/opt/lqosync/install_backups/<timestamp>/
```

Backups can be restored from the UI.

---

## 14. LibreQoS Runner

LQoSync calls:

```text
/opt/libreqos/src/LibreQoS.py --updateonly
```

Rules:

```text
only if files changed
never during dry-run
never overlap multiple LibreQoS updates
capture stdout/stderr/exit code
show result in dashboard/logs
```

---

## 15. UI Theme

LQoSync supports:

```text
Light mode
Dark mode
```

Light mode is default. Theme preference is saved in browser localStorage.

---

## 16. Installation Options

LQoSync supports two installation styles:

1. Docker Compose host-integrated install
2. Bare-metal Ubuntu/Debian install using systemd

Read:

```text
DOCKER_INSTALL.md
BARE_METAL_INSTALL.md
INSTALLATION.md
```

---

## 17. Production Safety Checklist

Before enabling scheduler:

```text
old updatecsv.service disabled
config.json reviewed
MikroTik API test successful
dry-run output reviewed
manual sync successful
LibreQoS update successful
backup directory writable
```

---

## 18. Default Login

```text
admin / adminpass
```

Change immediately after install.

Docker:

```bash
sudo docker exec -it lqos_shaped_sync sh -lc "USERS_PATH=/opt/lqosync/users.json python /app/scripts/set_password.py admin 'new-password' admin"
```

Bare-metal:

```bash
sudo USERS_PATH=/opt/lqosync/users.json /opt/lqosync/venv/bin/python /opt/lqosync/scripts/set_password.py admin 'new-password' admin
```

---

## Network Layout Modes

LQoSync supports three `network_mode` values. The selected mode controls both `ShapedDevices.csv` Parent Node assignment and generated `network.json`.

### 1. `router_children`

This is the default and matches the original production `updatecsv.py` style.

```text
RB5k9-Distro
 ├─ Tier-15M-RB5k9-Distro
 ├─ Tier-25M-RB5k9-Distro
 ├─ DHCP-LAN-RB5k9-Distro
 └─ HS-RB5k9-Distro
```

Generated rows point to child nodes:

```text
PPP user       -> Tier-15M-RB5k9-Distro
DHCP LAN lease -> DHCP-LAN-RB5k9-Distro
Hotspot user   -> HS-RB5k9-Distro
```

Config compatibility flags are normalized to:

```json
{
  "network_mode": "router_children",
  "flat_network": false,
  "no_parent": false
}
```

### 2. `flat_router_root`

This mode keeps a router root in `network.json`, but does not generate PPPoE/DHCP/Hotspot child nodes. Every generated circuit uses the router name as Parent Node.

```text
RB5k9-Distro
 ├─ all PPPoE users
 ├─ all DHCP leases
 └─ all Hotspot users
```

Generated rows use:

```text
Parent Node = RB5k9-Distro
```

Generated `network.json` contains only router roots:

```json
{
  "RB5k9-Distro": {
    "children": {},
    "downloadBandwidthMbps": 115,
    "uploadBandwidthMbps": 115,
    "type": "site",
    "virtual": false
  }
}
```

Config compatibility flags are normalized to:

```json
{
  "network_mode": "flat_router_root",
  "flat_network": true,
  "no_parent": false
}
```

### 3. `flat_no_parent`

This is the pure flat mode. LQoSync still reads MikroTik and generates `ShapedDevices.csv`, but generated rows have blank Parent Node.

Generated rows use:

```text
Parent Node = ""
```

Generated `network.json` is empty by default:

```json
{}
```

If an operator wants to preserve an existing external `network.json`, set:

```json
{
  "preserve_network_config": true
}
```

Config compatibility flags are normalized to:

```json
{
  "network_mode": "flat_no_parent",
  "flat_network": true,
  "no_parent": true
}
```

### Config Center Behavior

The Config Center exposes a Network Layout Mode dropdown. When changed, it automatically updates:

```text
network_mode
flat_network
no_parent
```

It does not delete old PPPoE/DHCP/Hotspot node settings. Those settings are kept so an operator can switch back to hierarchy mode without rebuilding the config.

# Services, Journals, and Timing Metrics

LQoSync has a Services & Journals page for monitoring the LQoSync service, LibreQoS-related systemd units, and the LibreQoS apply command.

## Systemd Services vs LibreQoS Apply Command

Systemd services are long-running units such as:

```text
lqosd
lqos_scheduler
lqos_node_manager
lqos_shaped_sync
```

`LibreQoS.py --updateonly` is not treated as a daemon. It is an apply hook that LQoSync runs after `ShapedDevices.csv` or `network.json` changes. LQoSync captures stdout, stderr, exit code, and elapsed time for each apply run.

## Restart Groups

The default config includes restart groups:

```json
"services": {
  "restart_groups": {
    "libreqos_core": ["lqosd", "lqos_scheduler"],
    "libreqos_standard": ["lqosd", "lqos_scheduler", "lqos_node_manager"]
  }
}
```

The `libreqos_core` group is equivalent to:

```bash
sudo systemctl restart lqosd lqos_scheduler
```

On systems using different LibreQoS unit names, edit `services.units` and `services.restart_groups` in `config.json`.

## Journal Viewer

LQoSync can show journal logs for allowlisted services. Bare-metal installs read journal logs through `journalctl`. Docker host-integrated installs use `nsenter` to read the host journal.

Examples:

```bash
journalctl -u lqosd -n 100 --no-pager
journalctl -u lqos_scheduler -n 100 --no-pager
journalctl -u lqos_shaped_sync -n 100 --no-pager
```

## Timing Metrics

Every sync/dry-run cycle records elapsed time per process step. Dashboard and Services pages show:

```text
Cycle Total
MikroTik Scan
CSV Render
network.json Render
Diff
Backup
CSV Write
network.json Write
LibreQoS Apply
```

Detailed timeline data is also available at:

```text
GET /api/performance/last-cycle
```

## LibreQoS Apply Logs

Each `LibreQoS.py --updateonly` run writes files to:

```text
/opt/lqosync/logs/libreqos_apply/
```

Each run has:

```text
<run_id>.json
<run_id>.stdout.log
<run_id>.stderr.log
```

These logs are displayed in the Services & Journals page.


## LibreQoS service status check

```bash
sudo systemctl status lqosd lqos_scheduler
```


## User Settings UI

LQoSync includes an admin-only **Settings → User settings** page for local login management.

Features:

- add users
- edit username
- change role (`admin` / `viewer`)
- change password
- delete users

Storage remains file-based. Users are saved in:

```text
/opt/lqosync/users.json
```

Passwords are saved as bcrypt hashes, never plain text. The UI prevents deleting the current logged-in user, deleting the last admin, or demoting the last admin.

## About Module

The web UI includes an About module at `/about` and in the sidebar under **Help → About**. It is an in-app operator manual that summarizes the project description, workflow, feature modules, network modes, Docker installation, bare-metal installation, requirements, important file paths, operator commands, and safety notes.

Use it when handing the tool to an operator who needs a quick, readable reference without opening the Markdown files on disk.


---

## Uninstall Reference

For complete Docker, bare-metal, and Git-based uninstall steps, see:

```text
UNINSTALLATION.md
```


---

## Git Installation Reference

For installing from GitHub using Docker or bare-metal Ubuntu, see:

```text
GIT_INSTALL.md
```


## Troubleshooting

### Bare-metal permission denied on config.json.tmp

If Config Center, DHCP Discovery, or config save fails with:

```text
Permission denied: /opt/libreqos/src/config.json.tmp
```

This means the `lqosync` service user cannot create atomic-write temp files inside `/opt/libreqos/src`. LQoSync writes `config.json`, `ShapedDevices.csv`, and `network.json` using a temp-file-then-rename flow, so the user needs write access to the parent directory as well as the files.

The installer now applies this automatically. To repair an existing install manually:

```bash
sudo systemctl stop lqos_shaped_sync

sudo apt update
sudo apt install -y acl

sudo setfacl -m u:lqosync:rwx /opt/libreqos/src
sudo setfacl -m u:lqosync:rw /opt/libreqos/src/config.json
sudo setfacl -m u:lqosync:rw /opt/libreqos/src/ShapedDevices.csv
sudo setfacl -m u:lqosync:rw /opt/libreqos/src/network.json
sudo setfacl -d -m u:lqosync:rwX /opt/libreqos/src

sudo systemctl start lqos_shaped_sync
```

Test the permission fix:

```bash
sudo -u lqosync touch /opt/libreqos/src/config.json.tmp
sudo -u lqosync rm -f /opt/libreqos/src/config.json.tmp
```

If there is no error, retry the action in the web UI.


## LQoSync apply policy and pending apply recovery

LQoSync treats file generation and LibreQoS apply as two separate stages. A successful write of `ShapedDevices.csv` or `network.json` must be followed by a successful `LibreQoS.py --updateonly` run before the changes are considered fully applied.

Production policy:

1. Dry Run Preview never writes files and never runs LibreQoS.
2. Scheduled sync and manual sync are non-dry-run cycles. If generated files change, LQoSync writes the files and immediately runs `LibreQoS.py --updateonly`.
3. `LibreQoS.py` is executed from `/opt/libreqos/src` through `libreqos.working_dir` because LibreQoS uses some relative file references internally.
4. If LibreQoS apply fails after files were written, LQoSync marks `pending_libreqos_apply=true` in runtime state. The next non-dry-run cycle retries LibreQoS apply even when `files_changed=false`.
5. When scheduler auto-apply is enabled, the dashboard disables manual Run Sync Now to avoid overlapping operator-triggered applies. Use Dry Run for preview or disable the scheduler before manual sync.
6. Services & Journals includes Force LibreQoS Apply for applying current files immediately without requiring a file diff.

Recommended config block:

```json
"libreqos": {
  "cmd": "/opt/libreqos/src/LibreQoS.py",
  "args": ["--updateonly"],
  "working_dir": "/opt/libreqos/src",
  "run_only_when_files_changed": true,
  "retry_if_last_apply_failed": true,
  "sudo": true,
  "timeout_seconds": 300
}
```



## Upgrade note: config migration is automatic

Starting v2.23.0, installs and updates automatically normalize the existing `/opt/libreqos/src/config.json` while preserving operator values. This means upgrade-required defaults such as:

```json
"libreqos": {
  "working_dir": "/opt/libreqos/src",
  "retry_if_last_apply_failed": true
}
```

are added by `install.sh` or `docker-entrypoint.sh` even when using `LQOSYNC_INIT_POLICY=preserve_existing`. This avoids manual edits after update and ensures `LibreQoS.py --updateonly` runs from `/opt/libreqos/src`.

## Config Center and LibreQoS apply policy

The Config Center is the web UI for `config.json`. It now includes a dashboard-style Apply Policy section for the LibreQoS runner. Operators should keep `libreqos.working_dir` set to `/opt/libreqos/src` so that `LibreQoS.py --updateonly` can read LibreQoS relative files such as `ShapedDevices.lastLoaded.csv` correctly.

The production apply rule is:

- Dry-run: scan and preview only; no file write and no LibreQoS apply.
- Scheduled/manual non-dry-run: write changed files and immediately run LibreQoS.py when `app.auto_apply=true`.
- Failed apply recovery: if files were written but LibreQoS.py failed, LQoSync marks a pending apply and retries even when the next scan sees `files_changed=false`.

The installer and Docker entrypoint run `scripts/migrate_config.py` to add missing keys such as `libreqos.working_dir` and `libreqos.retry_if_last_apply_failed` without resetting router credentials or operator settings.


### Bare-metal LibreQoS runner policy

Bare-metal/systemd installs must run LibreQoS directly, not through Docker `nsenter`. The installer now normalizes `/opt/libreqos/src/config.json` and `/opt/lqosync/.env` so these settings are present after every update:

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

If you see `nsenter: cannot open /proc/1/ns/ipc: Permission denied` on a bare-metal install, update and reinstall with preserve mode:

```bash
cd /opt/lqosync
sudo git pull origin main
sudo systemctl stop lqos_shaped_sync
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
sudo systemctl start lqos_shaped_sync
```

Then confirm:

```bash
grep -A12 '"libreqos"' /opt/libreqos/src/config.json
grep -E 'LQOSYNC_RUN_MODE|HOST_CONTROL_MODE|LQOSYNC_INSTALL_MODE|LQOSYNC_FORCE_DIRECT' /opt/lqosync/.env
```


## v2.26 Note: Fresh Install Config Template and Startup Migration

Fresh installations are based on `config.json.example`. This template must always include the production-safe LibreQoS apply settings below:

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

`working_dir` is required because LibreQoS.py uses some relative filenames internally, including `ShapedDevices.lastLoaded.csv`. On bare-metal/systemd installations, `run_mode` must be `direct`; `host_nsenter` is Docker-only.

LQoSync also normalizes config at application startup. This means a `git pull` followed by `systemctl restart lqos_shaped_sync` can still persist missing safe defaults into `/opt/libreqos/src/config.json`, even when `install.sh` is not re-run.


### Troubleshooting: LibreQoS says `ShapedDevices.csv` not found

If LQoSync logs show `FileNotFoundError: ShapedDevices.csv` while manual execution succeeds from `/opt/libreqos/src`, the LibreQoS apply command is being launched from the wrong working directory. Ensure the live config contains:

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

Then restart bare-metal LQoSync:

```bash
sudo systemctl restart lqos_shaped_sync
journalctl -u lqos_shaped_sync -f
```

LQoSync v2.27+ also enforces the effective working directory at runtime and records it in each LibreQoS apply log metadata.


## LibreQoS service compatibility note

`lqos_node_manager` is legacy/optional. Older LibreQoS installs may use it as a separate Web UI service, while newer installs commonly expose the Web UI through `lqosd`. LQoSync now treats `lqos_node_manager` as optional and auto-hides it when it is not installed. The primary service health check remains `sudo systemctl status lqosd lqos_scheduler`.


### Mobile-responsive UI

LQoSync includes a mobile-responsive layout for phones and tablets. The top navigation exposes a mobile drawer, dashboard cards stack vertically, tables support horizontal swipe scrolling, and Config Center modules become touch-friendly horizontal tabs on small screens.


## Restore LibreQoS Permissions After Uninstall

Bare-metal LQoSync adds ACL permissions so the `lqosync` service user can atomically write temporary files in `/opt/libreqos/src`, for example `config.json.tmp`, `ShapedDevices.csv.tmp`, and `network.json.tmp`. When uninstalling LQoSync, restore those permissions so LibreQoS is returned to a normal root-owned state.

Recommended managed restore:

```bash
sudo bash /opt/lqosync/scripts/restore_libreqos_permissions.sh --managed
```

This removes ACL entries for `lqosync` and restores root ownership on:

```text
/opt/libreqos/src
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

It also applies conservative permissions:

```text
/opt/libreqos/src                       root:root 755
/opt/libreqos/src/config.json           root:root 600
/opt/libreqos/src/ShapedDevices.csv     root:root 644
/opt/libreqos/src/network.json          root:root 644
```

Optional full restore, only if you intentionally want every file under LibreQoS src returned to root ownership:

```bash
sudo bash /opt/lqosync/scripts/restore_libreqos_permissions.sh --full
```

The restore script saves an ACL backup in `/root/lqosync_libreqos_acl_backup_<timestamp>.acl` when `getfacl` is available.


## Bare-metal Uninstall Helper

From `/opt/lqosync`, you can use the bundled helper:

```bash
cd /opt/lqosync
sudo bash uninstall.sh
```

To also remove `/opt/lqosync` after backup:

```bash
cd /opt/lqosync
sudo REMOVE_RUNTIME=true bash uninstall.sh
```

The helper stops/removes `lqos_shaped_sync`, removes sudoers entries, restores LibreQoS ACL/ownership for managed files, and optionally removes the runtime folder.

## Fresh LibreQoS Install and Existing File Safety

LQoSync can be installed on a newly installed LibreQoS server even when these files do not exist yet:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

During installation, the installer checks each managed LibreQoS file before writing anything.

### If the files are missing

For a fresh LibreQoS system, LQoSync creates the missing files from bundled templates:

```text
config.json.example          -> /opt/libreqos/src/config.json
ShapedDevices.csv.example    -> /opt/libreqos/src/ShapedDevices.csv
network.json.example         -> /opt/libreqos/src/network.json
```

This allows a fresh LibreQoS installation to become LQoSync-ready without manual file creation.

### If the files already exist

For an existing or live LibreQoS system, the installer now stops and asks what the operator wants to do when running interactively:

```text
[P] Preserve existing files and create only missing files  (recommended for live systems)
[O] Backup and overwrite existing files from LQoSync templates
[M] Create missing files only; do not touch existing files
[A] Abort install
```

For non-interactive installation, existing files are preserved by default. To explicitly overwrite, set:

```bash
sudo LQOSYNC_INIT_POLICY=overwrite_with_backup bash install.sh
```

Available policies:

```text
smart_confirm          default; create missing on fresh installs, confirm/preserve when files exist
overwrite_with_backup  backup existing files, then replace with LQoSync templates
preserve_existing      keep existing files, create missing files only
create_missing_only    only create files that do not exist
```

Recommended for production updates:

```bash
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
```

Recommended for a fresh LibreQoS server:

```bash
sudo bash install.sh
```

The default `smart_confirm` mode will create the required files if they are missing.


---

## MikroTik Setup Requirement

LQoSync is read-only against MikroTik. Before running live sync, create a dedicated RouterOS API group and user for LQoSync. This is an **Important Notice** / setup prerequisite for fresh installations.

Replace `<Strong Password>` and `<LibreQoS IP Address>` before pasting into MikroTik Terminal:

```rsc
/user group add name=API_READ policy="read,sensitive,api,!policy,!local,!telnet,!ssh,!ftp,!reboot,!write,!test,!winbox,!password,!web,!sniff,!romon"
/user add name="libreqosyncAPI" group=API_READ password="<Strong Password>" address="<LibreQoS IP Address>" disabled=no
```

Use the same credentials in `/opt/libreqos/src/config.json`:

```json
{
  "routers": [
    {
      "username": "libreqosyncAPI",
      "password": "<Strong Password>",
      "address": "<MikroTik IP>",
      "port": 8728
    }
  ]
}
```

This user can read the RouterOS API resources required by LQoSync while blocking write, reboot, policy, shell, web, Winbox, sniffing, and other unnecessary access. Limit the `address=` field to the LibreQoS/LQoSync server IP whenever possible.

> Note: Some RouterOS deployments may not need `sensitive` for the fields LQoSync reads. If your router still exposes the required PPPoE/profile/session fields with `read,api` only, you may remove `sensitive`; otherwise keep the policy above for maximum compatibility while still denying write/reboot/policy access.


### Audit Events and Client Change Timeline

LQoSync records client-level change summaries when ShapedDevices.csv changes. Audit entries include the affected client/circuit name, speed, parent node, source type, changed fields, and elapsed process timings. The Dashboard Last Sync Timeline displays compact info bits for recent client changes, while Logs & Backups provides a filterable Audit Events table for deeper review.


## Table View Limits

LQoSync table views now include selectable row limits. Audit Events and Shaped Devices can display 25, 50, 100, 200, 300, 400, or 500 visible rows at a time. Filtering and sorting still run against the full dataset, but only the selected number of visible rows is rendered to keep the UI responsive and prevent large tables from overflowing the page.

## GitHub Source Install and Smart Updates

LQoSync supports GitHub-based installation and updates. This does **not** require GitHub CLI (`gh`); it only requires the standard `git` command.

Fresh install from GitHub:

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

Production-safe update from GitHub:

```bash
cd /opt/lqosync
sudo bash upgrade.sh
```

Default update policy is `preserve_and_migrate`, which preserves live operator files:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
/opt/lqosync/users.json
/opt/lqosync/.env
```

Advanced update policies:

```bash
sudo UPDATE_POLICY=pull_only bash upgrade.sh
sudo UPDATE_POLICY=code_only bash upgrade.sh
sudo UPDATE_POLICY=preserve_and_migrate bash upgrade.sh
sudo UPDATE_POLICY=refresh_with_backup bash upgrade.sh
sudo UPDATE_POLICY=factory_reset CONFIRM_FACTORY_RESET=yes bash upgrade.sh
```

See `docs/GITHUB_INSTALL.md` for the full Git source install and update guide.


## Smart Existing Install Adoption

The GitHub source installer can now safely process existing LQoSync installations, regardless of whether they were created from a ZIP package, manual copy, Git clone, Docker version, bare-metal version, or partial/broken install.

Use:

```bash
sudo EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh
```

or interactive mode:

```bash
sudo bash /tmp/install-lqosync.sh
```

Full details are preserved as-is in `docs/EXISTING_INSTALL_ADOPTION.md`.

---

# In-App About Module and Operator Guide

The LQoSync dashboard includes an **About** module that acts as a built-in operator manual. The About module should be treated as part of the official documentation, not as static marketing text.

It now includes:

- Project description and safety model.
- Full sync workflow.
- LibreQoS apply policy and `working_dir` explanation.
- Feature/module list.
- Network layout modes.
- Fresh installation guide.
- Existing install adoption flow.
- GitHub update and preservation policies.
- Uninstall and permission restore workflow.
- MikroTik API setup requirement.
- Important runtime paths.
- Operator command reference.
- Atomic troubleshooting guide with expected outcomes.

The complete Markdown version is available at:

```text
docs/ABOUT_MODULE_OPERATOR_GUIDE.md
```

When the project changes, update these files together:

```text
README.md
FULL_DOCUMENTATION.md
INSTALLATION.md
BARE_METAL_INSTALL.md
DOCKER_INSTALL.md
UNINSTALLATION.md
docs/*.md
RELEASE_NOTES.md
templates/about.html
```


## v2.38 Selective MikroTik Collection

LQoSync now supports selective RouterOS property reads, a universal speed resolver, metadata-cache tracking, Hotspot enhanced metadata reads, source-aware cleanup, and richer Dashboard collector monitoring.

Key rules:

```text
PPPoE speed: secret comment -> active comment -> profile comment -> profile name -> profile rate-limit -> default
DHCP speed: DHCP server comment/speed_comment -> DHCP server name -> server config speed -> global default
Hotspot speed: user comment -> profile comment -> profile name -> profile rate-limit -> hotspot config -> default
```

See `docs/SELECTIVE_COLLECTION.md` and the in-app About module for the full operator guide.


## v2.39 Operations Dashboard UX

The Dashboard has been expanded into a production operations cockpit. It now groups information by operator question instead of showing unrelated counters.

### Health and attention

The System Health card combines config errors, sync errors, router errors, warnings, and pending LibreQoS apply state. A healthy state means the last sync completed without errors and no pending apply retry is waiting.

### Apply Decision

The Apply Decision panel explains exactly why LibreQoS was or was not triggered. Examples:

```text
files_changed              -> generated CSV/network changed, so LibreQoS.py ran
retry_pending_failed_apply -> a previous apply failed after file writes, so LQoSync retried
force_apply                -> operator forced LibreQoS.py --updateonly
dry_run                    -> preview only; no writes and no apply
auto_apply_disabled        -> files may be written, but automatic apply is disabled
no_changes                 -> generated files match current files, so LibreQoS.py was skipped
```

This prevents confusion when `files_changed=false` and `libreqos_triggered=false` are correct behavior.

### Performance Breakdown

The dashboard now shows where cycle time is spent:

```text
MikroTik API       -> RouterOS connection and selected property reads
Build / diff       -> CSV/network render and comparison
File writes        -> atomic write time for changed files
LibreQoS apply     -> LibreQoS.py --updateonly runtime
```

If MikroTik API dominates, tune selective collection, cache behavior, and source size. If LibreQoS apply dominates, reduce unnecessary writes and allow apply debounce/cooldown to combine changes.

### Data Source Status

The PPPoE/DHCP/Hotspot source cards show source-specific counts, metadata reads, generated rows, and timing. This helps identify whether PPP secrets, DHCP leases, or Hotspot profiles are the bottleneck.

### Cleanup Safety

The Cleanup Safety card makes source-aware cleanup visible. Rows are removed only for sources that scanned successfully. If a DHCP scan fails, old DHCP rows are preserved instead of mass-deleted.

### Recent Client Change Feed

The dashboard shows the most recent client changes directly: added, updated, removed, speed, parent node, speed source, and changed fields. Detailed history remains in Logs & Backups → Audit Events.

### Git and version visibility

The Dashboard now exposes Git-managed state: branch, commit, dirty worktree, and upstream relation. This helps operators detect `behind`, `ahead`, or `diverged` install states before running a GitHub update.


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


# v2.42 Privacy UX + Topology Save Fix

This release improves Network Layout usability and screenshot safety. The Topology Tree is wider, the Visual Topology area gives up space proportionally, and the Node Inspector remains stable. Privacy Mode replaces visible sensitive values with stable labels rather than blur effects. The topology save action now uses the same CSRF protection model as form-based writes, preventing stale or missing security tokens from silently failing.

Expected CSRF behavior: if the browser session token is valid, Save Topology writes `network.json` after validation. If the token is expired or missing, no file is modified and the UI asks the operator to refresh the page.


## v2.43 UI Polish and Git Update Detection

This release is a UI/UX polish update. It does not change the core sync engine.

### Privacy toggle

The topbar Privacy Mode control now uses an incognito-style icon. When privacy mode is disabled, the same icon is shown with a slash indicator. When privacy mode is enabled, the slash disappears and visible subscriber, node, IP, MAC, and ID values are replaced with stable redaction labels such as `Client-001`, `IP-001`, and `MAC-001`. This is browser-only redaction for screenshots and demos; source files are not modified.

### Services & Journals layout

The Services & Journals page now uses equal-height desktop panels for Journal Viewer and LibreQoS Apply Logs. The Journal Viewer output pane is larger, scrolls cleanly inside the card, and keeps controls aligned at the top. The apply log list uses a matching scroll area so the two panels feel balanced. On smaller screens, the panels stack vertically.

### Update Center detection

Update Center now performs a fresh `git fetch origin main` before comparing local and remote state. It compares local `HEAD` against the latest fetched `origin/main`, displays local and remote commits, reads the remote `VERSION` file using `git show origin/main:VERSION`, and shows whether an update is needed based on commit or version difference.

Update Center remains read-only. It displays safe SSH commands for updating, but it does not execute Git or upgrade actions from the browser.
