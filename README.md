# LQoSync / `lqos_shaped_sync`

## AI-Assisted Development Disclosure and Acknowledgement

LQoSync was developed and refined through an AI-assisted development workflow with substantial assistance from **GPT-5.5 Thinking by OpenAI**, working interactively with the project owner/operator. AI assistance does not replace human review, security auditing, backup verification, configuration validation, or production testing. See [docs/AI_ASSISTED_DEVELOPMENT.md](docs/AI_ASSISTED_DEVELOPMENT.md).


LQoSync is a standalone, database-free WebUI and scheduler for syncing live MikroTik PPPoE, DHCP, and Hotspot subscriber/session data into LibreQoS `ShapedDevices.csv` and `network.json`.

```text
MikroTik RouterOS API → LQoSync → ShapedDevices.csv/network.json → LibreQoS.py --updateonly
```

## What LQoSync is

- A focused MikroTik-to-LibreQoS sync companion.
- A WebUI for dry-run preview, policy-aware cleanup, config/settings, reports, lifecycle visibility, operations logs, backups, and setup/repair.
- A safety layer for live LibreQoS input-file generation.

## What LQoSync is not

- Not a billing system.
- Not an ISP CRM.
- Not a replacement for LibreQoS.
- Not a replacement for human validation before production changes.

## Key features

- MikroTik PPPoE, DHCP, and Hotspot collection through read-only RouterOS API.
- LibreQoS `ShapedDevices.csv` and `network.json` generation.
- Policy-aware cleanup and source lifecycle behavior.
- Dry Run / impact preview before apply.
- Config Center with policies and Telegram notification settings.
- Dashboard with live status, source health, and apply health.
- Operations Center for services, journals, logs, audit events, backups, and LibreQoS apply history.
- Documentation Center with local search.
- Setup Wizard and Setup & Repair workflows.

## Standard paths

```text
/opt/libreqos/                     # LibreQoS application folder
/opt/libreqos/src/config.json       # LQoSync config consumed by the engine
/opt/libreqos/src/ShapedDevices.csv # generated LibreQoS shaped-device output
/opt/libreqos/src/network.json      # generated LibreQoS topology output
/opt/lqosync/                       # LQoSync app/runtime folder
/opt/lqosync/state/                 # runtime, policy, lifecycle, notification state
/opt/lqosync/logs/                  # audit and apply logs
/opt/lqosync/backups/               # pre-apply and restore backups
```

## Quick install from GitHub

```bash
cd /opt
curl -fsSL https://raw.githubusercontent.com/p33ckab00/lqos_shaped_sync/main/install-from-github.sh -o /tmp/install-lqosync.sh
sudo EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh
```

## Safe update from GitHub

```bash
cd /opt/lqosync
git fetch origin main
sudo ./upgrade.sh
sudo systemctl restart lqos_shaped_sync
```

## First-run flow

1. Open the WebUI.
2. Follow **Setup Wizard**.
3. Configure LibreQoS paths and MikroTik routers.
4. Choose PPPoE/DHCP/Hotspot sources.
5. Choose Network Layout mode.
6. Choose Smart Policy preset.
7. Run Dry Run.
8. Review Dashboard/Operations/Reports.
9. Enable scheduler only when production-ready.

## Documentation

The documentation is consolidated into one coherent system:

- [FULL_DOCUMENTATION.md](FULL_DOCUMENTATION.md) — complete single-file manual.
- [docs/DOCUMENTATION_INDEX.md](docs/DOCUMENTATION_INDEX.md) — GitHub topic index.
- [docs/content/](docs/content/) — source-of-truth topic files used by WebUI docs search.
- WebUI **Documentation Center** — searchable local documentation.

## Safety note

LQoSync can write LibreQoS input files and trigger LibreQoS apply behavior. Always verify `config.json`, backups, policies, dry-run output, and apply results before using it in production.


## v2.63.1 Operations Center hotfix

This hotfix resolves an Internal Server Error on `/operations` caused by a variable-name collision between the journal line-count selector and the app log line list. The Operations Center now passes `journal_lines_count` separately from `lines`, so app logs render safely while all tabs and compatibility redirects remain unchanged.


## v2.64 UI Consistency and Redundancy Polish

LQoSync v2.64 improves the compact operator experience without changing engine behavior. Dashboard remains the live status cockpit, Operations Center owns services/journals/logs/audit/backups, Reports is export-focused, Config Center owns settings/policies/notifications, and Documentation Center is the single manual surface. Operations Center Apply History and Audit Events now use consistent pagination and row-limit controls.


## v2.65 Production Hardening + Regression Suite

LQoSync v2.65 adds offline regression checks for route/template wiring, high-risk template context, preserved config migration, policy safety behavior, Operations Center compatibility, and documentation integrity. Before publishing or updating from GitHub, run:

```bash
cd /opt/lqosync
python3 scripts/release_check.py
python3 scripts/regression_check.py
python3 scripts/config_migration_check.py
```

The full environment doctor also runs these checks:

```bash
sudo CONFIG_PATH=/opt/libreqos/src/config.json bash scripts/lqosync-doctor.sh
```


## v2.66 Backup / Restore Center Polish

Operations Center backups now support read-only preview, metadata/hash integrity checks, live-file comparison, selected-backup zip download, and retention preview visibility. Restore still creates a fresh backup of current live files before rollback so restore remains reversible. This is a backup/restore UX and safety improvement only.
