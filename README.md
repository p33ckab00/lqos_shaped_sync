# LQoSync / `lqos_shaped_sync`

**LQoSync** is a standalone, database-free, production-ready web dashboard and scheduler for syncing live MikroTik subscriber/session data into LibreQoS.

It gives a web UI, safety controls, dry-run preview, service monitoring, timing metrics, and Docker/bare-metal installation around the original `updatecsv.py` workflow.

```text
MikroTik RouterOS API
        ↓ read-only
LQoSync sync engine
        ↓ generated output
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
        ↓ apply hook
/opt/libreqos/src/LibreQoS.py --updateonly
        ↓
LibreQoS shaping refresh
```

## GitHub Project Description


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


Use this as the GitHub repository description:

```text
Database-free MikroTik-to-LibreQoS subscriber sync dashboard that generates ShapedDevices.csv/network.json with dry-run, scheduler, Docker, and service monitoring.
```

Suggested topics:

```text
libreqos mikrotik routeros qos shaping isp pppoe dhcp hotspot scheduler docker python flask
```

Suggested repository name:

```text
lqos_shaped_sync
```

---

## What This Project Is

LQoSync is **not** a billing system, subscriber CRM, or ISP Manager. It is a focused LibreQoS companion tool.

It does this:

1. Reads `config.json` from LibreQoS source path.
2. Reads existing `ShapedDevices.csv` to preserve `Circuit ID` and `Device ID`.
3. Reads existing `network.json` to build/update LibreQoS topology.
4. Connects to MikroTik using read-only RouterOS API credentials.
5. Reads PPPoE, DHCP, and Hotspot live data.
6. Generates/updates `ShapedDevices.csv`.
7. Generates/updates `network.json`.
8. Removes inactive generated rows, except static rows.
9. Writes files only when content changed.
10. Calls `LibreQoS.py --updateonly` only when files changed.
11. Shows status, logs, service health, journal logs, and timing metrics in the dashboard.

---

## Non-Negotiable Design Rules

| Rule | Meaning |
|---|---|
| No database | No PostgreSQL, MySQL, or SQLite for core state. |
| MikroTik read-only | LQoSync reads RouterOS API only; it never writes to MikroTik. |
| `config.json` driven | All settings are backed by `/opt/libreqos/src/config.json`. |
| File-based output | LibreQoS receives `ShapedDevices.csv` and `network.json`. |
| LibreQoS remains applier | LQoSync only calls `LibreQoS.py --updateonly`; it does not replace LibreQoS. |
| One sync at a time | Scheduler/manual/dry-run jobs are locked to prevent overlap. |
| Dry-run safety | Dry-run never writes files and never calls LibreQoS. |
| Backup before write | Current generated files are backed up before apply/restore. |

---

## Source of Truth

```text
MikroTik live state + /opt/libreqos/src/config.json = source of truth
```

LQoSync does not store subscribers in a database. Subscriber/session data comes from MikroTik at every sync cycle.

### RouterOS API resources read

LQoSync reads these resources only:

```text
/ppp/secret
/ppp/active
/ppp/profile
/ip/dhcp-server/lease
/ip/hotspot/active
/ip/dhcp-server       # for DHCP discovery UI only
```

### MikroTik setup requirement

For fresh installations, create a dedicated read-only RouterOS API group and user before enabling live sync. Use this as the recommended MikroTik Terminal setup:

```rsc
/user group add name=API_READ policy="read,sensitive,api,!policy,!local,!telnet,!ssh,!ftp,!reboot,!write,!test,!winbox,!password,!web,!sniff,!romon"
/user add name="libreqosyncAPI" group=API_READ password="<Strong Password>" address="<LibreQoS IP Address>" disabled=no
```

Then use `libreqosyncAPI` and its password in `/opt/libreqos/src/config.json`.

This gives LQoSync the required read/API access while denying write, reboot, policy, shell, web, Winbox, sniffing, and other unnecessary access. Limit the `address=` value to the LibreQoS/LQoSync server IP whenever possible.

> Note: Some RouterOS deployments can work with `read,api` only. If all required PPPoE/profile/session fields are visible without `sensitive`, you may remove `sensitive`; otherwise keep the policy above for compatibility while still denying dangerous write/admin actions.

---

## Main Files and Paths

### LibreQoS-managed files

| File | Purpose |
|---|---|
| `/opt/libreqos/src/config.json` | Main LQoSync configuration. |
| `/opt/libreqos/src/ShapedDevices.csv` | Generated LibreQoS shaped devices output. |
| `/opt/libreqos/src/network.json` | Generated LibreQoS network topology output. |
| `/opt/libreqos/src/LibreQoS.py` | LibreQoS update/apply command target. |

