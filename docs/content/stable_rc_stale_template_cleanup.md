# Stable RC Stale Template Cleanup Hotfix

v2.70.1-rc1 adds a conservative stale-file cleanup helper for older ZIP/manual installs.

## Problem

Some installs may keep files that were removed from the canonical package, such as `templates/routers.html`. This can happen when a manual/ZIP update copies new files over an old install without deleting removed files.

Router Insight now belongs in Config Center → Routers. `/routers` remains as a compatibility redirect, so the old standalone `templates/routers.html` is stale.

## Fix

Run:

```bash
cd /opt/lqosync
python3 scripts/cleanup_stale_files.py --apply
python3 scripts/stable_release_check.py
```

`upgrade.sh` also runs this cleanup automatically after updating code.

## Safety

The cleanup list is intentionally conservative. It only removes known stale files that are no longer canonical and are safe to delete.
