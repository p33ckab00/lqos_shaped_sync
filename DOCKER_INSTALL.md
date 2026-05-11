# LQoSync Docker / Compose Installation Guide

This guide installs **LQoSync / lqos_shaped_sync** using Docker Compose.

Docker mode is host-integrated because LQoSync must write LibreQoS files and call the host LibreQoS apply command.

---

## What LQoSync Does

```text
MikroTik RouterOS API  →  LQoSync Engine  →  ShapedDevices.csv + network.json  →  LibreQoS.py --updateonly
```

No database. MikroTik is read-only. `/opt/libreqos/src/config.json` drives the sync behavior.

---

## Why Docker Uses Host Integration



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

The Compose file uses:

```yaml
privileged: true
pid: host
network_mode: host
```

because the container needs to:

1. write `/opt/libreqos/src/config.json`
2. write `/opt/libreqos/src/ShapedDevices.csv`
3. write `/opt/libreqos/src/network.json`
4. call host `/opt/libreqos/src/LibreQoS.py --updateonly`
5. optionally restart allowlisted host services

---

## Host Paths

```text
/opt/libreqos/src/config.json          # LQoSync config
/opt/libreqos/src/ShapedDevices.csv    # generated LibreQoS CSV
/opt/libreqos/src/network.json         # generated LibreQoS topology
/opt/lqosync/                 # LQoSync runtime data
/opt/lqosync/users.json       # web login users
/opt/lqosync/backups/         # backups
/opt/lqosync/state/           # runtime state and lock
/opt/lqosync/logs/            # audit/logs
```

---

## Install Steps

### 1. Stop old updatecsv service

```bash
sudo systemctl disable --now updatecsv.service 2>/dev/null || true
```

### 2. Install Docker and Compose plugin

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

### 3. Unzip package

```bash
cd /home/pi
unzip lqos_shaped_sync_v2_17_opt_lqosync.zip
cd lqos_docker
```

### 4. Edit compose.yaml

Generate a secret:

```bash
openssl rand -hex 32
```

Edit:

```bash
nano compose.yaml
```

Change:

```yaml
SECRET_KEY: "change-this-generate-with-openssl-rand-hex-32"
```

Paste your generated secret.

### 5. Choose init policy

Default in `compose.yaml`:

```yaml
LQOSYNC_INIT_POLICY: "overwrite_with_backup"
```

Meaning:

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

For production servers with existing working files, use preserve mode:

```bash
sudo docker compose -f compose.preserve-existing.yaml up -d --build
```

or edit `compose.yaml`:

```yaml
LQOSYNC_INIT_POLICY: "preserve_existing"
```

### 6. Start container

Default mode:

```bash
sudo docker compose up -d --build
```

### 7. Check logs

```bash
sudo docker logs -f lqos_shaped_sync
```

### 8. Open UI

```text
http://<server-ip>:9202
```

Default login:

```text
admin / adminpass
```

Change password:

```bash
sudo docker exec -it lqos_shaped_sync sh -lc "USERS_PATH=/opt/lqosync/users.json python /app/scripts/set_password.py admin 'new-strong-password' admin"
```

---

## Post-Install Checklist

1. Open Config Center.
2. Set MikroTik router address, API username/password, PPPoE/DHCP/Hotspot settings.
3. Test router API from Config Center.
4. Run Dry Run Preview.
5. Run Sync Now.
6. Enable Scheduler only after output is confirmed.

---

## Useful Docker Commands

Stop:

```bash
sudo docker compose down
```

Start:

```bash
sudo docker compose up -d
```

Restart:

```bash
sudo docker compose restart
```

Shell:

```bash
sudo docker exec -it lqos_shaped_sync bash
```

Doctor:

```bash
sudo docker exec -it lqos_shaped_sync python /app/scripts/doctor.py
sudo docker exec -it lqos_shaped_sync python /app/scripts/doctor.py --router-test
```

Logs:

```bash
sudo docker logs -f lqos_shaped_sync
```

---

## Docker Uninstall

From the package directory:

```bash
sudo docker compose down
```

Remove image, optional:

```bash
sudo docker image rm lqos_shaped_sync:2.4-docs-baremetal 2>/dev/null || true
```

Remove runtime data, optional:

```bash
sudo tar -czf /root/lqos_shaped_sync_backup_$(date +%Y%m%d_%H%M%S).tar.gz /opt/lqosync 2>/dev/null || true
sudo rm -rf /opt/lqosync
```

Do not remove LibreQoS files unless you know you no longer need them:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

## Services & Journals in Docker

The Docker deployment is host-integrated (`privileged`, `pid: host`, `network_mode: host`). LQoSync uses `nsenter` to run host `systemctl` and `journalctl` for allowlisted LibreQoS units.

The default `libreqos_core` restart group runs the host equivalent of:

```bash
systemctl restart lqosd lqos_scheduler
```


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


## GitHub source updates for Docker deployments

If the Docker deployment source folder is Git-managed, update with:

```bash
cd /home/pi/lqos_shaped_sync
sudo git pull origin main
sudo docker compose down
sudo docker compose build --no-cache
sudo docker compose up -d
```

For bare-metal `/opt/lqosync` installs, use:

```bash
cd /opt/lqosync
sudo bash upgrade.sh
```