### LQoSync application files

| Path | Purpose |
|---|---|
| `/opt/lqosync/users.json` | Local UI users with bcrypt password hashes. |
| `/opt/lqosync/state/runtime_state.json` | Runtime scheduler/sync state. |
| `/opt/lqosync/logs/` | App logs, audit logs, LibreQoS apply logs. |
| `/opt/lqosync/backups/` | Runtime backups before apply/restore. |
| `/opt/lqosync/install_backups/` | Install-time backups when init policy overwrites files. |

---

## Features

### Dashboard

The dashboard is the operator cockpit for answering these production questions quickly:

```text
Is the system healthy?
Did MikroTik collection succeed?
Did generated files change?
Did LibreQoS.py run or skip, and why?
Who changed, what speed was applied, and which node was affected?
Where did the last cycle spend time?
Is cleanup safe?
Are Git/update and service states healthy?
```

The dashboard shows:

- System Health card with errors, warnings, and pending apply state.
- LibreQoS Apply card with trigger state, exit code, duration, and pending retry status.
- Scheduler card with enabled/disabled state and next run information.
- Source counters for PPPoE, DHCP, Hotspot, generated CSV rows, and network nodes.
- Apply Decision panel explaining why LibreQoS ran, skipped, retried, or was blocked by dry-run/auto-apply policy.
- Performance Breakdown with MikroTik API time, build/diff time, file write time, and LibreQoS apply time.
- Data Source Status for PPPoE, DHCP, and Hotspot collector counts and read timing.
- Last Sync Timeline with started time, status, file-change state, LibreQoS result, speed resolver summary, client changes, and process steps.
- Cleanup Safety card showing which source cleanups were allowed and how many rows were removed.
- Recent Client Change Feed showing affected clients, speed, parent node, and speed source.
- Speed Source Breakdown showing how many rows used comments, profile names, config speeds, or defaults.
- Generated Files and Drift Policy showing CSV/network change state, backup setting, and file drift behavior.
- Version/Git Status showing branch, commit, dirty state, and diverged/behind/ahead state.
- Services Snapshot for lqosd, lqos_scheduler, LQoSync, and optional legacy services.

Actions:

- Run Sync Now, only when scheduler auto-apply is not active.
- Dry Run Preview.
- Enable/disable scheduler.
- Navigate to Services & Journals, Logs & Backups, Shaped Devices, and Network Layout.

### Dry Run Preview

Dry-run uses the same engine as real apply, but:

```text
No file writes
No LibreQoS.py call
No destructive cleanup on disk
```

It previews:

- added circuits
- updated circuits
- removed circuits
- added nodes
- updated nodes
- removed nodes
- warnings/errors
- whether CSV would change
- whether `network.json` would change
- whether LibreQoS would run if applied

### Config Center

The Config Center is a UI-backed editor for `/opt/libreqos/src/config.json`.

Settings shown in UI are reflected in Advanced Raw JSON.

Config Center includes:

- app settings
- paths
- LibreQoS runner command
- scheduler settings
- preflight policies
- network layout mode
- router settings
- PPPoE settings
- DHCP server include/exclude
- DHCP per-site/per-plan settings
- Hotspot settings
- raw JSON advanced editor

### Network Layout

Network Layout shows generated `network.json` as router/node cards.

It supports:

- router-as-root cards
- PPPoE plan nodes
- DHCP site nodes
- Hotspot nodes
- bandwidth bars
- factor math display
- node filters
- Advanced JSON View button for raw `network.json`

### Shaped Devices

The Shaped Devices module shows generated CSV rows.

Features:

- full table view
- global search
- filter chips: All / PPP / DHCP / Hotspot / Static / Duplicate IP
- per-column filters for all visible headers
- sortable columns
- detail panel when clicking a device
- Speed source column
- Export CSV button

Columns include:

- Circuit Name
- Type
- Parent Node
- IPv4
- Download Max
- Upload Max
- Download Min
- Upload Min
- MAC
- Speed Source
- Status

### Services and Journals

This module monitors LQoSync and LibreQoS-related units.

Default service units:

```text
lqosd
lqos_scheduler
lqos_node_manager
lqos_shaped_sync
```

Correct LibreQoS status command:

```bash
sudo systemctl status lqosd lqos_scheduler
```

Default grouped restart exposed in UI as `libreqos_core`:

```bash
sudo systemctl restart lqosd lqos_scheduler
```

The page can show:

- service active/inactive/failed state
- per-service journal logs
- restart buttons for allowlisted services
- grouped restart buttons
- LibreQoS apply stdout/stderr
- last cycle performance timeline

### User Settings

Admin-only user manager.

Features:

- add user
- edit username
- change role: `admin` / `viewer`
- change password
- delete user

