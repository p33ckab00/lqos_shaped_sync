# Upgrade Guide

## Safe GitHub update

```bash
cd /opt/lqosync
git fetch origin main
python3 scripts/release_check.py
python3 scripts/regression_check.py
python3 scripts/config_migration_check.py
python3 scripts/policy_path_audit.py
python3 scripts/stable_release_check.py
sudo ./upgrade.sh
sudo systemctl restart lqos_shaped_sync
sudo CONFIG_PATH=/opt/libreqos/src/config.json bash scripts/lqosync-doctor.sh
```

## If Git has diverged

Do not blindly pull. Create a backup first, then decide whether GitHub main is the app-code source of truth. Use the preserve-existing installer/adoption flow when converting a manual or ZIP install into a Git-managed install.

## Post-upgrade checks

- Open Dashboard.
- Open Config Center and confirm no missing policy/default warnings.
- Run Dry Run.
- Open Operations Center and check apply/log/audit tabs.
- Open System Validation and run the validation chain.
