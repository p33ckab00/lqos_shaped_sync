# v2.70 Stable Release Candidate

LQoSync v2.70 is a feature-freeze and production-stabilization release.

## Feature freeze rule

Allowed during the stable candidate phase:

- bug fixes
- route cleanup
- UI consistency fixes
- documentation cleanup
- installer/update safety
- config migration safety
- regression/test coverage

Not allowed during the stable candidate phase:

- new sidebar modules
- duplicated configuration pages
- experimental engines
- production behavior changes without tests

## Required validation chain

Before publishing or updating a production install, run:

```bash
cd /opt/LQoSync
python3 scripts/release_check.py
python3 scripts/regression_check.py
python3 scripts/config_migration_check.py
python3 scripts/policy_path_audit.py
python3 scripts/stable_release_check.py
```

Or run the combined doctor:

```bash
cd /opt/LQoSync
sudo CONFIG_PATH=/opt/libreqos/src/config.json bash scripts/lqosync-doctor.sh
```

## Stable candidate goal

The goal is not to add more modules. The goal is to make the current system stable, predictable, upgrade-safe, and easier to validate.