Users are saved in:

```text
/opt/lqosync/users.json
```

Passwords are bcrypt hashes only. Passwords are never shown in UI.

Safety rules:

- cannot delete current logged-in user
- cannot delete last admin
- cannot demote last admin
- users.json is written atomically

### Light/Dark Theme

Light mode is default.

Theme preference is stored in browser `localStorage`.

---

## Sync Engine Workflow

Every sync cycle follows this workflow:

```text
1. Read /opt/libreqos/src/config.json
2. Read /opt/libreqos/src/ShapedDevices.csv
3. Read /opt/libreqos/src/network.json
4. Normalize config/network mode flags
5. Connect to each enabled MikroTik router
6. Process PPPoE
7. Process Hotspot
8. Process DHCP
9. Build active code set
10. Cleanup inactive non-static generated rows only if router scan succeeded
11. Render proposed ShapedDevices.csv
12. Render proposed network.json
13. Compare current files vs proposed files
14. If unchanged: skip file write and skip LibreQoS apply
15. If changed: backup current files
16. Atomically write changed files
17. Call LibreQoS.py --updateonly
18. Store runtime state, logs, audit events, apply logs, and timing metrics
```

---

## PPPoE Logic

When PPPoE is enabled for a router, LQoSync reads:

```text
/ppp/secret
/ppp/active
/ppp/profile
```

It only processes PPPoE users where:

- secret exists
- active session exists
- secret is not disabled
- secret is not inactive

### PPPoE Speed Priority

Speed is resolved using this priority:

1. PPP secret comment
2. PPP active comment
3. PPP profile comment
4. PPP profile `rate-limit`
5. Speed parsed from profile name
6. `defaults.default_pppoe_rate`

Supported speed formats:

```text
Juan|15M/15M|0917
15M/15M
25M
Tier-15M
Business-50M
```

### PPPoE Parent Node

In default hierarchy mode:

```text
Parent Node = {profile}-{router}
```

Example:

```text
Tier-15M-RB5k9-Distro
```

### PPPoE Plan Factor Math

Example:

```text
17 active users × 15 Mbps × 0.31 = 79.05 Mbps
```

This becomes the plan node bandwidth in `network.json`.

---

## DHCP Logic

When DHCP is enabled, LQoSync reads:

```text
/ip/dhcp-server/lease
```

A lease is included when:

- lease server matches a configured DHCP server name
- lease has `mac-address`
- lease has `active-address` or `address`

### DHCP Server Include/Exclude

Each DHCP server entry supports:

```json
{
  "name": "LAN",
  "enabled": true,
  "mode": "per_site"
}
```

If `enabled: false`:

```text
server skipped completely
no leases processed
no node generated
no CSV rows generated
```

### DHCP per_site Mode

One node per DHCP server.

Example parent node:

```text
DHCP-LAN-RB5k9-Distro
```

Example bandwidth math:

```text
3 leases × 15 Mbps × 0.30 = 13.5 Mbps
```

### DHCP per_plan Mode

Speed is parsed from DHCP lease comment.

Example comment:

```text
ClientName|15M/15M|phone
```

Parent node example:

```text
PLAN-DHCP-15M-RB5k9-Distro
```

---

## Hotspot Logic

When Hotspot is enabled, LQoSync reads:

```text
/ip/hotspot/active
```

Parent node in hierarchy mode:

```text
HS-{router}
```

If `include_mac: true`:

```text
Circuit Name = HS-{MAC without colon}
```

If `include_mac: false`:

```text
Circuit Name = HS-{username}
```

---

## Network Modes

LQoSync supports three network layout modes.

### 1. `router_children` — Hierarchy Mode

Default mode. Router root with PPPoE/DHCP/Hotspot child nodes.

```text
RB5k9-Distro
 ├─ Tier-15M-RB5k9-Distro
 ├─ Tier-25M-RB5k9-Distro
 ├─ DHCP-LAN-RB5k9-Distro
 └─ HS-RB5k9-Distro
```

Config flags:

```json
{
  "network_mode": "router_children",
  "flat_network": false,
  "no_parent": false
}
```

### 2. `flat_router_root` — Flat Under Router Root

No child plan/DHCP/HS nodes. All generated devices point directly to router root.

```text
RB5k9-Distro
 ├─ CelynGallos
 ├─ DaisySeraspi
 ├─ DHCP-MeshLink
 └─ DHCP-POCO-C65
```

CSV behavior:

```text
Parent Node = RB5k9-Distro
```

Config flags:

```json
{
  "network_mode": "flat_router_root",
  "flat_network": true,
  "no_parent": false
}
```

### 3. `flat_no_parent` — Pure Flat Network

