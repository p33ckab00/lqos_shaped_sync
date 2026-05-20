# LQoSync Operator Commands

> **Canonical path:** LQoSync installs and runs from `/opt/LQoSync`. LibreQoS remains under `/opt/libreqos`. Do not use a user-home directory as the documented install base.


This page lists the common commands for Docker and bare-metal installs.

## Docker container commands

Run these from the folder that contains `compose.yaml`, usually:

```bash
cd /opt/lqos_docker
```

### Check container status

```bash
sudo docker compose ps
sudo docker ps -a | grep lqosync
```

### Start / stop / restart

```bash
sudo docker compose up -d
sudo docker compose down
sudo docker compose restart
```

### View logs

```bash
sudo docker logs -f lqosync
sudo docker logs --tail=120 lqosync
```

### Rebuild after package update

```bash
sudo docker compose down
sudo docker compose build --no-cache
sudo docker compose up -d
```

### Change admin password

Use this explicit command so the script always writes to the mounted `users.json` path:

```bash
sudo docker exec -it lqosync sh -lc "USERS_PATH=/opt/LQoSync/users.json python /app/scripts/set_password.py admin 'new-strong-password' admin"
```

Create or update a viewer user:

```bash
sudo docker exec -it lqosync sh -lc "USERS_PATH=/opt/LQoSync/users.json python /app/scripts/set_password.py viewer 'viewer-password' viewer"
```

### Run doctor checks

```bash
sudo docker exec -it lqosync python /app/scripts/doctor.py
sudo docker exec -it lqosync python /app/scripts/doctor.py --router-test
```

## Bare-metal Ubuntu commands

### Service status

```bash
sudo systemctl status lqosync
sudo journalctl -u lqosync -f
```

### Start / stop / restart

```bash
sudo systemctl start lqosync
sudo systemctl stop lqosync
sudo systemctl restart lqosync
```

### Change admin password

```bash
sudo USERS_PATH=/opt/LQoSync/users.json /opt/LQoSync/venv/bin/python /opt/LQoSync/scripts/set_password.py admin 'new-strong-password' admin
```

### Run doctor checks

```bash
sudo /opt/LQoSync/venv/bin/python /opt/LQoSync/scripts/doctor.py
sudo /opt/LQoSync/venv/bin/python /opt/LQoSync/scripts/doctor.py --router-test
```

## LibreQoS related commands

### Check LibreQoS services

```bash
sudo systemctl status lqosd lqos_scheduler
```

### Restart LibreQoS core services

```bash
sudo systemctl restart lqosd lqos_scheduler
```

### Manually run LibreQoS apply hook

```bash
sudo /opt/libreqos/src/LibreQoS.py --updateonly
```

## User management via UI

Open the web interface as an admin:

```text
http://<LibreQoS-server-IP>:9202/settings/users
```

From this page you can:

- add a user
- edit username
- change role
- change password
- delete user

Passwords are stored in `/opt/LQoSync/users.json` as bcrypt hashes. LQoSync does not use a database.

## User management via CLI

Docker:

```bash
sudo docker exec -it lqosync sh -lc "USERS_PATH=/opt/LQoSync/users.json python /app/scripts/set_password.py admin 'new-strong-password' admin"
```

Bare-metal:

```bash
sudo USERS_PATH=/opt/LQoSync/users.json /opt/LQoSync/venv/bin/python /opt/LQoSync/scripts/set_password.py admin 'new-strong-password' admin
```


---

## Uninstall Reference

For complete Docker, bare-metal, and Git-based uninstall steps, see:

```text
UNINSTALLATION.md
```


---

## Uninstall Commands

Full guide:

```text
UNINSTALLATION.md
```

### Docker uninstall

```bash
cd /opt/LQoSync 2>/dev/null || cd /opt/lqos_docker
sudo docker compose down
```

Optional remove runtime folder:

```bash
sudo tar -czf /root/lqosync_runtime_backup_$(date +%F_%H%M%S).tar.gz /opt/LQoSync 2>/dev/null || true
sudo rm -rf /opt/LQoSync
```

If installed from Git and you want to remove the source clone:

```bash
rm -rf /opt/LQoSync
```

### Bare-metal uninstall

```bash
sudo systemctl stop lqosync
sudo systemctl disable lqosync
sudo rm -f /etc/systemd/system/lqosync.service
sudo systemctl daemon-reload
sudo systemctl reset-failed
sudo rm -f /etc/sudoers.d/lqosync
sudo rm -f /etc/sudoers.d/lqosync
sudo tar -czf /root/lqosync_runtime_backup_$(date +%F_%H%M%S).tar.gz /opt/LQoSync 2>/dev/null || true
sudo rm -rf /opt/LQoSync
sudo userdel lqosync 2>/dev/null || true
```

Optional remove ACL permissions:

```bash
sudo setfacl -x u:lqosync /opt/libreqos/src 2>/dev/null || true
sudo setfacl -x u:lqosync /opt/libreqos/src/config.json 2>/dev/null || true
sudo setfacl -x u:lqosync /opt/libreqos/src/ShapedDevices.csv 2>/dev/null || true
sudo setfacl -x u:lqosync /opt/libreqos/src/network.json 2>/dev/null || true
sudo setfacl -d -x u:lqosync /opt/libreqos/src 2>/dev/null || true
```

Restore old updatecsv service:

```bash
sudo systemctl enable --now updatecsv.service
sudo systemctl status updatecsv.service
```

---

# ACL Permission Repair for Bare-Metal Install

Use this if Config Center, DHCP Discovery, or file save fails with:

```text
Permission denied: /opt/libreqos/src/config.json.tmp
```

Repair:

```bash
sudo systemctl stop lqosync

sudo apt update
sudo apt install -y acl

sudo setfacl -m u:lqosync:rwx /opt/libreqos/src
sudo setfacl -m u:lqosync:rw /opt/libreqos/src/config.json
sudo setfacl -m u:lqosync:rw /opt/libreqos/src/ShapedDevices.csv
sudo setfacl -m u:lqosync:rw /opt/libreqos/src/network.json
sudo setfacl -d -m u:lqosync:rwX /opt/libreqos/src

sudo systemctl start lqosync
```

Test:

```bash
sudo -u lqosync touch /opt/libreqos/src/config.json.tmp
sudo -u lqosync rm -f /opt/libreqos/src/config.json.tmp
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

## Apply-policy config check

Check that the live config has the correct LibreQoS working directory and failed-apply retry:

```bash
python3 - <<'PY'
import json
p='/opt/libreqos/src/config.json'
c=json.load(open(p))
print(json.dumps(c.get('libreqos', {}), indent=2))
PY
```

Expected important keys:

```json
{
  "working_dir": "/opt/libreqos/src",
  "retry_if_last_apply_failed": true
}
```

Run migration manually after a Git update:

```bash
cd /opt/LQoSync
sudo CONFIG_PATH=/opt/libreqos/src/config.json /opt/LQoSync/venv/bin/python scripts/migrate_config.py
```


### Bare-metal LibreQoS runner policy

Bare-metal/systemd installs must run LibreQoS directly, not through Docker `nsenter`. The installer now normalizes `/opt/libreqos/src/config.json` and `/opt/LQoSync/.env` so these settings are present after every update:

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
cd /opt/LQoSync
sudo git pull origin lqosync-in-rust
sudo systemctl stop lqosync
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
sudo systemctl start lqosync
```

Then confirm:

```bash
grep -A12 '"libreqos"' /opt/libreqos/src/config.json
grep -E 'LQOSYNC_RUN_MODE|HOST_CONTROL_MODE|LQOSYNC_INSTALL_MODE|LQOSYNC_FORCE_DIRECT' /opt/LQoSync/.env
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

LQoSync also normalizes config at application startup. This means a `git pull` followed by `systemctl restart lqosync` can still persist missing safe defaults into `/opt/libreqos/src/config.json`, even when `install.sh` is not re-run.


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
sudo systemctl restart lqosync
journalctl -u lqosync -f
```

LQoSync v2.27+ also enforces the effective working directory at runtime and records it in each LibreQoS apply log metadata.


## LibreQoS service compatibility note

