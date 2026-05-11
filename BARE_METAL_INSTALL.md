# LQoSync Bare-Metal Ubuntu Installation Guide

This guide installs **LQoSync / lqos_shaped_sync** directly on Ubuntu/Debian using Python venv + systemd.

Bare-metal install is recommended if you want the simplest host integration and do not want Docker/Compose.

---

## What LQoSync Does

LQoSync is a database-free dashboard and scheduler for the MikroTik-to-LibreQoS sync workflow.

```text
MikroTik RouterOS API  →  LQoSync Engine  →  ShapedDevices.csv + network.json  →  LibreQoS.py --updateonly
```

It follows the original updatecsv.py idea:

1. read `/opt/libreqos/src/config.json`
2. read existing `/opt/libreqos/src/ShapedDevices.csv`


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

3. read existing `/opt/libreqos/src/network.json`
4. connect to MikroTik read-only API
5. process PPPoE, Hotspot, and DHCP
6. remove inactive non-static generated rows only when router processing succeeds
7. write files only if changed
8. call `/opt/libreqos/src/LibreQoS.py --updateonly` only when files changed

---

## Host Paths

LQoSync app files:

```text
/opt/lqosync/
```

LibreQoS-managed files:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

Runtime/log/backup files:

```text
/opt/lqosync/users.json
/opt/lqosync/state/runtime_state.json
/opt/lqosync/backups/
/opt/lqosync/logs/
/var/log/lqos_shaped_sync.log
```

---

## Before Installing

Stop the old `updatecsv.service` first so two systems do not write the same LibreQoS files.

```bash
sudo systemctl disable --now updatecsv.service 2>/dev/null || true
```

Confirm LibreQoS source path exists:

```bash
ls -ld /opt/libreqos/src
```

---

## Install Steps

### 1. Unzip the package

```bash
cd /home/pi
unzip lqos_shaped_sync_v2_17_opt_lqosync.zip
cd lqos_docker
```

The folder name remains `lqos_docker` because the same package supports Docker and bare-metal installs.

### 2. Choose file initialization policy

Default behavior is:

```bash
LQOSYNC_INIT_POLICY=overwrite_with_backup
```

This means:

```text
if /opt/libreqos/src/config.json exists       → backup then overwrite from LQoSync template
if /opt/libreqos/src/ShapedDevices.csv exists → backup then overwrite from LQoSync template
if /opt/libreqos/src/network.json exists      → backup then overwrite from LQoSync template
if missing                                    → create from template
```

Backups are saved under:

```text
/opt/lqosync/install_backups/<timestamp>/
```

Available policies:

| Policy | Behavior |
|---|---|
| `overwrite_with_backup` | Backup existing files, then replace with LQoSync templates. Default. |
| `preserve_existing` | Backup existing files and keep them unchanged. Missing files are created. |
| `create_missing_only` | Create missing files only. Existing files are preserved. |

For production servers that already have working LibreQoS files, you may prefer:

```bash
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
```

### 3. Run bare-metal installer

Default install:

```bash
sudo bash install.sh
```

or using wrapper:

```bash
sudo bash install-baremetal.sh
```

Preserve existing LibreQoS files:

```bash
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
```

Create missing files only:

```bash
sudo LQOSYNC_INIT_POLICY=create_missing_only bash install.sh
```

### 4. Check service

```bash
sudo systemctl status lqos_shaped_sync
sudo journalctl -u lqos_shaped_sync -f
```

### 5. Open web UI

```text
http://<server-ip>:9202
```

Example:

```text
http://172.27.185.15:9202
```

Default login:

```text
admin / adminpass
```

Change password immediately:

```bash
sudo USERS_PATH=/opt/lqosync/users.json /opt/lqosync/venv/bin/python /opt/lqosync/scripts/set_password.py admin 'new-strong-password' admin
```

---

## Post-Install Checklist

### 1. Edit config

Open the Config Center in the UI, or edit directly:

```bash
sudo nano /opt/libreqos/src/config.json
```

Set your router:

```json
{
  "name": "RB5k9-Distro",
  "address": "10.200.1.2",
  "port": 8728,
  "username": "libreqos",
  "password": "libreqos"
}
```