No parent node and generated `network.json` is empty unless preserved.

CSV behavior:

```text
Parent Node = blank
```

Config flags:

```json
{
  "network_mode": "flat_no_parent",
  "flat_network": true,
  "no_parent": true
}
```

### Config Normalization

When the user changes Network Layout Mode in Config Center, LQoSync normalizes the legacy flags automatically.

| UI Mode | `network_mode` | `flat_network` | `no_parent` |
|---|---|---:|---:|
| Router + child nodes | `router_children` | false | false |
| Flat under router root | `flat_router_root` | true | false |
| Flat no parent | `flat_no_parent` | true | true |

The normalizer should not destroy previous node settings. It only changes how the engine interprets them, so switching back to hierarchy restores prior PPP/DHCP/Hotspot node rules.

---

## Generated `ShapedDevices.csv`

LQoSync preserves LibreQoS field names exactly:

```csv
Circuit ID,Circuit Name,Device ID,Device Name,Parent Node,MAC,IPv4,IPv6,Download Min Mbps,Upload Min Mbps,Download Max Mbps,Upload Max Mbps,Comment
```

Rows are keyed by `Circuit Name`.

Existing rows preserve:

- `Circuit ID`
- `Device ID`

New rows receive generated short IDs.

Rows are sorted by:

```text
Parent Node
Circuit Name
Device Name
IPv4
MAC
```

### Min/Max Mbps Rule

Default:

```text
Max = resolved speed
Min = resolved speed × defaults.min_rate_percentage
```

Example with `min_rate_percentage = 0.5`:

```text
15 Mbps max → 7.5 Mbps min
25 Mbps max → 12.5 Mbps min
```

### Static Rows

Rows with:

```text
Comment = static
```

case-insensitive, are preserved during inactive cleanup.

---

## Generated `network.json`

In hierarchy mode, generated output follows router-as-root style:

```json
{
  "RB5k9-Distro": {
    "children": {
      "DHCP-LAN-RB5k9-Distro": {
        "children": {},
        "downloadBandwidthMbps": 13.5,
        "type": "site",
        "uploadBandwidthMbps": 13.5
      },
      "Tier-15M-RB5k9-Distro": {
        "children": {},
        "downloadBandwidthMbps": 79.05,
        "type": "plan",
        "uploadBandwidthMbps": 79.05
      }
    },
    "downloadBandwidthMbps": 115,
    "type": "site",
    "uploadBandwidthMbps": 115,
    "virtual": false
  }
}
```

---

## Timing and Performance Metrics

Every sync records elapsed time for major steps.

Tracked metrics include:

- config load
- CSV read/parse
- `network.json` read/parse
- MikroTik connection
- PPPoE processing
- DHCP processing
- Hotspot processing
- cleanup
- CSV render
- network render
- diff
- backup
- CSV write
- network write
- LibreQoS apply
- full cycle total

UI displays:

```text
Cycle Total
MikroTik Scan
Build Files
LibreQoS Apply Time
```

### Performance Goal

LQoSync itself should remain lightweight because it:

- uses no database
- performs bulk RouterOS reads
- writes only if changed
- calls LibreQoS only if files changed
- prevents overlapping sync cycles
- avoids repeated unnecessary `LibreQoS.py --updateonly` calls

The heavier operation is usually LibreQoS itself applying queue/qdisc changes.

---

## Docker Installation

### 1. Stop old updatecsv service

Do this before running LQoSync scheduler to avoid two writers touching the same files.

```bash
sudo systemctl disable --now updatecsv.service 2>/dev/null || true
```

### 2. Install Docker

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

Check:

```bash
docker --version
docker compose version
```

### 3. Extract package

```bash
cd /home/pi
unzip lqos_shaped_sync_v2_17_opt_lqosync.zip
cd lqos_docker
```

### 4. Configure secret key

Generate secret:

```bash
openssl rand -hex 32
```

Edit compose file:

```bash
nano compose.yaml
```

Set:

```yaml
SECRET_KEY: "paste-generated-secret-here"
```

### 5. Choose init policy

Default policy:

```yaml
LQOSYNC_INIT_POLICY: "overwrite_with_backup"
```

Meaning:

```text
If /opt/libreqos/src/config.json exists       → backup then overwrite with template
If /opt/libreqos/src/ShapedDevices.csv exists → backup then overwrite with template
If /opt/libreqos/src/network.json exists      → backup then overwrite with template
If missing                                    → create from template
```

Install-time backups go to:

```text
/opt/lqosync/install_backups/<timestamp>/
```

Safer option to preserve existing production files:

```bash
sudo docker compose -f compose.preserve-existing.yaml up -d --build
```

Or edit `compose.yaml`:

