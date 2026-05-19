# LQoSync Full Documentation

> **Canonical path:** LQoSync installs and runs from `/opt/lqosync`. LibreQoS remains under `/opt/libreqos`. Do not use a user-home directory as the documented install base.


This is the consolidated single-file manual for LQoSync. It is compiled from the same topic files used by the WebUI Documentation Center and GitHub documentation index.

## Documentation source model

- `docs/content/*.md` contains topic-level source documentation.
- `docs/docs_manifest.json` indexes documentation topics.
- `docs/DOCUMENTATION_INDEX.md` is the GitHub documentation map.
- `README.md` is intentionally compact.
- This `FULL_DOCUMENTATION.md` is the complete long-form manual.


---

# LQoSync Operator Summary

LQoSync is a MikroTik-to-LibreQoS companion inspired by the LibreQoS operating model. It is designed to make the sync path visible: collection, normalization, speed resolution, node assignment, policy decisions, Dry Run impact, backups, generated files, LibreQoS apply, logs, and audit events.

## Install and update safety

Fresh installs and updates must protect operator-owned production files. If `/opt/libreqos/src/config.json`, `/opt/libreqos/src/ShapedDevices.csv`, or `/opt/libreqos/src/network.json` already exist, they are backed up first and preserved by default. Missing files are created from templates. Existing files are not overwritten unless overwrite-with-backup is explicitly selected.

## Update visibility ownership

About describes project identity and purpose. Update Center owns installed version, GitHub/latest version, local and remote commits, latest fetched changes, update-needed state, and copy-ready safe update commands.

---

# AI-Assisted Development Disclosure and Acknowledgement

LQoSync was developed and refined through an AI-assisted development workflow.

A significant portion of the system planning, code generation, documentation, UI/UX refinement, troubleshooting logic, release structuring, and implementation guidance was assisted by **GPT-5.5 Thinking by OpenAI**, working interactively with the project owner/operator.

The project owner/operator provided the real-world ISP requirements, LibreQoS and MikroTik deployment context, feature direction, testing feedback, operational decisions, and final approval for changes.

This acknowledgement is included to recognize the role of AI-assisted engineering in accelerating the development of LQoSync while preserving the importance of human validation, operational judgment, and production responsibility.

Because LQoSync may interact with live network infrastructure, LibreQoS files, MikroTik routers, scheduler behavior, and service-level automation, all AI-assisted code, configuration, documentation, and operational behavior should be reviewed, tested, and validated by a qualified human operator before production use.

AI assistance does not replace human review, security auditing, backup verification, configuration validation, or production testing.


---

# LQoSync Documentation Index

This index is the GitHub-friendly map for the consolidated LQoSync documentation. The same topic files are searchable inside the WebUI Documentation Center.

## Main entry points

- [README](../README.md) — compact project landing page
- [Full Documentation](../FULL_DOCUMENTATION.md) — complete single-file manual
- [AI-Assisted Development Disclosure](AI_ASSISTED_DEVELOPMENT.md)
- [Command Reference](COMMANDS.md)

## Topic index

- [Policy Settings Integration](content/policy_settings_integration.md)
- [Setup & Repair Center](content/setup_repair_center.md)
- [Smart Policy Center](SMART_POLICY_CENTER.md)
- [Smart Setup / Repair](SMART_SETUP_REPAIR.md)
- [Policy-Aware Cleanup Intelligence](content/policy_aware_cleanup_intelligence.md)
  - v2.50 source-aware stale lifecycle, optional grace, risk-aware auto apply, and decision trace.
- [Config Schema + Policy Simulation Engine](content/config_schema_policy_simulation.md)
  - v2.51 config_schema_version, config health, unsaved config preview, policy simulation, and impact verdicts.
- [Smart Reports + Operator Audit](content/smart_reports_operator_audit.md)
  - v2.52 operator report page with 24h summary, policy decision report, cleanup report, client changes, config audit, and exports.
- [Client Lifecycle Timeline](content/client_lifecycle_timeline.md)
  - v2.53 client lifecycle timeline, active/stale/queued/removed/returned states, cleanup queue, confirmations, and exports.
- [First Run Setup Wizard](content/setup_wizard_first_run.md)
  - v2.54 guided first-run onboarding for paths, routers, sources, layout, policy preset, Dry Run, and scheduler readiness.
- [Smart Reports route hotfix](content/smart_reports_route_hotfix.md)
- [Policy Center Settings Guidelines](content/policy_center_settings_guidelines.md)
  - Atomic operator explanations for every editable Policy Center setting.
- [Network Layout Drag-and-Drop](content/network_layout_drag_drop.md)
  - v2.54.3 wired desktop drag-and-drop for moving topology nodes with safe validation and preview-before-save behavior.
- [AI-Assisted Development Disclosure and Acknowledgement](../AI_ASSISTED_DEVELOPMENT.md)
- [Privacy Icon Polish](content/privacy_icon_polish.md)
- [Package Quality + Environment Doctor](content/package_quality_environment_doctor.md)
  - v2.55 release integrity checks, environment doctor, route/template validation, and Smart Defaults Repair.
- [Policy UX + Conflict Intelligence](content/policy_ux_conflict_identity.md)
  - v2.56 Policy Conflict Resolver, richer preset comparison, and client identity handling guidance.
- [Source Health + Performance Trends](content/source_health_performance_trends.md)
  - v2.57 source health dashboard, RouterOS API timing trends, LibreQoS apply health, and internal notification candidates.
- [Source Health & Performance Trends](content/source_health_performance_trends.md)
  - Dashboard-consolidated source health, RouterOS API timing, LibreQoS apply health, and internal notification candidates.
- [Telegram Notifications](content/telegram_notifications.md)
  - v2.58 optional Telegram delivery for internal health, policy, apply, and source notification candidates.
- [Documentation Search + UI/Mobile Polish](content/documentation_search_ui_polish.md)
  - v2.59 local documentation search, docs view pages, read-only docs API, and reusable UI/mobile consistency helpers.
- [Better Fresh Install Experience](content/better_fresh_install_experience.md)
  - v2.60 first-run gate, scheduler readiness protection, setup wizard redirect, and fresh install workflow.
- [Client Lifecycle View and Filter Hotfix](content/client_lifecycle_timeline.md)
  - v2.60.1 fixes Lifecycle View button wiring, adds instant table/card filtering, and adds timeline pagination/row limits.
- [Backup Pagination and Actions](content/backup_pagination_actions.md)
- [Compact Information Architecture](content/compact_information_architecture.md)
  - v2.61 Operations Center consolidation, compact sidebar, Dashboard/Reports separation, and documentation source-of-truth cleanup.
- [Config + Policy + Notification Unification](content/config_policy_notification_unification.md)
  - v2.62 consolidates Policy Center and Telegram notification delivery settings into Config Center while keeping compatibility redirects.
- [Documentation Consolidation and Source of Truth](content/documentation_consolidation.md)
  - v2.63 consolidates GitHub and WebUI documentation into docs/content, docs_manifest, README, and FULL_DOCUMENTATION as one coherent source-of-truth system.


---

# LQoSync Installation Options

LQoSync can be installed in two ways:

1. **Docker Compose** — recommended if you prefer containerized deployment.
2. **Bare Metal Ubuntu/Debian** — recommended if you prefer direct Python/systemd integration.
3. **Git-based install** — clone the repository first, then install using Docker or bare-metal.

Both Docker and bare-metal modes use the same paths and same workflow.

---

## Shared Requirements

Before installing either mode:

```bash
sudo systemctl disable --now updatecsv.service 2>/dev/null || true
```

The old updatecsv service must not run at the same time as LQoSync scheduler.


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

The systemd service name and Docker container name remain `lqosync` for compatibility, but the application/runtime directory is now `/opt/lqosync`.


---

## Option A: Docker Compose Install

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin unzip
sudo systemctl enable --now docker
cd /opt
unzip LQoSync_v2_17_opt_lqosync.zip
cd lqos_docker
openssl rand -hex 32
nano compose.yaml
sudo docker compose up -d --build
sudo docker logs -f lqosync
```

Open:

```text
http://<server-ip>:9202
```

More details:

```text
DOCKER_INSTALL.md
```

---

## Option B: Bare-Metal Ubuntu Install

```bash
sudo apt update
sudo apt install -y unzip
cd /opt
unzip LQoSync_v2_17_opt_lqosync.zip
cd lqos_docker
sudo bash install.sh
sudo systemctl status lqosync
```

Open:

```text
http://<server-ip>:9202
```

More details:

```text
BARE_METAL_INSTALL.md
```

---

## Option C: Git-Based Install

Use this when installing directly from GitHub instead of a ZIP package.

### Clone

```bash
cd /opt
git clone https://github.com/p33ckab00/LQoSync.git
cd lqosync
```

### Docker from Git

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git
sudo systemctl enable --now docker
sudo LQOSYNC_INIT_POLICY=preserve_existing docker compose up -d --build
sudo docker logs -f lqosync
```

### Bare-metal from Git

```bash
sudo apt update
sudo apt install -y git
cd /opt/lqosync
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
sudo systemctl status lqosync
```

Full details:

```text
GIT_INSTALL.md
```

---

## Init Policy

Both Docker and bare-metal modes support:

```text
overwrite_with_backup
preserve_existing
create_missing_only
```

Recommended for an existing production LibreQoS server:

```text
preserve_existing
```

Recommended for first clean install/lab:

```text
overwrite_with_backup
```


---

## Uninstall / Removal

For complete uninstall instructions covering Docker, bare-metal, and Git-based installs, see:

```text
UNINSTALLATION.md
```

Quick bare-metal stop:

```bash
sudo systemctl stop lqosync
sudo systemctl disable lqosync
```

Quick Docker stop:

```bash
cd /opt/lqosync
sudo docker compose down
```

---

## Bare-Metal Permission Notes

Bare-metal installation now applies ACL permissions automatically so the `lqosync` service user can atomically write to the LibreQoS source directory:

```text
/opt/libreqos/src/
```

This prevents errors like:

```text
Permission denied: /opt/libreqos/src/config.json.tmp
```

Manual repair command:

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

Permission test:

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
sudo systemctl stop lqosync
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
sudo systemctl start lqosync
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

## GitHub Source Install and Smart Updates

LQoSync supports GitHub-based installation and updates. This does **not** require GitHub CLI (`gh`); it only requires the standard `git` command.

Fresh install from GitHub:

```bash
sudo apt update
sudo apt install -y git
cd /opt
sudo git clone https://github.com/p33ckab00/LQoSync.git lqosync
cd /opt/lqosync
sudo bash install.sh
```

One-command bootstrap:

```bash
curl -fsSL https://raw.githubusercontent.com/p33ckab00/LQoSync/main/install-from-github.sh -o /tmp/install-lqosync.sh
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


## GitHub installer: existing install adoption

For systems that already have LQoSync installed from ZIP, manual copy, Git, Docker leftovers, or partial installs, use:

```bash
cd /opt
curl -fsSL https://raw.githubusercontent.com/p33ckab00/LQoSync/main/install-from-github.sh -o /tmp/install-lqosync.sh
sudo bash /tmp/install-lqosync.sh
```

For unattended production-safe adoption:

```bash
sudo EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh
```

This preserves operator-owned files by default: `/opt/libreqos/src/config.json`, `ShapedDevices.csv`, `network.json`, `/opt/lqosync/users.json`, `.env`, `state/`, `logs/`, and `backups/`.

---

## In-App About / Operator Manual

After installation, open:

```text
http://<server-ip>:9202/about
```

The About page is now a full built-in operator manual. It includes installation, GitHub updates, existing install adoption, uninstall/permission restore, MikroTik setup, troubleshooting, expected results, and important paths.

The Markdown companion is:

```text
docs/ABOUT_MODULE_OPERATOR_GUIDE.md
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


---

# GitHub Source Installation and Smart Update

LQoSync can be installed and updated directly from the GitHub repository without GitHub CLI (`gh`). The server only needs the normal `git` command and network access to GitHub.

Repository:

```bash
https://github.com/p33ckab00/LQoSync.git
```

## Important concept

GitHub is only the source-code delivery method. LQoSync still preserves production files by default:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
/opt/lqosync/users.json
/opt/lqosync/.env
/opt/lqosync/state/
/opt/lqosync/logs/
```

Those files are operator/runtime files and are not overwritten during normal Git updates.

## Fresh install from GitHub

Use this when the system does not yet have LQoSync installed or you want the install source to be Git-managed:

```bash
sudo apt update
sudo apt install -y git
cd /opt
sudo git clone https://github.com/p33ckab00/LQoSync.git lqosync
cd /opt/lqosync
sudo bash install.sh
```

The default installer behavior is smart:

```text
Fresh LibreQoS files missing → create from templates
Existing LibreQoS files found → ask/preserve by default
```

## One-command bootstrap from GitHub

If `install-from-github.sh` is available from the repository, use:

```bash
curl -fsSL https://raw.githubusercontent.com/p33ckab00/LQoSync/main/install-from-github.sh -o /tmp/install-lqosync.sh
sudo bash /tmp/install-lqosync.sh
```

Optional variables:

```bash
sudo LQOSYNC_REPO_URL=https://github.com/p33ckab00/LQoSync.git \
     LQOSYNC_BRANCH=main \
     LQOSYNC_INSTALL_DIR=/opt/lqosync \
     LQOSYNC_INIT_POLICY=smart_confirm \
     bash /tmp/install-lqosync.sh
```

## If `/opt/lqosync` was installed from ZIP/manual copy

The Git installer can convert it into a Git-managed install. It backs up and preserves:

```text
users.json
.env
state/
logs/
```

Then it clones/syncs the GitHub source and runs the normal production-safe installer.

## Smart Git update

Once `/opt/lqosync` is Git-managed:

```bash
cd /opt/lqosync
sudo bash upgrade.sh
```

Default update policy:

```text
UPDATE_POLICY=preserve_and_migrate
```

This means:

```text
pull latest code from GitHub
preserve live config.json
preserve users.json
preserve ShapedDevices.csv and network.json
run safe config migration for missing defaults
reapply ACL/sudoers/service settings
restart lqosync
run service health check
```

## Update policies

### Safe production update

```bash
cd /opt/lqosync
sudo UPDATE_POLICY=preserve_and_migrate bash upgrade.sh
```

Recommended for live systems.

### Pull only

```bash
sudo UPDATE_POLICY=pull_only bash upgrade.sh
```

Only pulls/updates the Git working tree. It does not reinstall dependencies, migrate config, or restart the service.

### Code only

```bash
sudo UPDATE_POLICY=code_only bash upgrade.sh
```

Updates app code and dependencies, then restarts the service. It does not run full install/migration.

### Refresh with backup

```bash
sudo UPDATE_POLICY=refresh_with_backup bash upgrade.sh
```

Backs up and refreshes installer-controlled files while preserving production config/users/generated files.

### Factory reset

Danger mode:

```bash
sudo UPDATE_POLICY=factory_reset CONFIRM_FACTORY_RESET=yes bash upgrade.sh
```

Use only for lab rebuilds or intentional reset. Existing files are backed up first.

## No GitHub CLI required

This works without `gh auth login`.

Required:

```bash
git --version
```

Install Git if missing:

```bash
sudo apt update
sudo apt install -y git
```

Public repositories can be cloned/pulled without login. Private repositories require HTTPS token or SSH key access.


---

# LQoSync Bare-Metal Ubuntu Installation Guide

This guide installs **LQoSync** directly on Ubuntu/Debian using Python venv + systemd.

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

The systemd service name and Docker container name remain `lqosync` for compatibility, but the application/runtime directory is now `/opt/lqosync`.

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
/var/log/lqosync.log
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
cd /opt
unzip LQoSync_v2_17_opt_lqosync.zip
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
sudo systemctl status lqosync
sudo journalctl -u lqosync -f
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
sudo systemctl restart lqosync
```

Stop LQoSync:

```bash
sudo systemctl stop lqosync
```

View logs:

```bash
sudo journalctl -u lqosync -f
sudo tail -f /var/log/lqosync.log
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
sudo systemctl stop lqosync
sudo systemctl disable lqosync
sudo rm -f /etc/systemd/system/lqosync.service
sudo systemctl daemon-reload
sudo rm -f /etc/sudoers.d/lqosync
sudo tar -czf /root/lqosync_backup_$(date +%Y%m%d_%H%M%S).tar.gz /opt/lqosync 2>/dev/null || true
sudo rm -rf /opt/lqosync
sudo rm -f /var/log/lqosync.log
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

If your LibreQoS unit names differ, update `services.units` and `services.restart_groups` in `/opt/libreqos/src/config.json` and adjust `/etc/sudoers.d/lqosync` accordingly.


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

Test permission:

```bash
sudo -u lqosync touch /opt/libreqos/src/config.json.tmp
sudo -u lqosync rm -f /opt/libreqos/src/config.json.tmp
```

If the test returns no error, try DHCP Discovery or Config Save again from the web UI.

Check logs:

```bash
journalctl -u lqosync -f
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
sudo systemctl stop lqosync
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
sudo systemctl start lqosync
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

## GitHub Source Install and Smart Updates

LQoSync supports GitHub-based installation and updates. This does **not** require GitHub CLI (`gh`); it only requires the standard `git` command.

Fresh install from GitHub:

```bash
sudo apt update
sudo apt install -y git
cd /opt
sudo git clone https://github.com/p33ckab00/LQoSync.git lqosync
cd /opt/lqosync
sudo bash install.sh
```

One-command bootstrap:

```bash
curl -fsSL https://raw.githubusercontent.com/p33ckab00/LQoSync/main/install-from-github.sh -o /tmp/install-lqosync.sh
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


---

# LQoSync Docker / Compose Installation Guide

This guide installs **LQoSync** using Docker Compose.

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

The systemd service name and Docker container name remain `lqosync` for compatibility, but the application/runtime directory is now `/opt/lqosync`.

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
cd /opt
unzip LQoSync_v2_17_opt_lqosync.zip
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
sudo docker logs -f lqosync
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
sudo docker exec -it lqosync sh -lc "USERS_PATH=/opt/lqosync/users.json python /app/scripts/set_password.py admin 'new-strong-password' admin"
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
sudo docker exec -it lqosync bash
```

Doctor:

```bash
sudo docker exec -it lqosync python /app/scripts/doctor.py
sudo docker exec -it lqosync python /app/scripts/doctor.py --router-test
```

Logs:

```bash
sudo docker logs -f lqosync
```

---

## Docker Uninstall

From the package directory:

```bash
sudo docker compose down
```

Remove image, optional:

```bash
sudo docker image rm lqosync:2.4-docs-baremetal 2>/dev/null || true
```

Remove runtime data, optional:

```bash
sudo tar -czf /root/lqosync_backup_$(date +%Y%m%d_%H%M%S).tar.gz /opt/lqosync 2>/dev/null || true
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
cd /opt/lqosync
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


---

# LQoSync Uninstallation Guide

This guide explains how to stop and remove LQoSync safely.

It covers:

1. Docker installation uninstall
2. Bare-metal Ubuntu/systemd uninstall
3. Git-based install cleanup
4. Optional cleanup of `/opt/lqosync`
5. Optional cleanup of permissions/ACL
6. Optional restore of old `updatecsv.service`

---

## Important Safety Note

Do **not** delete these files unless you are sure LibreQoS no longer needs them:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

These are LibreQoS working files. LQoSync may manage them, but LibreQoS reads them.

Before removing anything, create a backup:

```bash
sudo mkdir -p /root/lqosync_uninstall_backup_$(date +%F_%H%M%S)
BACKUP_DIR=$(ls -td /root/lqosync_uninstall_backup_* | head -1)
sudo cp -a /opt/lqosync "$BACKUP_DIR/opt_lqosync" 2>/dev/null || true
sudo cp -a /opt/libreqos/src/config.json "$BACKUP_DIR/config.json" 2>/dev/null || true
sudo cp -a /opt/libreqos/src/ShapedDevices.csv "$BACKUP_DIR/ShapedDevices.csv" 2>/dev/null || true
sudo cp -a /opt/libreqos/src/network.json "$BACKUP_DIR/network.json" 2>/dev/null || true
echo "Backup saved to: $BACKUP_DIR"
```

---

# A. Docker Uninstall

Use this if you installed with:

```bash
sudo docker compose up -d --build
```

## 1. Go to the Git/project folder

Common locations:

```bash
cd /opt/lqosync
```

or:

```bash
cd /opt/lqos_docker
```

Confirm Compose file exists:

```bash
ls -lah compose.yaml
```

## 2. Stop and remove the container

```bash
sudo docker compose down
```

Check:

```bash
sudo docker ps -a | grep lqos || true
```

## 3. Optional: remove Docker image

List LQoSync images:

```bash
sudo docker images | grep lqos
```

Remove by image ID:

```bash
sudo docker rmi IMAGE_ID
```

Or try common tags:

```bash
sudo docker image rm lqosync:latest 2>/dev/null || true
sudo docker image rm lqosync:2.17-opt-lqosync 2>/dev/null || true
```

## 4. Optional: remove runtime folder

LQoSync runtime path:

```text
/opt/lqosync
```

Backup then delete:

```bash
sudo tar -czf /root/lqosync_runtime_backup_$(date +%F_%H%M%S).tar.gz /opt/lqosync 2>/dev/null || true
sudo rm -rf /opt/lqosync
```

## 5. Optional: remove Git project folder

If installed from Git:

```bash
rm -rf /opt/lqosync
```

If using old local folder name:

```bash
rm -rf /opt/lqos_docker
```

Only do this after you no longer need local source files.

---

# B. Bare-metal Ubuntu/Systemd Uninstall

Fast path using the bundled uninstall helper:

```bash
cd /opt/lqosync
sudo bash uninstall.sh
```

Remove `/opt/lqosync` too:

```bash
cd /opt/lqosync
sudo REMOVE_RUNTIME=true bash uninstall.sh
```

Restore the entire LibreQoS src tree to root ownership instead of only managed files:

```bash
cd /opt/lqosync
sudo RESTORE_MODE=full bash uninstall.sh
```

Use this if you installed with:

```bash
sudo bash install.sh
```

or:

```bash
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
```

## 1. Stop and disable service

```bash
sudo systemctl stop lqosync
sudo systemctl disable lqosync
```

Check:

```bash
sudo systemctl status lqosync
```

## 2. Remove systemd service file

```bash
sudo rm -f /etc/systemd/system/lqosync.service
sudo systemctl daemon-reload
sudo systemctl reset-failed
```

## 3. Remove sudoers rules

```bash
sudo rm -f /etc/sudoers.d/lqosync
sudo rm -f /etc/sudoers.d/lqosync
```

## 4. Backup and remove app/runtime folder

```bash
sudo tar -czf /root/lqosync_runtime_backup_$(date +%F_%H%M%S).tar.gz /opt/lqosync 2>/dev/null || true
sudo rm -rf /opt/lqosync
```

## 5. Remove log file, optional

```bash
sudo rm -f /var/log/lqosync.log
```

## 6. Remove Linux user, optional

```bash
sudo userdel lqosync 2>/dev/null || true
# LQoSync system user is created with --no-create-home; no user-home install path is used.
```

## 7. Restore LibreQoS permissions to root

Bare-metal LQoSync grants ACL write access to the `lqosync` user so it can create atomic temp files under `/opt/libreqos/src`. During uninstall, restore these permissions so LibreQoS returns to a normal root-owned state.

Recommended managed restore:

```bash
sudo bash /opt/lqosync/scripts/restore_libreqos_permissions.sh --managed
```

This restores only the directory and files managed by LQoSync:

```text
/opt/libreqos/src
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

Expected result:

```text
/opt/libreqos/src                       root:root 755
/opt/libreqos/src/config.json           root:root 600
/opt/libreqos/src/ShapedDevices.csv     root:root 644
/opt/libreqos/src/network.json          root:root 644
```

Optional full restore if you intentionally want everything under `/opt/libreqos/src` returned to root ownership:

```bash
sudo bash /opt/lqosync/scripts/restore_libreqos_permissions.sh --full
```

Manual fallback if the script is already gone:

```bash
sudo setfacl -x u:lqosync /opt/libreqos/src 2>/dev/null || true
sudo setfacl -x u:lqosync /opt/libreqos/src/config.json 2>/dev/null || true
sudo setfacl -x u:lqosync /opt/libreqos/src/ShapedDevices.csv 2>/dev/null || true
sudo setfacl -x u:lqosync /opt/libreqos/src/network.json 2>/dev/null || true
sudo setfacl -d -x u:lqosync /opt/libreqos/src 2>/dev/null || true

sudo chown root:root /opt/libreqos/src
sudo chown root:root /opt/libreqos/src/config.json /opt/libreqos/src/ShapedDevices.csv /opt/libreqos/src/network.json
sudo chmod 755 /opt/libreqos/src
sudo chmod 600 /opt/libreqos/src/config.json
sudo chmod 644 /opt/libreqos/src/ShapedDevices.csv /opt/libreqos/src/network.json
```

## 8. Optional: remove Git project folder

If installed from Git:

```bash
rm -rf /opt/lqosync
```

If using old extracted package folder:

```bash
rm -rf /opt/lqos_docker
```

---

# C. What Not To Remove By Default

Normally, keep:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

These files may still be required by LibreQoS.

Only remove them if you intentionally want to remove LQoSync-managed LibreQoS output:

```bash
sudo cp -a /opt/libreqos/src/config.json /root/config.json.backup.$(date +%F_%H%M%S) 2>/dev/null || true
sudo cp -a /opt/libreqos/src/ShapedDevices.csv /root/ShapedDevices.csv.backup.$(date +%F_%H%M%S) 2>/dev/null || true
sudo cp -a /opt/libreqos/src/network.json /root/network.json.backup.$(date +%F_%H%M%S) 2>/dev/null || true

sudo rm -f /opt/libreqos/src/config.json
sudo rm -f /opt/libreqos/src/ShapedDevices.csv
sudo rm -f /opt/libreqos/src/network.json
```

---

# D. Restore Old updatecsv.service

If you want to return to the old script workflow:

```bash
sudo systemctl enable --now updatecsv.service
sudo systemctl status updatecsv.service
journalctl -u updatecsv.service -f
```

Make sure LQoSync is stopped/removed first to avoid two writers touching `ShapedDevices.csv` and `network.json`.

---

# E. Verify Removal

```bash
systemctl status lqosync
ls -lah /opt/lqosync
sudo docker ps -a | grep lqos || true
```

Expected after full uninstall:

```text
Unit lqosync.service could not be found
/opt/lqosync: No such file or directory
no lqosync container
```

---

## Related In-App Manual

The web UI includes an About page with the latest uninstall and permission-restore guide:

```text
http://<server-ip>:9202/about
```

See also:

```text
docs/ABOUT_MODULE_OPERATOR_GUIDE.md
```


---

# LQoSync Operator Commands

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
sudo docker exec -it lqosync sh -lc "USERS_PATH=/opt/lqosync/users.json python /app/scripts/set_password.py admin 'new-strong-password' admin"
```

Create or update a viewer user:

```bash
sudo docker exec -it lqosync sh -lc "USERS_PATH=/opt/lqosync/users.json python /app/scripts/set_password.py viewer 'viewer-password' viewer"
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
sudo USERS_PATH=/opt/lqosync/users.json /opt/lqosync/venv/bin/python /opt/lqosync/scripts/set_password.py admin 'new-strong-password' admin
```

### Run doctor checks

```bash
sudo /opt/lqosync/venv/bin/python /opt/lqosync/scripts/doctor.py
sudo /opt/lqosync/venv/bin/python /opt/lqosync/scripts/doctor.py --router-test
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

Passwords are stored in `/opt/lqosync/users.json` as bcrypt hashes. LQoSync does not use a database.

## User management via CLI

Docker:

```bash
sudo docker exec -it lqosync sh -lc "USERS_PATH=/opt/lqosync/users.json python /app/scripts/set_password.py admin 'new-strong-password' admin"
```

Bare-metal:

```bash
sudo USERS_PATH=/opt/lqosync/users.json /opt/lqosync/venv/bin/python /opt/lqosync/scripts/set_password.py admin 'new-strong-password' admin
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
cd /opt/lqosync 2>/dev/null || cd /opt/lqos_docker
sudo docker compose down
```

Optional remove runtime folder:

```bash
sudo tar -czf /root/lqosync_runtime_backup_$(date +%F_%H%M%S).tar.gz /opt/lqosync 2>/dev/null || true
sudo rm -rf /opt/lqosync
```

If installed from Git and you want to remove the source clone:

```bash
rm -rf /opt/lqosync
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
sudo tar -czf /root/lqosync_runtime_backup_$(date +%F_%H%M%S).tar.gz /opt/lqosync 2>/dev/null || true
sudo rm -rf /opt/lqosync
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
cd /opt/lqosync
sudo CONFIG_PATH=/opt/libreqos/src/config.json /opt/lqosync/venv/bin/python scripts/migrate_config.py
```


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
sudo systemctl stop lqosync
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
sudo systemctl start lqosync
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
cd /opt/lqosync
sudo bash install.sh
```

One-command bootstrap:

```bash
curl -fsSL https://raw.githubusercontent.com/p33ckab00/LQoSync/main/install-from-github.sh -o /tmp/install-lqosync.sh
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


## GitHub install with existing install adoption

Download the GitHub bootstrap installer:

```bash
curl -fsSL https://raw.githubusercontent.com/p33ckab00/LQoSync/main/install-from-github.sh -o /tmp/install-lqosync.sh
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


---

# Policy Settings Integration

LQoSync v2.49 makes Smart Policy Center a real settings surface. Policies are operator intent stored in `config.json -> policies`, not hidden backend behavior.

## Source of truth

- `config.json -> policies`: operator-configured policy values
- `engine/policy_schema.py`: labels, descriptions, allowed values, risk levels, defaults, and UI metadata
- `engine/policy_defaults.py`: base defaults and presets
- `engine/policy_engine.py`: runtime decision maker before write/apply
- `policy_state.json`: pending confirmations, cleanup queue, and runtime decision history

## Preset behavior

Available presets:

- Conservative
- Balanced
- Aggressive
- Custom

Applying a preset writes the full preset into `config.json -> policies`.

Manual edits from Policy Center or Config Center switch `policies.mode` to `custom` because the current values no longer exactly match a preset.

## Visible policy groups

- Cleanup Core
- PPPoE Cleanup
- DHCP Cleanup
- Hotspot Cleanup
- Static/manual Cleanup
- Mass Removal Guards
- Apply Guards
- Collector Guards
- Data Quality Guards
- Topology Guards
- Backup Guards
- Anomaly Detection
- Recommendations

## Operator workflow

1. Open Policy Center.
2. Choose a preset or edit individual policies.
3. Save custom policy settings.
4. Run Dry Run.
5. Review policy verdict, risk, confirmations, and recommendations.
6. Enable scheduler/auto-apply only when behavior is expected.

## Why this matters

Smart behavior must not be blind. Operators need to know what policy is enabled, what threshold is active, and what action happens when the policy is triggered.


---

# Setup & Repair Center

Setup & Repair is a diagnostics and repair guidance surface. It should not duplicate the full manual.

## Purpose

- inspect the current system
- show pass/fail/warn checks
- compute readiness score
- recommend the next action
- provide copy-ready SSH repair commands
- link to documentation sections for deeper explanations

## Not the purpose

Setup & Repair should not become a second About/manual page. Long installation, update, uninstall, and troubleshooting explanations belong in Documentation / About.

## Source of truth

Use `docs/content/*.md` and `docs/docs_manifest.json` as the documentation source. Setup & Repair should reference these sections by key.


---

# LQoSync Smart / Intelligent Policy Center — Full Implementation Handoff

Ito ang **full handoff documentation** ng napag-usapan natin para i-copy paste mo sa original branch/chat na may full project context.

````markdown
# LQoSync Smart / Intelligent Policy Center — Full Implementation Handoff

## Important instruction

Do not blindly apply any patch pack from a branch-off conversation. The correct implementation must be done directly inside the latest full LQoSync project tree / original branch.

This document contains the full agreed design, logic, UI/UX behavior, policy model, cleanup rules, smart decision engine, and roadmap.

Target next release:

LQoSync v2.45 Smart Policy Center

Core goal:

LQoSync should not just sync MikroTik data to LibreQoS. It should observe, decide, explain, protect, and recommend.

---

# 1. Core philosophy

LQoSync should become a smart operator system.

Current/simple behavior:

```text
Collect MikroTik data
Generate ShapedDevices.csv
Generate network.json
If changed, run LibreQoS.py --updateonly
````

Target smart behavior:

```text
Collect MikroTik data
Classify source health
Build proposed output
Compare current vs proposed
Classify removals and changes
Run policy engine
Calculate risk
Decide:
  allow
  warn
  cleanup immediately
  cleanup next run
  require confirmation
  block cleanup
  block apply
Explain the decision in Dashboard and Dry Run
Apply only if safe under operator policies
```

Important principle:

```text
Config = operator intent
Policies = safety rules
Policy engine = decision maker
Dashboard / Dry Run = explanation layer
```

The system should not be blind. All smart behaviors must be visible in Settings / Config Center through a Policy Center UI.

---

# 2. Why policies are needed

Example:

Operator disables PPPoE because they only want DHCP and Hotspot.

Result:

```text
Existing PPP rows = 35
PPP collector disabled
Proposed PPP rows = 0
Removal = 100%
```

A naive mass-removal guard would think this is dangerous and block it.

But in reality:

```text
PPP disabled by operator = intentional config change
PPP API failed = unintentional failure
PPP returned zero while enabled = suspicious
```

These must be treated differently.

Therefore:

```text
Detection is not deletion.
The system may detect stale rows, but cleanup policy decides what to do.
```

---

# 3. Main Policy Center concept

Create a visible Policy Center module in Settings / Config Center.

Recommended modules:

```text
Policy Center
├─ Policy Preset
├─ Cleanup Policies
├─ Source Lifecycle Policies
├─ Apply Guard Policies
├─ Collector Guard Policies
├─ Mass Change Guard Policies
├─ Data Quality Policies
├─ Topology Guard Policies
├─ Backup Guard Policies
├─ Anomaly Detection Policies
└─ Recommendations
```

Each policy card should show:

```text
Policy name
Enabled / disabled
Threshold value
Action when triggered
Why this matters
Recommended setting
Current effective value
```

Do not hide these in raw JSON only.

Raw JSON editor can remain available for advanced users.

---

# 4. Suggested config structure

Use this as a recommended config model. Adjust names based on existing project style.

```json
{
  "policies": {
    "mode": "balanced",

    "cleanup": {
      "enabled": true,

      "global_default_action": "require_confirm_next_run",

      "confirmation_expires_hours": 24,
      "apply_confirmed_cleanup": "next_run",

      "normal_inactive_default_action": "cleanup_next_run",
      "source_disabled_default_action": "require_confirm_next_run",
      "collector_failed_default_action": "preserve_rows",
      "source_zero_result_default_action": "block_cleanup",

      "allow_immediate_cleanup": true
    },

    "cleanup_sources": {
      "pppoe": {
        "enabled": true,
        "normal_inactive_action": "cleanup_next_run",
        "source_disabled_action": "require_confirm_next_run",
        "collector_failed_action": "preserve_rows",
        "zero_result_action": "block_cleanup",
        "mass_removal_action": "require_confirm_next_run",
        "respect_percentage_guards": true
      },
      "dhcp": {
        "enabled": true,
        "normal_inactive_action": "cleanup_immediate",
        "source_disabled_action": "require_confirm_next_run",
        "collector_failed_action": "preserve_rows",
        "zero_result_action": "block_cleanup",
        "mass_removal_action": "require_confirm_next_run",
        "respect_percentage_guards": false
      },
      "hotspot": {
        "enabled": true,
        "normal_inactive_action": "cleanup_immediate",
        "source_disabled_action": "cleanup_next_run",
        "collector_failed_action": "preserve_rows",
        "zero_result_action": "warn_only",
        "mass_removal_action": "require_confirm_next_run",
        "respect_percentage_guards": false
      },
      "static": {
        "enabled": true,
        "normal_inactive_action": "preserve_rows",
        "source_disabled_action": "preserve_rows",
        "collector_failed_action": "preserve_rows",
        "zero_result_action": "preserve_rows",
        "mass_removal_action": "preserve_rows",
        "respect_percentage_guards": true
      }
    },

    "node_cleanup_guard": {
      "enabled": true,
      "threshold_percent": 30,
      "min_node_size": 10,
      "min_removed_count": 3,
      "action": "require_confirm_next_run"
    },

    "small_node_guard": {
      "enabled": true,
      "max_node_size": 5,
      "partial_removal_action": "cleanup_next_run",
      "full_removal_action": "require_confirm_next_run"
    },

    "source_cleanup_guard": {
      "enabled": true,
      "threshold_percent": 30,
      "min_removed_count": 5,
      "action": "require_confirm_next_run"
    },

    "apply_guard": {
      "block_apply_on_collector_failure": true,
      "block_apply_on_missing_parent": true,
      "block_apply_on_duplicate_ip": true,
      "block_apply_on_invalid_speed": true,
      "require_manual_confirm_on_medium_risk": true,
      "allow_auto_apply_on_low_risk": true
    },

    "collector_guard": {
      "block_cleanup_if_source_failed": true,
      "block_cleanup_if_enabled_source_returns_zero": true,
      "block_cleanup_if_source_returns_zero_after_previous_success": true,
      "zero_source_drop_threshold_percent": 80,
      "warn_if_router_api_slow_ms": 2000
    },

    "data_quality": {
      "warn_on_fallback_speed": true,
      "fallback_speed_warning_threshold_percent": 10,
      "block_if_fallback_speed_threshold_percent": 50,
      "warn_on_missing_mac": true,
      "warn_on_missing_ip": true
    },

    "topology_guard": {
      "block_missing_parent_nodes": true,
      "block_duplicate_node_names": true,
      "warn_on_virtual_node_promotion": true,
      "warn_on_deep_hierarchy_depth": true,
      "max_recommended_depth": 4
    },

    "backup_guard": {
      "require_backup_before_apply": true,
      "warn_if_backup_disabled_while_auto_apply_enabled": true,
      "minimum_backup_retention": 30
    },

    "anomaly_detection": {
      "enabled": true,
      "compare_with_last_successful_run": true,
      "warn_if_client_count_drops_percent": 30,
      "warn_if_sync_duration_increases_multiplier": 5,
      "warn_if_apply_duration_increases_multiplier": 5
    },

    "recommendations": {
      "enabled": true,
      "show_why_fix_messages": true,
      "show_operator_next_action": true
    }
  }
}
```

---

# 5. Supported cleanup actions

The cleanup system must support these actions:

```text
preserve_rows
warn_only
cleanup_immediate
cleanup_next_run
require_confirm_immediate
require_confirm_next_run
block_cleanup
block_apply
```

Meanings:

## preserve_rows

Keep old rows. No deletion.

## warn_only

Show warning but do not delete.

## cleanup_immediate

Delete rows in the same sync cycle.

## cleanup_next_run

Mark rows for cleanup, then delete on the next successful sync run.

## require_confirm_immediate

Operator must confirm; after confirmation, cleanup can happen immediately.

## require_confirm_next_run

Operator must confirm; after confirmation, cleanup applies on the next successful sync run.

Recommended production default for risky cases.

## block_cleanup

Do not delete. Keep files safe.

## block_apply

Block LibreQoS apply. Used for dangerous validation failures.

---

# 6. Cleanup reason classification

Every removed/stale row must be classified before applying policy.

Reasons:

```text
normal_inactive
source_disabled
collector_failed
source_zero_result
mass_removal
manual_excluded
topology_policy
duplicate_policy
```

Important distinction:

```text
PPP disabled intentionally ≠ PPP API failed
DHCP source returned zero while enabled ≠ DHCP server disabled by operator
One client inactive ≠ node/source mass removal
```

Policy engine must decide based on reason.

---

# 7. Source lifecycle behavior

Each source should be handled independently:

```text
PPP / PPPoE
DHCP
Hotspot
Static/manual rows
```

Example behavior:

```text
PPP normal inactive      → cleanup_next_run
DHCP normal inactive     → cleanup_immediate
Hotspot normal inactive  → cleanup_immediate

PPP disabled             → require_confirm_next_run
DHCP server disabled     → require_confirm_next_run
Hotspot disabled         → cleanup_next_run

Collector failed         → preserve_rows
Zero result while enabled → block_cleanup or require_confirm_next_run
```

This gives the operator full freedom.

---

# 8. Immediate vs next-run cleanup

Operator must be able to choose per source:

```text
cleanup immediately
cleanup next run
require confirmation then cleanup immediately
require confirmation then cleanup next run
preserve rows
warn only
block cleanup
```

Example:

```text
DHCP normal inactive = cleanup_immediate
PPP normal inactive = cleanup_next_run
Hotspot normal inactive = cleanup_immediate
```

This supports fast / effective updates when the operator wants immediate behavior.

Tradeoff warning:

If cleanup is immediate and clients flap:

```text
client disappears → row removed → LibreQoS apply
client returns → row added → LibreQoS apply again
```

Optional anti-flap setting can be added later:

```json
{
  "anti_flap": {
    "enabled": true,
    "minimum_apply_interval_seconds": 30,
    "coalesce_changes": true
  }
}
```

---

# 9. Per-source override precedence

Policy precedence should be predictable.

Recommended order:

```text
1. Hard safety rules
2. Per-server / per-profile override
3. Per-source policy
4. Global cleanup policy
5. Default fallback
```

Example:

```text
DHCP-LAN has custom cleanup policy
→ use DHCP-LAN policy

No DHCP-LAN override
→ use DHCP source policy

No DHCP policy
→ use global cleanup policy
```

Optional future model:

```json
{
  "dhcp_server_overrides": {
    "LAN": {
      "normal_inactive_action": "cleanup_next_run"
    },
    "Wifi5Soft": {
      "normal_inactive_action": "cleanup_immediate"
    }
  }
}
```

---

# 10. Small node handling

Percentage-only cleanup guards are dangerous for small nodes.

Example:

```text
DHCP node before: 3 clients
Removed: 1 client
Removal percent: 33.33%
Threshold: 30%
```

Naive result:

```text
Block deletion
```

But this is too sensitive because only one client disappeared.

Correct logic:

```text
Apply percentage guard only if:
removed_percent >= threshold_percent
AND removed_count >= min_removed_count
AND previous_node_count >= min_node_size
```

Recommended policy:

```json
{
  "node_cleanup_guard": {
    "enabled": true,
    "threshold_percent": 30,
    "min_node_size": 10,
    "min_removed_count": 3,
    "action": "require_confirm_next_run"
  }
}
```

So:

```text
Before: 3
Removed: 1
Percent: 33%

But:
node size < 10
removed count < 3

Result:
Do not block.
Treat as small-node normal cleanup.
```

Small node policy:

```json
{
  "small_node_guard": {
    "enabled": true,
    "max_node_size": 5,
    "partial_removal_action": "cleanup_next_run",
    "full_removal_action": "require_confirm_next_run"
  }
}
```

Recommended rule:

```text
Use percentage only for medium/large nodes.
Use absolute count/grace behavior for small nodes.
Require confirmation for full-node removal, even if small.
```

---

# 11. Node / source / global cleanup guards

There should be multiple guard layers:

```text
1. Per-client normal inactive cleanup
2. Per-node removal guard
3. Per-source removal guard
4. Global mass-removal guard
```

Per-node example:

```text
Node: DHCP-LAN
Before: 100
Removed: 35
Removal percent: 35%
Policy: threshold 30%
Result: require confirmation / block
```

Per-source example:

```text
DHCP total before: 80
DHCP total after: 10
Removed: 70
Result: block or require confirmation
```

Global example:

```text
All generated clients before: 300
All generated clients after: 100
Removed: 200
Result: critical risk
```

---

# 12. Pending confirmation system

If policy action is:

```text
require_confirm_next_run
```

then system should create a pending confirmation.

Suggested runtime state:

```json
{
  "pending_confirmations": [
    {
      "id": "cleanup-pppoe-RB5k9-Distro-20260513",
      "type": "cleanup_confirmation",
      "source": "pppoe",
      "router": "RB5k9-Distro",
      "reason": "source_disabled",
      "affected_rows": 35,
      "apply_mode": "next_run",
      "scope_hash": "abc123",
      "config_hash": "def456",
      "created_by": "admin",
      "created_at": "2026-05-13T10:00:00+08:00",
      "expires_at": "2026-05-14T10:00:00+08:00",
      "confirmed": true
    }
  ]
}
```

Important:

Confirmation must be specific.

Not enough:

```text
Yes, delete
```

Required:

```text
Confirm PPP cleanup
Source: PPPoE
Router: RB5k9-Distro
Rows affected: 35
Reason: PPPoE collector disabled
Apply mode: next run
Expires: 24h
```

If config changes after confirmation:

```text
Confirmation invalidated.
Please confirm cleanup again.
```

---

# 13. Source disabled cleanup flow

Example:

Before:

```text
PPP enabled
PPP rows: 35
```

Operator changes config:

```text
pppoe.enabled = false
```

Dry run / scheduler detects:

```text
PPP source disabled.
35 existing PPP rows would be removed.
```

Policy:

```text
source_disabled_action = require_confirm_next_run
```

System result:

```text
No cleanup yet.
No apply yet if cleanup is the only change.
Dashboard shows pending confirmation.
```

UI:

```text
Pending Cleanup Confirmation

PPP source disabled
35 PPP rows are pending removal

Policy:
require_confirm_next_run

Action:
Confirm cleanup or re-enable PPP collector
```

After operator confirms:

```text
Confirmation saved.
PPP rows will be removed on the next successful sync run.
```

Next run:

```text
Valid confirmation found.
PPP cleanup applied.
ShapedDevices.csv changed.
LibreQoS apply triggered if auto_apply allowed.
```

---

# 14. Collector failure behavior

If source is enabled but collector fails:

```text
pppoe.enabled = true
PPP API failed
```

This is not operator intent.

Recommended behavior:

```text
preserve old PPP rows
block cleanup for PPP
possibly block apply if proposed output is unsafe
show warning/error
```

Policy:

```json
{
  "collector_failed_action": "preserve_rows"
}
```

Dashboard:

```text
PPP collector failed.
PPP cleanup blocked.
Old PPP rows preserved.

Reason:
Source is enabled but API read failed.

Recommended action:
Check MikroTik API, credentials, firewall, or router availability.
```

---

# 15. Zero result behavior

If source is enabled and scan succeeds but returns zero:

```text
DHCP enabled
DHCP scan OK
valid leases = 0
last successful DHCP count = 42
```

This is suspicious.

Recommended default:

```text
block_cleanup
```

or:

```text
require_confirm_next_run
```

Policy:

```json
{
  "zero_result_action": "block_cleanup"
}
```

Dashboard:

```text
DHCP returned zero active rows.
Previous successful scan had 42.
Cleanup blocked to prevent accidental mass deletion.
```

---

# 16. Dry Run Verdict

Dry Run should classify result:

```text
Safe to apply
Apply with caution
Requires confirmation
Blocked by policy
```

Examples:

## Safe

```text
Dry Run Verdict: Safe to apply

Changes:
1 client added
0 removed
0 duplicate IPs
0 missing parent nodes
No collector failure
```

## Requires confirmation

```text
Dry Run Verdict: Requires confirmation

PPP source disabled.
35 PPP rows would be removed.

Policy:
require_confirm_next_run

Next action:
Confirm PPP cleanup or re-enable PPP.
```

## Blocked

```text
Dry Run Verdict: Blocked by policy

Reasons:
- DHCP source returned zero rows after previous successful scan
- 3 missing parent nodes
- duplicate IP detected

No files were written.
LibreQoS will not be applied.
```

---

# 17. Dashboard Policy Decision Card

Dashboard should show:

```text
Policy Decision

Status:
Allowed / Warn / Requires confirmation / Blocked

Risk:
Low / Medium / High / Critical

Triggered policies:
- Source Lifecycle: PPP disabled
- Cleanup Guard: 35 rows pending removal
- Apply Guard: confirmation required

Next action:
Confirm cleanup / Run dry-run / Fix config / Re-enable source
```

Example:

```text
Cleanup Decision

Node: DHCP-LAN-RB5k9-Distro
Before: 3 clients
After: 2 clients
Removed: 1 client
Removal percent: 33.3%

Policy result:
Allowed as small-node normal cleanup.

Reason:
Node size is below minimum threshold of 10 clients,
and removed count is below minimum count of 3.

Action:
Mark stale and cleanup on next run.
```

---

# 18. Recommendations panel

Add Dashboard / Policy Center recommendations.

Examples:

```text
Recommended Actions

1. Confirm PPP cleanup
Reason: PPP source is disabled and 35 rows are pending removal.

2. Review fallback-speed clients
Reason: 2 clients used global default speed.

3. Enable backup_before_apply
Reason: auto_apply is enabled but backups are disabled.

4. Update available
Reason: GitHub version is newer.

5. Check DHCP source
Reason: DHCP returned zero rows after previous successful scan.
```

Each recommendation should have:

```text
Title
Reason
Suggested action
Severity
Link/button
```

---

# 19. Risk score

Policy engine should output:

```json
{
  "risk_score": 0,
  "risk_level": "low"
}
```

Suggested levels:

```text
0–20    Low
21–50   Medium
51–80   High
81–100  Critical
```

Risk inputs:

```text
collector failure
source zero result
mass removal
missing parent nodes
duplicate IPs
invalid speed
fallback speed percentage
backup disabled while auto_apply enabled
LibreQoS previous apply failed
file drift
```

Result example:

```text
Risk: High

Reasons:
- 42% of clients would be removed
- DHCP scan returned zero rows
- 3 missing parent nodes
```

---

# 20. Apply guard before file write/apply

Important design:

Policy engine must run before final file write and LibreQoS apply.

Flow:

```text
1. Load config
2. Load existing ShapedDevices.csv and network.json
3. Collect MikroTik sources
4. Build proposed ShapedDevices.csv and network.json
5. Diff existing vs proposed
6. Classify cleanup/removals
7. Validate proposed data
8. Evaluate policies
9. Decide:
   - write allowed?
   - cleanup allowed?
   - apply allowed?
   - confirmation required?
10. Only then write files / apply LibreQoS
```

Do not write dangerous output first and block later.

---

# 21. Policy result object

Suggested policy evaluation output:

```json
{
  "verdict": "requires_confirmation",
  "risk_score": 72,
  "risk_level": "high",
  "apply_allowed": false,
  "write_allowed": false,
  "cleanup_allowed": false,
  "requires_confirmation": true,
  "confirmation_items": [],
  "blocked_reasons": [],
  "warnings": [],
  "recommendations": [],
  "cleanup_decisions": [],
  "triggered_policies": []
}
```

Possible verdicts:

```text
safe_to_apply
apply_with_caution
requires_confirmation
blocked_by_policy
dry_run_only
```

---

# 22. Policy Center UI details

Suggested UI layout:

```text
Config Center → Policy Center

[Preset Mode]
Conservative / Balanced / Aggressive / Custom

[Cleanup Policies]
Global default action
Confirmation expiry
Apply confirmed cleanup: immediate / next run

[PPP Cleanup]
Normal inactive
Source disabled
Collector failed
Zero result
Mass removal
Respect guards

[DHCP Cleanup]
Normal inactive
Source disabled
Collector failed
Zero result
Mass removal
Respect guards

[Hotspot Cleanup]
Normal inactive
Source disabled
Collector failed
Zero result
Mass removal
Respect guards

[Node Cleanup Guard]
Threshold percent
Minimum node size
Minimum removed count
Action

[Small Node Guard]
Max small node size
Partial removal action
Full removal action

[Apply Guard]
Block duplicate IP
Block missing parent
Block invalid speed
Block collector failure

[Recommendations]
Show why/fix messages
Show next action
```

Each dropdown should include:

```text
Preserve rows
Warn only
Cleanup immediately
Cleanup on next run
Require confirmation then cleanup immediately
Require confirmation then cleanup next run
Block cleanup
Block apply
```

---

# 23. Preset modes

Add presets to simplify the UI.

## Conservative

Best for production / live ISP.

```text
More blocking
More confirmations
Lowest risk
```

Suggested behavior:

```text
PPP normal inactive: cleanup_next_run
DHCP normal inactive: cleanup_next_run
Hotspot normal inactive: cleanup_next_run
Source disabled: require_confirm_next_run
Collector failed: preserve_rows
Zero result: block_cleanup
Mass removal: require_confirm_next_run
Respect guards: true
```

## Balanced

Recommended default.

```text
Blocks dangerous changes
Allows normal operations
```

Suggested behavior:

```text
PPP normal inactive: cleanup_next_run
DHCP normal inactive: cleanup_next_run
Hotspot normal inactive: cleanup_immediate
Source disabled: require_confirm_next_run
Collector failed: preserve_rows
Zero result: block_cleanup
Mass removal: require_confirm_next_run
```

## Aggressive

For lab/testing or highly dynamic environments.

```text
Fast apply
Fewer blocks
More operator responsibility
```

Suggested behavior:

```text
PPP normal inactive: cleanup_immediate
DHCP normal inactive: cleanup_immediate
Hotspot normal inactive: cleanup_immediate
Source disabled: cleanup_next_run or require_confirm_next_run
Collector failed: preserve_rows
Zero result: warn_only or cleanup_next_run
Respect guards: optional
```

## Custom

Operator controls everything manually.

---

# 24. Smart warning format

Every warning should answer:

```text
What happened?
Why it matters?
What should I do?
```

Example:

```text
Some clients used fallback speed.

What happened:
3 PPPoE clients did not match speed from secret comment, active comment, profile comment, profile name, or rate-limit.

Why it matters:
They were assigned the default speed, which may be incorrect.

Recommended action:
Add speed to PPP secret comment or profile name.
```

---

# 25. Speed resolver diagnostics

For each client, optionally show resolver path.

Example PPP:

```text
Speed Resolution Path

1. PPP secret comment       empty
2. PPP active comment       empty
3. PPP profile comment      empty
4. PPP profile name         Tier-15M → matched
5. PPP profile rate-limit   not used
6. Default                  not used

Resolved speed: 15/15 Mbps
```

Example DHCP:

```text
1. DHCP server speed_comment   empty
2. DHCP server name            LAN → parsed 15M
3. DHCP server config speed    not used
4. Global default              not used

Resolved speed: 15/15 Mbps
```

This can be v2.46 if too large for v2.45.

---

# 26. Smart topology policies

Network Layout / topology save should respect:

```text
block_missing_parent_nodes
block_duplicate_node_names
warn_on_virtual_node_promotion
warn_on_deep_hierarchy_depth
max_recommended_depth
```

Before saving topology:

```text
Topology Impact Preview

network.json will change
6 nodes affected
17 clients affected
LibreQoS apply required after save
Risk: Low
```

If invalid:

```text
Topology save blocked.

Reasons:
3 clients reference missing parent nodes.
Duplicate node name found.
```

---

# 27. Backup guard

Recommended policy:

```json
{
  "backup_guard": {
    "require_backup_before_apply": true,
    "warn_if_backup_disabled_while_auto_apply_enabled": true,
    "minimum_backup_retention": 30
  }
}
```

Dashboard card:

```text
Backup Readiness

backup_before_apply: enabled
last backup: 3 minutes ago
retention: 30 backups
restorable: yes
```

If disabled:

```text
Warning:
Auto-apply is enabled but backup_before_apply is disabled.
Recommended: enable backups.
```

---

# 28. Event/audit logging

Every policy decision should be logged in audit events.

Audit event types:

```text
policy_decision
cleanup_blocked
cleanup_confirm_required
cleanup_confirmed
cleanup_applied
apply_blocked
risk_score_changed
recommendation_created
```

Audit event should include:

```json
{
  "event": "cleanup_confirm_required",
  "source": "pppoe",
  "router": "RB5k9-Distro",
  "reason": "source_disabled",
  "affected_rows": 35,
  "policy": "require_confirm_next_run",
  "risk_level": "high",
  "recommendations": []
}
```

---

# 29. State files

This can use existing runtime_state.json or add a dedicated policy state file.

Possible state structure:

```json
{
  "last_policy_decision": {},
  "pending_confirmations": [],
  "cleanup_queue": [],
  "last_successful_source_counts": {
    "pppoe": 35,
    "dhcp": 42,
    "hotspot": 8
  },
  "last_successful_node_counts": {
    "DHCP-LAN-RB5k9-Distro": 12
  }
}
```

If possible, store this under:

```text
/opt/lqosync/state/policy_state.json
```

or inside existing runtime state if project already centralizes state.

---

# 30. Suggested implementation phases

## v2.45 Smart Policy Center

Implement foundation:

```text
policy config defaults
Policy Center UI
per-source cleanup policy
immediate vs next-run cleanup
require confirmation
mass-removal guard
small-node guard
source-disabled handling
collector-failed preserve behavior
Dry Run verdict
Dashboard policy decision card
audit events
docs
```

## v2.46 Smart Insights

```text
risk score cards
data quality score
backup readiness
speed fallback review
recommendations panel
anomaly detection basics
```

## v2.47 Smart Lifecycle

```text
stale client lifecycle
pending cleanup queue
cleanup history table
confirmation expiry
per-client event timeline
```

## v2.48 Smart Setup / Repair

```text
setup wizard
guided repair assistant
update repair wizard
config health check
```

---

# 31. Acceptance criteria for v2.45

A v2.45 implementation is acceptable when:

```text
1. policies config exists with safe defaults
2. Policy Center UI exposes cleanup/apply policies
3. operator can set PPP/DHCP/Hotspot cleanup behavior independently
4. operator can choose immediate or next-run cleanup
5. source-disabled cleanup can require confirmation
6. collector failure preserves rows by default
7. zero result blocks or warns by policy
8. small-node percentage issue is handled
9. mass-removal guard works with min count and min node size
10. Dry Run shows verdict and policy decision
11. Dashboard shows policy decision card
12. pending confirmations are stored and expire
13. confirmation applies immediate or next run depending on policy
14. audit events record decisions and confirmations
15. no dangerous cleanup happens before policy evaluation
```

---

# 32. Example scenario tests

## Test A: DHCP small node

Before:

```text
DHCP-LAN = 3 clients
Removed = 1
Threshold = 30%
```

Expected:

```text
Not blocked by percentage guard because min_node_size/min_removed_count not met.
Uses small_node_guard.partial_removal_action.
```

## Test B: PPP disabled

Before:

```text
PPP rows = 35
pppoe.enabled = false
```

Policy:

```text
source_disabled_action = require_confirm_next_run
```

Expected:

```text
Dry run verdict: Requires confirmation
No deletion yet
Dashboard shows Confirm PPP cleanup
After confirmation, next run removes PPP rows
```

## Test C: DHCP collector failed

```text
dhcp.enabled = true
API read failed
```

Expected:

```text
DHCP rows preserved
cleanup blocked for DHCP
warning shown
apply blocked if proposed output unsafe
```

## Test D: DHCP zero result

```text
dhcp.enabled = true
scan succeeded
valid leases = 0
previous successful DHCP count = 42
```

Expected:

```text
cleanup blocked or require confirmation depending on zero_result_action
```

## Test E: DHCP immediate cleanup

Policy:

```text
dhcp.normal_inactive_action = cleanup_immediate
dhcp.respect_percentage_guards = false
```

Expected:

```text
Absent DHCP rows removed same cycle
LibreQoS apply runs if files changed and apply guard allows
```

## Test F: Duplicate IP

Policy:

```text
block_apply_on_duplicate_ip = true
```

Expected:

```text
Policy decision blocks apply
Dry Run verdict: Blocked by policy
```

---

# 33. UI wording examples

## Policy blocked

```text
Apply blocked by policy.

Reason:
DHCP source returned zero rows after previous successful scan.

Why this matters:
This may indicate a MikroTik API, VLAN, DHCP server, or collector issue.
Deleting all DHCP rows could remove valid clients from LibreQoS.

Recommended action:
Check DHCP source and run Dry Run again.
```

## Confirmation required

```text
Cleanup confirmation required.

Source:
PPPoE

Reason:
PPPoE collector was disabled in config.

Affected rows:
35

Policy:
Require confirmation, cleanup on next run.

Next action:
Confirm cleanup or re-enable PPPoE collector.
```

## Immediate cleanup allowed

```text
Cleanup allowed.

Source:
DHCP

Reason:
Normal inactive clients.

Policy:
Cleanup immediately.

Result:
Rows will be removed in this sync cycle and LibreQoS will apply if files changed.
```

---

# 34. Final architecture statement

The correct final architecture:

```text
LQoSync should be policy-driven.

Config defines what the operator wants.
Policies define how safely it happens.
Policy engine decides before write/apply.
Dashboard and Dry Run explain every decision.
```

This turns LQoSync into a smart and intelligent production operator tool, not just a sync script.

````

I recommend i-paste mo ito sa original branch, then sabihin mo:

```text
Use this as the implementation spec for v2.45 Smart Policy Center. Do not apply the old patch blindly. Implement directly against the latest full project tree.
````


```markdown
# Suggested Release Roadmap

## v2.45 Smart Policy Center

Main brain of the system.

- policy config defaults
- Policy Center UI
- cleanup policy engine
- per-source policy overrides
- immediate vs next-run cleanup
- confirmation requirement
- mass-removal guard
- source-disabled handling
- collector-failed preserve behavior
- Dry Run verdict
- Dashboard policy decision card
- audit events
- documentation update

## v2.46 Smart Insights

- risk score
- data quality score
- backup readiness
- speed fallback review
- recommendation cards
- anomaly detection basics
- smart warning explanations
- Why / Fix / Next Action messages
- update status recommendation
- fallback-speed review table

## v2.47 Smart Lifecycle

- stale client lifecycle
- pending cleanup queue
- cleanup history
- confirmation expiry
- per-client event timeline
- cleanup applied / blocked / confirmed audit trail
- returned-client detection
- source lifecycle state tracking

## v2.48 Smart Setup / Repair

- setup wizard
- guided repair assistant
- update repair wizard
- config health check
- MikroTik connection test wizard
- LibreQoS path / permission checker
- Git install/adoption checker
- policy preset setup during first install
```

Final instruction to paste sa original branch:

```text
Use the full handoff documentation plus this release roadmap as the implementation spec. Do not apply any old patch blindly. Implement directly against the latest full LQoSync project tree.
```


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


## v2.54.2 Policy Center Setup Guidelines

Policy Center now includes atomic setup guidance for every visible setting. Each field explains what it controls, recommended setup, risk note, config path, recommended value, and risk level. The detailed guide is available at `docs/content/policy_center_settings_guidelines.md`.

This update also normalizes stale lifecycle PPPoE policy naming to the canonical `pppoe` key while accepting the older `ppoe` alias from previous schema builds, preventing false missing-policy warnings after upgrades or fresh installs.


## v2.56 Policy UX + Conflict Intelligence

LQoSync v2.56 adds read-only Policy Conflict Resolver checks, improved current-vs-preset comparison, and Client Identity Handling guidance inside Smart Policy Center.

The conflict resolver explains risky combinations such as immediate cleanup combined with permissive zero-result handling, collector-failed cleanup that could delete rows, source-disabled immediate cleanup, high/critical risk auto-apply, disabled apply guards, and grace enabled for mixed/unstable identity sources.

Client Identity Handling explains that PPPoE usernames are usually stable, DHCP server+MAC is mixed because of private/random MAC behavior, Hotspot is stable only when username/voucher based, and Static/manual rows are operator-controlled.


---

# Smart Setup / Repair Center

LQoSync v2.48 adds a guided Setup / Repair Center for operators who want a safer way to verify, repair, and prepare an installation without guessing which command to run.

The center is read-only by default. It does not automatically repair the server when opened. Instead, it checks the current config, paths, services, Git status, LibreQoS runner settings, router configuration completeness, and backup readiness, then explains what is healthy, what needs attention, and what command should be run from SSH.

## What it checks

- `config.json` validation errors and warnings
- LibreQoS managed files: `ShapedDevices.csv` and `network.json`
- Runtime files such as `runtime_state.json`, `policy_state.json`, `audit.jsonl`, and backups
- LibreQoS command and working directory
- Bare-metal runner mode safety, especially `run_mode=direct`
- Router configuration completeness
- Required service status for `lqosd`, `lqos_scheduler`, and `lqosync`
- Git/update state when available
- Backup-before-apply readiness

## Readiness levels

- `ready` means no failed checks or warnings were found.
- `needs_attention` means no hard failure was found, but warnings should be reviewed before enabling scheduler or auto-apply.
- `repair_required` means one or more failed checks should be fixed before production use.

## Guided setup checklist

The page shows a first-install checklist:

1. Confirm LibreQoS base path.
2. Create restricted MikroTik API user.
3. Add or verify routers.
4. Discover DHCP servers.
5. Choose network layout mode.
6. Select Smart Policy preset.
7. Run Dry Run.
8. Enable scheduler only after the dry run is clean.

## Guided repair commands

The page provides copy-ready repair commands for common scenarios:

- Safe bare-metal repair/reinstall with `LQOSYNC_INIT_POLICY=preserve_existing`
- Restore LibreQoS permissions after uninstall or stale ACLs
- Run the environment doctor
- Safe GitHub update with `UPDATE_POLICY=preserve_and_migrate`
- Adopt ZIP/manual install into GitHub-managed install
- Check LibreQoS core services

## Policy preset setup

The page can apply one of the built-in Smart Policy presets:

- Conservative: safest live production behavior with more confirmations.
- Balanced: recommended default.
- Aggressive: fast cleanup for lab or highly dynamic environments.

After changing presets, always run Dry Run before enabling scheduler or auto-apply.

## MikroTik connection testing

The page lists configured routers and links operators to Config Center for live API tests. The Setup / Repair Center itself avoids contacting routers during page load so it remains safe and fast.

## Safety principle

The Setup / Repair Center explains actions and gives commands. It does not blindly modify LibreQoS files, run Git updates, restart services, or contact routers just because the page is opened.


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


## v2.54 First Run Setup Wizard

LQoSync v2.54 adds a guided First Run Setup Wizard. The wizard computes readiness from config, runtime state, setup/repair checks, source configuration, Network Layout mode, Smart Policy preset, Dry Run status, and scheduler state. It gives the operator a clean onboarding path: confirm LibreQoS paths, configure MikroTik routers, enable PPPoE/DHCP/Hotspot sources, choose Network Layout, choose policy preset, run Dry Run, and enable scheduler only after results are clean and expected.

The wizard is read-only while loading. It does not contact routers or write generated LibreQoS files automatically. Policy preset and layout-mode changes are explicit form actions and are followed by a reminder to run Dry Run.


## v2.59 Documentation Search + UI/Mobile Polish

LQoSync v2.59 adds a local Documentation Search Center at `/docs/search`. It indexes bundled Markdown documentation and docs manifest entries so operators can quickly find policy, setup, troubleshooting, update, Telegram, MikroTik, and LibreQoS guidance. Search is local/read-only and does not send queries outside the WebUI.

This release also adds reusable UI/mobile consistency helpers for cleaner responsive grids, action strips, empty states, section cards, and mobile sticky action areas.


## v2.60 Better Fresh Install Experience

LQoSync v2.60 improves first-run onboarding. New installs are guided to the First Run Setup Wizard, the Dashboard shows a setup-incomplete banner, and scheduler enable is protected until router/source setup, Dry Run, and Setup & Repair checks are ready. Existing live installs with prior run history or scheduler already enabled are not forced into the wizard after upgrade.

The new `setup_wizard` config block controls redirect behavior, Dashboard banners, and scheduler-enable requirements. Operators can mark setup complete when readiness is satisfied or reset the wizard to repeat onboarding.


---

# Policy-Aware Cleanup Intelligence

LQoSync v2.50 extends Smart Policy Center with deeper policy intelligence while keeping operator control in `config.json -> policies`.

## What changed

- Added optional source-aware stale lifecycle settings.
- Added optional grace-run behavior for normal inactive cleanup.
- Added risk-aware LibreQoS auto-apply policy.
- Added policy decision trace entries so operators can see which policies influenced cleanup/apply behavior.
- Added cleanup queue seen-run tracking so next-run/grace cleanup can be reasoned about across sync cycles.

## Stale lifecycle and grace

Grace is optional and disabled by default per source. It should only be enabled when identity is stable.

Recommended use:

```text
PPPoE username        -> grace can be useful
Hotspot username      -> grace can be useful if voucher/username is stable
DHCP randomized MAC   -> grace is risky and should stay disabled
```

If grace is enabled for a source, normal inactive rows are queued until they have been missing for the configured number of consecutive runs. If the same client identity returns before cleanup, Smart Lifecycle records a returned-client event and active state resumes.

## Risk-aware auto apply

`policies.auto_apply_policy` decides whether LibreQoS.py may run automatically by risk level:

```json
{
  "enabled": true,
  "allow_low_risk": true,
  "allow_medium_risk": false,
  "allow_high_risk": false,
  "allow_critical_risk": false,
  "when_blocked": "keep_pending_manual_apply"
}
```

If files are written but risk-aware auto apply does not allow the current risk level, LQoSync keeps the LibreQoS apply pending for operator review. This gives fast automatic apply for low-risk changes while preventing medium/high-risk changes from silently applying.

## Decision trace

Policy decisions now include a `decision_trace` list. It explains rules like:

```text
cleanup_next_run queued a client
optional stale lifecycle required N missing runs
auto apply was allowed or held by risk policy
source cleanup guard triggered
confirmation required
```

The trace is intended for Dashboard, Dry Run, logs, and troubleshooting.


---

# Config Schema + Policy Simulation Engine

LQoSync v2.51 adds a read-only simulation layer for Config Center. The goal is to let operators preview settings changes before saving `config.json` or running a live sync.

## What it does

- Adds `config_schema_version` to config.json.
- Migrates missing safe defaults without overwriting operator values.
- Validates required paths, network mode, LibreQoS working directory, policy actions, policy data types, and risky policy combinations.
- Calculates a Config Health score.
- Compares saved config with the in-browser proposed config.
- Simulates policy impact before save.
- Shows verdict, risk level, recommendations, and important changed fields.

## New engine modules

```text
engine/config_schema.py
engine/config_diff.py
engine/config_simulator.py
engine/policy_simulator.py
```

## Config Center behavior

The Config Center side panel now includes **Config Health / Simulation**.

Operators can click:

```text
Preview Impact
```

This sends the current unsaved UI config to `/config/simulate` and returns:

```text
verdict
risk_level
schema health
migration notes
changed fields
important changes
policy simulation
recommendations
```

No files are written. `config.json`, `ShapedDevices.csv`, `network.json`, and LibreQoS are untouched.

## Verdict examples

```text
safe_to_save
```

The proposed config has no major schema or risk issues.

```text
dry_run_recommended
```

The proposed config is valid but changes important behavior. Dry Run is recommended before live scheduler/auto-apply.

```text
save_with_caution_and_dry_run
```

The proposed config changes risky behavior such as auto-apply, source enablement, network mode, or immediate cleanup.

```text
cannot_save
```

The proposed config has schema errors and should not be saved.

## Why this matters

Policy Center gives operators freedom. v2.51 adds a safety preview so that flexibility remains understandable and traceable.

Example:

```text
DHCP normal inactive cleanup:
cleanup_next_run → cleanup_immediate
```

Simulation can explain:

```text
Immediate cleanup enabled.
Missing DHCP rows can be removed in the same sync cycle.
Run Dry Run after saving, especially if auto-apply is enabled.
```

## Design rule

```text
Settings changes should be explainable before they are saved.
```


---

# Smart Reports + Operator Audit

LQoSync v2.52 adds an operator-facing Smart Reports center at `/reports`. The page summarizes the last 24 hours of sync, dry-run, policy, cleanup, configuration, LibreQoS apply, and audit events.

## What it reports

- 24h sync and dry-run summary
- failed sync count
- policy blocked count
- cleanup confirmation count
- latest policy decision and risk level
- cleanup report with removed, queued, preserved, and pending confirmation counts
- client change report from the latest run
- config/operator audit report
- smart recommendations from Smart Insights

## Export options

Reports can be exported as JSON, CSV, or Markdown. The page also has a print-friendly layout for browser print/PDF workflows. Exports are read-only and do not write config, generated files, or LibreQoS state.

## Source of truth

The report uses existing runtime state, policy state, audit events, apply history, services, and backup metadata. It does not create a separate database.


---

# Client Lifecycle Timeline

LQoSync v2.53 expands the Smart Lifecycle Center into a client timeline and cleanup-state investigation tool.

## Purpose

The Lifecycle Center helps operators answer:

- Which clients are active, stale, queued for cleanup, removed, or returned?
- Why was a cleanup queued or preserved?
- Which source is responsible: PPPoE, DHCP, Hotspot, Static, or Unknown?
- Which client changed speed, parent node, IP, MAC, or status?
- Are there pending confirmations or cleanup queue entries?

## Client lifecycle states

- `active` — client is present in the latest generated output.
- `stale` — client is missing but preserved by policy.
- `queued_cleanup` — client is scheduled for cleanup by policy on a later run.
- `confirmed_cleanup` — operator confirmed cleanup and it is waiting to be applied.
- `removed` — client has been removed or cleanup was applied.
- `unknown` — state is incomplete or imported from older runtime state.

## Timeline events

Lifecycle events include:

- `client_added`
- `client_updated`
- `client_returned`
- `client_removed`
- `cleanup_queued`
- `cleanup_preserved`
- `cleanup_applied`

Every event can carry source, reason, parent node, IP, MAC, speed, changed fields, and timestamp.

## Exports

The Lifecycle Center provides JSON, CSV, and Markdown exports so operators can attach a lifecycle report to audits, support requests, or troubleshooting notes.

## Privacy mode

Lifecycle tables and timelines use WebUI redaction classes. When Privacy Mode is enabled, visible client names, nodes, IP addresses, and MAC addresses are masked in the browser only. Source files and state files are unchanged.


## v2.60.1 Client Lifecycle View and Filter Hotfix

The Client Lifecycle page now uses instant searchable filters similar to the Shaped Devices/Subscribers table. The View button preserves current filters and focuses the selected client's timeline correctly. Timeline Focus now supports event type filtering, row-limit selection, and pagination with Prev/Next controls. Mobile lifecycle cards use the same filtering and View/focus behavior as the desktop table.


---

# First Run Setup Wizard

LQoSync v2.54 adds a guided First Run Setup Wizard. The wizard is designed for new installs and major reconfiguration work. It does not replace Setup & Repair; instead, it gives operators a clean step-by-step path to production readiness.

## Purpose

The wizard answers:

- Are LibreQoS paths available?
- Are MikroTik routers configured?
- Are PPPoE / DHCP / Hotspot sources selected?
- Which Network Layout mode is active?
- Which Smart Policy preset is active?
- Has a Dry Run been completed?
- Is the scheduler ready to be enabled?

## Safety model

The wizard is read-only while loading. It does not contact routers or write generated LibreQoS files on page load. Write actions are deliberate form submissions such as applying a policy preset or saving a network layout mode.

Operators should follow this order:

1. Confirm LibreQoS paths.
2. Configure MikroTik router access.
3. Choose enabled PPPoE / DHCP / Hotspot sources.
4. Choose Network Layout mode.
5. Choose Smart Policy preset.
6. Run Dry Run.
7. Review Smart Reports / Lifecycle if needed.
8. Enable scheduler only after Dry Run is clean and expected.

## Relationship to Setup & Repair

Setup Wizard is for first-run onboarding and go-live flow.

Setup & Repair is for diagnostics, failed checks, repair commands, permission/path checks, and recovery guidance.

About / Documentation remains the long-form manual source of truth.


---

# v2.54.1 Smart Reports Route Hotfix

This hotfix restores the missing Flask route wiring for Smart Reports in `app.py`.

Fixed routes:

- `/reports`
- `/api/reports/operator`
- `/reports/export/json`
- `/reports/export/csv`
- `/reports/export/markdown`

The issue was that the Smart Reports engine, template, and navigation existed, but Flask did not register the page/API routes, so the browser returned `404 Not Found`.


---

# Policy Center Settings Guidelines

This guide is the operator-facing explanation for every visible Policy Center setting. It is intended as setup guidance, not just developer documentation.

## Cleanup action meanings

- **preserve_rows** — Keep existing rows and do not delete stale entries. Safest when the source may be temporarily unavailable.
- **warn_only** — Show a warning but do not remove rows. Useful while tuning policies.
- **cleanup_immediate** — Remove stale rows in the same sync cycle. Fastest, but can cause more LibreQoS applies if clients flap.
- **cleanup_next_run** — Mark stale rows and remove them on the next successful run. Safer than immediate cleanup.
- **require_confirm_immediate** — Ask operator confirmation first, then allow same-cycle cleanup after confirmation.
- **require_confirm_next_run** — Ask operator confirmation first, then apply cleanup on the next successful run. Recommended for risky changes.
- **block_cleanup** — Prevent cleanup. Existing rows are preserved until the issue is fixed or policy is changed.
- **block_apply** — Block LibreQoS apply for this condition. Used for dangerous validation failures.

## Policy settings by section

### Preset

#### Preset mode

- **Config path:** `policies.mode`
- **Type:** `select`
- **Allowed values:** `conservative`, `balanced`, `aggressive`, `custom`
- **Recommended:** `balanced`
- **Risk:** `low`
- **What it controls:** Selects the active policy preset. Conservative is strict, Balanced is recommended for production, Aggressive prioritizes speed, and Custom means the operator manually changed individual settings.
- **Setup guide:** Start with Balanced. Use Conservative for live networks where accidental deletion is unacceptable. Use Aggressive only for lab/highly dynamic environments. Any manual policy edit should save as Custom.
- **Risk note:** Changing presets can modify many cleanup/apply rules at once. Run Dry Run after applying a preset.

### Cleanup Core

#### Cleanup policy engine

- **Config path:** `policies.cleanup.enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `high`
- **What it controls:** Turns the Smart Cleanup Policy Engine on or off. When enabled, LQoSync classifies why rows are stale before deciding whether to delete, preserve, confirm, or block.
- **Setup guide:** Keep enabled. Disabling this returns cleanup behavior closer to simple sync logic and removes important protection.
- **Risk note:** Disabling cleanup intelligence can allow unintended stale-row removal depending on older code paths.

#### Global default cleanup action

- **Config path:** `policies.cleanup.global_default_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `require_confirm_next_run`
- **Risk:** `high`
- **What it controls:** Fallback cleanup action used when no source-specific or reason-specific policy matches a cleanup candidate.
- **Setup guide:** Use require_confirm_next_run for conservative production behavior. Use cleanup_next_run for a faster but still staged workflow.
- **Risk note:** Avoid cleanup_immediate as the global default unless the operator accepts fast deletion for all sources.

#### Confirmation expiry hours

- **Config path:** `policies.cleanup.confirmation_expires_hours`
- **Type:** `number`
- **Recommended:** `24`
- **Risk:** `medium`
- **What it controls:** Controls how long a pending cleanup confirmation remains valid before the operator must confirm again.
- **Setup guide:** 24 hours is a good default. Use shorter values if many operators change config; use longer values for planned migrations.
- **Risk note:** Very long expiry can apply an old confirmation after the network/config has changed.

#### Confirmed cleanup apply mode

- **Config path:** `policies.cleanup.apply_confirmed_cleanup`
- **Type:** `select`
- **Allowed values:** `immediate`, `next_run`
- **Recommended:** `next_run`
- **Risk:** `medium`
- **What it controls:** Controls when cleanup happens after the operator confirms a pending cleanup decision.
- **Setup guide:** Use next_run for production so LQoSync re-checks current config and source state before deleting. Use immediate for urgent manual cleanup.
- **Risk note:** Immediate confirmed cleanup can remove rows before another full collection confirms the condition.

#### Allow immediate cleanup

- **Config path:** `policies.cleanup.allow_immediate_cleanup`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `high`
- **What it controls:** Master permission that allows any policy to delete stale rows in the same sync cycle.
- **Setup guide:** Enable if DHCP/Hotspot should update quickly. Disable if all deletions must be staged or confirmed first.
- **Risk note:** If enabled with aggressive source policies, dynamic clients can cause more file churn and LibreQoS applies.

### PPPoE Cleanup

#### PPPoE cleanup policy

- **Config path:** `policies.cleanup_sources.pppoe.enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Enables the source-specific cleanup policy block for PPPoE. When disabled, global cleanup defaults are used for this source.
- **Setup guide:** Keep enabled if PPPoE should have its own behavior for inactive, disabled, failed, zero-result, and mass-removal cases.
- **Risk note:** Disabling source-specific policies can make the source follow broader defaults that may be too aggressive or too conservative.

#### Normal inactive action

- **Config path:** `policies.cleanup_sources.pppoe.normal_inactive_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `cleanup_next_run`
- **Risk:** `high`
- **What it controls:** Action when a PPPoE account that was previously active is no longer active during a normal scan.
- **Setup guide:** cleanup_next_run is recommended because PPPoE usernames are stable but sessions can reconnect shortly.
- **Risk note:** cleanup_immediate can remove/add the same subscriber if PPP reconnects quickly.

#### Source disabled action

- **Config path:** `policies.cleanup_sources.pppoe.source_disabled_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `require_confirm_next_run`
- **Risk:** `high`
- **What it controls:** Action when PPPoE collection is disabled in config and existing PPPoE rows would disappear.
- **Setup guide:** Use require_confirm_next_run because this is an intentional but high-impact operator change.
- **Risk note:** cleanup_immediate can remove all PPPoE rows if the source is disabled by mistake.

#### Collector failed action

- **Config path:** `policies.cleanup_sources.pppoe.collector_failed_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `preserve_rows`
- **Risk:** `critical`
- **What it controls:** Action when PPPoE is enabled but MikroTik API collection fails.
- **Setup guide:** Use preserve_rows. API failure is not proof that subscribers are gone.
- **Risk note:** Deleting on collector failure can wipe valid PPPoE clients from LibreQoS.

#### Zero-result action

- **Config path:** `policies.cleanup_sources.pppoe.zero_result_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `block_cleanup`
- **Risk:** `critical`
- **What it controls:** Action when PPPoE collection succeeds but returns zero rows while enabled.
- **Setup guide:** Use block_cleanup or require_confirm_next_run unless zero active PPP users is normal for your network.
- **Risk note:** Zero result after previous success may indicate API/profile/query issues.

#### Mass-removal action

- **Config path:** `policies.cleanup_sources.pppoe.mass_removal_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `require_confirm_next_run`
- **Risk:** `high`
- **What it controls:** Action when PPPoE removal exceeds node/source guard thresholds.
- **Setup guide:** Use require_confirm_next_run so the operator reviews the impact.
- **Risk note:** Immediate mass PPPoE cleanup can remove many active subscribers if detection is wrong.

#### Respect percentage/count guards

- **Config path:** `policies.cleanup_sources.pppoe.respect_percentage_guards`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Allows node/source percentage and count guards to override normal PPPoE cleanup behavior.
- **Setup guide:** Keep enabled for PPPoE because PPP usernames represent real subscribers.
- **Risk note:** Turning off guards makes PPPoE cleanup more aggressive.

### DHCP Cleanup

#### DHCP cleanup policy

- **Config path:** `policies.cleanup_sources.dhcp.enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Enables the source-specific cleanup policy block for DHCP. When disabled, global cleanup defaults are used for this source.
- **Setup guide:** Keep enabled if DHCP should have its own behavior for inactive, disabled, failed, zero-result, and mass-removal cases.
- **Risk note:** Disabling source-specific policies can make the source follow broader defaults that may be too aggressive or too conservative.

#### Normal inactive action

- **Config path:** `policies.cleanup_sources.dhcp.normal_inactive_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `cleanup_immediate`
- **Risk:** `high`
- **What it controls:** Action when a DHCP lease/client disappears during normal operation.
- **Setup guide:** Use cleanup_immediate for dynamic/PisoWiFi-style DHCP, or cleanup_next_run for subscriber DHCP.
- **Risk note:** Immediate cleanup is fast but can increase LibreQoS apply frequency if leases flap.

#### Source disabled action

- **Config path:** `policies.cleanup_sources.dhcp.source_disabled_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `require_confirm_next_run`
- **Risk:** `high`
- **What it controls:** Action when DHCP collection or a DHCP server source is disabled and existing DHCP rows would disappear.
- **Setup guide:** Use require_confirm_next_run because disabling a source can remove many rows intentionally.
- **Risk note:** Immediate cleanup can remove rows because of a config mistake.

#### Collector failed action

- **Config path:** `policies.cleanup_sources.dhcp.collector_failed_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `preserve_rows`
- **Risk:** `critical`
- **What it controls:** Action when DHCP is enabled but lease collection fails.
- **Setup guide:** Use preserve_rows. Failure to read leases is not proof that clients are gone.
- **Risk note:** Deleting rows on failed collection can remove valid clients.

#### Zero-result action

- **Config path:** `policies.cleanup_sources.dhcp.zero_result_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `block_cleanup`
- **Risk:** `critical`
- **What it controls:** Action when DHCP scan succeeds but returns zero leases while DHCP is enabled.
- **Setup guide:** Use block_cleanup by default. A zero result may mean VLAN/API/DHCP source issue.
- **Risk note:** cleanup_immediate can wipe DHCP rows if the scan result is wrong.

#### Mass-removal action

- **Config path:** `policies.cleanup_sources.dhcp.mass_removal_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `require_confirm_next_run`
- **Risk:** `high`
- **What it controls:** Action when DHCP removal exceeds source/node guard thresholds.
- **Setup guide:** require_confirm_next_run is safest. If DHCP is intentionally dynamic, adjust respect_percentage_guards.
- **Risk note:** Mass DHCP cleanup can be normal in guest networks but dangerous in subscriber networks.

#### Respect percentage/count guards

- **Config path:** `policies.cleanup_sources.dhcp.respect_percentage_guards`
- **Type:** `bool`
- **Recommended:** `False`
- **Risk:** `medium`
- **What it controls:** Controls whether mass-removal guards can override DHCP normal cleanup.
- **Setup guide:** Disable for highly dynamic DHCP; enable for subscriber DHCP.
- **Risk note:** Disabling guards makes DHCP cleanup faster but less protected.

### Hotspot Cleanup

#### Hotspot cleanup policy

- **Config path:** `policies.cleanup_sources.hotspot.enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Enables the source-specific cleanup policy block for Hotspot. When disabled, global cleanup defaults are used for this source.
- **Setup guide:** Keep enabled if Hotspot should have its own behavior for inactive, disabled, failed, zero-result, and mass-removal cases.
- **Risk note:** Disabling source-specific policies can make the source follow broader defaults that may be too aggressive or too conservative.

#### Normal inactive action

- **Config path:** `policies.cleanup_sources.hotspot.normal_inactive_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `cleanup_immediate`
- **Risk:** `high`
- **What it controls:** Action when Hotspot active users/sessions disappear normally.
- **Setup guide:** cleanup_immediate is usually acceptable for session-style Hotspot. Use cleanup_next_run if users flap often.
- **Risk note:** Immediate cleanup may cause more applies in busy captive/session environments.

#### Source disabled action

- **Config path:** `policies.cleanup_sources.hotspot.source_disabled_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `require_confirm_next_run`
- **Risk:** `high`
- **What it controls:** Action when Hotspot collection is disabled and existing Hotspot rows would disappear.
- **Setup guide:** cleanup_next_run or require_confirm_next_run are safer than immediate deletion.
- **Risk note:** Immediate deletion can remove all Hotspot rows if disabled accidentally.

#### Collector failed action

- **Config path:** `policies.cleanup_sources.hotspot.collector_failed_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `preserve_rows`
- **Risk:** `critical`
- **What it controls:** Action when Hotspot is enabled but active-user collection fails.
- **Setup guide:** Use preserve_rows because a read failure is not proof users are gone.
- **Risk note:** Deleting on failure can remove valid active sessions.

#### Zero-result action

- **Config path:** `policies.cleanup_sources.hotspot.zero_result_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `warn_only`
- **Risk:** `critical`
- **What it controls:** Action when Hotspot scan succeeds but returns zero users.
- **Setup guide:** warn_only or cleanup_next_run can be reasonable if sessions naturally empty; block_cleanup for production sensitivity.
- **Risk note:** cleanup_immediate may be okay for small guest networks but risky after a collector anomaly.

#### Mass-removal action

- **Config path:** `policies.cleanup_sources.hotspot.mass_removal_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `require_confirm_next_run`
- **Risk:** `high`
- **What it controls:** Action when Hotspot removal exceeds thresholds.
- **Setup guide:** require_confirm_next_run is safest if Hotspot users are subscribers; warn_only/cleanup_next_run may fit guest sessions.
- **Risk note:** Mass Hotspot removal may be normal after vouchers expire but should be visible.

#### Respect percentage/count guards

- **Config path:** `policies.cleanup_sources.hotspot.respect_percentage_guards`
- **Type:** `bool`
- **Recommended:** `False`
- **Risk:** `medium`
- **What it controls:** Controls whether mass-removal guards can override Hotspot cleanup.
- **Setup guide:** Disable for highly dynamic sessions; enable for subscriber-like Hotspot use.
- **Risk note:** Disabling guards favors speed over safety.

### Static/manual rows Cleanup

#### Static/manual rows cleanup policy

- **Config path:** `policies.cleanup_sources.static.enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Enables the source-specific cleanup policy block for Static/manual. When disabled, global cleanup defaults are used for this source.
- **Setup guide:** Keep enabled if Static/manual should have its own behavior for inactive, disabled, failed, zero-result, and mass-removal cases.
- **Risk note:** Disabling source-specific policies can make the source follow broader defaults that may be too aggressive or too conservative.

#### Normal inactive action

- **Config path:** `policies.cleanup_sources.static.normal_inactive_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `preserve_rows`
- **Risk:** `high`
- **What it controls:** Action when static/manual rows appear absent from generated data.
- **Setup guide:** preserve_rows is recommended because manual/static rows are operator-managed.
- **Risk note:** Automatic deletion of manual rows can remove intentionally preserved devices.

#### Source disabled action

- **Config path:** `policies.cleanup_sources.static.source_disabled_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `require_confirm_next_run`
- **Risk:** `high`
- **What it controls:** Action when static/manual source behavior is disabled or excluded.
- **Setup guide:** preserve_rows unless the operator explicitly confirms removal.
- **Risk note:** Immediate cleanup can delete hand-maintained entries.

#### Collector failed action

- **Config path:** `policies.cleanup_sources.static.collector_failed_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `preserve_rows`
- **Risk:** `critical`
- **What it controls:** Action when manual/static source loading fails.
- **Setup guide:** preserve_rows. Manual rows should not disappear due to a read error.
- **Risk note:** Deleting on load failure is unsafe.

#### Zero-result action

- **Config path:** `policies.cleanup_sources.static.zero_result_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `warn_only`
- **Risk:** `critical`
- **What it controls:** Action when static/manual source returns no rows.
- **Setup guide:** preserve_rows by default.
- **Risk note:** Zero result may be a file/path/config problem.

#### Mass-removal action

- **Config path:** `policies.cleanup_sources.static.mass_removal_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `require_confirm_next_run`
- **Risk:** `high`
- **What it controls:** Action when many static/manual rows would be removed.
- **Setup guide:** preserve_rows or require_confirm_next_run.
- **Risk note:** Manual rows should not be mass-deleted automatically.

#### Respect percentage/count guards

- **Config path:** `policies.cleanup_sources.static.respect_percentage_guards`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Allows mass-removal guards to protect manual/static rows.
- **Setup guide:** Keep enabled.
- **Risk note:** Disabling can allow aggressive cleanup of manual data.

### Mass Removal Guards

#### Node removal guard

- **Config path:** `policies.node_cleanup_guard.enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `high`
- **What it controls:** Enables protection for individual generated nodes such as a DHCP server node, PPP plan node, or Hotspot node.
- **Setup guide:** Keep enabled so one node losing many clients is detected before cleanup/apply.
- **Risk note:** Disabling can allow a broken source/node to delete many rows.

#### Node removal threshold percent

- **Config path:** `policies.node_cleanup_guard.threshold_percent`
- **Type:** `number`
- **Recommended:** `30`
- **Risk:** `high`
- **What it controls:** Percentage of clients removed from one node before the node guard can trigger.
- **Setup guide:** 30% is a good default. Lower is stricter; higher is more permissive.
- **Risk note:** Percentage alone is not enough for small nodes; min_node_size and min_removed_count also apply.

#### Minimum node size

- **Config path:** `policies.node_cleanup_guard.min_node_size`
- **Type:** `number`
- **Recommended:** `10`
- **Risk:** `medium`
- **What it controls:** Minimum previous node size required before percentage-based node protection applies.
- **Setup guide:** Use 10 so a small node with 3 clients does not block just because 1 client disappeared.
- **Risk note:** Too low makes small nodes noisy; too high may miss medium-size node failures.

#### Minimum removed count

- **Config path:** `policies.node_cleanup_guard.min_removed_count`
- **Type:** `number`
- **Recommended:** `3`
- **Risk:** `medium`
- **What it controls:** Minimum number of removed rows required before percentage-based node protection applies.
- **Setup guide:** Use 3 to avoid blocking normal 1-client movement in small DHCP nodes.
- **Risk note:** Too low causes false alarms; too high can miss real removals.

#### Node guard action

- **Config path:** `policies.node_cleanup_guard.action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `require_confirm_next_run`
- **Risk:** `high`
- **What it controls:** Action taken when one generated node exceeds node removal thresholds.
- **Setup guide:** require_confirm_next_run is safest. cleanup_next_run is faster. block_cleanup is strictest.
- **Risk note:** cleanup_immediate here can delete many rows from one node without review.

#### Small-node guard

- **Config path:** `policies.small_node_guard.enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Uses special behavior for small nodes so raw percentages do not overreact to one client disappearing.
- **Setup guide:** Keep enabled. It prevents cases like 1 of 3 clients removed from being treated as a dangerous 33% mass removal.
- **Risk note:** Disabling means percentage thresholds may be noisy on tiny nodes.

#### Small-node max size

- **Config path:** `policies.small_node_guard.max_node_size`
- **Type:** `number`
- **Recommended:** `5`
- **Risk:** `medium`
- **What it controls:** Defines what counts as a small node for small-node handling.
- **Setup guide:** 5 is a practical default for small DHCP/Hotspot groups.
- **Risk note:** Higher values make more nodes bypass normal percentage logic.

#### Small-node partial removal

- **Config path:** `policies.small_node_guard.partial_removal_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `cleanup_next_run`
- **Risk:** `medium`
- **What it controls:** Action when only some clients disappear from a small node.
- **Setup guide:** cleanup_next_run is a balanced default. cleanup_immediate is acceptable for dynamic DHCP/Hotspot if operator wants fast cleanup.
- **Risk note:** require_confirm for every small-node partial removal can create too many prompts.

#### Small-node full removal

- **Config path:** `policies.small_node_guard.full_removal_action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `require_confirm_next_run`
- **Risk:** `high`
- **What it controls:** Action when all clients disappear from a small node.
- **Setup guide:** require_confirm_next_run is recommended because 100% removal, even on a small node, may indicate source/config trouble.
- **Risk note:** cleanup_immediate can delete all rows from a small node without review.

#### Source removal guard

- **Config path:** `policies.source_cleanup_guard.enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `high`
- **What it controls:** Protects an entire source, such as all PPPoE, all DHCP, or all Hotspot rows, from large unexpected removal.
- **Setup guide:** Keep enabled in production. Source-wide drops are usually high-risk unless intentionally disabled.
- **Risk note:** Disabling removes protection against source-wide API/config mistakes.

#### Source threshold percent

- **Config path:** `policies.source_cleanup_guard.threshold_percent`
- **Type:** `number`
- **Recommended:** `30`
- **Risk:** `high`
- **What it controls:** Percentage of a whole source that must disappear before the source guard triggers.
- **Setup guide:** 30% is a good production default. Adjust higher if the source is naturally volatile.
- **Risk note:** A threshold too high may allow accidental mass cleanup.

#### Source minimum removed count

- **Config path:** `policies.source_cleanup_guard.min_removed_count`
- **Type:** `number`
- **Recommended:** `5`
- **Risk:** `medium`
- **What it controls:** Minimum removed rows required before source percentage protection applies.
- **Setup guide:** 5 prevents small source groups from constantly requiring confirmation.
- **Risk note:** Too high may ignore meaningful losses in small deployments.

#### Source guard action

- **Config path:** `policies.source_cleanup_guard.action`
- **Type:** `select`
- **Allowed values:** `preserve_rows`, `warn_only`, `cleanup_immediate`, `cleanup_next_run`, `require_confirm_immediate`, `require_confirm_next_run`, `block_cleanup`, `block_apply`
- **Recommended:** `require_confirm_next_run`
- **Risk:** `high`
- **What it controls:** Action taken when source-wide mass-removal threshold is exceeded.
- **Setup guide:** require_confirm_next_run is recommended. block_cleanup is stricter. cleanup_immediate is not recommended for production.
- **Risk note:** This can override source-specific immediate cleanup if respect_percentage_guards is enabled.

### Apply Guards

#### Block apply on collector failure

- **Config path:** `policies.apply_guard.block_apply_on_collector_failure`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `critical`
- **What it controls:** Prevents LibreQoS apply when a source collector failed and output may be incomplete.
- **Setup guide:** Keep enabled in production.
- **Risk note:** Applying after collector failure can remove valid clients from shaping.

#### Block apply on missing parent

- **Config path:** `policies.apply_guard.block_apply_on_missing_parent`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `critical`
- **What it controls:** Blocks apply when ShapedDevices rows reference Parent Nodes missing from network.json.
- **Setup guide:** Keep enabled. Fix topology or parent naming before applying.
- **Risk note:** Missing parents can break expected hierarchy/shaping placement.

#### Block apply on duplicate IP

- **Config path:** `policies.apply_guard.block_apply_on_duplicate_ip`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `critical`
- **What it controls:** Blocks apply when duplicate IPv4 values are detected in generated rows.
- **Setup guide:** Keep enabled unless duplicates are intentionally handled elsewhere.
- **Risk note:** Duplicate IPs can cause wrong shaping assignment.

#### Block apply on invalid speed

- **Config path:** `policies.apply_guard.block_apply_on_invalid_speed`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `critical`
- **What it controls:** Blocks apply when speed values cannot be parsed or are invalid.
- **Setup guide:** Keep enabled. Fix plan comments/profile names/default speeds.
- **Risk note:** Invalid speeds can create bad or failed LibreQoS config.

#### Require manual confirm on medium risk

- **Config path:** `policies.apply_guard.require_manual_confirm_on_medium_risk`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `high`
- **What it controls:** Requires operator review for medium-risk policy outcomes.
- **Setup guide:** Keep enabled for production. Disable only if you want more automation.
- **Risk note:** Disabling lets medium-risk changes auto-apply if other settings allow it.

#### Allow auto-apply on low risk

- **Config path:** `policies.apply_guard.allow_auto_apply_on_low_risk`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Allows low-risk changes to run LibreQoS automatically.
- **Setup guide:** Enable for efficient normal operations.
- **Risk note:** Disable if you want every apply to be manual.

### Collector Guards

#### Block cleanup if source failed

- **Config path:** `policies.collector_guard.block_cleanup_if_source_failed`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `critical`
- **What it controls:** Stops cleanup for a source when its collection failed.
- **Setup guide:** Keep enabled. Preserve rows until a successful scan confirms state.
- **Risk note:** Disabling can delete clients because of temporary API failure.

#### Block cleanup if enabled source returns zero

- **Config path:** `policies.collector_guard.block_cleanup_if_enabled_source_returns_zero`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `critical`
- **What it controls:** Stops cleanup when an enabled source returns zero rows.
- **Setup guide:** Keep enabled unless a source naturally returns zero often.
- **Risk note:** A zero result can be a collector/router/VLAN problem.

#### Block zero-after-success cleanup

- **Config path:** `policies.collector_guard.block_cleanup_if_source_returns_zero_after_previous_success`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `critical`
- **What it controls:** Blocks cleanup when a source that previously had rows suddenly returns zero.
- **Setup guide:** Keep enabled. This catches sudden source loss.
- **Risk note:** Disabling can wipe a source after an anomaly.

#### Zero-source drop threshold percent

- **Config path:** `policies.collector_guard.zero_source_drop_threshold_percent`
- **Type:** `number`
- **Recommended:** `80`
- **Risk:** `high`
- **What it controls:** Defines the drop percentage considered suspicious when a source goes near-zero.
- **Setup guide:** 80% catches extreme drops while allowing normal changes.
- **Risk note:** Too low causes noise; too high may miss failures.

#### Warn if router API slow ms

- **Config path:** `policies.collector_guard.warn_if_router_api_slow_ms`
- **Type:** `number`
- **Recommended:** `2000`
- **Risk:** `medium`
- **What it controls:** Warns when MikroTik API collection time is slower than expected.
- **Setup guide:** 2000 ms is a practical warning threshold.
- **Risk note:** Slow API can indicate router load, network issue, or timeout risk.

### Data Quality Guards

#### Warn on fallback speed

- **Config path:** `policies.data_quality.warn_on_fallback_speed`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Warns when clients use default/fallback speed instead of comment/profile/server-derived speed.
- **Setup guide:** Keep enabled so incorrect plan detection is visible.
- **Risk note:** Fallback speeds can silently assign wrong shaping.

#### Fallback speed warning threshold

- **Config path:** `policies.data_quality.fallback_speed_warning_threshold_percent`
- **Type:** `number`
- **Recommended:** `10`
- **Risk:** `medium`
- **What it controls:** Percentage of fallback-speed clients that triggers warning.
- **Setup guide:** 10% is good for production.
- **Risk note:** Too high can hide plan-detection issues.

#### Block if fallback speed threshold

- **Config path:** `policies.data_quality.block_if_fallback_speed_threshold_percent`
- **Type:** `number`
- **Recommended:** `50`
- **Risk:** `high`
- **What it controls:** Percentage of fallback-speed clients that blocks apply.
- **Setup guide:** 50% catches severe speed-source failures.
- **Risk note:** Blocking too low can interrupt normal migration; too high may allow bad speeds.

#### Warn on missing MAC

- **Config path:** `policies.data_quality.warn_on_missing_mac`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `low`
- **What it controls:** Warns when generated rows have no MAC address.
- **Setup guide:** Keep enabled for better audit/identity quality.
- **Risk note:** Some sources may not always provide MAC; this is usually warning-only.

#### Warn on missing IP

- **Config path:** `policies.data_quality.warn_on_missing_ip`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Warns when generated rows have no IPv4 address.
- **Setup guide:** Keep enabled because LibreQoS shaping generally needs IP mapping.
- **Risk note:** Missing IP rows may not shape correctly.

### Topology Guards

#### Block missing parent nodes

- **Config path:** `policies.topology_guard.block_missing_parent_nodes`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `critical`
- **What it controls:** Blocks apply when generated Parent Node values do not exist in network.json.
- **Setup guide:** Keep enabled when using hierarchy modes.
- **Risk note:** Disabling can produce unclear or broken topology placement.

#### Block duplicate node names

- **Config path:** `policies.topology_guard.block_duplicate_node_names`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `critical`
- **What it controls:** Blocks topology/apply when duplicate node names could collide.
- **Setup guide:** Keep enabled, especially with virtual/deep hierarchy.
- **Risk note:** Duplicate names can confuse hierarchy and promotion behavior.

#### Warn on virtual node promotion

- **Config path:** `policies.topology_guard.warn_on_virtual_node_promotion`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Warns when virtual nodes may promote children to nearest physical ancestor.
- **Setup guide:** Keep enabled so operators understand LibreQoS virtual-node behavior.
- **Risk note:** Virtual nodes are useful but can surprise operators if not explained.

#### Warn on deep hierarchy depth

- **Config path:** `policies.topology_guard.warn_on_deep_hierarchy_depth`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Warns when topology depth grows beyond recommended levels.
- **Setup guide:** Keep enabled for readability and performance awareness.
- **Risk note:** Very deep trees are harder to debug.

#### Max recommended hierarchy depth

- **Config path:** `policies.topology_guard.max_recommended_depth`
- **Type:** `number`
- **Recommended:** `4`
- **Risk:** `medium`
- **What it controls:** Recommended maximum hierarchy depth before warnings appear.
- **Setup guide:** 4 is a good practical default.
- **Risk note:** Higher depth may be valid but should be deliberate.

### Backup Guards

#### Require backup before apply

- **Config path:** `policies.backup_guard.require_backup_before_apply`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `high`
- **What it controls:** Requires or expects a backup before LibreQoS apply.
- **Setup guide:** Keep enabled for production.
- **Risk note:** Applying without backups makes rollback harder.

#### Warn if backups disabled with auto-apply

- **Config path:** `policies.backup_guard.warn_if_backup_disabled_while_auto_apply_enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `high`
- **What it controls:** Warns when auto-apply is enabled but backup_before_apply is disabled.
- **Setup guide:** Keep enabled.
- **Risk note:** This exact warning is a strong production-safety signal.

#### Minimum backup retention

- **Config path:** `policies.backup_guard.minimum_backup_retention`
- **Type:** `number`
- **Recommended:** `30`
- **Risk:** `medium`
- **What it controls:** Minimum number of backups considered healthy.
- **Setup guide:** 30 gives practical rollback history.
- **Risk note:** Too low reduces rollback options.

### Anomaly Detection

#### Anomaly detection

- **Config path:** `policies.anomaly_detection.enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Enables rule-based anomaly detection from previous successful runs.
- **Setup guide:** Keep enabled for smart warnings.
- **Risk note:** Disabling removes early warning for unusual drops/slowness.

#### Compare with last successful run

- **Config path:** `policies.anomaly_detection.compare_with_last_successful_run`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Uses last successful run as baseline for anomaly checks.
- **Setup guide:** Keep enabled.
- **Risk note:** Without baseline comparison, sudden changes are harder to classify.

#### Warn if client count drops percent

- **Config path:** `policies.anomaly_detection.warn_if_client_count_drops_percent`
- **Type:** `number`
- **Recommended:** `30`
- **Risk:** `high`
- **What it controls:** Warns when client count drops by this percentage compared with baseline.
- **Setup guide:** 30% is a practical default.
- **Risk note:** Too low can be noisy; too high may miss incidents.

#### Warn if sync duration multiplier

- **Config path:** `policies.anomaly_detection.warn_if_sync_duration_increases_multiplier`
- **Type:** `number`
- **Recommended:** `5`
- **Risk:** `medium`
- **What it controls:** Warns when sync duration is many times slower than usual.
- **Setup guide:** 5x is a practical starting point.
- **Risk note:** Slow sync may indicate API/router/system issues.

#### Warn if apply duration multiplier

- **Config path:** `policies.anomaly_detection.warn_if_apply_duration_increases_multiplier`
- **Type:** `number`
- **Recommended:** `5`
- **Risk:** `medium`
- **What it controls:** Warns when LibreQoS apply takes much longer than baseline.
- **Setup guide:** 5x is a practical starting point.
- **Risk note:** Slow apply can indicate host/load/config growth problems.

### Recommendations

#### Recommendations

- **Config path:** `policies.recommendations.enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `low`
- **What it controls:** Enables operator recommendation cards.
- **Setup guide:** Keep enabled so the UI suggests the safest next action.
- **Risk note:** Disabling removes helpful guidance but not enforcement.

#### Show Why/Fix messages

- **Config path:** `policies.recommendations.show_why_fix_messages`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `low`
- **What it controls:** Shows What/Why/Fix explanations for warnings and policy decisions.
- **Setup guide:** Keep enabled for operator clarity.
- **Risk note:** Without explanations, policies can feel like hidden behavior.

#### Show operator next action

- **Config path:** `policies.recommendations.show_operator_next_action`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `low`
- **What it controls:** Shows the recommended next operator action.
- **Setup guide:** Keep enabled.
- **Risk note:** Operators may need to inspect raw logs without this guidance.

### PPPoE Stale Lifecycle

#### PPPoE identity key

- **Config path:** `policies.stale_lifecycle.sources.pppoe.identity`
- **Type:** `select`
- **Allowed values:** `username`, `server_mac`, `username_or_mac`, `manual`
- **Recommended:** `username`
- **Risk:** `medium`
- **What it controls:** Identity used to decide whether a missing client is the same client if it returns later.
- **Setup guide:** Use username for PPPoE, server_mac for DHCP, username_or_mac for Hotspot, and manual for static rows.
- **Risk note:** Grace should only be enabled when identity is stable.

#### PPPoE optional grace

- **Config path:** `policies.stale_lifecycle.sources.pppoe.grace_enabled`
- **Type:** `bool`
- **Recommended:** `False`
- **Risk:** `high`
- **What it controls:** Enables optional grace behavior so a missing client is held for configured runs before cleanup.
- **Setup guide:** Keep disabled by default for DHCP/Hotspot random-MAC environments. Consider enabling only for stable PPPoE usernames.
- **Risk note:** Grace can preserve ghost rows if devices change MAC/IP.

#### PPPoE grace runs

- **Config path:** `policies.stale_lifecycle.sources.pppoe.grace_runs`
- **Type:** `number`
- **Recommended:** `1`
- **Risk:** `medium`
- **What it controls:** Number of consecutive missing runs required before cleanup when grace is enabled.
- **Setup guide:** Use 1 for PPPoE if you want short reconnect tolerance; use 0 for DHCP/Hotspot unless identities are stable.
- **Risk note:** Higher values delay cleanup and may preserve stale rows.

#### PPPoE return cancels cleanup

- **Config path:** `policies.stale_lifecycle.sources.pppoe.return_cancels_cleanup`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `low`
- **What it controls:** If the same identity returns before cleanup is applied, pending cleanup is cancelled.
- **Setup guide:** Enable for PPPoE/stable identities. Disable for unstable DHCP identities.
- **Risk note:** If identity is unstable, returns may not match the old row anyway.

### DHCP Stale Lifecycle

#### DHCP identity key

- **Config path:** `policies.stale_lifecycle.sources.dhcp.identity`
- **Type:** `select`
- **Allowed values:** `username`, `server_mac`, `username_or_mac`, `manual`
- **Recommended:** `server_mac`
- **Risk:** `medium`
- **What it controls:** Identity used to decide whether a missing client is the same client if it returns later.
- **Setup guide:** Use username for PPPoE, server_mac for DHCP, username_or_mac for Hotspot, and manual for static rows.
- **Risk note:** Grace should only be enabled when identity is stable.

#### DHCP optional grace

- **Config path:** `policies.stale_lifecycle.sources.dhcp.grace_enabled`
- **Type:** `bool`
- **Recommended:** `False`
- **Risk:** `high`
- **What it controls:** Enables optional grace behavior so a missing client is held for configured runs before cleanup.
- **Setup guide:** Keep disabled by default for DHCP/Hotspot random-MAC environments. Consider enabling only for stable PPPoE usernames.
- **Risk note:** Grace can preserve ghost rows if devices change MAC/IP.

#### DHCP grace runs

- **Config path:** `policies.stale_lifecycle.sources.dhcp.grace_runs`
- **Type:** `number`
- **Recommended:** `0`
- **Risk:** `medium`
- **What it controls:** Number of consecutive missing runs required before cleanup when grace is enabled.
- **Setup guide:** Use 1 for PPPoE if you want short reconnect tolerance; use 0 for DHCP/Hotspot unless identities are stable.
- **Risk note:** Higher values delay cleanup and may preserve stale rows.

#### DHCP return cancels cleanup

- **Config path:** `policies.stale_lifecycle.sources.dhcp.return_cancels_cleanup`
- **Type:** `bool`
- **Recommended:** `False`
- **Risk:** `low`
- **What it controls:** If the same identity returns before cleanup is applied, pending cleanup is cancelled.
- **Setup guide:** Enable for PPPoE/stable identities. Disable for unstable DHCP identities.
- **Risk note:** If identity is unstable, returns may not match the old row anyway.

### Hotspot Stale Lifecycle

#### Hotspot identity key

- **Config path:** `policies.stale_lifecycle.sources.hotspot.identity`
- **Type:** `select`
- **Allowed values:** `username`, `server_mac`, `username_or_mac`, `manual`
- **Recommended:** `username_or_mac`
- **Risk:** `medium`
- **What it controls:** Identity used to decide whether a missing client is the same client if it returns later.
- **Setup guide:** Use username for PPPoE, server_mac for DHCP, username_or_mac for Hotspot, and manual for static rows.
- **Risk note:** Grace should only be enabled when identity is stable.

#### Hotspot optional grace

- **Config path:** `policies.stale_lifecycle.sources.hotspot.grace_enabled`
- **Type:** `bool`
- **Recommended:** `False`
- **Risk:** `high`
- **What it controls:** Enables optional grace behavior so a missing client is held for configured runs before cleanup.
- **Setup guide:** Keep disabled by default for DHCP/Hotspot random-MAC environments. Consider enabling only for stable PPPoE usernames.
- **Risk note:** Grace can preserve ghost rows if devices change MAC/IP.

#### Hotspot grace runs

- **Config path:** `policies.stale_lifecycle.sources.hotspot.grace_runs`
- **Type:** `number`
- **Recommended:** `0`
- **Risk:** `medium`
- **What it controls:** Number of consecutive missing runs required before cleanup when grace is enabled.
- **Setup guide:** Use 1 for PPPoE if you want short reconnect tolerance; use 0 for DHCP/Hotspot unless identities are stable.
- **Risk note:** Higher values delay cleanup and may preserve stale rows.

#### Hotspot return cancels cleanup

- **Config path:** `policies.stale_lifecycle.sources.hotspot.return_cancels_cleanup`
- **Type:** `bool`
- **Recommended:** `False`
- **Risk:** `low`
- **What it controls:** If the same identity returns before cleanup is applied, pending cleanup is cancelled.
- **Setup guide:** Enable for PPPoE/stable identities. Disable for unstable DHCP identities.
- **Risk note:** If identity is unstable, returns may not match the old row anyway.

### Static/manual rows Stale Lifecycle

#### Static/manual rows identity key

- **Config path:** `policies.stale_lifecycle.sources.static.identity`
- **Type:** `select`
- **Allowed values:** `username`, `server_mac`, `username_or_mac`, `manual`
- **Recommended:** `manual`
- **Risk:** `medium`
- **What it controls:** Identity used to decide whether a missing client is the same client if it returns later.
- **Setup guide:** Use username for PPPoE, server_mac for DHCP, username_or_mac for Hotspot, and manual for static rows.
- **Risk note:** Grace should only be enabled when identity is stable.

#### Static/manual rows optional grace

- **Config path:** `policies.stale_lifecycle.sources.static.grace_enabled`
- **Type:** `bool`
- **Recommended:** `False`
- **Risk:** `high`
- **What it controls:** Enables optional grace behavior so a missing client is held for configured runs before cleanup.
- **Setup guide:** Keep disabled by default for DHCP/Hotspot random-MAC environments. Consider enabling only for stable PPPoE usernames.
- **Risk note:** Grace can preserve ghost rows if devices change MAC/IP.

#### Static/manual rows grace runs

- **Config path:** `policies.stale_lifecycle.sources.static.grace_runs`
- **Type:** `number`
- **Recommended:** `0`
- **Risk:** `medium`
- **What it controls:** Number of consecutive missing runs required before cleanup when grace is enabled.
- **Setup guide:** Use 1 for PPPoE if you want short reconnect tolerance; use 0 for DHCP/Hotspot unless identities are stable.
- **Risk note:** Higher values delay cleanup and may preserve stale rows.

#### Static/manual rows return cancels cleanup

- **Config path:** `policies.stale_lifecycle.sources.static.return_cancels_cleanup`
- **Type:** `bool`
- **Recommended:** `False`
- **Risk:** `low`
- **What it controls:** If the same identity returns before cleanup is applied, pending cleanup is cancelled.
- **Setup guide:** Enable for PPPoE/stable identities. Disable for unstable DHCP identities.
- **Risk note:** If identity is unstable, returns may not match the old row anyway.

### Stale Lifecycle Core

#### Stale lifecycle policy

- **Config path:** `policies.stale_lifecycle.enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `medium`
- **What it controls:** Enables stale lifecycle features as a policy group.
- **Setup guide:** Keep enabled so source-aware lifecycle settings are available; per-source grace can remain disabled.
- **Risk note:** Disabling removes lifecycle visibility and grace behavior.

### Policy-Aware Auto Apply

#### Risk-aware auto apply

- **Config path:** `policies.auto_apply_policy.enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `high`
- **What it controls:** Enables risk-aware auto-apply decisions using policy risk level.
- **Setup guide:** Keep enabled so low risk can apply while higher risk is held by policy.
- **Risk note:** If disabled, behavior may fall back to simpler auto_apply rules.

#### Auto apply low risk

- **Config path:** `policies.auto_apply_policy.allow_low_risk`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `low`
- **What it controls:** Allows automatic LibreQoS apply for low-risk changes.
- **Setup guide:** Enable for normal efficient operation.
- **Risk note:** Disable if all changes must be manually applied.

#### Auto apply medium risk

- **Config path:** `policies.auto_apply_policy.allow_medium_risk`
- **Type:** `bool`
- **Recommended:** `False`
- **Risk:** `medium`
- **What it controls:** Allows automatic LibreQoS apply for medium-risk changes.
- **Setup guide:** Keep disabled for production unless operator accepts more automation.
- **Risk note:** Medium risk may include meaningful cleanup or policy warnings.

#### Auto apply high risk

- **Config path:** `policies.auto_apply_policy.allow_high_risk`
- **Type:** `bool`
- **Recommended:** `False`
- **Risk:** `high`
- **What it controls:** Allows automatic LibreQoS apply for high-risk changes.
- **Setup guide:** Keep disabled.
- **Risk note:** High-risk changes should be manually reviewed.

#### Auto apply critical risk

- **Config path:** `policies.auto_apply_policy.allow_critical_risk`
- **Type:** `bool`
- **Recommended:** `False`
- **Risk:** `critical`
- **What it controls:** Allows automatic LibreQoS apply for critical-risk changes.
- **Setup guide:** Keep disabled.
- **Risk note:** Critical risk should not auto-apply in production.

#### When auto apply is held

- **Config path:** `policies.auto_apply_policy.when_blocked`
- **Type:** `select`
- **Allowed values:** `keep_pending_manual_apply`, `block_write`, `dry_run_only`
- **Recommended:** `keep_pending_manual_apply`
- **Risk:** `high`
- **What it controls:** Action when file changes exist but policy risk does not allow automatic LibreQoS apply.
- **Setup guide:** keep_pending_manual_apply is safest because files can be staged while apply waits for review.
- **Risk note:** block_write is stricter; dry_run_only is safest for testing but may prevent live updates.

### Policy Decision Trace

#### Decision trace

- **Config path:** `policies.decision_trace.enabled`
- **Type:** `bool`
- **Recommended:** `True`
- **Risk:** `low`
- **What it controls:** Stores explainable trace entries showing which policy rules influenced cleanup/write/apply decisions.
- **Setup guide:** Keep enabled for troubleshooting and support.
- **Risk note:** Turning off reduces audit clarity.

#### Max trace items

- **Config path:** `policies.decision_trace.max_items`
- **Type:** `number`
- **Recommended:** `200`
- **Risk:** `low`
- **What it controls:** Limits how many trace items are kept per policy decision.
- **Setup guide:** 200 is enough for most deployments; increase for large networks if traces are truncated.
- **Risk note:** Very high values can make state/log output larger.


---

# Network Layout Drag-and-Drop

LQoSync v2.54.3 wires the Network Layout drag-and-drop behavior. Previous versions showed a topology builder with promote/move controls, but node dragging itself was mostly visual/aesthetic and not fully wired.

## What can be dragged

- Visual Topology node cards
- Topology Tree node items

## Drop targets

- Drop on another node to move the dragged node under that target parent.
- Drop on the root drop zone to move/promote the dragged node back to root level.

## Safety validation

The UI blocks unsafe drag moves before changing the preview:

- cannot move a node under itself
- cannot move a node under its own descendant
- cannot move a node to the same parent as a no-op
- cannot move a node where the target parent already has a child with the same name

## Save behavior

Drag-and-drop changes are preview-only until the operator clicks **Save topology**. Save still uses the existing `/api/network_layout/save` endpoint and backend validation before writing `network.json`.

Recommended workflow:

1. Drag node to desired parent.
2. Review the updated visual topology and JSON preview.
3. Click **Save topology**.
4. Run Dry Run to verify generated parent nodes and affected clients.
5. Allow scheduler/auto-apply only after the topology is validated.

## Mobile behavior

HTML5 drag-and-drop is primarily a desktop browser feature. On mobile or touch devices, use the Node Inspector **Move** dropdown instead.


---

# v2.54.5 Privacy Icon Polish

Privacy Mode now uses an incognito-style icon in the top navigation. Privacy OFF shows the icon with a slash overlay. Privacy ON highlights the icon and keeps existing browser-only redaction behavior.


---

# v2.55 Package Quality + Environment Doctor

LQoSync v2.55 focuses on release reliability, package integrity, and upgrade/fresh-install safety.

## Why this exists

A package can accidentally include a navigation link, template, or engine module without the matching Flask route. v2.55 adds checks that detect those gaps before publishing, after updating from GitHub, and from Setup & Repair.

## Built-in checks

The release integrity checker verifies:

- Flask routes discovered from `app.py`
- static internal links in templates resolve to registered routes
- templates referenced by `render_template()` exist
- high-value modules are fully wired, including Reports, Lifecycle, Policy Center, Setup & Repair, and Setup Wizard
- `config.json.example` parses as JSON
- config defaults can be migrated to the latest schema
- required policy defaults are present after migration
- canonical PPPoE stale lifecycle defaults are present

## Commands

Run full environment doctor:

```bash
cd /opt/lqosync
sudo CONFIG_PATH=/opt/libreqos/src/config.json bash scripts/lqosync-doctor.sh
```

Run package integrity check only:

```bash
cd /opt/lqosync
python3 scripts/release_check.py
```

JSON output for automation:

```bash
python3 scripts/release_check.py --json
```

## Smart Defaults Repair

Setup & Repair now includes a **Repair Missing Defaults** button. It:

- backs up the current `config.json`
- deep-merges missing safe defaults
- preserves operator values
- normalizes policy defaults and aliases
- validates the result
- writes an audit event

Use it after upgrades if Dashboard shows missing policy/default warnings.

## WebUI integration

Setup & Repair now shows package integrity summary and links to the JSON integrity endpoint.

API endpoint:

```text
/api/release/integrity
```

This endpoint is read-only.

## Fresh install expectation

A fresh install should generate a complete `config.json` with no missing policy setting warnings. If warnings appear, run Smart Defaults Repair and report the issue as a package default/migration bug.


---

# v2.56 Policy UX + Conflict Intelligence

LQoSync v2.56 improves the Smart Policy Center with read-only conflict detection, stronger preset comparison, and source-aware client identity guidance.

## Policy Conflict Resolver

The Policy Conflict Resolver reviews the current `config.json -> policies` block and explains risky policy combinations before they affect cleanup, Dry Run, or LibreQoS apply behavior.

Examples detected:

- `cleanup_immediate` normal cleanup combined with permissive zero-result behavior
- collector-failed action that can delete rows
- source-disabled cleanup set to immediate
- high/critical risk auto-apply enabled
- apply guards disabled
- grace enabled for mixed/unstable identity sources

Each conflict includes:

- severity
- what is configured
- why it matters
- recommended fix
- affected config paths

The resolver is read-only. It does not write config or change policy values.

## Better Policy Preset Comparison

Policy Center now shows a clearer current-vs-preset table. The table includes:

- setting label
- section/category
- current value
- selected preset value
- risk level
- setup guidance

This helps operators understand exactly how their custom policy differs from Conservative, Balanced, or Aggressive presets.

## Client Identity Handling

Lifecycle and cleanup decisions depend on how stable a client identity is.

Recommended identity model:

- PPPoE: username, usually stable
- DHCP: DHCP server + MAC, mixed stability because private/random MAC can create new clients
- Hotspot: username/voucher or MAC, stable only when username/voucher-based
- Static/manual: manual identity, stable

Grace/stale lifecycle behavior should remain optional and source-aware. It is safest on stable identities such as PPPoE usernames, and should normally stay disabled for DHCP environments where devices may use randomized MAC addresses.


---

# Source Health & Performance Trends

> v2.57.1 update: Source Health and Performance Trends are now consolidated into the main Dashboard. The standalone `/health` page redirects to the Dashboard health section, while `/api/health/trends` remains available for JSON diagnostics and integrations.

# v2.57 Source Health + Performance Trends

LQoSync v2.57 adds a read-only Health Trends center for operational monitoring.

## What it adds

- Source Health cards for PPPoE, DHCP, and Hotspot
- Router API and sync timing trend summaries
- LibreQoS apply health trend summary
- Internal notification candidates for conditions that may later be sent to Telegram
- `/health` WebUI page
- `/api/health/trends` JSON endpoint

## Source Health

Each source card summarizes:

- active rows from the latest run
- stale and queued lifecycle counts when available
- configured cleanup policy
- zero-result policy
- collector-failed policy
- source warnings
- raw collector metrics

## Performance Trends

Performance trends use recent audit timing samples. The goal is not deep analytics; the goal is early warning when RouterOS API latency, full sync time, or LibreQoS apply time becomes much slower than normal.

## LibreQoS Apply Health

The apply health card shows recent successful and failed apply runs, average duration, repeated failures, and pending apply warnings. This helps operators see whether generated files are being applied reliably.

## Notification foundation

v2.57 creates internal notification candidates. These are shown in the WebUI only. Telegram delivery is intentionally planned for v2.58 so secrets, test-message workflow, and notification rules can be implemented safely.

## Safety

The Health Trends center is read-only. It does not modify config.json, generated files, policy state, scheduler behavior, or LibreQoS apply behavior.


---

# v2.58 Telegram Notifications

LQoSync v2.58 adds optional Telegram delivery for the internal notification candidates generated by Dashboard Source Health, performance trends, LibreQoS apply health, and policy/confirmation events.

Telegram delivery is disabled by default. Internal WebUI notifications continue to work even when Telegram is off.

## What Telegram can notify

Telegram can deliver notification-worthy conditions such as:

- LibreQoS apply failures or repeated apply warnings
- source health warnings for PPPoE, DHCP, or Hotspot
- performance slowdowns such as RouterOS API latency or apply duration spikes
- policy blocks or confirmation-required events when exposed as notification candidates
- update-available events when exposed as notification candidates

## Configuration location

Open:

```text
Notifications
```

Settings are saved under:

```text
config.json → notifications.telegram
```

Important fields:

```json
{
  "notifications": {
    "telegram": {
      "enabled": false,
      "bot_token": "",
      "chat_id": "",
      "base_url": "",
      "notify_levels": ["critical", "warning"],
      "minimum_interval_seconds": 60,
      "dedupe_window_minutes": 60,
      "max_items_per_digest": 10,
      "send_digest": true,
      "send_individual": false
    }
  }
}
```

## Recommended setup

1. Create a Telegram bot using BotFather.
2. Copy the bot token into the Notifications page.
3. Add the bot to the target private chat or group.
4. Set the chat ID.
5. Keep `notify_levels` as `critical` and `warning` for production.
6. Use digest mode to reduce message noise.
7. Click **Test Telegram**.
8. Use **Send current alerts** to send the Dashboard health candidates.

## Dedupe and rate limiting

Telegram delivery includes two safety controls:

```text
minimum_interval_seconds
```

Prevents repeat deliveries too quickly.

```text
dedupe_window_minutes
```

Suppresses repeated identical alerts for a configured time window.

## Security notes

Telegram bot tokens are secrets. They are masked in UI summaries, but they are stored in `config.json`. Protect file permissions and avoid sharing raw config screenshots.

## Design note

Telegram is delivery only. Notification generation remains based on existing LQoSync health, policy, apply, and trend logic. If Telegram is disabled or misconfigured, Dashboard/internal notifications still remain available.


---

# v2.59 Documentation Search + UI/Mobile Polish

LQoSync v2.59 adds a local Documentation Search Center and small global UI consistency helpers.

## Documentation Search Center

The `/docs/search` page indexes bundled local Markdown documentation, including `docs/content/*.md`, the Smart Policy Center guides, setup/repair guides, README, full documentation, installation guides, and release documentation.

The search is local and read-only. Queries are not sent to external services.

Operators can use it to quickly find topics such as:

- policy cleanup
- backup_before_apply
- LibreQoS working_dir
- GitHub update
- fresh install
- Telegram notifications
- MikroTik API setup
- DHCP identity
- Smart Defaults Repair

## Routes

```text
/docs
/docs/search
/docs/view/<doc_id>
/api/docs/search
/api/docs/index
```

## UI consistency helpers

v2.59 adds reusable layout helpers for future templates:

- `responsive-grid`
- `content-stack`
- `empty-state`
- `section-card`
- `action-strip`
- `mobile-sticky-actions`
- `kbd-hint`

These helpers support cleaner desktop layout and better mobile stacking, especially for action buttons, cards, and empty states.

## Product direction

About / Documentation remains the long-form manual source of truth. Setup & Repair remains diagnostic/action focused. Documentation Search connects both by helping operators find the correct guide quickly.


---

# Better Fresh Install Experience

LQoSync v2.60 improves the first-run onboarding path so a new installation is guided through setup before the production scheduler is enabled.

## Goals

- Fresh installs should open the First Run Setup Wizard instead of silently landing on the normal Dashboard.
- Existing/upgraded production installs should not be trapped in the wizard if they already have a scheduler or previous run history.
- Scheduler enable should be protected by a production-readiness gate.
- Operators should clearly see what is blocking go-live.

## First-run gate

The wizard checks:

- LibreQoS paths and files
- MikroTik router credentials
- enabled PPPoE/DHCP/Hotspot sources
- selected Network Layout mode
- selected Smart Policy preset
- completed Dry Run
- Setup & Repair failed checks

If the gate is not ready, the scheduler enable button is locked and the Dashboard shows a First Run Setup banner.

## Scheduler protection

Scheduler enable is blocked when any required setup gate is not satisfied. The default requirements are:

```json
{
  "setup_wizard": {
    "scheduler_enable_requires_dry_run": true,
    "scheduler_enable_requires_no_failed_checks": true,
    "scheduler_enable_requires_router_and_source": true
  }
}
```

This prevents a fresh installation from accidentally auto-applying LibreQoS before the operator has tested MikroTik collection, generated files, and policy decisions with Dry Run.

## Existing installs

Existing installs are treated as already acknowledged when they have prior run history or scheduler is already enabled. Operators can still reset the wizard from the Setup Wizard page if they want to re-run onboarding.

## Operator workflow

Recommended fresh install sequence:

1. Confirm LibreQoS paths.
2. Configure MikroTik API access.
3. Choose PPPoE/DHCP/Hotspot sources.
4. Choose Network Layout mode.
5. Choose Smart Policy preset.
6. Run Dry Run.
7. Review Dashboard, Reports, Lifecycle, and Setup & Repair.
8. Enable scheduler deliberately.

## Notes

The First Run Setup Wizard is an onboarding and safety workflow. It does not replace Config Center, Policy Center, Setup & Repair, or the documentation system.


---

# Backup Pagination and Actions

The Logs & Backups page includes a paginated backup list to prevent overflow when many backups exist.

## Actions

- Restore: icon-only restore action. Current live files are backed up before restore, so restore is reversible.
- Delete: icon-only trash action. This permanently deletes the selected backup directory after admin confirmation.

## Safety

Backup delete is CSRF-protected, admin-only, and restricted to direct child directories under the configured backup directory. Every restore/delete action writes an audit event.


---

# Compact Information Architecture and Documentation Consolidation

LQoSync v2.61 reduces redundant operator surfaces while preserving all important data and compatibility routes.

## Purpose

The project had grown into many powerful pages that sometimes repeated similar information: health data in Dashboard and Health Trends, logs split between Services/Journals and Logs/Backups, reports repeating Dashboard cards, and long-form guidance duplicated between About, Setup & Repair, README, and docs files.

The v2.61 direction is:

- Dashboard is the single live operator status page.
- Config Center is the settings and policy home.
- Operations Center is the home for services, journals, LibreQoS apply history, app logs, audit events, and backups.
- Reports Center is for exports and report snapshots, not another Dashboard.
- Documentation Center is the searchable source of truth for guides.
- About is lightweight project/version/disclosure information.

## New compact sidebar model

```text
Main
├─ Dashboard
├─ Shaped Devices
├─ Network Layout
├─ Dry-run Preview
├─ Lifecycle

Settings
├─ Config Center
├─ Users

Operations
├─ Operations Center
├─ Reports
├─ Updates

Help
├─ Documentation
├─ Setup Wizard
├─ Setup / Repair
├─ About
```

## Operations Center

Operations Center consolidates:

- Service Status
- Restart Groups
- Journal Viewer
- LibreQoS Apply History
- Last Cycle Timeline
- App Logs
- Audit Events
- Backups

Compatibility routes remain:

```text
/services → /operations?tab=services or journals
/logs → /operations?tab=logs
/health → Dashboard health section
```

## Reports Center

Reports Center is intentionally compact. It provides export bundles and snapshot previews. Use Dashboard for live status and Operations Center for live logs.

## Documentation model

Documentation is consolidated so GitHub and WebUI use the same content model:

- `docs/content/*.md` is the reusable source content.
- `docs/docs_manifest.json` is the documentation index and ordering map.
- `FULL_DOCUMENTATION.md` is the consolidated long-form manual for GitHub/offline reading.
- `README.md` stays compact and links to the full docs.
- WebUI Documentation Center searches local docs content.
- Setup & Repair should diagnose and link to docs instead of repeating full manuals.

## Operator guidance

Use these pages by intent:

- Need live status? Open Dashboard.
- Need logs/services/backups? Open Operations Center.
- Need to change behavior? Open Config Center.
- Need to preview impact? Run Dry Run.
- Need audit/export? Open Reports.
- Need help? Open Documentation Center.


---

# Config + Policy + Notification Unification

v2.62 reduces settings redundancy by making Config Center the single operator-facing home for normal settings, Smart Policy Center settings, and Telegram notification delivery settings.

## What changed

- Policy Center settings are now a native Config Center tab.
- Notification delivery settings are now a native Config Center tab.
- `/policy` remains as a compatibility alias and redirects to `/config?tab=policies`.
- `/notifications` remains as a compatibility alias and redirects to `/config?tab=notifications`.
- Advanced Raw JSON still mirrors the same `config.json` payload.
- Dry Run remains the canonical place to preview runtime impact before enabling scheduler or auto-apply.

## Why

Policies and notifications are configuration. Keeping them as isolated pages made the project feel larger and created multiple places to look for operator intent. The new model is:

```text
Config Center = settings, policies, notification delivery, raw JSON
Dashboard = live health and active alerts
Operations Center = services, logs, journals, backups
Reports = export/report snapshots
Documentation Center = searchable manual
```

## Operator workflow

1. Open Config Center.
2. Edit normal settings, policies, or Telegram delivery settings from tabs.
3. Use Preview Impact to check unsaved config changes.
4. Save normalized config.json.
5. Run Dry Run before production scheduler/auto-apply changes.

## Compatibility

Old links are preserved:

```text
/policy        → /config?tab=policies
/notifications → /config?tab=notifications
```

Existing POST endpoints for policy presets, cleanup confirmations, Telegram test, and Telegram current-alert delivery remain available for compatibility.


---

# Documentation Consolidation and Source of Truth

LQoSync documentation is consolidated so operators and GitHub readers see one consistent manual instead of repeated explanations across many pages.

## Documentation model

```text
README.md
  Compact GitHub landing page: what LQoSync is, install/update commands, and links.

FULL_DOCUMENTATION.md
  Complete single-file manual compiled from the documented topics below.

docs/DOCUMENTATION_INDEX.md
  GitHub-friendly table of contents that points to the canonical topic files.

docs/content/*.md
  Topic-level documentation source used by WebUI Documentation Center and GitHub docs.

docs/docs_manifest.json
  Documentation index: title, file, anchor, and summary for search/rendering order.

WebUI Documentation Center
  Searchable/readable view of the same local documentation files.

About page
  Lightweight project/version/AI disclosure entry point with links to Documentation Center.

Setup & Repair
  Diagnostics and repair actions; it should link to documentation instead of duplicating long manual text.
```

## Operator rule

Use the Documentation Center or `FULL_DOCUMENTATION.md` as the manual. Use Setup & Repair when something is failing. Use Dashboard for live status. Use Operations Center for logs, services, journals, backups, and apply history.

## GitHub rule

Keep `README.md` short. Put detailed guides in `docs/content/*.md` and let `FULL_DOCUMENTATION.md` act as the single-file export.

## Maintenance rule

When adding a new feature:

1. Add or update one topic file under `docs/content/`.
2. Add the topic to `docs/docs_manifest.json`.
3. Regenerate or update `FULL_DOCUMENTATION.md`.
4. Keep README concise.
5. Link from WebUI pages to the documentation topic instead of duplicating long explanations.

## Why this matters

A compact documentation model prevents conflicting instructions, reduces UI clutter, improves search quality, and makes the project easier to maintain as LQoSync grows.



## v2.63.1 Operations Center hotfix

This hotfix resolves an Internal Server Error on `/operations` caused by a variable-name collision between the journal line-count selector and the app log line list. The Operations Center now passes `journal_lines_count` separately from `lines`, so app logs render safely while all tabs and compatibility redirects remain unchanged.


## v2.64 UI Consistency and Redundancy Polish

LQoSync v2.64 improves the compact operator experience without changing engine behavior. Dashboard remains the live status cockpit, Operations Center owns services/journals/logs/audit/backups, Reports is export-focused, Config Center owns settings/policies/notifications, and Documentation Center is the single manual surface. Operations Center Apply History and Audit Events now use consistent pagination and row-limit controls.


## v2.65 Production Hardening + Regression Suite

LQoSync v2.65 adds offline regression checks for route/template wiring, high-risk template context, preserved config migration, policy safety behavior, Operations Center compatibility, and documentation integrity. Before publishing or updating from GitHub, run:

```bash
cd /opt/lqosync
python3 scripts/release_check.py
python3 scripts/regression_check.py
python3 scripts/config_migration_check.py
```

The full environment doctor also runs these checks:

```bash
sudo CONFIG_PATH=/opt/libreqos/src/config.json bash scripts/lqosync-doctor.sh
```


## v2.66 Backup / Restore Center Polish

Operations Center backups now support read-only preview, metadata/hash integrity checks, live-file comparison, selected-backup zip download, and retention preview visibility. Restore still creates a fresh backup of current live files before rollback so restore remains reversible. This is a backup/restore UX and safety improvement only.


## v2.67 Access Control + Role Hardening

LQoSync v2.67 adds a clearer owner/admin/operator/viewer role model. Owner controls users, updates, and high-trust repair actions. Admin controls config, policies, scheduler, backups, operations, and live apply actions. Operator can monitor and run dry-run previews. Viewer remains read-only. Older installs with only an admin account are upgraded safely by promoting the first admin to owner if no owner exists. See `docs/content/access_control_role_hardening.md`.


## v2.68 Production Readiness Score

LQoSync v2.68 adds a read-only Dashboard Production Readiness score and `/api/production/readiness`. It summarizes config validity, Setup Wizard state, Dry Run readiness, router/source configuration, backup-before-apply safety, LibreQoS paths, policy conflicts, Dashboard source/apply health, and service health into one go-live confidence card. This feature is read-only and does not change scheduler, cleanup, generated files, Telegram, or LibreQoS apply behavior.


## v2.69 Router Overview + Multi-Router UX Polish

LQoSync v2.69 adds a read-only `/routers` Router Overview page. Operators can inspect configured MikroTik routers, enabled PPPoE/DHCP/Hotspot sources, generated row ownership hints, parent-node role, and last-run collector warnings in one compact place. The page links to Config Center, Dry Run, and Operations Center for the next action. It does not modify config, generated files, scheduler state, or LibreQoS.


## v2.69.1 Router Insight De-duplication + Policy/Path Audit

LQoSync v2.69.1 removes redundant Router UX by moving Router Insight into `Config Center → Routers`. The old `/routers` path remains as a compatibility alias and redirects to `/config?tab=routers`; `/api/routers/overview` remains available for read-only diagnostics. The package also adds `scripts/policy_path_audit.py` to verify required runtime paths, policy schema/default coverage, migrated config policy paths, missing-policy warnings, and schema errors.


## v2.70 Stable Release Candidate / Production Freeze

LQoSync v2.70.0-rc1 is a stable release candidate. The feature-freeze rule allows bug fixes, route cleanup, UI consistency fixes, documentation cleanup, installer/update safety, config migration safety, and test coverage. It avoids new sidebar modules, duplicate settings pages, and undocumented production behavior changes.

Before publishing or updating production, run:

```bash
cd /opt/lqosync
python3 scripts/release_check.py
python3 scripts/regression_check.py
python3 scripts/config_migration_check.py
python3 scripts/policy_path_audit.py
python3 scripts/stable_release_check.py
```

Compatibility aliases remain in place: `/health`, `/services`, `/logs`, `/policy`, `/notifications`, and `/routers` redirect to their canonical compact UI destinations.


## v2.70.1-rc1 Stable RC Stale Template Cleanup Hotfix

This hotfix adds `scripts/cleanup_stale_files.py` for older ZIP/manual installs that may keep files removed from the canonical package. The first known stale file is `templates/routers.html`, because Router Insight now lives in Config Center → Routers and `/routers` redirects there. Run `python3 scripts/cleanup_stale_files.py --apply` then rerun `python3 scripts/stable_release_check.py`.


## v2.70.2-rc1 Config Policy Hierarchy UI

LQoSync v2.70.2-rc1 reorganizes Config Center → Policies into a compact hierarchy tree. Policies remain inside Config Center to avoid redundant modules, but are now grouped by operator intent: Overview, General Core, PPPoE, DHCP, Hotspot, Static, Cleanup Lifecycle, Mass Removal, Apply Guards, Auto Apply, Backup Policy, Topology/Data, Speed Resolution, and Advanced JSON.

This release also separates required and optional behavior: `app.auto_apply` is required when `app.operation_mode=automatic`, while `app.backup_before_apply` is optional by default to support storage-saving deployments. Production Readiness blocks disabled auto-apply in automatic mode but treats disabled auto-backup as allowed operator choice.


## v2.70.3 Policy Preset Wiring Hotfix

Config Center → Policies now includes visible Conservative, Balanced, and Aggressive preset buttons wired to the saved config preset route. `policies.mode` is displayed as managed preset status instead of a misleading normal field, while manual policy edits still set mode to `custom` when saved.


## v2.70.4-rc1 UI Wiring Audit + Role Visibility Hotfix

LQoSync v2.70.4-rc1 adds `scripts/ui_wiring_audit.py` and fixes role-visibility gaps after owner/admin/operator/viewer hardening. Admin-capable actions now use `role_at_least(user.role, 'admin')`, operator dry-run actions use `role_at_least(user.role, 'operator')`, owner-only Update Center links are gated, Config Center policy preset wiring is audited, and stale files such as `app.py.pre_reports_route_fix` are removed from stable packages.


## v2.70.5 Settings UI State Wiring Hotfix

LQoSync v2.70.5-rc1 fixes the Config Center → Policies preset active-state mismatch. The active Conservative/Balanced/Aggressive button now follows `cfg.policies.mode`, so `Current: aggressive` highlights Aggressive, `Current: balanced` highlights Balanced, and `Current: conservative` highlights Conservative. The UI wiring audit now also checks Config Center nav/section pairing, policy tree/panel pairing, preset active-state binding, and normalized config save binding.


## v2.70.6 Checkbox State Wiring Hotfix

LQoSync v2.70.6 fixes Config Center checkbox visual-state wiring. Boolean policy fields now use normalized checked binding through `asBool(getPath(...))`, explicit `x-effect` checked synchronization, and visible checked-state CSS so true values display with a clear checked mark in light and dark mode. UI wiring audit now checks this behavior.


## v2.70.7 LibreQoS Apply Failure Visibility

LQoSync v2.70.7-rc1 makes failed LibreQoS apply runs actionable. Dashboard and Telegram apply warnings now link to an apply diagnostic page when a run ID is available. Operations Center → Apply History includes a Detail / Resolve button and failed runs show a short summary and resolution hint. The new `/libreqos/apply/<run_id>` page shows stderr/stdout tails, command metadata, failure classification, suggested resolve page, and suggested commands. This is a UI/diagnostics wiring improvement only.


## v2.70.8 Policy Preset Alignment + Save Semantics

LQoSync v2.70.8 aligns Conservative, Balanced, and Aggressive presets so they do not create high/critical conflicts immediately after apply. Aggressive mode still uses faster normal inactive cleanup, but PPPoE/DHCP/Hotspot zero-result cleanup remains `block_cleanup`. Config Center saves now reconcile policy mode server-side: exact presets keep their preset name, while edited policy values are saved as `custom`. The new `scripts/policy_preset_audit.py` validates preset alignment, user preference preservation, and custom-mode reconciliation.


## v2.70.9 Custom Policy Mode Persistence

Config Center → Policies now shows Custom as a visible policy state beside Conservative, Balanced, and Aggressive. Manual policy edits change the UI state to Custom immediately, and server-side save preserves explicit `policies.mode = custom`. Named presets still stay named when exact, and edited named presets reconcile to Custom.


## v2.70.10 Policy Overview Custom Wiring Hotfix

Changing Operation Mode, Auto Apply, Optional Auto Backup, or Backup Retention inside Config Center → Policies now marks `policies.mode` as `custom` and remains custom after save. Server-side save also detects these policy-adjacent `app.*` changes so the mode is protected even if browser JS misses the change event.


---

# LQoSync-in-Rust Branch Documentation Addendum

This package includes first-class documentation for the future `lqosync-in-rust` branch. The branch direction is hybrid, not a full rewrite.

```text
Python Flask WebUI remains the operator interface.
Rust becomes the deterministic backend safety core.
No database is introduced.
Autosave/no-save-button behavior remains.
LibreQoS remains external.
```

## Rust branch documents

- `docs/RUST_CORE_MIGRATION.md` — phased migration plan and module boundaries.
- `docs/RUST_CORE_PROTOCOL.md` — stable JSON protocol shared by CLI and future Unix socket daemon.
- `docs/COLLECTOR_OUTPUT_CONTRACT.md` — typed collector trust envelope for PPPoE/DHCP/Hotspot source safety.
- `docs/AUTOSAVE_AND_ATOMIC_STATE.md` — autosave, dangerous-change confirmation, atomic state/file writes, and rollback behavior.
- `docs/COMMIT_AND_PUSH_GUIDE.md` — branch workflow, commit messages, push commands, and PR template.

## Corrected migration priorities

```text
v0.1 Protocol + validator core
v0.2 Diff + collector output contract
v0.3 Atomic state/file engine, including collector_cache.json
v0.4 Optional Rust core daemon using the same JSON protocol
v0.5 Policy decision engine
v0.6 Circuit builder / possible Rust RouterOS collector
```

The most important safety correction is that collector output must be validated before cleanup. A source that returns an empty list without raising an exception must not be treated as safe for cleanup unless Rust classifies it as `zero_valid`.

The second safety correction is that `collector_cache.json` belongs with the atomic state engine. It may influence speed/source continuity and source-trust decisions in later cycles, so it must not be treated as an unimportant warning-only cache.

# LQoSync-in-Rust Optional Core Scaffold

Version `v2.71.0-rc1` adds the first optional Rust safety-core scaffold for the `lqosync-in-rust` branch.

Implemented files:

```text
rust/lqosync-core/Cargo.toml
rust/lqosync-core/src/protocol.rs
rust/lqosync-core/src/bandwidth.rs
rust/lqosync-core/src/shaped_devices.rs
rust/lqosync-core/src/network.rs
rust/lqosync-core/src/validators.rs
rust/lqosync-core/src/main.rs
engine/rust_core.py
scripts/build-rust-core.sh
scripts/install-rust-core.sh
```

Supported Rust operations:

```text
parse-bandwidth
validate-config
validate-shaped-devices
validate-network
validate-files
validate-collector-output
```

The Python runtime remains the primary path. If the Rust binary is not installed,
`engine.rust_core` returns a structured fallback response and existing Python
validation remains active.

Rust core config defaults:

```json
{
  "rust_core": {
    "enabled": true,
    "binary_path": "",
    "timeout_seconds": 10,
    "enforce_validation": false,
    "prefer_daemon": false,
    "unix_socket": "/run/lqosync-core.sock"
  }
}
```

Dry Run now includes `diff.rust_core_validation` for visibility. Rust errors only
block when the binary is available and `rust_core.enforce_validation` is enabled.

Build commands:

```bash
scripts/build-rust-core.sh
sudo scripts/install-rust-core.sh
```

## Rust Core v0.2 Trust and Diff Guard

The `lqosync-in-rust` branch now includes a second Rust-core integration step. The sync cycle builds a collector trust envelope after each PPPoE, DHCP, and Hotspot processor result. A source is only added to cleanup eligibility when the trust response reports `safe_for_cleanup=true`. This protects against silent empty or partial RouterOS API results.

The Rust core also provides `diff-shaped-devices`, `diff-network`, and `diff-files` protocol operations. Python's existing diff remains the primary UI-compatible diff, while the Rust diff appears in Dry Run as `rust_core_diff` for cross-checking and future migration.

