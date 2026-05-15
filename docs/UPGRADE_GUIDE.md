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


## v2.70.1-rc1 Stable RC Stale Template Cleanup Hotfix

This hotfix adds `scripts/cleanup_stale_files.py` for older ZIP/manual installs that may keep files removed from the canonical package. The first known stale file is `templates/routers.html`, because Router Insight now lives in Config Center → Routers and `/routers` redirects there. Run `python3 scripts/cleanup_stale_files.py --apply` then rerun `python3 scripts/stable_release_check.py`.


## v2.70.4-rc1 UI Wiring Audit + Role Visibility Hotfix

LQoSync v2.70.4-rc1 adds `scripts/ui_wiring_audit.py` and fixes role-visibility gaps after owner/admin/operator/viewer hardening. Admin-capable actions now use `role_at_least(user.role, 'admin')`, operator dry-run actions use `role_at_least(user.role, 'operator')`, owner-only Update Center links are gated, Config Center policy preset wiring is audited, and stale files such as `app.py.pre_reports_route_fix` are removed from stable packages.