```yaml
LQOSYNC_INIT_POLICY: "preserve_existing"
```

Other supported values:

```text
overwrite_with_backup
preserve_existing
create_missing_only
```

### 6. Build and start

```bash
sudo docker compose up -d --build
```

### 7. Check container

```bash
sudo docker compose ps
sudo docker logs -f lqos_shaped_sync
```

### 8. Open UI

```text
http://<LibreQoS-server-IP>:9202
```

Example:

```text
http://172.27.185.15:9202
```

Default login:

```text
admin / adminpass
```

Change password immediately.

### 9. Change password in Docker

Using UI:

```text
Settings → User settings
```

Using command:

```bash
sudo docker exec -it lqos_shaped_sync sh -lc "USERS_PATH=/opt/lqosync/users.json python /app/scripts/set_password.py admin 'new-strong-password' admin"
```

### 10. Common Docker commands

```bash
# status
sudo docker compose ps
sudo docker ps -a | grep lqos

# logs
sudo docker logs -f lqos_shaped_sync
sudo docker logs --tail=120 lqos_shaped_sync

# restart
sudo docker compose restart

# stop
sudo docker compose down

# rebuild
sudo docker compose down
sudo docker compose build --no-cache
sudo docker compose up -d

# shell
sudo docker exec -it lqos_shaped_sync bash

# doctor
sudo docker exec -it lqos_shaped_sync python scripts/doctor.py
sudo docker exec -it lqos_shaped_sync python scripts/doctor.py --router-test
```

### 11. Docker restarting troubleshooting

Check:

```bash
cd /home/pi/lqos_docker
sudo docker compose ps
sudo docker logs --tail=120 lqos_shaped_sync
sudo docker inspect lqos_shaped_sync --format='Status={{.State.Status}} ExitCode={{.State.ExitCode}} RestartCount={{.RestartCount}} Error={{.State.Error}}'
```

Run foreground:

```bash
sudo docker compose down
sudo docker compose up --build
```

Common causes:

- Python import error
- missing helper function
- invalid `config.json`
- permission issue on mounted paths
- port 9202 conflict
- bad `users.json`

Validate JSON:

```bash
sudo python3 -m json.tool /opt/libreqos/src/config.json
sudo python3 -m json.tool /opt/lqosync/users.json
```

Check port:

```bash
sudo ss -tulpn | grep :9202 || true
```

---

## Bare-Metal Ubuntu Installation

Bare-metal install runs LQoSync directly as a systemd service on Ubuntu/Debian.

### 1. Stop old updatecsv service

```bash
sudo systemctl disable --now updatecsv.service 2>/dev/null || true
```

### 2. Extract package

```bash
cd /home/pi
unzip lqos_shaped_sync_v2_17_opt_lqosync.zip
cd lqos_docker
```

### 3. Run installer

Default install:

```bash
sudo bash install.sh
```

or:

```bash
sudo bash install-baremetal.sh
```

Safer preserve-existing install:

```bash
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
```

Create missing only:

```bash
sudo LQOSYNC_INIT_POLICY=create_missing_only bash install.sh
```

Overwrite with backup:

```bash
sudo LQOSYNC_INIT_POLICY=overwrite_with_backup bash install.sh
```

### 4. What installer does

The installer:

1. Installs Python, venv, pip, git, and required tools.
2. Creates Linux user `lqosync`.
3. Copies app files to `/opt/lqosync/`.
4. Creates Python virtualenv.
5. Installs Python requirements.
6. Creates `.env` if missing.
7. Creates `users.json` if missing.
8. Initializes `/opt/libreqos/src/config.json`, `ShapedDevices.csv`, and `network.json` based on init policy.
9. Creates backups/logs/state folders.
10. Sets permissions.
11. Installs sudoers rule for allowlisted commands.
12. Creates systemd service `lqos_shaped_sync.service`.
13. Enables and starts LQoSync.

### 5. systemd service

```bash
sudo systemctl status lqos_shaped_sync
sudo systemctl restart lqos_shaped_sync
sudo journalctl -u lqos_shaped_sync -f
```

### 6. Open UI

```text
http://<LibreQoS-server-IP>:9202
```

### 7. Bare-metal password reset

```bash
sudo USERS_PATH=/opt/lqosync/users.json /opt/lqosync/venv/bin/python /opt/lqosync/scripts/set_password.py admin 'new-strong-password' admin
```

---

## Git-Based Installation

You can install directly from GitHub instead of using a ZIP file.

Repository:

```text
https://github.com/p33ckab00/lqos_shaped_sync.git
```

### Clone

```bash
cd /home/pi
git clone https://github.com/p33ckab00/lqos_shaped_sync.git
cd lqos_shaped_sync
```

