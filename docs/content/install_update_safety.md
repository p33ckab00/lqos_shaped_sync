# Install and Update Safety

LQoSync treats LibreQoS input files as operator-owned production data.

## Atomic rule

Do not overwrite a production operator file unless the operator explicitly selected overwrite-with-backup.

## Fresh install with existing files

When the GitHub installer runs, it creates a timestamped safety backup before proceeding. If these files already exist, they are backed up first and preserved by default:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

Missing files are created from templates. Existing files are not overwritten unless the operator intentionally chooses overwrite-with-backup.

## Update existing install

For normal updates, LQoSync updates app code and safe missing defaults. Operator-owned files remain in place:

```text
config.json
ShapedDevices.csv
network.json
users.json
.env
state/
logs/
backups/
```

## Why this matters

`config.json` defines routers, paths, policies, and source behavior. `ShapedDevices.csv` and `network.json` may represent live production shaping state. Replacing them without a backup can change subscriber shaping behavior immediately.

## Operator verification

After update:

```bash
cd /opt/lqosync
python3 scripts/release_check.py
python3 scripts/regression_check.py
python3 scripts/config_migration_check.py
python3 scripts/policy_path_audit.py
python3 scripts/stable_release_check.py
sudo systemctl restart lqos_shaped_sync
```

Then open WebUI:

```text
Dashboard → Config Center → Dry Run → Operations Center
```
