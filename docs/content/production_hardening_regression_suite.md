# v2.65 Production Hardening + Regression Test Suite

LQoSync v2.65 adds an offline regression suite to improve release discipline and production confidence. It does not change MikroTik collection, cleanup policy behavior, generated files, scheduler behavior, or LibreQoS apply behavior.

## Why this exists

As LQoSync grew into Dashboard, Config Center, Policy Center, Operations Center, Reports, Lifecycle, Setup Wizard, Setup & Repair, Documentation Search, Notifications, and backup workflows, the risk moved from missing features to accidental regressions.

The regression suite is designed to catch issues before pushing to GitHub or after updating a live install, such as:

- navigation links pointing at missing Flask routes
- Flask routes rendering missing templates
- template context mismatches such as a variable being used for two different data types
- preserved older `config.json` files missing new defaults after upgrade
- policy behavior drift
- Operations Center route/tab regressions
- documentation manifest or release note mismatches

## Commands

Run the release integrity checker:

```bash
cd /opt/LQoSync
python3 scripts/release_check.py
```

Run the full regression suite:

```bash
cd /opt/LQoSync
python3 scripts/regression_check.py
```

Run only config migration regression checks:

```bash
cd /opt/LQoSync
python3 scripts/config_migration_check.py
```

Run the full environment doctor wrapper:

```bash
cd /opt/LQoSync
sudo CONFIG_PATH=/opt/libreqos/src/config.json bash scripts/lqosync-doctor.sh
```

JSON output for automation:

```bash
python3 scripts/regression_check.py --json
python3 scripts/config_migration_check.py --json
```

## What regression_check.py validates

- important WebUI/API routes exist
- major page routes render the expected templates
- high-risk templates receive required context variables
- older config scenarios migrate to the current schema
- policy safety behavior remains predictable
- Operations Center compatibility routes and pagination variables exist
- documentation manifest, GitHub docs, release notes, and VERSION agree

## What config_migration_check.py validates

The migration check simulates preserved older configs and verifies that migration adds current defaults without wiping operator choices. It specifically checks for blocks that caused upgrade warnings in earlier builds:

- `policies.stale_lifecycle.sources.pppoe`
- `policies.auto_apply_policy`
- `setup_wizard`
- `notifications.telegram`
- `package_quality`

## Release rule

Before publishing a package or pushing to GitHub, run:

```bash
python3 scripts/release_check.py
python3 scripts/regression_check.py
python3 scripts/config_migration_check.py
```

If any command fails, fix the issue before publishing.