`lqos_node_manager` is legacy/optional. Older LibreQoS installs may use it as a separate Web UI service, while newer installs commonly expose the Web UI through `lqosd`. LQoSync now treats `lqos_node_manager` as optional and auto-hides it when it is not installed. The primary service health check remains `sudo systemctl status lqosd lqos_scheduler`.


## Restore LibreQoS Permissions After Uninstall

Bare-metal LQoSync adds ACL permissions so the `lqosync` service user can atomically write temporary files in `/opt/libreqos/src`, for example `config.json.tmp`, `ShapedDevices.csv.tmp`, and `network.json.tmp`. When uninstalling LQoSync, restore those permissions so LibreQoS is returned to a normal root-owned state.

Recommended managed restore:

```bash
sudo bash /opt/LQoSync/scripts/restore_libreqos_permissions.sh --managed
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
sudo bash /opt/LQoSync/scripts/restore_libreqos_permissions.sh --full
```

The restore script saves an ACL backup in `/root/lqosync_libreqos_acl_backup_<timestamp>.acl` when `getfacl` is available.


## Bare-metal Uninstall Helper

From `/opt/LQoSync`, you can use the bundled helper:

```bash
cd /opt/LQoSync
sudo bash uninstall.sh
```

To also remove `/opt/LQoSync` after backup:

```bash
cd /opt/LQoSync
sudo REMOVE_RUNTIME=true bash uninstall.sh
```

The helper stops/removes `lqosync`, removes sudoers entries, restores LibreQoS ACL/ownership for managed files, and optionally removes the runtime folder.

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
sudo git clone https://github.com/p33ckab00/LQoSync.git lqosync
cd /opt/LQoSync
sudo bash install.sh
```

One-command bootstrap:

```bash
curl -fsSL https://raw.githubusercontent.com/p33ckab00/LQoSync/lqosync-in-rust/install-from-github.sh -o /tmp/install-lqosync.sh
sudo bash /tmp/install-lqosync.sh
```

Production-safe update from GitHub:

```bash
cd /opt/LQoSync
sudo bash upgrade.sh
```

Default update policy is `preserve_and_migrate`, which preserves live operator files:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
/opt/LQoSync/users.json
/opt/LQoSync/.env
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


## GitHub install with existing install adoption

Download the GitHub bootstrap installer:

```bash
curl -fsSL https://raw.githubusercontent.com/p33ckab00/LQoSync/lqosync-in-rust/install-from-github.sh -o /tmp/install-lqosync.sh
```

Interactive mode:

```bash
sudo bash /tmp/install-lqosync.sh
```

Recommended non-interactive adoption:

```bash
sudo EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh
```

Other actions:

```bash
sudo EXISTING_INSTALL_ACTION=code_only bash /tmp/install-lqosync.sh
sudo EXISTING_INSTALL_ACTION=repair bash /tmp/install-lqosync.sh
sudo EXISTING_INSTALL_ACTION=replace_app bash /tmp/install-lqosync.sh
sudo EXISTING_INSTALL_ACTION=remove_fresh bash /tmp/install-lqosync.sh
sudo EXISTING_INSTALL_ACTION=abort bash /tmp/install-lqosync.sh
```

---

## Open Built-In About / Operator Manual

```text
http://<server-ip>:9202/about
```

The About module contains the current operator-facing documentation for install, update, uninstall, troubleshooting, commands, and expected results. Keep it aligned with repository documentation whenever project behavior changes.


## v2.38 Selective MikroTik Collection

LQoSync now supports selective RouterOS property reads, a universal speed resolver, metadata-cache tracking, Hotspot enhanced metadata reads, source-aware cleanup, and richer Dashboard collector monitoring.

Key rules:

```text
PPPoE speed: secret comment -> active comment -> profile comment -> profile name -> profile rate-limit -> default
DHCP speed: DHCP server comment/speed_comment -> DHCP server name -> server config speed -> global default
Hotspot speed: user comment -> profile comment -> profile name -> profile rate-limit -> hotspot config -> default
```

See `docs/SELECTIVE_COLLECTION.md` and the in-app About module for the full operator guide.
