# v2.55 Package Quality + Environment Doctor

LQoSync v2.55 focuses on release reliability, package integrity, and upgrade/fresh-install safety.

## Why this exists

A package can accidentally include a navigation link, template, or engine module without the matching Flask route. v2.55 adds checks that detect those gaps before publishing, after updating from GitHub, and from Setup & Repair.

## Built-in checks

The release integrity checker verifies:

- Flask routes discovered from `app.py`
- static internal links in templates resolve to registered routes
- templates referenced by `render_template()` exist
- high-value modules are fully wired, including Reports, Lifecycle, Policy Center, Setup & Repair, and Setup Wizard
- `config.json.example` parses as JSON
- config defaults can be migrated to the latest schema
- required policy defaults are present after migration
- canonical PPPoE stale lifecycle defaults are present

## Commands

Run full environment doctor:

```bash
cd /opt/lqosync
sudo CONFIG_PATH=/opt/libreqos/src/config.json bash scripts/lqosync-doctor.sh
```

Run package integrity check only:

```bash
cd /opt/lqosync
python3 scripts/release_check.py
```

JSON output for automation:

```bash
python3 scripts/release_check.py --json
```

## Smart Defaults Repair

Setup & Repair now includes a **Repair Missing Defaults** button. It:

- backs up the current `config.json`
- deep-merges missing safe defaults
- preserves operator values
- normalizes policy defaults and aliases
- validates the result
- writes an audit event

Use it after upgrades if Dashboard shows missing policy/default warnings.

## WebUI integration

Setup & Repair now shows package integrity summary and links to the JSON integrity endpoint.

API endpoint:

```text
/api/release/integrity
```

This endpoint is read-only.

## Fresh install expectation

A fresh install should generate a complete `config.json` with no missing policy setting warnings. If warnings appear, run Smart Defaults Repair and report the issue as a package default/migration bug.
