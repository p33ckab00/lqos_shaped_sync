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
/opt/LQoSync/users.json
/opt/LQoSync/.env
/opt/LQoSync/state/
/opt/LQoSync/logs/
```

Those files are operator/runtime files and are not overwritten during normal Git updates.

## Fresh install from GitHub

Use this when the system does not yet have LQoSync installed or you want the install source to be Git-managed:

```bash
sudo apt update
sudo apt install -y git
cd /opt
sudo git clone https://github.com/p33ckab00/LQoSync.git lqosync
cd /opt/LQoSync
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
curl -fsSL https://raw.githubusercontent.com/p33ckab00/LQoSync/lqosync-in-rust/install-from-github.sh -o /tmp/install-lqosync.sh
sudo bash /tmp/install-lqosync.sh
```

Optional variables:

```bash
sudo LQOSYNC_REPO_URL=https://github.com/p33ckab00/LQoSync.git \
     LQOSYNC_BRANCH=lqosync-in-rust \
     LQOSYNC_INSTALL_DIR=/opt/LQoSync \
     LQOSYNC_INIT_POLICY=smart_confirm \
     bash /tmp/install-lqosync.sh
```

## If `/opt/LQoSync` was installed from ZIP/manual copy

The Git installer can convert it into a Git-managed install. It backs up and preserves:

```text
users.json
.env
state/
logs/
```

Then it clones/syncs the GitHub source and runs the normal production-safe installer.

## Smart Git update

Once `/opt/LQoSync` is Git-managed:

```bash
cd /opt/LQoSync
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
cd /opt/LQoSync
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

## Existing installation handling

If `/opt/LQoSync` or an existing `lqosync` service is detected, `install-from-github.sh` now supports smart adoption.

Interactive mode:

```bash
sudo bash /tmp/install-lqosync.sh
```

Non-interactive recommended production mode:

```bash
sudo EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh
```

Available actions:

```text
adopt        Convert/update existing install to Git-managed source, preserve live data.
code_only    Update source code only, preserve config/users/generated files, skip migration.
repair       Reapply service/sudoers/ACL/config migration, preserve app data.
replace_app  Replace app source from GitHub with backup, restore users/.env/state/logs.
remove_fresh Move old /opt/LQoSync aside, clone fresh source, preserve LibreQoS files by default.
abort        Stop without changes.
```

Detailed design notes are in `docs/EXISTING_INSTALL_ADOPTION.md`.

## Current Rust Branch Install / Update Flow

For the `lqosync-in-rust` production series, use the canonical source path `/opt/LQoSync` and validate the Rust daemon before treating the install as production-ready.

```bash
cd /opt/LQoSync
git fetch origin
git checkout lqosync-in-rust
git pull --ff-only origin lqosync-in-rust

bash scripts/repair-script-permissions.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

Do not install a newly built Rust binary if `scripts/build-rust-core.sh` fails. The build helper removes stale release binaries before testing, so a failed test cannot accidentally install an old binary.

