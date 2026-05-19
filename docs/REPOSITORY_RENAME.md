# Repository Rename Guide — `lqosync` to `LQoSync`

This guide explains how to rename the GitHub repository while keeping existing production installs safe.

## Goal

Rename the GitHub repository identity from:

```text
p33ckab00/LQoSync
```

to:

```text
p33ckab00/LQoSync
```

The application name should be **LQoSync** in operator-facing documentation.

## Compatibility rule

Do not rename runtime compatibility names unless a future migration explicitly handles them.

Keep these as-is for now:

```text
/opt/lqosync
lqosync.service
lqosync log names
existing Docker container names when already deployed
```

This avoids breaking systemd, journald, sudoers, backup scripts, and existing operator commands.

## Rename using GitHub CLI

Run on a machine where `gh` is authenticated as the repository owner:

```bash
gh repo edit p33ckab00/LQoSync --name LQoSync
```

## Rename using GitHub Web UI

1. Open the repository on GitHub.
2. Go to **Settings**.
3. Open **General**.
4. Find **Repository name**.
5. Change `lqosync` to `LQoSync`.
6. Confirm rename.

## Update the production remote after rename

On every server or development checkout:

```bash
cd /opt/lqosync
git remote set-url origin https://github.com/p33ckab00/LQoSync.git
git remote -v
git fetch origin main
git status
```

For your development folder:

```bash
cd /opt/lqosync
git remote set-url origin https://github.com/p33ckab00/LQoSync.git
git remote -v
git fetch origin main
git status
```

## Update install commands

After the repository rename, use:

```bash
cd /opt
curl -fsSL https://raw.githubusercontent.com/p33ckab00/LQoSync/main/install-from-github.sh -o /tmp/install-lqosync.sh
sudo EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh
```

If a server is still using the old repository URL temporarily, force the source with:

```bash
sudo LQOSYNC_REPO_URL=https://github.com/p33ckab00/LQoSync.git EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh
```

## What to change in documentation

Use **LQoSync** for product/repository-facing wording.

Keep `lqosync` only when it refers to an existing compatibility name:

- systemd service name
- journald unit name
- existing log file name
- existing Docker container/image name
- legacy migration examples

## Safe push flow after documentation changes

```bash
cd /opt/lqosync
git status
python3 -m py_compile app.py engine/policy_schema.py engine/regression.py
python3 scripts/release_check.py
python3 scripts/regression_check.py
python3 scripts/config_migration_check.py
python3 scripts/policy_path_audit.py
python3 scripts/stable_release_check.py
git add .
git commit -m "Align documentation with LQoSync repository name"
git push -u origin main
```

## Operator note

GitHub usually redirects old repository URLs after rename, but production documentation should not rely on redirects. Update the remote URL and installer examples to the new repository name.
