# Rust Core v7.5.1 Installation Documentation and Installer Alignment

LQoSync `2.145.1-rc1` / `lqosync-core 7.5.1` aligns installation documentation, GitHub install examples, installer defaults, and verification scripts with the current `lqosync-in-rust` production series.

## Canonical install model

- Repository branch: `lqosync-in-rust`
- Application source/runtime path: `/opt/LQoSync`
- LibreQoS source path: `/opt/libreqos/src`
- Rust daemon binary: `/usr/local/bin/lqosync-core`
- Rust daemon service: `lqosync-core.service`
- WebUI/UX/static assets: preserved as-is
- Python/Flask backend: legacy/fallback only after the full Rust production cutover path is verified

## Standard branch install

```bash
sudo apt update
sudo apt install -y git curl build-essential pkg-config libssl-dev unzip

# Install Rust if cargo is missing.
command -v cargo >/dev/null 2>&1 || curl https://sh.rustup.rs -sSf | sh -s -- -y
source "$HOME/.cargo/env"

sudo git clone --branch lqosync-in-rust --single-branch https://github.com/p33ckab00/LQoSync.git /opt/LQoSync
cd /opt/LQoSync

bash scripts/repair-script-permissions.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

## Standard branch update

```bash
cd /opt/LQoSync
sudo git fetch origin
sudo git checkout lqosync-in-rust
sudo git pull --ff-only origin lqosync-in-rust

bash scripts/repair-script-permissions.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

## Expected production-series verification

After v7.5.1 alignment, the currently active v7.5 line should retain the v7.5 audit sentinel expectations:

- Cargo tests pass.
- `lqosync-core` self-test returns `ok: true`.
- `build-full-rust-backend-production-drift-monitor` remains advertised.
- `build-full-rust-backend-production-audit-sentinel` is advertised after v7.5 is built and installed.
- WebUI/UX/static paths remain unchanged.
- Rollback package remains available.

## Installer alignment

The following defaults now point to the Rust branch and canonical path:

```text
LQOSYNC_BRANCH=lqosync-in-rust
LQOSYNC_INSTALL_DIR=/opt/LQoSync
```

Affected scripts:

- `install-from-github.sh`
- `upgrade.sh`
- `install.sh`
- `uninstall.sh`

A new checker is included:

```bash
bash scripts/verify-installation-docs-alignment.sh
```

It checks that primary install docs mention the Rust branch, canonical path, and Rust daemon install flow, and that install/update scripts default to the current branch/path.

## Safety notes

This is a documentation and installer-alignment release. It does not change live packet shaping behavior, write generated LibreQoS files, execute rollback, delete Python files, or mutate WebUI/UX assets.

## Codebase path alignment

The documentation alignment also updates path defaults and operator-facing examples across Python wrappers, configuration defaults, templates, scripts, and Rust fixture/default paths from the old `/opt/lqosync` spelling to `/opt/LQoSync`.

This keeps the install guide, installer scripts, runtime defaults, UI repair commands, config examples, Rust self-test fixtures, and rollback/journal path examples consistent with the branch install flow.