### Docker from Git

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git
sudo systemctl enable --now docker
sudo LQOSYNC_INIT_POLICY=preserve_existing docker compose up -d --build
sudo docker logs -f lqos_shaped_sync
```

Open:

```text
http://<LibreQoS-server-IP>:9202
```

### Bare-metal from Git

```bash
cd /home/pi/lqos_shaped_sync
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
sudo systemctl status lqos_shaped_sync
journalctl -u lqos_shaped_sync -f
```

Full Git installation guide:

```text
GIT_INSTALL.md
```

---

## Updating Existing Installation

### Docker update

```bash
cd /home/pi
unzip -o lqos_shaped_sync_v2_17_opt_lqosync.zip -d lqos_docker
cd /home/pi/lqos_docker
sudo docker compose down
sudo docker compose build --no-cache
sudo docker compose up -d
```

### Bare-metal update

```bash
cd /home/pi
unzip -o lqos_shaped_sync_v2_17_opt_lqosync.zip -d lqos_docker
cd /home/pi/lqos_docker
sudo bash install.sh
sudo systemctl restart lqos_shaped_sync
```

Use preserve existing config when updating production:

```bash
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
```

---

## Uninstall

Full uninstall guide:

```text
UNINSTALLATION.md
```

### Docker uninstall

Use this if LQoSync was installed using Docker Compose.

```bash
cd /home/pi/lqos_shaped_sync 2>/dev/null || cd /home/pi/lqos_docker
sudo docker compose down
```

Optional remove Docker image:

```bash
sudo docker images | grep lqos
sudo docker rmi IMAGE_ID
```

Optional remove runtime data after backup:

```bash
sudo tar -czf /root/lqosync_runtime_backup_$(date +%F_%H%M%S).tar.gz /opt/lqosync 2>/dev/null || true
sudo rm -rf /opt/lqosync
```

If installed from Git and you also want to remove the source clone:

```bash
rm -rf /home/pi/lqos_shaped_sync
```

### Bare-metal uninstall

Use this if LQoSync was installed as a native systemd service.

```bash
sudo systemctl stop lqos_shaped_sync
sudo systemctl disable lqos_shaped_sync
sudo rm -f /etc/systemd/system/lqos_shaped_sync.service
sudo systemctl daemon-reload
sudo systemctl reset-failed
sudo rm -f /etc/sudoers.d/lqosync
sudo rm -f /etc/sudoers.d/lqos_shaped_sync
sudo tar -czf /root/lqosync_runtime_backup_$(date +%F_%H%M%S).tar.gz /opt/lqosync 2>/dev/null || true
sudo rm -rf /opt/lqosync
sudo rm -f /var/log/lqos_shaped_sync.log
sudo userdel lqosync 2>/dev/null || true
```

Optional remove ACL permissions if applied:

```bash
sudo setfacl -x u:lqosync /opt/libreqos/src 2>/dev/null || true
sudo setfacl -x u:lqosync /opt/libreqos/src/config.json 2>/dev/null || true
sudo setfacl -x u:lqosync /opt/libreqos/src/ShapedDevices.csv 2>/dev/null || true
sudo setfacl -x u:lqosync /opt/libreqos/src/network.json 2>/dev/null || true
sudo setfacl -d -x u:lqosync /opt/libreqos/src 2>/dev/null || true
```

If installed from Git and you also want to remove the source clone:

```bash
rm -rf /home/pi/lqos_shaped_sync
```

### Do not delete LibreQoS files by default

Normally keep:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

LibreQoS may still need those files.

### Restore old updatecsv.service

If returning to the original script workflow:

```bash
sudo systemctl enable --now updatecsv.service
sudo systemctl status updatecsv.service
journalctl -u updatecsv.service -f
```

---

## Security Model

### MikroTik

Use read-only RouterOS API credentials.

Recommended policy:

```text
read,api
```

### App user

Bare-metal runs as:

```text
lqosync
```

The web app should not run as root.

### Passwords

Passwords are bcrypt hashes in:

```text
/opt/lqosync/users.json
```

### Sudoers

Only allow specific commands required for LibreQoS apply and service control.

Avoid broad sudo.

### File permissions

Recommended:

```bash
sudo chmod 600 /opt/libreqos/src/config.json
sudo chmod 600 /opt/lqosync/users.json
```

---

## Configuration Reference

Main config file:

```text
/opt/libreqos/src/config.json
```

Example core sections:

```json
{
  "network_mode": "router_children",
  "flat_network": false,
  "no_parent": false,
  "preserve_network_config": false,
  "app": {
    "name": "LQoSync",
    "auto_apply": true,
    "backup_before_apply": true,
    "backup_retention": 30,
    "dry_run_default": false,
    "file_drift_policy": "overwrite_with_backup"
  },
  "scheduler": {
    "enabled": true,
    "active_interval_seconds": 30,
    "idle_interval_seconds": 120,
    "error_retry_interval_seconds": 30,
    "apply_cooldown_seconds": 20,
    "max_instances": 1
  },
  "libreqos": {
    "cmd": "/opt/libreqos/src/LibreQoS.py",
    "args": ["--updateonly"],
    "sudo": true,
    "timeout_seconds": 300,
    "run_only_when_files_changed": true
  }
}
```

### Recommended production scheduler

```json
{
  "scheduler": {
    "enabled": true,
    "active_interval_seconds": 30,
    "idle_interval_seconds": 120,
    "error_retry_interval_seconds": 30,
    "apply_cooldown_seconds": 20,
    "max_instances": 1
  }
}
```

Conservative setting:

```json
{
  "scheduler": {
    "active_interval_seconds": 60,
    "idle_interval_seconds": 180,
    "apply_cooldown_seconds": 30
  }
}
```

---

## Operator Commands

### LibreQoS status

```bash
sudo systemctl status lqosd lqos_scheduler
```

### LibreQoS core restart

```bash
sudo systemctl restart lqosd lqos_scheduler
```

### Manual LibreQoS apply

```bash
sudo /opt/libreqos/src/LibreQoS.py --updateonly
```

### View LQoSync Docker logs

```bash
sudo docker logs -f lqos_shaped_sync
```

### View LQoSync bare-metal logs

```bash
sudo journalctl -u lqos_shaped_sync -f
```

### Check resource use

```bash
sudo docker stats lqos_shaped_sync
```

---

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


### UI shows Internal Server Error

Check Docker logs:

```bash
sudo docker logs --tail=120 lqos_shaped_sync
```

Common causes:

- missing Python helper function
- bad template variable
- invalid config file
- invalid users file

### Container restarts repeatedly

```bash
sudo docker compose ps
sudo docker logs --tail=120 lqos_shaped_sync
sudo docker inspect lqos_shaped_sync --format='Status={{.State.Status}} ExitCode={{.State.ExitCode}} RestartCount={{.RestartCount}} Error={{.State.Error}}'
```

Run in foreground:

```bash
sudo docker compose down
sudo docker compose up --build
```

### Port 9202 conflict

```bash
sudo ss -tulpn | grep :9202
```

Change port in `.env` / compose if needed.

### Invalid config

```bash
sudo python3 -m json.tool /opt/libreqos/src/config.json
```

### No MikroTik connection

Check:

- router IP reachable
- RouterOS API service enabled
- port 8728 open
- username/password correct
- user has `read,api` policy

Run doctor:

```bash
sudo docker exec -it lqos_shaped_sync python scripts/doctor.py --router-test
```

### Old updatecsv still running

Disable it:

```bash
sudo systemctl disable --now updatecsv.service
```

Only one writer should manage `ShapedDevices.csv` and `network.json`.

---

## Release Notes Summary

### v2.14

- Expanded README into full granular project manual.
- Added Docker and bare-metal install instructions directly in README.
- Added workflow, engine, config, network mode, security, and troubleshooting docs.
- Added GitHub project description and suggested topics.

### Recent feature milestones

- v2.13: Shaped Devices per-column filters.
- v2.12: User Settings UI with bcrypt-backed `users.json`.
- v2.11: command documentation improvements.
- v2.10: status helper fix.
- v2.9: auth boot fix.
- v2.8: LibreQoS service unit naming fix: `lqosd`, `lqos_scheduler`.
- v2.7: Services/Journals and timing metrics.
- v2.6: network modes: hierarchy, flat router root, flat no parent.
- v2.4: Docker and bare-metal documentation.
- v2.3: Config Center light mode fix and network JSON view.
- v2.2: light/dark theme switch.
- v2.1: core parity with original `updatecsv.py` workflow.

---

## Final Mental Model

```text
config.json tells LQoSync what to do.
MikroTik tells LQoSync who is active.
LQoSync generates LibreQoS files.
LibreQoS.py applies the shaping update.
The dashboard gives operators visibility and control.
```

That is the whole project.

---

## About Module in the Web UI

LQoSync includes an operator-friendly **About** page at:

```text
/about
```

The About module is intended as the in-app readable manual. It contains:

- project description
- exact LQoSync workflow
- feature/module overview
- network layout mode explanation
- Docker installation quick guide
- bare-metal Ubuntu installation quick guide
- requirements
- important paths
- operator commands
- safety notes

It is available from the sidebar under **Help → About**.

### Browser tab icon / favicon

LQoSync includes a browser tab icon, commonly called a **favicon**. The project ships `static/favicon.ico`, `static/favicon.svg`, PNG touch icons, and `static/site.webmanifest`. These are wired in the main dashboard and login templates, so the LQoSync icon appears in the browser tab, bookmarks, and supported mobile shortcuts.


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

## Config Center apply-policy update

The Config Center includes a dedicated **Apply Policy** module. This is where operators configure how LQoSync calls LibreQoS after generated files change.

Recommended production values:

```json
"libreqos": {
  "cmd": "/opt/libreqos/src/LibreQoS.py",
  "args": ["--updateonly"],
  "working_dir": "/opt/libreqos/src",
  "run_mode": "direct",
  "run_only_when_files_changed": true,
  "retry_if_last_apply_failed": true,
  "sudo": true,
  "timeout_seconds": 300
}
```

`working_dir` is important because LibreQoS.py reads some files by relative name internally. LQoSync therefore runs LibreQoS.py from `/opt/libreqos/src`. If a file write succeeds but LibreQoS apply fails, `retry_if_last_apply_failed=true` keeps a pending apply state and retries on the next non-dry-run cycle.

During install/update, `scripts/migrate_config.py` safely normalizes existing config files by adding missing apply-policy defaults and converting LQoSync runtime paths to `/opt/lqosync` when needed.


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


## LibreQoS service notes

LQoSync treats `lqosd` and `lqos_scheduler` as primary services. `lqos_node_manager` is legacy/optional and auto-hidden if not installed.


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

LQoSync can now safely handle existing installations when using the GitHub source installer. This is useful if the system was previously installed from ZIP, manual copy, Docker, Git, or a partial/broken bare-metal install.

Recommended command for production adoption:

```bash
cd /opt
curl -fsSL https://raw.githubusercontent.com/p33ckab00/lqos_shaped_sync/main/install-from-github.sh -o /tmp/install-lqosync.sh
sudo EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh
```

Interactive install:

```bash
sudo bash /tmp/install-lqosync.sh
```

When an existing install is detected, the installer can adopt/update, update code only, repair, replace app files with backup, remove then fresh install, or abort.

See: [`docs/EXISTING_INSTALL_ADOPTION.md`](docs/EXISTING_INSTALL_ADOPTION.md)

## In-App About Module / Operator Manual

The web UI includes **About LQoSync**, a complete built-in operator manual. It now mirrors the latest repository documentation for project purpose, process workflow, apply policy, fresh installation, existing install adoption, GitHub updates, uninstall/permission restore, MikroTik setup, important paths, operator commands, and troubleshooting.

For the full text version, see:

```text
docs/ABOUT_MODULE_OPERATOR_GUIDE.md
```

Documentation rule: every meaningful code, installer, update, uninstall, troubleshooting, or lifecycle change should update both the repository manuals and `templates/about.html` so operators can read the latest guidance directly inside the dashboard.


## v2.38 Selective MikroTik Collection

LQoSync now supports selective RouterOS property reads, a universal speed resolver, metadata-cache tracking, Hotspot enhanced metadata reads, source-aware cleanup, and richer Dashboard collector monitoring.

Key rules:

```text
PPPoE speed: secret comment -> active comment -> profile comment -> profile name -> profile rate-limit -> default
DHCP speed: DHCP server comment/speed_comment -> DHCP server name -> server config speed -> global default
Hotspot speed: user comment -> profile comment -> profile name -> profile rate-limit -> hotspot config -> default
```

See `docs/SELECTIVE_COLLECTION.md` and the in-app About module for the full operator guide.


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

- Network Layout gives the Topology Tree more width and keeps the Node Inspector stable for easier topology editing.
- Privacy Mode now uses stable redaction labels such as `Client-001`, `Node-001`, `IP-001`, and `MAC-001` instead of visual blur.
- Topbar theme and privacy controls are compact icon-only toggles.
- Topology save uses the session CSRF token in AJAX requests and shows a friendly explanation if the token is stale or missing.


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

LQoSync v2.45 introduces the Smart Policy Center. It adds policy-driven safety decisions before file writes and LibreQoS apply. Cleanup candidates are classified by reason such as normal inactive, source disabled, collector failed, source zero result, and mass removal. The policy engine then decides whether to preserve rows, warn only, clean immediately, queue cleanup for the next run, require confirmation, block cleanup, or block apply.

The Dashboard and Dry Run pages now expose policy verdict, risk level, write/apply permission, pending confirmations, and recommendations. The Policy Center page shows current policy mode, source cleanup behavior, pending cleanup confirmations, apply guards, collector guards, runtime policy state, and last policy decision.

This turns LQoSync into a policy-driven operator tool: config defines operator intent, policies define how safely it happens, the policy engine decides before write/apply, and the UI explains every decision.

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
