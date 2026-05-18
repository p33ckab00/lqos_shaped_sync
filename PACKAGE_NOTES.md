# LQoSync Full Package Notes

This package is based on the provided LQoSync v2.70.10-rc1 codebase and applies only the requested scoped changes:

- Clarifies fresh-install backup-first behavior for existing config.json, ShapedDevices.csv, and network.json.
- Clarifies update-only behavior: app code and safe missing defaults update while operator-owned files are preserved.
- Cleans the About module so version/release update details are moved out of About.
- Enhances Update Center ownership for installed version, GitHub version, local/remote commit, latest fetched changes, and safe update commands.
- Updates operator-facing repository/product naming to LQoSync while preserving compatibility service/path names.
- Adds operator-focused documentation with Table of Contents, glossary, appendices, and LibreQoS-inspired design explanation.

Validation run:

- python3 -m py_compile app.py engine/policy_schema.py engine/setup_repair.py
- python3 scripts/release_check.py
- python3 scripts/regression_check.py
- python3 scripts/config_migration_check.py
- python3 scripts/policy_path_audit.py
- python3 scripts/stable_release_check.py

All checks passed.