Use a read-only MikroTik API user with policies:

```text
read, api
```

### 2. Test router connection

From UI: Config Center → Router → Test Current UI API

or from shell:

```bash
sudo /opt/lqosync/venv/bin/python /opt/lqosync/scripts/doctor.py --router-test
```

### 3. Run dry-run first

Use UI: Dry Run Preview → Run Dry Run

Confirm:

```text
added/updated/removed circuits
network node changes
warnings/errors
```

### 4. Run manual sync

Use UI: Dashboard → Run Sync Now

### 5. Enable scheduler

Use UI: Dashboard → Enable Scheduler

---

## Useful Commands

Restart LQoSync:

```bash
sudo systemctl restart lqos_shaped_sync
```

Stop LQoSync:

```bash
sudo systemctl stop lqos_shaped_sync
```

View logs:

```bash
sudo journalctl -u lqos_shaped_sync -f
sudo tail -f /var/log/lqos_shaped_sync.log
```

Run doctor:

```bash
sudo /opt/lqosync/venv/bin/python /opt/lqosync/scripts/doctor.py
```

Set admin password:

```bash
sudo USERS_PATH=/opt/lqosync/users.json /opt/lqosync/venv/bin/python /opt/lqosync/scripts/set_password.py admin 'new-password' admin
```

---

## Uninstall Bare-Metal Install

```bash
sudo systemctl stop lqos_shaped_sync
sudo systemctl disable lqos_shaped_sync
sudo rm -f /etc/systemd/system/lqos_shaped_sync.service
sudo systemctl daemon-reload
sudo rm -f /etc/sudoers.d/lqos_shaped_sync
sudo tar -czf /root/lqos_shaped_sync_backup_$(date +%Y%m%d_%H%M%S).tar.gz /opt/lqosync 2>/dev/null || true
sudo rm -rf /opt/lqosync
sudo rm -f /var/log/lqos_shaped_sync.log
sudo userdel lqosync 2>/dev/null || true
```

Do not remove these unless you are sure LibreQoS no longer needs them:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

## Service Restart Permissions

The installer creates a restricted sudoers file for LQoSync. It allows only the LibreQoS apply command and allowlisted service restarts, including:

```bash
sudo systemctl restart lqosd lqos_scheduler
sudo systemctl restart lqosd lqos_scheduler lqos_node_manager
```

If your LibreQoS unit names differ, update `services.units` and `services.restart_groups` in `/opt/libreqos/src/config.json` and adjust `/etc/sudoers.d/lqos_shaped_sync` accordingly.


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

---

## Automatic ACL Permission Setup

Bare-metal installs automatically install the `acl` package and apply ACL permissions for the `lqosync` service user.

This is required because LQoSync writes files atomically. For example, when the Config Center or DHCP Discovery updates the config, the engine first creates a temporary file:

```text
/opt/libreqos/src/config.json.tmp
```

Then it renames the temp file into:

```text
/opt/libreqos/src/config.json
```

Because of this, `lqosync` needs write access to both:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/
```

The installer now applies:

```bash
sudo setfacl -m u:lqosync:rwx /opt/libreqos/src
sudo setfacl -m u:lqosync:rw /opt/libreqos/src/config.json
sudo setfacl -m u:lqosync:rw /opt/libreqos/src/ShapedDevices.csv
sudo setfacl -m u:lqosync:rw /opt/libreqos/src/network.json
sudo setfacl -d -m u:lqosync:rwX /opt/libreqos/src
```

It also performs a smoke test by creating and removing a temporary file in `/opt/libreqos/src` as the `lqosync` user.

---

## Troubleshooting: Permission Denied on config.json.tmp

If you see this error:

```text
DHCP discovery failed: [Errno 13] Permission denied: '/opt/libreqos/src/config.json.tmp'
```

Run this repair command:

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

Test permission:

```bash
sudo -u lqosync touch /opt/libreqos/src/config.json.tmp
sudo -u lqosync rm -f /opt/libreqos/src/config.json.tmp
```

If the test returns no error, try DHCP Discovery or Config Save again from the web UI.

Check logs:

```bash
journalctl -u lqos_shaped_sync -f
```


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

