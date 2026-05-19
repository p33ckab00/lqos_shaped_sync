

## v2.85.0-rc1 — Rust Core v1.5 Rollback Execution Rehearsal

- Added Rust `execute-rollback` operation.
- Added rollback rehearsal and opt-in file restore execution guarded by `CONFIRM_ROLLBACK`.
- Added `/api/rust-core/rollback-execute` admin endpoint.
- Added rollback authority config flags with safe defaults.
- Python fallback never restores files.
## 2.84.0-rc1 — Rust Core v1.4 Transaction History and Rollback Plan Viewer

- Add read-only Rust transaction journal history operation.
- Add rollback-plan-from-journal preview operation.
- Add `/api/rust-core/transaction-journal` and `/api/rust-core/rollback-plan`.
- Keep rollback execution disabled; Python remains authoritative by default.

# Release Notes

## v2.76.0-rc1 - Rust Core v0.6 Circuit Shadow Normalizer

- Adds Rust `normalize-circuits` protocol operation.
- Adds shadow circuit normalization diagnostics in Dry Run as `rust_circuit_shadow`.
- Keeps Python collectors and builders authoritative while Rust verifies normalized circuit row shape.
- Fixes the v0.5 unused `mut` Rust warning in `policy.rs`.

## v2.73.1-rc1 - Rust Core v0.3 Build Hotfix

- Fixes Rust build failure in `shaped_devices.rs` by using `csv::Terminator::Any(b'\n')` instead of the non-existent `csv::Terminator::LF` variant.
- Keeps v0.3 atomic state/file behavior unchanged.
- Python fallback remains active if the Rust binary is unavailable.

## v2.73.0-rc1 - Rust Core v0.3 Atomic State/File Engine

- Adds Rust protocol operations for `validate-json-state`, `write-json-state`, `write-text-file`, and `append-audit-jsonl`.
- Hardens Python fallback atomic writes with parent-directory fsync where supported.
- Moves `runtime_state.json`, `policy_state.json`, `collector_cache.json`, and audit JSONL writes onto shared safe writer helpers.
- Keeps Rust-backed writes opt-in via `LQOSYNC_RUST_ATOMIC_WRITES=1`; Python fallback remains default.

# 2.72.0-rc1 — Rust Core v0.2 Trust/Diff Guard

- Added Rust `diff-shaped-devices`, `diff-network`, and `diff-files` protocol operations.
- Added collector trust envelope enforcement inside `run_cycle.py` before source cleanup eligibility.
- Added Python fallback implementation of the collector trust contract so silent empty collector results are guarded even before the Rust binary is built.
- Added Dry Run visibility for Rust diff and collector trust diagnostics.
- Added `docs/RUST_CORE_V02_TRUST_DIFF.md` to document the new safety boundary.

# Release Notes

## v2.71.0-rc2 - Canonical /opt Install Path Cleanup

Path documentation cleanup package for the `lqosync-in-rust` branch.

### Fixed

- Replaced remaining user-home install examples with canonical `/opt` paths.
- Normalized project checkout examples to `/opt/lqosync`.
- Normalized legacy Docker/project examples to `/opt/lqos_docker` where that legacy folder is still referenced for cleanup/migration guidance.
- Confirmed the canonical installation base is `/opt`.

### Safety notes

- Documentation/path guidance only.
- Runtime sync/apply behavior is unchanged.
- Rust core scaffold remains optional and non-blocking by default.

## v2.71.0-rc1 - Optional Rust Core Scaffold

First implementation package for the `lqosync-in-rust` branch.

### Added

- Added `rust/lqosync-core`, an optional Rust safety-core crate.
- Added a stable JSON protocol envelope in `protocol.rs` for CLI now and future Unix socket daemon later.
- Added Rust bandwidth parser with unit, comment, and RouterOS `rate-limit` parsing.
- Added Rust ShapedDevices.csv parser/render validator.
- Added Rust network.json parser/tree validator.
- Added Rust config/policy action validation.
- Added Rust collector output trust validation for partial and suspicious zero-result source data.
- Added `engine/rust_core.py` Python wrapper with subprocess transport and Python fallback.
- Added `rust_core` config defaults: enabled, binary path, timeout, enforce mode, daemon preference, and socket path.
- Added Dry Run visibility for `rust_core_validation` when the binary is available.
- Added `/api/rust-core/status` for checking wrapper/binary availability.
- Added build/install helpers: `scripts/build-rust-core.sh` and `scripts/install-rust-core.sh`.

### Safety notes

- Runtime sync/apply behavior remains Python-first.
- Rust validation is optional and non-blocking by default.
- If the Rust binary is missing, Python fallback remains active.
- `rust_core.enforce_validation=false` by default; enable only after lab/staging validation.
- This release does not yet move atomic state/file writes into Rust; that remains v0.3 migration scope.

## v2.70.10-rust-docs - LQoSync-in-Rust Documentation Package

Documentation-only package for the planned `lqosync-in-rust` branch.

### Added

- `docs/RUST_CORE_MIGRATION.md` documents the phased hybrid migration from Python backend core to Rust safety core.
- `docs/RUST_CORE_PROTOCOL.md` defines the stable JSON request/response envelope for subprocess CLI and future Unix socket daemon.
- `docs/COLLECTOR_OUTPUT_CONTRACT.md` documents typed collector trust validation to prevent silent partial/zero RouterOS results from triggering unsafe cleanup.
- `docs/AUTOSAVE_AND_ATOMIC_STATE.md` documents no-save-button autosave, dangerous-change confirmation, and atomic state/file writes.
- `docs/COMMIT_AND_PUSH_GUIDE.md` documents branch workflow, commit messages, push commands, and pull request template for `lqosync-in-rust`.
- Added `docs/assets/lqosync_rust_migration_plan.svg` as the Rust migration planning diagram.

### Safety notes

- No runtime behavior change in this documentation package.
- Python Flask WebUI remains the operator interface in the migration plan.
- Rust is planned as a deterministic safety boundary before cleanup, diff, write, and apply decisions.
- `collector_cache.json` is explicitly included in the future atomic state engine scope.


## v2.70.10-rc1 — Policy Overview Custom Wiring Hotfix

- Fixes Config Center → Policies so Policy Overview controls also switch the visible policy mode to Custom.
- Operation Mode, Auto Apply, Optional Auto Backup, and Backup Retention now call markPolicyCustom() when changed in the Policy Hierarchy UI.
- Adds server-side protection in /config save: if policy-adjacent app.* settings changed while a named preset was active, policies.mode is saved as custom.
- Extends UI wiring audit so this Custom-mode wiring is checked in release/regression/stable validation.

This is a Config Center save/UX hotfix only. It does not change MikroTik collection, cleanup execution, generated file formats, scheduler timing, backup implementation, Telegram delivery, or LibreQoS apply mechanics.

# LQoSync Release Notes

## v2.70.9-rc1 - Custom Policy Mode Persistence Hotfix

### Fixed

- Restores Custom as a visible policy state in Config Center → Policies.
- Adds a Custom state badge beside Conservative, Balanced, and Aggressive so customized policies do not appear to disappear.
- Preserves explicit `policies.mode = custom` on Config Center save. Custom is now treated as an operator preference, not auto-converted back to a named preset.
- Keeps named preset behavior intact: exact Conservative/Balanced/Aggressive stays named, while edited named presets reconcile to `custom`.
- Updates Policy Preset Audit to verify exact named presets, edited named presets, and explicit custom preservation.
- Updates UI Wiring Audit to verify visible Custom policy state wiring.

### Notes

This is a policy UI/save-semantics hotfix. It does not change MikroTik collection, cleanup policy execution, generated file formats, scheduler timing, backup implementation, Telegram delivery, or LibreQoS apply mechanics.

## v2.70.8-rc1 - Policy Preset Alignment + Save Semantics Hotfix

### Fixed

- Aligns Conservative, Balanced, and Aggressive policy presets with the stable safety model.
- Aggressive mode still uses faster normal inactive cleanup, but PPPoE/DHCP/Hotspot zero-result cleanup now remains `block_cleanup`.
- Balanced defaults now use `block_cleanup` for Hotspot zero-result instead of `warn_only`.
- Adds server-side policy mode reconciliation during Config Center saves: exact presets keep their preset name, while modified policy blocks are saved as `custom`.
- Ensures policy preset apply preserves user preferences outside `config.json → policies`, including optional auto-backup, Telegram settings, operation mode, router settings, and paths.
- Adds `engine/policy_preset_audit.py` and `scripts/policy_preset_audit.py` to validate preset alignment and custom-save semantics.
- Integrates Policy Preset Audit into release integrity, regression, stable release checks, and lqosync-doctor.
- Adds `package_quality.policy_preset_audit_script` and bumps `config_schema_version` to 12.

### Notes

This is a policy preset alignment and Config Center save-semantics hotfix. It does not change MikroTik collection, generated file formats, scheduler timing, backup implementation, Telegram delivery mechanics, or LibreQoS apply mechanics.

## v2.70.7-rc1 - LibreQoS Apply Failure Visibility Hotfix

### Fixed

- Fixes the invisible LibreQoS apply failure workflow where Dashboard/Telegram could warn about failed apply but did not clearly link to where the error should be inspected or resolved.
- Adds `engine/apply_diagnostics.py` to classify saved LibreQoS apply failures using stderr/stdout and metadata.
- Adds `/libreqos/apply/<run_id>` as a human-readable apply diagnostic page.
- Adds `/api/libreqos/apply/<run_id>/diagnostic` as a read-only JSON diagnostic endpoint.
- Updates Dashboard notification cards so apply warnings/failures are clickable and show “Open resolve page”.
- Updates apply health notification targets from the old `/services` pointer to `/libreqos/apply/<run_id>` when possible, or `/operations?tab=apply` as fallback.
- Updates Operations Center → Apply History with a **Detail / Resolve** button and inline summary/resolution hints for failed apply runs.
- Stores `last_libreqos_run_id` in runtime state for force-apply and scheduler apply attempts.
- Extends UI wiring audit to validate apply failure notification-to-resolution wiring.

### Notes

This is an apply failure visibility and diagnostics wiring hotfix only. It does not change MikroTik collection, cleanup policy execution, generated file formats, scheduler timing, backup implementation, Telegram delivery, or LibreQoS apply mechanics.

## v2.70.6-rc1 - Checkbox State Wiring Hotfix

### Fixed

- Fixes Config Center checkbox visual-state wiring where a boolean policy value could be true in config but the checkbox did not visibly show as checked.
- Adds `asBool()` boolean normalization for true-like values such as `true`, `"true"`, `1`, `"1"`, `yes`, and `on`.
- Updates dynamic policy boolean checkboxes to use normalized `:checked` binding and `x-effect` synchronization.
- Adds checkbox accent/checked-state styling so checked boxes are visible in both light and dark mode.
- Extends UI wiring audit to detect missing checkbox state binding and checked-state CSS.

### Notes

This is a Config Center UI/UX wiring hotfix only. It does not change MikroTik collection, cleanup policy execution, generated file formats, scheduler timing, backup implementation, Telegram delivery, or LibreQoS apply mechanics.

## v2.70.5-rc1 — Settings UI State Wiring Hotfix

- Fixed Config Center → Policies preset active-state mismatch where `Current: aggressive` could display while the Balanced button remained highlighted.
- Policy preset buttons now derive active styling from `cfg.policies.mode` through `policyPresetActive()`, `policyPresetClass()`, and `policyPresetLabel()`.
- Extended `engine/ui_wiring_audit.py` to validate Config Center dynamic UI state, including nav tab/section pairing, policy tree/panel pairing, preset active-state binding, and normalized config save binding.
- Updated `scripts/ui_wiring_audit.py` output to include the Config Center UI state wiring check.
- Updated documentation, docs manifest, documentation index, README, full documentation, operator guide, stable checklist, upgrade guide, and version metadata to 2.70.5-rc1.

This is a UI/UX wiring hotfix only. It does not change MikroTik collection, cleanup policy execution, generated file formats, scheduler timing, backup implementation, Telegram delivery, or LibreQoS apply mechanics.


## v2.70.4-rc1 — UI Wiring Audit + Role Visibility Hotfix

- Added `engine/ui_wiring_audit.py` and `scripts/ui_wiring_audit.py` for deeper static UI wiring validation.
- Fixed role-hardened action visibility by replacing literal `user.role == 'admin'` checks with `role_at_least(user.role, 'admin')` or `role_at_least(user.role, 'operator')` where appropriate.
- Fixed owner accounts not seeing admin-capable action buttons in Dashboard, Network Layout, Shaped Devices, Operations Center, Backup Preview, and compatibility templates.
- Gated owner-only Update Center links in About and Setup/System Validation pages so non-owner users do not see links that lead to 403 Forbidden.
- Added UI wiring checks for policy preset wiring inside Config Center → Policies, canonical compatibility routes, owner-only links, role visibility, and stale files.
- Integrated UI wiring audit into `release_check.py`, `regression_check.py`, `stable_release_check.py`, and `lqosync-doctor.sh`.
- Expanded stale-file cleanup to include `app.py.pre_reports_route_fix` in addition to old `templates/routers.html`.
- Added `package_quality.ui_wiring_audit_script` to config defaults and schema migration.
- Updated documentation, docs manifest, documentation index, README, full documentation, operator guide, release notes, and version metadata to `2.70.4-rc1`.

This is a UI wiring, role visibility, and validation hotfix only. It does not change MikroTik collection, cleanup policy execution, generated file formats, scheduler timing, backup implementation, Telegram delivery, or LibreQoS apply mechanics.

## v2.70.3-rc1 - Policy Preset Wiring Hotfix

### Fixed

- Fixes Config Center → Policies preset workflow after the policy UI was moved into the compact hierarchy.
- Adds visible Conservative, Balanced, and Aggressive preset buttons inside Config Center → Policies.
- Wires preset buttons to the existing CSRF-protected `/policy/apply-preset/<preset>` route.
- Makes `policies.mode` display as managed preset status instead of a misleading normal editable field.
- Keeps manual policy edits switching mode to `custom`.
- Ensures preset apply redirects back to `/config?tab=policies`.

### Notes

This is a UI wiring hotfix only. It does not change MikroTik collection, cleanup policy execution, generated file formats, scheduler timing, backup implementation, Telegram delivery, or LibreQoS apply mechanics.

## v2.70.2-rc1 - Config Policy Hierarchy UI + Optional Auto-Backup Semantics

### Improved

- Rebuilds Config Center → Policies into a compact hierarchy tree instead of a flat policy card list.
- Groups policies by operator intent: Overview, General Core, PPPoE, DHCP, Hotspot, Static, Cleanup Lifecycle, Mass Removal, Apply Guards, Auto Apply, Backup Policy, Topology/Data, Speed Resolution, and Advanced JSON.
- Shows policy labels, current values, recommended values, risk badges, descriptions, setup guidance, and config paths for visible policy settings.
- Adds `app.operation_mode` with `automatic` and `manual` modes.
- Treats `app.auto_apply` as required when `app.operation_mode=automatic`.
- Treats `app.backup_before_apply` as optional storage/rollback policy by default.
- Updates Production Readiness so auto-apply disabled in automatic mode is a blocker, while auto-backup disabled is accepted as storage-saving mode.
- Updates policy defaults, policy schema, config migration, config simulator, insights, and setup/repair interpretation to match optional auto-backup semantics.
- Adds Policy Hierarchy documentation.

### Notes

This is a Config Center UI and status-interpretation update. It does not change MikroTik collection, cleanup policy execution, generated file formats, scheduler timing, backup implementation, Telegram delivery, or LibreQoS apply mechanics.

## v2.70.1-rc1 - Stable RC Stale Template Cleanup Hotfix

### Fixed

- Adds `scripts/cleanup_stale_files.py` to detect and remove known stale files left behind by older ZIP/manual installs.
- Adds `templates/routers.html` to the known stale-file cleanup list because Router Insight now lives in Config Center → Routers and `/routers` is only a compatibility redirect.
- Updates `upgrade.sh` to run stale-file cleanup automatically after code update so stable validation does not warn about old untracked templates.
- Updates `lqosync-doctor.sh` to show stale-file cleanup status before running the stable release candidate check.
- Updates stable release validation guidance to recommend running `python3 scripts/cleanup_stale_files.py --apply` when stale templates are detected.

### Notes

This is a cleanup/hotfix release. It does not change MikroTik collection, cleanup policy behavior, generated files, scheduler behavior, backups, Telegram delivery, or LibreQoS apply behavior.

# Release Notes

## v2.70.0-rc1 — Stable Release Candidate / Production Freeze

- Declares v2.70 as a stable release candidate and feature-freeze release.
- Adds `engine/stable_release.py` and `scripts/stable_release_check.py` for stable candidate validation.
- Adds route compatibility validation for `/health`, `/services`, `/logs`, `/policy`, `/notifications`, and `/routers`.
- Adds template classification for active, compatibility/deprecated, and review templates.
- Adds update preflight validation for required release/update scripts and config JSON.
- Integrates the stable release check into `lqosync-doctor.sh`.
- Adds `/api/stable-release/check` for read-only stable release diagnostics.
- Updates Update Center with stable-candidate validation commands and System Validation links.
- Renames Setup / Repair presentation toward System Validation and adds stable validation guidance.
- Adds stable documentation: `docs/STABLE_RELEASE_CHECKLIST.md`, `docs/ROUTE_COMPATIBILITY.md`, `docs/UPGRADE_GUIDE.md`, `docs/POLICY_PATH_REFERENCE.md`, and `docs/content/stable_release_candidate.md`.
- Updates package quality defaults with `stable_release_check_script`.

This is a stabilization release. It does not change MikroTik collection, cleanup policy decisions, generated files, scheduler behavior, backups, Telegram delivery, or LibreQoS apply behavior.


## v2.69.1 — Router Insight De-duplication + Policy/Path Audit

- Reimagines the Router module to avoid redundant UX: Router Insight now lives inside Config Center → Routers where router settings already exist.
- Removes the top-level Routers sidebar item and removes the active standalone router page template.
- Keeps `/routers` as a compatibility alias that redirects to `/config?tab=routers`.
- Keeps `/api/routers/overview` as a read-only diagnostics API.
- Adds `engine/policy_path_audit.py` and `scripts/policy_path_audit.py` to verify required runtime paths, policy schema paths, policy defaults coverage, migrated config completeness, missing-policy warnings, and schema errors.
- Integrates policy/path audit into release integrity, regression checks, and lqosync-doctor.
- Adds `policy_path_audit_script` to package quality defaults and config.json.example.
- Updates documentation, docs manifest, documentation index, README, full documentation, operator guide, release notes, and version metadata to v2.69.1.

This is a UI de-duplication and safety-audit release. It does not change MikroTik collection, cleanup policy decisions, generated files, scheduler behavior, backups, Telegram delivery, or LibreQoS apply behavior.


## v2.69.0 — Router Overview + Multi-Router UX Polish

- Added a read-only Router Overview page at `/routers` so operators can inspect configured MikroTik routers, enabled sources, generated row ownership hints, parent-node role, and last-run collector warnings in one compact view.
- Added `/api/routers/overview` for structured read-only router overview diagnostics.
- Added `engine/router_overview.py` and `templates/routers.html`.
- Added Routers to the Main navigation for faster multi-router inspection.
- Updated release integrity checks to include Router Overview route/template/engine wiring.
- Updated documentation, docs manifest, documentation index, README, full documentation, operator guide, and version metadata to v2.69.0.

This is a read-only UX polish release. It does not change MikroTik collection, cleanup policies, generated files, scheduler behavior, backups, Telegram delivery, or LibreQoS apply behavior.

# LQoSync Release Notes

## v2.68.0 - Production Readiness Score

### Added

- Adds `engine/production_readiness.py` as a read-only Production Readiness scoring helper.
- Adds a Dashboard Production Readiness card that combines config validity, Setup Wizard go-live state, first Dry Run, router/source readiness, backup-before-apply safety, LibreQoS paths, policy conflicts, source health, apply health, and service health into one operator-facing score.
- Adds `/api/production/readiness` for read-only JSON readiness diagnostics.
- Adds `production_readiness` defaults to config.json.example and config schema migration.
- Updates docs/content, docs manifest, documentation index, README, full documentation, operator guide, release notes, and version metadata.

### Notes

This is a read-only operator confidence release. It does not change MikroTik collection, cleanup policy decisions, generated file behavior, scheduler enforcement, backup behavior, Telegram delivery, or LibreQoS apply behavior.

## v2.67.0 - Access Control + Role Hardening

### Added

- Adds an explicit `owner`, `admin`, `operator`, and `viewer` role hierarchy.
- Promotes the first preserved `admin` account to `owner` when upgrading older installs with no owner, preventing lockout from owner-only controls.
- Adds owner-only access for Users & Roles, Update Center, Smart Defaults Repair, and release integrity API.
- Keeps admin/owner access for config, policies, scheduler, operations, backup restore/delete, setup/repair operations, and LibreQoS apply actions.
- Allows operator-or-above users to run Dry Run previews while viewers remain read-only.
- Updates the Users page with role cards, a permission summary, role labels, and mobile-friendly user rows.
- Adds access_control defaults to config.json.example and schema migration.

### Notes

This is a security/permission hardening release. It does not change MikroTik collection, cleanup policy decisions, generated files, scheduler timing, backup behavior, Telegram delivery behavior, or LibreQoS apply logic.

## v2.66.0 - Backup / Restore Center Polish

### Improved

- Adds read-only backup preview/inspection from Operations Center.
- Adds backup integrity details for tracked backup files and metadata hashes.
- Adds live-file comparison so operators can see whether selected backup files differ from current live files before restore.
- Adds backup zip download for a selected backup directory.
- Adds retention preview API for visibility into configured backup retention pruning.
- Keeps restore behavior reversible by creating a new backup of current live files before rollback.

### Notes

This is an Operations Center backup/restore UX and safety release. It does not change MikroTik collection, cleanup policy behavior, generated file building, scheduler behavior, or LibreQoS apply behavior.

## v2.65.0 - Production Hardening + Regression Test Suite

### Added

- Added `engine/regression.py` as an offline production-hardening regression suite.
- Added `scripts/regression_check.py` for route/template wiring, high-risk template context, config migration, policy safety behavior, Operations Center compatibility, and documentation integrity checks.
- Added `scripts/config_migration_check.py` to focused-test preserved older config scenarios against the current schema and policy defaults.
- Updated `scripts/lqosync-doctor.sh` to run release integrity, regression, config migration, and environment/config checks in one operator command.
- Strengthened config schema migration so preserved older configs deep-merge `notifications`, `setup_wizard`, `package_quality`, and `config_validation` defaults without overwriting operator values.
- Added regression script paths to `package_quality` defaults.
- Added production hardening documentation under `docs/content/production_hardening_regression_suite.md`.

### Notes

This is a hardening and testing release. It does not change MikroTik collection, cleanup policy decisions, generated files, scheduler behavior, backup behavior, Telegram delivery behavior, or LibreQoS apply behavior.

## v2.64.0 - UI Consistency and Redundancy Polish

### Improved

- Adds reusable UI consistency helpers for page maps, compact chips, table toolbars, pagination, mobile table-card behavior, icon buttons, and empty states.
- Adds Dashboard section shortcuts so the Dashboard behaves more like a compact operator cockpit instead of a long wall of cards.
- Standardizes Operations Center Apply History with row-limit selector, pagination, and consistent empty-state behavior.
- Standardizes Operations Center Audit Events with row-limit selector, pagination, consistent toolbar, and mobile-friendly stacked row behavior.
- Keeps Reports export-focused, Dashboard status-focused, Operations evidence-focused, and Documentation as the single manual surface.

### Notes

This is a UI/UX polish release only. It does not change MikroTik collection, cleanup policy decisions, generated files, scheduler behavior, backup behavior, or LibreQoS apply behavior.

## v2.63.1 - Operations Center Log Variable Hotfix

### Fixed

- Fixes an Internal Server Error on `/operations` caused by a template variable collision after Operations Center consolidation.
- The journal line-count selector and app log line list now use separate variables so the App Logs section can render safely even when another tab is active.
- Keeps `/operations`, `/services`, and `/logs` compatibility behavior unchanged.

### Notes

This is a routing/template hotfix only. It does not change MikroTik collection, policy logic, generated files, scheduler behavior, backup behavior, or LibreQoS apply behavior.

## v2.63.0 - Documentation Center Consolidation

### Improved

- Consolidates GitHub-facing and WebUI-facing documentation into one source-of-truth model.
- Keeps `README.md` compact as the GitHub landing page.
- Rebuilds `FULL_DOCUMENTATION.md` as the complete single-file manual compiled from indexed documentation topics.
- Adds `docs/DOCUMENTATION_INDEX.md` as the GitHub-friendly table of contents for documentation topics.
- Adds `docs/content/documentation_consolidation.md` describing the documentation ownership model and maintenance rules.
- Updates the Documentation Center landing copy to emphasize that WebUI docs, GitHub docs, and source topic files share the same documentation model.

### Notes

This is a documentation consolidation and UI guidance update. It does not change MikroTik collectors, policy decisions, cleanup behavior, generated files, scheduler behavior, or LibreQoS apply behavior.

## v2.62.0 - Config + Policy + Notification Unification

### Improved

- Makes Config Center the single settings home for normal config, Smart Policy Center settings, Telegram notification delivery settings, and Advanced Raw JSON.
- Adds a Config Center Notifications tab for Telegram bot token, chat ID, base URL, alert levels, dedupe/min interval, digest/individual delivery, and event filters.
- Enhances the Config Center Policies tab with Policy Conflict Resolver summary and Client Identity Handling guidance so operators do not need a separate Policy page for common decisions.
- Keeps `/policy` and `/notifications` as compatibility aliases that redirect to `/config?tab=policies` and `/config?tab=notifications`.
- Preserves Telegram test/current alert actions and policy preset/confirmation endpoints for compatibility.
- Updates documentation with the consolidated settings model.

### Notes

This is a UI/routing/settings organization update. It does not change MikroTik collection, cleanup/apply policy evaluation, generated file formats, scheduler behavior, or LibreQoS apply execution.

## v2.61.0 - Compact Information Architecture + Documentation Consolidation

### Improved

- Adds a consolidated Operations Center that brings together Services, Journals, LibreQoS Apply History, App Logs, Audit Events, and Backups.
- Keeps old `/services` and `/logs` routes as compatibility redirects into Operations Center tabs.
- Cleans the sidebar into operator-intent groups: Main, Settings, Operations, and Help.
- Keeps Dashboard as the single live health/status surface and leaves `/health` as a compatibility redirect.
- Reduces Reports Center to export/report snapshot behavior instead of duplicating Dashboard health cards.
- Reduces About into lightweight project/version/AI disclosure links while Documentation Center becomes the searchable manual source.
- Updates GitHub-facing docs with the consolidated documentation model: README stays compact, FULL_DOCUMENTATION is the long-form manual, and docs/content + docs_manifest drive WebUI docs.

### Compatibility

Existing links to `/services`, `/logs`, and `/health` continue to work through redirects. API endpoints remain available for integrations.

## v2.60.2 - Backup Pagination and Actions

### Fixed / Improved

- Adds wired delete action for backups under Logs & Backups. Delete removes the selected backup directory after CSRF-protected admin confirmation and writes an audit event.
- Converts backup restore into an icon-only restore action to keep the Backups panel compact and consistent with operator action controls.
- Adds backup pagination and row-limit controls so backup lists no longer overflow the panel when many backups exist.
- Adds a safe backend `delete_backup()` helper that blocks path traversal by requiring the selected backup id to resolve as a direct child of the configured backup directory.
- Adds `/backups/<backup_id>/delete` and `/api/backups/<backup_id>/delete` endpoints.

### Notes

Restore remains reversible because LQoSync creates a backup of current live files before restoring. Delete is permanent for the selected backup directory and should be used only after confirming the backup is no longer needed.

## v2.60.1 - Client Lifecycle View and Filter Hotfix

### Fixed / Improved

- Fixed the Client Lifecycle Table **View** action so it focuses the selected client timeline while preserving the current status, source, search, row-limit, and timeline filter context.
- Reworked Lifecycle filters into instant, client-side searchable controls similar to the Shaped Devices/Subscribers table. Search, status pills, source selector, row-limit selector, and column filters update the table/cards without requiring the Apply button workflow.
- Added Timeline Focus pagination controls with event type filter, timeline row-limit selector, Prev/Next controls, page count, and total event count.
- Improved mobile lifecycle cards so they use the same auto-filtering behavior and View/focus wiring as the desktop table.

### Notes

This is a UI/UX and route-parameter hotfix. It does not change policy decisions, cleanup behavior, MikroTik collection, generated files, scheduler behavior, Telegram notifications, or LibreQoS apply behavior.

## v2.60.0 - Better Fresh Install Experience

### Added

- Added `setup_wizard` configuration defaults for first-run onboarding, Dashboard setup banners, scheduler go-live gates, and optional redirect to the First Run Setup Wizard.
- Added a fresh-install production gate that checks router/source readiness, successful Dry Run, and Setup & Repair failed checks before allowing scheduler enable.
- Added Dashboard First Run Setup banner when onboarding is not complete.
- Added Setup Wizard readiness banner, blocker list, Mark Setup Complete action, and Reset Wizard action.
- Added scheduler-enable protection in both WebUI form routes and API routes so new installs cannot enable scheduler until setup requirements are satisfied.
- Preserved upgrade friendliness by treating existing live installs with scheduler enabled or previous run history as already acknowledged.

### Notes

This release improves onboarding and go-live safety. It does not change MikroTik collection, generated file formats, policy evaluation, Telegram notifications, or LibreQoS apply behavior.

## v2.59.0 - Documentation Search and UI Mobile Polish

### Added

- Added `engine/docs_search.py` for local, read-only documentation indexing and search over bundled Markdown docs and docs manifest entries.
- Added `/docs/search`, `/docs/view/<doc_id>`, `/api/docs/search`, and `/api/docs/index`.
- Added a Documentation Search page with quick topic chips, result excerpts, docs source paths, and links back to About anchors when available.
- Added Docs Search to the Help navigation section.
- Added reusable UI consistency helpers for responsive grids, empty states, section cards, action strips, mobile sticky actions, and keyboard hints.

### Notes

Documentation Search is local to the LQoSync WebUI. It does not call external services and does not modify config, state, generated files, or LibreQoS.

## v2.58.0 - Telegram Notifications

### Added

- Added `engine/notifications.py` for optional Telegram delivery of LQoSync internal notification candidates.
- Added `/notifications` Telegram Notification Center for bot token, chat ID, base URL, notify levels, digest mode, dedupe, and delivery filters.
- Added Telegram test workflow and current-alert delivery workflow.
- Added `/api/notifications/telegram/test` for structured Telegram test delivery.
- Added digest formatting, level filtering, event filtering, minimum interval protection, and dedupe window protection.
- Added notification state tracking under `state/notification_state.json` by default.
- Updated Dashboard health notification delivery state from planned to available.
- Added Telegram notification config defaults and documentation.

### Notes

Telegram is disabled by default. Internal Dashboard notifications still work even when Telegram is off. Bot tokens are secrets and are stored in `config.json`, so protect file permissions and avoid sharing raw config screenshots.

## v2.57.1 - Dashboard Health Consolidation

### Improved

- Consolidated Source Health and Performance Trends into the main Dashboard to avoid duplicate monitoring pages with similar operational information.
- Added Dashboard Source Health & Performance section with health score, source cards, timing trends, LibreQoS apply health, and internal notification candidates.
- Removed the separate Health Trends navigation item from the sidebar so the Dashboard is the single operator landing page for health/status monitoring.
- Kept `/api/health/trends` as the read-only JSON endpoint for integrations and diagnostics.
- Kept `/health` as a compatibility redirect to the Dashboard health section so old bookmarks do not break.

### Notes

This is a UI/UX consolidation update. It does not change collection, policy decisions, generated files, scheduler behavior, or LibreQoS apply logic.

## v2.57.0 - Source Health + Performance Trends

### Added

- Added `engine/health_trends.py` for read-only source health, performance trend, LibreQoS apply health, and notification candidate reporting.
- Added `/health` Health Trends center with PPPoE/DHCP/Hotspot source cards, Router API timing trends, sync cycle trends, LibreQoS apply health, and internal notification candidates.
- Added `/api/health/trends` JSON endpoint for integrations and diagnostics.
- Added monitoring and notification foundation defaults in `config.json.example`.
- Added Health Trends navigation under Monitor.

### Notes

This release is read-only. Telegram delivery is planned for v2.58; v2.57 only creates internal notification candidates and monitoring summaries.

## v2.56.0 - Policy UX + Conflict Intelligence

### Added

- Added `engine/policy_conflicts.py` for read-only Policy Conflict Resolver and Client Identity guidance.
- Added `/api/policy/conflicts` for structured conflict and identity reports.
- Added Policy Conflict Resolver card in Smart Policy Center, including severity, what happened, why it matters, recommended fix, and affected config paths.
- Added Client Identity Handling card explaining PPPoE, DHCP, Hotspot, and Static/manual identity stability and grace recommendations.
- Improved Current vs Preset comparison into a table with section, current value, preset value, risk, and setup guidance.

### Why

Policies are powerful and flexible. This release makes policy combinations easier to understand before they affect cleanup, Dry Run, or LibreQoS apply behavior.

## v2.55.0 - Package Quality + Environment Doctor

### Added

- Added `engine/release_integrity.py` for package integrity, route/template checks, feature wiring checks, config default completeness checks, and Smart Defaults Repair helpers.
- Added `scripts/release_check.py` for pre-publish and post-upgrade release validation.
- Added `scripts/lqosync-doctor.sh` as a full environment doctor wrapper that runs package integrity plus config/path/permission/LibreQoS diagnostics.
- Added `/api/release/integrity` read-only endpoint for Setup & Repair and automation.
- Added Setup & Repair Smart Defaults Repair action that backs up `config.json`, deep-merges missing safe defaults, preserves operator values, and validates the result.
- Added Package Integrity Guard and Smart Defaults Repair cards in Setup & Repair.
- Added package_quality config defaults and documentation.

### Why

This release prevents package gaps such as a navigation link pointing to a missing Flask route, templates without matching routes, missing feature engine files, or incomplete config defaults after upgrade/fresh install.

## v2.54.5 - Privacy Incognito Icon Polish

### Improved

- Replaced the Privacy Mode shield-and-eye icon with a cleaner incognito-style icon for better visual relevance to masked/screenshot-safe mode.
- Kept the slash overlay when Privacy Mode is disabled.
- Kept the active highlighted state when Privacy Mode is enabled.
- Updated the Privacy Mode banner icon to match the new privacy/incognito visual language.

### Notes

This is a UI/UX polish update only. It does not change privacy redaction behavior, policy logic, MikroTik collection, generated files, scheduler behavior, or LibreQoS apply behavior.

## v2.54.4 - AI-Assisted Development Disclosure

### Added

- Added an AI-Assisted Development Disclosure and Acknowledgement at the top of README.md and FULL_DOCUMENTATION.md for clear project transparency.
- Added docs/AI_ASSISTED_DEVELOPMENT.md as the standalone disclosure source.
- Added the same disclosure to the About / Documentation module near the top of the operator guide.
- Updated docs/docs_manifest.json so the disclosure is discoverable by the documentation system.

### Notes

This is a documentation-only transparency update. It does not change MikroTik collection, policy behavior, generated files, scheduler behavior, Network Layout, LibreQoS apply logic, or service automation.

## v2.54.3 - Network Layout Drag-and-Drop Wiring

### Added

- Wired desktop drag-and-drop behavior in Network Layout.
- Node cards and topology tree items can now be dragged onto another node to move them under that parent.
- Added a root drop zone to promote/move dragged nodes back to root level.
- Added visual drag-over and invalid-drop states for allowed/blocked moves.
- Added validation for drag moves to prevent moving a node under itself, moving a node under its own descendant, moving to the same parent, or creating duplicate child names under a target parent.
- Added drag status messaging and a Network Layout guide explaining that drag-and-drop edits the in-browser preview only until Save topology is clicked.

### Notes

Drag-and-drop is intended for desktop browsers. On mobile/touch devices, operators should continue using the Node Inspector Move control. This update changes only the Network Layout UI behavior; saved topology still goes through the existing network.json save validation.

## v2.54.2 - Policy Center Setup Guidelines

### Improved

- Added atomic operator explanations for every visible Policy Center setting.
- Policy Center now explains each setting with What it controls, Setup guide, Risk note, Config path, Recommended value, and Risk level.
- Added Policy Setup Guidelines card to the Policy Center with cleanup action meanings such as preserve_rows, warn_only, cleanup_immediate, cleanup_next_run, require_confirm_next_run, block_cleanup, and block_apply.
- Added docs/content/policy_center_settings_guidelines.md as the detailed source-of-truth setup guide for every policy setting.
- Updated docs/docs_manifest.json so the new policy guidelines are discoverable by Documentation / Setup & Repair links.
- Normalized stale lifecycle PPPoE policy naming to the canonical pppoe key while accepting the older ppoe alias from previous schema builds, preventing false missing-policy warnings after upgrade or fresh install.

### Notes

This is a Policy Center UX/documentation/config-defaults hotfix. It does not change MikroTik collection, ShapedDevices.csv generation, network.json generation, or LibreQoS apply behavior.

# Release Notes

## v2.54.1 - Smart Reports Route Hotfix

### Fixed

- Restored the missing Flask route wiring for `/reports` in `app.py`.
- Restored `/api/reports/operator` JSON endpoint.
- Restored `/reports/export/json`, `/reports/export/csv`, and `/reports/export/markdown` export endpoints.
- Keeps the existing `engine/reports.py`, `templates/reports.html`, and Smart Reports navigation entry cumulative with v2.54.

### Why

The v2.54 package included the Smart Reports engine/template/navigation from v2.52, but the Flask routes were missing from `app.py`, causing `/reports` to return `404 Not Found`.

## v2.54.0 - First Run Setup Wizard

### Added

- Added `engine/setup_wizard.py` for read-only first-run readiness computation, progress scoring, guided step state, source summary, and safe next-action guidance.
- Added `/setup-wizard` page with a step-by-step onboarding checklist for LibreQoS paths, MikroTik routers, enabled PPPoE/DHCP/Hotspot sources, Network Layout mode, Smart Policy preset, Dry Run, and scheduler go-live.
- Added wizard actions to apply Conservative/Balanced/Aggressive Smart Policy presets directly from the wizard while reminding operators to run Dry Run afterward.
- Added wizard action to save Network Layout mode from the wizard, preserving legacy `flat_network` / `no_parent` compatibility flags.
- Added Setup Wizard navigation and cross-links between Setup Wizard, Setup & Repair, Config Center, Policy Center, Network Layout, Dry Run, and Dashboard.

### Notes

Setup Wizard is for first-run onboarding and go-live flow. Setup & Repair remains the diagnostics/repair center. About / Documentation remains the long-form manual source of truth.


## v2.53.0 - Client Lifecycle Timeline FULL

- Adds `engine/lifecycle_report.py` for read-only client lifecycle reports, filtering, per-client event timelines, cleanup queue visibility, confirmation history, recommendations, and export formatting.
- Upgrades `/lifecycle` into a Client Lifecycle Timeline Center with filters for status, source, search, and row limits.
- Adds active/stale/queued/removed/returned lifecycle visibility with source lifecycle status, cleanup queue, pending confirmations, selected-client detail, and recent event timeline.
- Adds `/api/lifecycle/report` and lifecycle exports for JSON, CSV, and Markdown.
- Keeps Privacy Mode support for client names, nodes, IPs, and MACs inside lifecycle tables and timelines.
- Adds documentation source `docs/content/client_lifecycle_timeline.md` and updates docs manifest, About module, README, full documentation, operator guide, release notes, and version metadata for v2.53.


## v2.52.0 - Smart Reports + Operator Audit FULL

- Adds `engine/reports.py` for read-only operator report generation from runtime state, policy state, audit events, services, backups, smart insights, policy decisions, cleanup decisions, and client changes.
- Adds `/reports` Smart Reports page with 24h summary cards, last run summary, policy decision report, cleanup report, recommendations, client change table, config/operator audit table, and JSON preview.
- Adds `/reports/export/json`, `/reports/export/csv`, and `/reports/export/markdown` for copy-ready operator reports.
- Adds `/api/reports/operator` for structured report consumption by UI/integrations.
- Adds Smart Reports navigation entry under History.
- Adds documentation source `docs/content/smart_reports_operator_audit.md` and updates docs manifest, About module, README, full documentation, operator guide, release notes, and version metadata for v2.52.


## v2.51.0 - Config Schema + Policy Simulation Engine FULL

- Adds `config_schema_version` and `config_validation` defaults to `config.json`.
- Adds `engine/config_schema.py` for versioned migration, schema validation, policy setting validation, and Config Health scoring.
- Adds `engine/config_diff.py` for safe saved-vs-proposed config diffing with sensitive value masking.
- Adds `engine/policy_simulator.py` for read-only policy-impact simulation based on unsaved Config Center changes and the latest runtime state.
- Adds `engine/config_simulator.py` to combine schema health, config diff, policy simulation, risk level, verdict, impacts, and recommendations.
- Adds `/config/simulate`, a read-only endpoint that previews unsaved Config Center changes without writing config.json, ShapedDevices.csv, network.json, or applying LibreQoS.
- Adds a Config Health / Simulation card in Config Center with Preview Impact, verdict, risk, changed fields, and first recommendation.
- Updates `config.json.example`, docs manifest, documentation, About module, release notes, and version metadata for v2.51.


## v2.50.0 - Policy-Aware Cleanup Intelligence FULL

- Adds optional source-aware stale lifecycle settings under `policies.stale_lifecycle`. Grace remains disabled by default per source and is intended only for stable identities such as PPPoE usernames or Hotspot vouchers.
- Adds cleanup queue seen-run tracking so `cleanup_next_run` and optional grace can wait for a configured number of consecutive missing runs before removal.
- Adds risk-aware LibreQoS auto-apply policy under `policies.auto_apply_policy`, allowing low-risk automatic applies while holding medium/high/critical changes pending for manual review by default.
- Adds policy decision trace entries to explain cleanup queueing, grace behavior, confirmation, and auto-apply risk decisions.
- Exposes the new v2.50 settings through the schema-driven Policy Center because `engine/policy_schema.py` powers the settings UI.
- Adds documentation source `docs/content/policy_aware_cleanup_intelligence.md` and updates the docs manifest.


## v2.49.0 - Policy Settings Integration FULL

- Adds `engine/policy_schema.py` as the single source of truth for visible Policy Center settings, allowed values, labels, descriptions, recommended defaults, and risk levels.
- Converts Smart Policy Center from read-mostly visibility into a real settings UI that writes directly to `config.json -> policies`.
- Adds editable Policy Center form groups for cleanup core, PPPoE/DHCP/Hotspot/static cleanup, mass-removal guards, apply guards, collector guards, data quality, topology, backup, anomaly detection, and recommendations.
- Adds preset actions for Conservative, Balanced, and Aggressive policies, plus manual edit behavior that saves as Custom.
- Adds current-vs-preset comparison, closest-preset detection, and policy difference display.
- Adds Policy Center integration inside Config Center so policy settings are visible and wired into the same settings workflow and raw JSON preview.
- Adds documentation centralization files under `docs/content/` and `docs/docs_manifest.json` so Setup & Repair can focus on diagnostics while About/Documentation remains the manual source of truth.
- Updates Setup & Repair wording to reduce duplication and link operators toward Documentation and Policy Center.

# LQoSync Release Notes

## v2.48.0 - Smart Setup / Repair Center

### Added

- Added Smart Setup / Repair Center at `/setup-repair`.
- Added setup/repair diagnostics through `engine/setup_repair.py`.
- Added readiness score, failed check count, warning count, and recommended next action.
- Added guided first-install checklist for LibreQoS path, MikroTik API user, routers, DHCP discovery, network layout, policy preset, Dry Run, and scheduler activation.
- Added safe repair command cards for preserve-existing reinstall, permission restore, environment doctor, safe GitHub update, GitHub adoption, and LibreQoS service checks.
- Added policy preset setup for Conservative, Balanced, and Aggressive Smart Policy modes.
- Added MikroTik connection-test workflow guidance without contacting routers during page load.

### Notes

The Setup / Repair Center is read-only by default. It gives commands and explanations instead of blindly repairing, restarting, updating, or applying from the browser.

## v2.47.0 - Smart Lifecycle

### Added

- Added Smart Lifecycle state tracking for active, stale, queued cleanup, removed, and returned clients.
- Added per-client event timeline stored in bounded runtime state.
- Added cleanup history and confirmation history for Smart Policy Center decisions.
- Added source lifecycle snapshots for PPP, DHCP, and Hotspot collectors.
- Added returned-client detection when a stale/queued client appears again before cleanup is applied.
- Added Lifecycle Center UI and Dashboard lifecycle summary.

### Notes

Smart Lifecycle uses `/opt/lqosync/state/policy_state.json`. It is runtime state and does not change operator config.

## v2.46.0 - Smart Insights

### Added

- Added Smart Insights as the operator guidance layer on top of Smart Policy Center.
- Added Data Quality score based on validation errors, collector errors, warnings, fallback-speed usage, and policy decision state.
- Added Backup Readiness checks for backup_before_apply and retention.
- Added Fallback Speed Review to identify clients using default/fallback speed sources.
- Added basic Anomaly Detection comparing current run against previous runtime state for sudden client-count drops and timing spikes.
- Added Recommendations panel with reason and next-action guidance.
- Added Why / Fix / Next explanations for common warnings such as fallback speeds, duplicate IPs, parent node issues, and collector/API problems.
- Added Smart Dry Run Insights so dry-run reports include the same operator guidance without writing files or applying LibreQoS.

### Notes

Smart Insights is rule-based and explanatory. It does not bypass Smart Policy Center; it uses policy decisions, preflight results, timings, and metadata to explain what happened and what the operator should do next.

## v2.45.0 - Smart Policy Center

### Added

- Added Smart Policy Center foundation with policy-driven cleanup and apply decisions.
- Added default policies for cleanup behavior, source lifecycle, collector guards, apply guards, mass-removal protection, small-node handling, backup readiness, topology safety, anomaly basics, and recommendations.
- Added runtime policy state at `/opt/lqosync/state/policy_state.json` for pending confirmations, cleanup queue, last successful source counts, and last policy decision.
- Added policy evaluation before file write and LibreQoS apply so dangerous output can be blocked before touching `ShapedDevices.csv` or `network.json`.
- Added Policy Center UI with current mode, last verdict, risk level, pending confirmations, source cleanup policy table, apply guards, collector guards, and runtime policy state viewer.
- Added Dry Run Policy Verdict and Dashboard Policy Decision panels.
- Added cleanup confirmation actions and audit events for confirmed/dismissed cleanup confirmations.

### Safety behavior

- Collector failures preserve rows and can block apply by policy.
- Enabled sources returning zero after previous success are protected from accidental mass deletion.
- Source-disabled cleanup can require confirmation before rows are removed.
- Duplicate IP, missing parent node, invalid speed, and collector failure can block write/apply through apply guards.
- Normal inactive cleanup can be immediate, queued for next run, confirmation-required, preserved, warn-only, blocked, or block apply depending on policy.

## v2.44.0 - Privacy Icon and Services Journal Layout Polish

### Improved

- Replaced the previous incognito-style Privacy Mode icon with a shield-and-eye redaction icon that better matches the purpose of masking visible subscriber, node, IP, MAC, circuit, and ID values for screenshots.
- Kept the slash overlay for Privacy Mode off and the active highlight for Privacy Mode on, while preserving browser-only redaction behavior.
- Refined Services & Journals so the Journal Viewer and LibreQoS Apply Logs use matching scroll-shell panels, equal desktop heights, cleaner card rhythm, and aligned scroll behavior.
- Improved the Journal Viewer container so the log output fills the available panel space instead of looking visually smaller than the LibreQoS Apply Logs column.

### Notes

These are UI/UX polish changes only. The core sync engine, MikroTik collectors, LibreQoS runner, generated files, and apply behavior are unchanged.

## v2.43.0 - UI Polish and Git Update Detection

### Improved

- Replaced the Privacy Mode topbar icon with an incognito-style operator icon and kept the slash indicator for privacy-off state.
- Polished the Services & Journals page with equal-height desktop panels, a larger Journal Viewer scroll area, sticky controls, cleaner LibreQoS apply-log cards, and responsive stacked layout on smaller screens.
- Improved Update Center accuracy by fetching `origin/main` before comparison when the page is opened, then comparing local HEAD against the latest fetched remote commit.
- Added remote VERSION detection using `origin/main:VERSION`, so the UI can show Installed Version vs GitHub Version and flag updates even when the local cached status previously appeared up to date.
- Added clearer fetch status, local/remote commit cards, update-needed indication, and refresh guidance.

### Notes

Update Center remains read-only. It checks GitHub status and shows safe SSH commands, but it does not execute `git pull`, reset, or upgrade actions from the browser.

## v2.42.0 - Privacy UX + Topology Save Fix

### Improved

- Increased the Network Layout Topology Tree width and reduced Visual Topology proportionally so node names, hierarchy depth, and badges are easier to read on desktop screens.
- Kept the Node Inspector at a stable width while letting the Visual Topology area absorb the width adjustment.
- Replaced text-based topbar theme/privacy controls with compact icon-only controls: sun for light mode, moon for dark mode, and mask/mask-with-slash for Privacy Mode.
- Improved Privacy Mode from blur-style masking to stable replacement labels such as `Client-001`, `Router-001`, `Node-001`, `IP-001`, `MAC-001`, `Circuit-001`, and `ID-001`.
- Added a global CSRF token meta tag and JSON fetch helper for protected browser-side write actions.
- Updated Network Layout save to send the CSRF token with AJAX requests and show a clearer explanation when a stale or missing token blocks the save.

### Notes

Privacy Mode remains browser-only redaction for screenshots and demos. It does not modify `config.json`, `ShapedDevices.csv`, `network.json`, logs, or any source data.

# Release Notes

## v2.41.0 — Topology UX and Privacy Mode

- Redesigned Network Layout into a topology-builder style UI with layout mode cards, topology tree, visual nested node cards, and Node Inspector.
- Added promote, move, delete, edit, virtual-node toggle, impact preview, and validation before saving `network.json`.
- Added deep/custom hierarchy support concepts, including `router.parent_node` so routers can be nested under upstream/core/site nodes while generated child nodes remain under their owning router.
- Added WebUI Privacy / Redaction Mode in the top navigation for screenshots and demos. It masks visible identifiers in the browser only and does not modify source files.
- Updated About module and repository documentation with topology modes, virtual nodes, deep hierarchy behavior, validation rules, and privacy-mode guidance.

# v2.40.0 - Operator Experience Polish

- Added a Dashboard health summary banner that explains healthy/warning/error/pending-apply states in operator-friendly language.
- Added Dashboard “What changed last sync?” and Apply Decision explanation panels.
- Added Config Center change preview and save confirmation for important settings such as scheduler, apply policy, collector settings, network mode, and router/source settings.
- Added Safe Simulation Report to Dry Run Preview with risk-check style status for duplicate IPs, parent nodes, invalid speeds, and explicit dry-run no-apply behavior.
- Added Update Center with read-only Git status, branch/commit relation, diverged-history guidance, safe update commands, and adoption commands for ZIP/manual installs.
- Added mobile card mode for Shaped Devices so phones can inspect clients without relying only on a wide table.
- Updated About module and repository documentation with the v2.40 operator-experience model.

# Release Notes

## v2.39.0 - Operations Dashboard UX

- Expanded the Dashboard into a production operations cockpit focused on health, apply decisions, source status, timing, cleanup safety, client changes, and Git/update visibility.
- Added Apply Decision explanation so operators can see why LibreQoS ran, skipped, retried a pending failed apply, was forced, or was blocked by dry-run/auto-apply policy.
- Added Performance Breakdown with MikroTik API time, build/diff time, file write time, and LibreQoS apply time.
- Added Data Source Status cards for PPPoE, DHCP, and Hotspot collector counts, metadata read stats, generated rows, and timing.
- Added Cleanup Safety visibility for source-aware cleanup and removed row counts.
- Added Recent Client Change Feed on the Dashboard with client, speed, parent node, speed source, and changed fields.
- Added Generated Files and Drift Policy card for CSV/network change state, backup setting, and file drift policy.
- Added Version/Git Status card showing branch, commit, dirty state, and upstream relation such as up-to-date, behind, ahead, or diverged.
- Updated the About module and documentation to describe the new operator dashboard model.


## v2.38.0 - Selective MikroTik Collection

- Added selective RouterOS field reads for PPPoE, DHCP, and Hotspot collectors.
- Added universal speed resolver with explicit speed-source labels and raw source values.
- Updated PPPoE speed priority: secret comment, active comment, profile comment, profile name, profile rate-limit, default.
- Updated DHCP speed priority: DHCP server comment/speed_comment, DHCP server name, server config speed, global default.
- Added Hotspot enhanced metadata reads from `/ip/hotspot/user` and `/ip/hotspot/user/profile`.
- Added metadata cache state file at `/opt/lqosync/state/collector_cache.json`.
- Added source-aware cleanup so stale rows are removed only for successfully scanned sources.
- Added Dashboard collector monitoring, cache efficiency, speed source breakdown, and richer Last Sync Timeline details.
- Added Config Center Collector Settings module and updated About module documentation.


## v2.37.0 - About Module Documentation Expansion

- Expanded the in-app **About LQoSync** module into a complete operator manual while retaining the existing dashboard-style UI/UX design.
- Added detailed About sections for project purpose, sync workflow, LibreQoS apply policy, feature modules, network layout modes, fresh installation, existing install adoption, GitHub updates, uninstall and permission restore, MikroTik setup, important paths, commands, and troubleshooting.
- Added atomic troubleshooting explanations with expected outcomes for common production issues: wrong LibreQoS working directory, `nsenter` on bare-metal, temp-file permission errors, pending apply retry, false service status, blank `/var/log` output, non-Git installations, port conflicts, and validation failures.
- Added `docs/ABOUT_MODULE_OPERATOR_GUIDE.md` as the Markdown source companion for the About module.
- Updated repository documentation guidance so every meaningful project change should update both repo docs and `templates/about.html`.

## v2.34.0 - Bounded Table Views

## v2.35.0 - GitHub source installer and smart updater

- Added `install-from-github.sh` for direct GitHub-based bare-metal installation without requiring GitHub CLI.
- Reworked `upgrade.sh` into a smart Git updater with policies: `pull_only`, `code_only`, `preserve_and_migrate`, `refresh_with_backup`, and `factory_reset`.
- Default update policy is production-safe: preserve live `config.json`, `users.json`, `ShapedDevices.csv`, `network.json`, `.env`, state, and logs while pulling source code and running safe config migration.
- Added Git conversion support for systems previously installed from ZIP/manual copy; runtime files are backed up and preserved while the install directory becomes Git-managed.
- Added `docs/GITHUB_INSTALL.md` and expanded installation/manual documentation for GitHub source install, Git updates, preservation policies, and no-`gh` requirements.

- Added row-limit controls to Logs & Backups → Audit Events so large audit logs do not overflow the page.
- Added selectable table limits: 25, 50, 100, 200, 300, 400, and 500 visible lines.
- Added the same bounded table view control to Shaped Devices.
- Counts now show visible rows, filtered rows, and total rows so operators know when results are limited.
- Filters and sorting still apply to the full dataset; only the rendered visible rows are capped by the selected view size.

## v2.33.0 - Audit Events Table and Dashboard Client Change Timeline

- Added operator-friendly client change summaries for each sync cycle.
- Audit events now include affected clients, speeds, parent nodes, source type, changed fields, and elapsed timings when file changes occur.
- Logs & Backups now renders Audit Events as a searchable/filterable table similar to the Shaped Devices table.
- Dashboard Last Sync Timeline now shows client-change info bits so operators can immediately see who changed, what speed, and which parent node was affected.
- Added a reusable change-summary builder that converts raw ShapedDevices.csv diffs into UI/audit-friendly records.

# Release Notes

## v2.32.0 - MikroTik Setup Requirement Notice

- Added a dedicated MikroTik setup requirement notice for fresh installations.
- Added recommended RouterOS terminal commands for creating a restricted `API_READ` group and `libreqosyncAPI` user.
- Updated bare-metal and Docker installers to print the MikroTik API setup notice when a fresh LibreQoS file set is detected.
- Added `docs/MIKROTIK_SETUP.md` and surfaced the same guidance in README, installation manuals, command docs, and the in-app About module.
- Clarified terminology: this is an **Important Notice** / **Setup Requirement**, not a generic warning.

## v2.31.0 - Smart Fresh Install File Initialization

- Added smart install initialization for fresh LibreQoS systems where `/opt/libreqos/src/config.json`, `ShapedDevices.csv`, and `network.json` do not exist yet.
- Installer now creates missing managed files dynamically from bundled templates.
- Existing live LibreQoS files are no longer overwritten by default in smart mode; interactive bare-metal installs ask the operator to preserve, overwrite with backup, create missing only, or abort.
- Non-interactive installs preserve existing files unless `LQOSYNC_INIT_POLICY=overwrite_with_backup` is explicitly set.
- Docker entrypoint now uses the same smart policy, preserving existing mounted LibreQoS files by default while creating missing files on fresh systems.
- Documentation updated with fresh install behavior, init-policy options, and production-safe recommendations.


## v2.30.0 - Uninstall Permission Restore

- Added `uninstall.sh` for safer bare-metal removal.
- Added `scripts/restore_libreqos_permissions.sh` to restore LibreQoS-managed paths after LQoSync uninstall.
- Bare-metal uninstall now documents how to remove LQoSync ACL entries and return `/opt/libreqos/src` plus managed files to `root:root`.
- Added conservative default restore mode for managed files only: `config.json`, `ShapedDevices.csv`, and `network.json`.
- Added optional full restore mode for operators who intentionally want to run `chown -R root:root /opt/libreqos/src`.
- Updated troubleshooting notes for stale ACLs, root ownership restoration, and manual uninstall verification.

## v2.29.0 - Mobile-responsive UI

- Improves the LQoSync interface for phones and tablets.
- Adds a mobile navigation drawer with backdrop and touch-friendly menu button.
- Stacks dashboard cards, service panels, network cards, Config Center sections, and detail panels on narrow screens.
- Keeps large data tables usable with horizontal swipe scrolling and responsive hints.
- Improves Config Center mobile navigation with horizontally scrollable module tabs.
- Preserves the desktop dashboard-style UI while making the app easier to operate from mobile devices.

## v2.28.0 - Legacy LibreQoS Service Labeling

- Treats `lqos_node_manager` as a legacy/optional LibreQoS Web UI service instead of a required service.
- Fresh `config.json.example` now uses `lqosd`, `lqos_scheduler`, and `lqosync` as primary units.
- Adds `services.legacy_optional_units`, `services.unit_metadata`, and `services.show_legacy_optional_not_installed`.
- Services & Journals now auto-hides missing legacy optional services by default and labels them clearly when shown.
- Config Center now has a Service Monitor Settings section for service units, legacy optional units, journal defaults, and restart groups.
- Documentation updated to clarify that the main LibreQoS status command is `sudo systemctl status lqosd lqos_scheduler`.


## v2.27.0 - LibreQoS working-directory enforcement

- Enforces `libreqos.working_dir` during every LibreQoS apply run so `LibreQoS.py --updateonly` always executes from `/opt/libreqos/src` in bare-metal direct mode.
- Falls back to the directory containing the configured `LibreQoS.py` command when `working_dir` is missing.
- Adds clearer apply metadata with the effective working directory and an early validation error if the directory is invalid.
- Resolves bare-metal apply failures where LibreQoS reported `FileNotFoundError: ShapedDevices.csv` because it was launched from `/opt/lqosync` or another directory instead of `/opt/libreqos/src`.


## v2.26.0 - Config Example Hardening and Startup Migration

- Hardened `config.json.example`, the template used by fresh installations, so it explicitly contains the production-safe LibreQoS apply defaults:
  - `libreqos.working_dir=/opt/libreqos/src`
  - `libreqos.retry_if_last_apply_failed=true`
  - `libreqos.run_mode=direct`
  - `libreqos.sudo=true`
  - absolute `/opt/lqosync` runtime paths.
- Added startup config normalization in `app.py`. This persists missing safe defaults even when an operator updates by `git pull` and restarts the service without running `install.sh`.
- Strengthened bare-metal detection in `engine/config_loader.py` so Docker-only `host_nsenter` cannot survive on systemd/bare-metal installs.
- Added `scripts/validate_config_example.py` to verify the fresh-install template contains mandatory production defaults.
- Keeps Docker support available, but prioritizes bare-metal/systemd as the default production deployment.

# LQoSync Release Notes

## v2.48.0 - Smart Setup / Repair Center

### Added

- Added Smart Setup / Repair Center at `/setup-repair`.
- Added setup/repair diagnostics through `engine/setup_repair.py`.
- Added readiness score, failed check count, warning count, and recommended next action.
- Added guided first-install checklist for LibreQoS path, MikroTik API user, routers, DHCP discovery, network layout, policy preset, Dry Run, and scheduler activation.
- Added safe repair command cards for preserve-existing reinstall, permission restore, environment doctor, safe GitHub update, GitHub adoption, and LibreQoS service checks.
- Added policy preset setup for Conservative, Balanced, and Aggressive Smart Policy modes.
- Added MikroTik connection-test workflow guidance without contacting routers during page load.

### Notes

The Setup / Repair Center is read-only by default. It gives commands and explanations instead of blindly repairing, restarting, updating, or applying from the browser.

## v2.25.0 - Bare-metal direct runner enforcement

- Prioritizes bare-metal/systemd installation as the default production path.
- Forces `libreqos.run_mode=direct` and `libreqos.sudo=true` during bare-metal install/update migration.
- Ensures `libreqos.working_dir=/opt/libreqos/src` and `libreqos.retry_if_last_apply_failed=true` remain present in live `config.json`.
- Normalizes `/opt/lqosync/.env` during bare-metal install/update so old Docker/nsenter values cannot survive upgrades.
- Protects service status and journal viewers from using `nsenter` on bare-metal systems.
- Prevents the bare-metal error `nsenter: cannot open /proc/1/ns/ipc: Permission denied`.
- Keeps Docker host-integrated mode available only through Docker environment variables and compose settings.


## v2.23.0 - Config migration included in install/update

- Added `scripts/migrate_config.py` to persist newly introduced config defaults into existing `/opt/libreqos/src/config.json` during upgrades.
- Bare-metal `install.sh` now normalizes existing config even when `LQOSYNC_INIT_POLICY=preserve_existing` is used. This means `libreqos.working_dir=/opt/libreqos/src` and `libreqos.retry_if_last_apply_failed=true` are added automatically instead of requiring manual JSON edits.
- Docker `docker-entrypoint.sh` now performs the same safe config migration on startup while preserving operator settings.
- Re-applies config ownership/permissions after atomic config migration so the `lqosync` service user can continue writing temp files safely.

# Release Notes

## v2.22.0 - LibreQoS apply retry and scheduler auto-apply policy

- Added `libreqos.working_dir` with default `/opt/libreqos/src` so `LibreQoS.py --updateonly` runs from the same directory used by manual LibreQoS execution. This fixes relative-file issues such as `ShapedDevices.lastLoaded.csv` lookups.
- Added `libreqos.retry_if_last_apply_failed=true` so LQoSync retries LibreQoS apply on the next non-dry-run cycle when files were already written but LibreQoS.py failed.
- Added pending LibreQoS apply state fields in `runtime_state.json`: `pending_libreqos_apply`, `last_libreqos_apply_failed`, `last_libreqos_apply_success`, `last_libreqos_apply_reason`, and `last_libreqos_exit_code`.
- Added Force LibreQoS Apply action in Services & Journals for applying current LibreQoS files without waiting for a new file diff.
- Updated Dashboard behavior: when scheduler auto-apply is active, manual Run Sync Now is disabled to avoid overlapping operator-triggered applies. Dry Run remains available for preview.
- Improved live status behavior by marking manual jobs queued/running immediately so dashboard/API polling reflects state changes on the fly.
- Documented the production apply policy: dry-run never applies; non-dry-run file writes automatically trigger LibreQoS; failed applies remain pending until successfully retried.

# LQoSync Release Notes

## v2.48.0 - Smart Setup / Repair Center

### Added

- Added Smart Setup / Repair Center at `/setup-repair`.
- Added setup/repair diagnostics through `engine/setup_repair.py`.
- Added readiness score, failed check count, warning count, and recommended next action.
- Added guided first-install checklist for LibreQoS path, MikroTik API user, routers, DHCP discovery, network layout, policy preset, Dry Run, and scheduler activation.
- Added safe repair command cards for preserve-existing reinstall, permission restore, environment doctor, safe GitHub update, GitHub adoption, and LibreQoS service checks.
- Added policy preset setup for Conservative, Balanced, and Aggressive Smart Policy modes.
- Added MikroTik connection-test workflow guidance without contacting routers during page load.

### Notes

The Setup / Repair Center is read-only by default. It gives commands and explanations instead of blindly repairing, restarting, updating, or applying from the browser.

LQoSync is a database-free LibreQoS companion dashboard and sync engine. It reads live MikroTik PPPoE, DHCP, and Hotspot data, generates LibreQoS-compatible `ShapedDevices.csv` and `network.json`, and calls `LibreQoS.py --updateonly` only when generated files change.

---

## v2.21.0 - Release Notes Maintenance

Documentation-only release.

- Rebuilt `RELEASE_NOTES.md` into a clean, chronological, up-to-date changelog.
- Consolidated duplicate headings from earlier documentation updates.
- Added all major releases from early prototype through the current ACL installer hardening release.
- Clarified which releases changed runtime behavior, installer behavior, UI/UX, documentation, and service monitoring.
- No sync engine behavior change.
- No database added.
- No MikroTik write behavior added.

---

## v2.20.0 - Installer ACL + Permission Troubleshooting

- Added automatic ACL installation and permission setup to the bare-metal installer.
- Bare-metal `install.sh` now installs the `acl` package when needed.
- Bare-metal installer now grants the `lqosync` service user write access to `/opt/libreqos/src` and the managed LibreQoS files:
  - `/opt/libreqos/src/config.json`
  - `/opt/libreqos/src/ShapedDevices.csv`
  - `/opt/libreqos/src/network.json`
- Added default ACL support for future temporary files created during atomic writes.
- Added a permission smoke test for `.tmp` file creation inside `/opt/libreqos/src`.
- Added troubleshooting documentation for this common error:

```text
Permission denied: /opt/libreqos/src/config.json.tmp
```

- Updated manuals with manual ACL repair commands and verification steps.

---

## v2.19.0 - Browser Tab Favicon

- Added a browser tab icon, technically called a favicon.
- Added SVG favicon, ICO fallback, PNG icons, mobile touch icons, Android icons, and web manifest.
- Wired favicon links into:
  - `templates/base.html`
  - `templates/login.html`
- Browser tab, bookmarks, and supported mobile shortcuts now show the LQoSync icon.

---

## v2.18.0 - Uninstall + Git Documentation

- Added `UNINSTALLATION.md`.
- Added `GIT_INSTALL.md`.
- Documented Docker uninstall.
- Documented bare-metal uninstall.
- Documented Git-source folder cleanup.
- Documented `/opt/lqosync` backup/removal.
- Documented systemd service removal.
- Documented sudoers cleanup.
- Documented ACL cleanup for `/opt/libreqos/src`.
- Documented how to restore the old `updatecsv.service`.
- Added Git clone installation instructions.
- Added Docker install from GitHub.
- Added bare-metal install from GitHub.
- Added Git update steps.
- Added Git upload safety notes.
- Updated:
  - `README.md`
  - `INSTALLATION.md`
  - `DOCKER_INSTALL.md`
  - `BARE_METAL_INSTALL.md`
  - `FULL_DOCUMENTATION.md`
  - `docs/COMMANDS.md`
- Added or updated `.gitignore` rules to avoid committing live runtime files and secrets.

---

## v2.17.0 - `/opt/lqosync` Install Path

- Changed LQoSync application/runtime install path from `/opt/lqosync` to:

```text
/opt/lqosync
```

- Keeps LQoSync beside LibreQoS in `/opt`:

```text
/opt/libreqos
/opt/lqosync
```

- Docker persistent runtime volume now maps:

```text
/opt/lqosync:/opt/lqosync
```

- Bare-metal installer now installs app files, `users.json`, state, logs, backups, and config backups under `/opt/lqosync`.
- LibreQoS-managed files remain under `/opt/libreqos/src`:
  - `config.json`
  - `ShapedDevices.csv`
  - `network.json`
- Service/container name remains `lqosync` for compatibility.
- Updated documentation, commands, About page, Dockerfile, compose files, and installer scripts.

---

## v2.16.0 - Default Web Port 9202

- Changed default LQoSync web UI port from `5050` to `9202`.
- Updated:
  - `.env.example`
  - `Dockerfile`
  - `compose.yaml`
  - `app.py` default port handling
  - `install.sh`
  - `README.md`
  - `DOCKER_INSTALL.md`
  - `BARE_METAL_INSTALL.md`
  - `INSTALLATION.md`
  - `docs/COMMANDS.md`
- New default UI URL:

```text
http://<server-ip>:9202
```

---

## v2.15.0 - About Module

- Added About module at:

```text
/about
```

- Added Help/About navigation in the UI.
- Added operator-friendly web documentation page with:
  - Project Description
  - Process Workflow
  - Features and Modules
  - Network Layout Modes
  - Docker Installation Guide
  - Bare-metal Ubuntu Installation Guide
  - Project Requirements
  - Important Paths
  - Operator Commands
  - Notes and Safety Model
- About page is light/dark theme compatible.
- About page is designed as an easy-to-read in-app operator reference.

---

## v2.14.0 - README Documentation Expansion

- Expanded `README.md` into a full granular project manual.
- Added project purpose, mental model, and GitHub project description.
- Added detailed Docker installation instructions.
- Added detailed bare-metal Ubuntu/systemd installation instructions.
- Added update, uninstall, troubleshooting, and operator commands.
- Added feature documentation for:
  - Dashboard
  - Dry Run Preview
  - Config Center
  - Network Layout
  - Shaped Devices
  - Services & Journals
  - User Settings
- Added detailed sync engine workflow.
- Added PPPoE, DHCP, and Hotspot logic explanation.
- Added network mode documentation for:
  - `router_children`
  - `flat_router_root`
  - `flat_no_parent`
- Added security model and performance notes.

---

## v2.13.0 - Shaped Devices Column Filters

- Added per-column filters to the Shaped Devices table.
- Added filters for:
  - Circuit Name
  - Type
  - Parent Node
  - IPv4
  - Download Max
  - Upload Max
  - Download Min
  - Upload Min
  - MAC
  - Speed Source
  - Status
- Every visible table header is now sortable.
- Global search remains available.
- PPP/DHCP/Hotspot/Static/Duplicate IP filter chips remain available.
- Column filters can be combined with global search and type/status chips.

---

## v2.12.0 - User Settings UI

- Added Settings → User Settings page.
- Added JSON-backed user management using `users.json`.
- Added admin-only UI features:
  - Add user
  - Edit username
  - Change role: `admin` or `viewer`
  - Change password
  - Delete user
- Passwords are stored only as bcrypt hashes.
- Added safety protections:
  - Cannot delete currently logged-in user.
  - Cannot delete the last admin.
  - Cannot demote the last admin.
  - Passwords are never displayed in the UI.
  - `users.json` is written atomically.
- Added audit logs for user changes.

---

## v2.11.0 - Documentation Command Fix

- Added `docs/COMMANDS.md`.
- Updated Docker password reset command to explicitly target:

```text
/opt/lqosync/users.json
```

- Updated bare-metal password reset command.
- Added command reference for:
  - Docker status/logs/rebuild
  - Docker password reset
  - Bare-metal service commands
  - Bare-metal password reset
  - LibreQoS service status
  - LibreQoS grouped restart
  - Manual `LibreQoS.py --updateonly` apply

---

## v2.10.0 - Status Helper Fix

- Fixed runtime dashboard error:

```text
NameError: name 'get_status' is not defined
```

- Added missing `get_status()` helper.
- Dashboard route now loads `config.json` and `runtime_state.json` correctly.
- Network, layout, devices, services, and API status routes now use the same status helper.

---

## v2.9.0 - Auth Boot Fix

- Fixed Gunicorn worker boot failure caused by missing auth helpers.
- Restored missing `login_required` decorator.
- Restored missing `admin_required` decorator.
- Restored `current_user()` helper.
- Restored CSRF helper wiring.
- Fixed error:

```text
NameError: name 'login_required' is not defined
```

---

## v2.8.0 - LibreQoS Service Unit Fix

- Corrected LibreQoS service unit names.
- Correct service status command:

```bash
sudo systemctl status lqosd lqos_scheduler
```

- Correct grouped restart command:

```bash
sudo systemctl restart lqosd lqos_scheduler
```

- Updated default service units:
  - `lqosd`
  - `lqos_scheduler`
  - `lqos_node_manager`
  - `lqosync`
- Added migration normalization for older names like `lqos` or `lqosd_scheduler`.

---

## v2.7.0 - Services, Journals, and Timing Metrics

- Added Services & Journals page.
- Added service status cards for LQoSync and LibreQoS-related units.
- Added journal viewer per service.
- Added restart button per allowlisted service.
- Added LibreQoS grouped restart action:

```bash
sudo systemctl restart lqosd lqos_scheduler
```

- Added configurable `services` section in `config.json`:
  - `services.units`
  - `services.restart_groups`
  - `services.journal_lines_default`
- Added `LibreQoS.py --updateonly` apply log history.
- Apply log captures:
  - stdout
  - stderr
  - exit code
  - elapsed time
  - command metadata
- Added elapsed-time metrics per sync cycle for:
  - config load
  - CSV read/parse
  - `network.json` read/parse
  - MikroTik connect
  - PPPoE process
  - DHCP process
  - Hotspot process
  - cleanup
  - CSV render
  - network render
  - diff
  - backup
  - CSV write
  - network write
  - LibreQoS apply
  - full cycle total
- Added performance timing cards to the dashboard.
- Added last-cycle process timeline.

---

## v2.6.0 - Network Layout Modes

- Added `network_mode` to `config.json`.
- Added Config Center dropdown for Network Layout Mode.
- Added automatic config normalization:

| Mode | `flat_network` | `no_parent` |
|---|---:|---:|
| `router_children` | false | false |
| `flat_router_root` | true | false |
| `flat_no_parent` | true | true |

- Added support for three output layouts:
  - `router_children`: router root + PPPoE/DHCP/Hotspot child nodes.
  - `flat_router_root`: all generated devices use router name as Parent Node.
  - `flat_no_parent`: generated devices have blank Parent Node and `network.json` can be empty.
- Engine now changes Parent Node behavior based on selected network mode.
- `network.json` builder now follows selected network mode.
- Preflight allows blank Parent Node only in `flat_no_parent` mode.
- Dry-run can preview network mode changes.
- Documentation updated for all three modes.

---

## v2.5.0 - Shaped Devices Light Mode Detail Fix

- Fixed selected device detail panel header in Shaped Devices page.
- Removed hardcoded dark styling from the detail panel header.
- Detail panel header now follows theme variables in both light and dark modes.

---

## v2.4.0 - Documentation + Bare-Metal Installation

- Added complete documentation package.
- Added bare-metal Ubuntu/systemd installation path.
- Added:
  - `FULL_DOCUMENTATION.md`
  - `INSTALLATION.md`
  - `DOCKER_INSTALL.md`
  - `BARE_METAL_INSTALL.md`
  - `README.md`
  - `install.sh`
  - `install-baremetal.sh`
- Docker and bare-metal installation are both supported.
- Added safe installation notes for production LibreQoS files.

---

## v2.3.0 - UI Polish + Advanced Network JSON View

- Fixed Config Center light-mode styling.
- Config Center panels, inputs, raw JSON preview, modals, tabs, and warnings now follow light theme properly.
- Added Advanced JSON View button to Network Layout filter row.
- Network Layout page can now show read-only `network.json` output.
- Added Copy JSON button.
- Renamed Shaped Devices table column from `Source` to `Speed source` to avoid confusion.

---

## v2.2.0 - Light/Dark Theme Switch

- Added Light/Dark mode switch in the topbar.
- Added Light/Dark mode switch on login page.
- Set Light mode as the default theme.
- Theme preference is saved in browser `localStorage`.
- Added config value:

```json
"ui": {
  "default_theme": "light"
}
```

---

## v2.1.0 - Core Parity Docker

- Aligned Docker-ready engine with the real production `updatecsv.py` workflow.
- DHCP lease handling now follows the original script behavior:
  - match DHCP server name
  - require `mac-address`
  - require `active-address` or `address`
  - do not require `status=bound`
- Default Docker config template now matches the real production model:
  - router-as-root: `RB5k9-Distro`
  - PPPoE `per_plan_node=true`
  - Tier-15M factor `0.31`
  - DHCP-LAN factor `0.3`
  - LibreQoEMgt included by default
  - Wifi5Soft included by default
- Added backward-compatible config handling:
  - `flat_network`
  - `no_parent`
  - `preserve_network_config`
  - old `download_limit_mbps` / `upload_limit_mbps`
  - new `default_plan_down_mbps` / `default_plan_up_mbps`

---

## v2.0.0 - Docker Ready

- Added Docker support.
- Added:
  - `Dockerfile`
  - `compose.yaml`
  - `compose.preserve-existing.yaml`
  - `docker-entrypoint.sh`
  - `DOCKER_INSTALL.md`
- Docker deployment uses host integration because LQoSync must:
  - write `/opt/libreqos/src/config.json`
  - write `/opt/libreqos/src/ShapedDevices.csv`
  - write `/opt/libreqos/src/network.json`
  - call host LibreQoS apply command
- Added init policy support:
  - `overwrite_with_backup`
  - `preserve_existing`
  - `create_missing_only`
- Added Docker install and operation guide.

---

## v1.9.0 - Fully Wired UI

- Dashboard buttons wired to backend actions:
  - Run Sync Now
  - Dry Run
  - Enable Scheduler
  - Disable Scheduler
  - Pause Scheduler
  - Resume Scheduler
  - Service restart buttons
- Dry-run page wired to:
  - Run dry-run
  - Run fresh apply
  - Show CSV diff
  - Show network diff
  - Show bandwidth math
  - Show warnings/errors
- Logs & Backups page wired to:
  - Download log
  - Restore backup
  - View audit JSON
  - View latest log lines
- Added API endpoints for sync, scheduler, backups, services, and status.

---

## v1.8.0 - UI Facelift

- Added enterprise-style app shell.
- Added topbar and sidebar.
- Improved dashboard cards.
- Improved service/status indicators.
- Improved Network Layout page with router-as-root cards, node badges, bandwidth bars, and math display.
- Improved Shaped Devices page with searchable/filterable table, badges, duplicate IP display, and detail panel.

---

## v1.7.0 - Route-Safe Config Actions

- Fixed Config UI action URL issue that generated paths like:

```text
/config/router//test
```

- Added safer endpoints:
  - `/config/router/test-current`
  - `/config/router/discover-dhcp-current`
- Router index is now submitted as hidden POST field.
- Backend now validates missing routers, invalid router index, and out-of-range router index.
- Kept older indexed routes for compatibility.

---

## v1.6.0 - Installer Init Policy

- Installer now checks for existing LibreQoS files in:
  - `/opt/libreqos/src/config.json`
  - `/opt/libreqos/src/ShapedDevices.csv`
  - `/opt/libreqos/src/network.json`
- Added init policy options:
  - `overwrite_with_backup`
  - `preserve_existing`
  - `create_missing_only`
- Added install backup directory.
- Added templates:
  - `config.json.example`
  - `ShapedDevices.csv.example`
  - `network.json.example`

---

## v1.5.0 - Config Path Alignment

- Changed default `CONFIG_PATH` to:

```text
/opt/libreqos/src/config.json
```

- Aligned config location with LibreQoS source directory.
- Updated install script, app fallback, config loader fallback, doctor script, upgrade script, and documentation.
- Final path convention established:
  - `/opt/libreqos/src/config.json`
  - `/opt/libreqos/src/ShapedDevices.csv`
  - `/opt/libreqos/src/network.json`

---

## v1.4.0 - Enterprise UI Sync

- Fixed mismatch between Router Settings UI and Advanced Raw JSON.
- Router settings UI and Advanced Raw JSON now mirror each other explicitly.
- Added Selected Router JSON Mirror panel.
- Router API test can now use current unsaved UI JSON payload.
- DHCP discovery can now use current UI JSON.
- Added client-side config normalization for nested router/PPPoE/DHCP/Hotspot fields.
- Added missing config controls:
  - `app.dry_run_default`
  - `scheduler.max_instances`
  - `libreqos.sudo`

---

## v1.3.0 - Enterprise Config UI

- Added full Config Center UI.
- Added UI-backed editor for `config.json`.
- Added live Advanced Raw JSON preview.
- Added editable raw JSON modal.
- Added router editor.
- Added PPPoE editor.
- Added DHCP editor.
- Added Hotspot editor.
- Added live node preview.
- Improved base UI and layout.

---

## v1.2.0 - Enterprise Hardened

- Added inter-process lock.
- Fixed Gunicorn deployment to use one worker to avoid multiple embedded schedulers.
- Added CSRF protection.
- Added structured audit log.
- Added config backup before every config save.
- Added Audit Events table.
- Added operator scripts:
  - `scripts/doctor.py`
  - `scripts/set_password.py`
- Added install hardening.
- Added config additions:
  - `paths.lock_file`
  - `paths.audit_log`

---

## v1.1.0 - Enterprise Improvements

- Improved scheduler lock handling.
- Added `next_run_at` runtime display.
- Added file drift detection.
- Added node math metadata.
- Added DHCP discovery from MikroTik.
- Added Router API test button.
- Improved rollback safety.
- Added backup retention.
- Added config validation before saving.
- Switched production service to Gunicorn.
- Added download buttons for current `ShapedDevices.csv` and `network.json`.
- Improved dashboard, dry-run, network layout, and shaped devices UI.

---

## v1.0.0 - Full System

- First full system package.
- Added database-free config-driven engine.
- Added Flask + Jinja + Tailwind UI.
- Added bcrypt-backed `users.json` login.
- Added scheduler enable/disable.
- Added manual sync.
- Added dry-run preview.
- Added Network Layout viewer.
- Added Shaped Devices viewer.
- Added Config editor.
- Added DHCP include/exclude toggle.
- Added Logs/Backups page.
- Added atomic writes.
- Added backup before apply.
- Added rollback from UI.
- Added `LibreQoS.py --updateonly` runner.
- Added read-only MikroTik collector layer.
- Added offline self-test script.
- Added install script and systemd service installer.

---

## v0.1.0 - Initial Scaffold

- First working scaffold/prototype.
- Added standalone LQoSync project structure.
- Added Flask + Jinja basic dashboard.
- Added config-driven no-database model.
- Added early scheduler thread.
- Added early manual sync and dry-run preview.
- Added early MikroTik collectors and PPPoE/DHCP/Hotspot processors.
- Added early CSV/network builders.
- Added early backup and LibreQoS apply runner.
- Added initial installer and systemd service template.

---

## Core Design That Remains True Across Releases

- No database.
- MikroTik is read-only.
- `config.json` is the persistent configuration source.
- `users.json` stores local web UI users with bcrypt password hashes.
- LQoSync writes LibreQoS-compatible:
  - `ShapedDevices.csv`
  - `network.json`
- LQoSync calls:

```bash
sudo /opt/libreqos/src/LibreQoS.py --updateonly
```

- LibreQoS remains the actual shaping applier.
- LQoSync does not replace LibreQoS.
- LQoSync is not a billing system, CRM, or ISP Manager.

## v2.24.0 - Config Center UX and Apply Config Wiring

- Reworked Config Center into a cleaner dashboard-style control plane with professional card layout, left-side module navigation, status summaries, and live raw JSON mirror.
- Added a dedicated Apply Policy section for LibreQoS command, arguments, working directory, run mode, sudo, timeout, run-on-change behavior, and failed-apply retry.
- Ensured the UI always wires `libreqos.working_dir=/opt/libreqos/src` and `libreqos.retry_if_last_apply_failed=true` into the saved `config.json`.
- Improved config migration so live installs normalize relative runtime paths to `/opt/lqosync` and LibreQoS file paths to `/opt/libreqos/src` without overwriting operator router settings.
- Kept dry-run safe: dry-run never writes files and never applies LibreQoS; scheduled/manual non-dry-run applies changes immediately when files change.
## v2.36.0 - Smart Existing Install Adoption

Added production-safe existing installation handling for GitHub-source installs.

### Added

- `install-from-github.sh` now detects existing LQoSync installations regardless of whether they came from ZIP, manual copy, Git clone, Docker leftovers, bare-metal installs, or partial/broken installs.
- Interactive action menu when an existing install is detected:
  - Adopt and update existing install
  - Update code only
  - Repair install, preserve all data
  - Backup and replace app files
  - Remove existing LQoSync then fresh install
  - Abort
- Non-interactive action support using `EXISTING_INSTALL_ACTION`:
  - `adopt`
  - `code_only`
  - `repair`
  - `replace_app`
  - `remove_fresh`
  - `abort`
- Safety backup for local runtime/operator-owned files before action.
- New documentation: `docs/EXISTING_INSTALL_ADOPTION.md`.

### Preserved by default

- `/opt/libreqos/src/config.json`
- `/opt/libreqos/src/ShapedDevices.csv`
- `/opt/libreqos/src/network.json`
- `/opt/lqosync/users.json`
- `/opt/lqosync/.env`
- `/opt/lqosync/state/`
- `/opt/lqosync/logs/`
- `/opt/lqosync/backups/`

### Notes

This update keeps LibreQoS integrity intact while allowing older ZIP/manual installs to become Git-managed and safely updatable from GitHub.

## v2.74.0-rc1 — Rust Core v0.4 Daemon Mode

- Added optional `lqosync-core --daemon --socket /run/lqosync-core.sock` Unix socket daemon.
- Added Python wrapper daemon transport with safe fallback to subprocess or Python fallback.
- Added `health` operation to the Rust core protocol.
- Added systemd service template and install/uninstall helper scripts for the daemon.

## v2.75.0-rc1 - Rust Core v0.5 Policy Shadow

- Added Rust `evaluate-policy` operation.
- Added shadow policy risk/verdict/parity checks.
- Added Dry Run Rust Policy Shadow panel.
- Python policy remains authoritative; Rust is diagnostics-only in this release.

## v2.77.0-rc1 - Rust Core v0.7 Sync Plan Shadow

- Added `evaluate-sync-plan` to `lqosync-core`.
- Added `rust_sync_plan` to Dry Run output.
- Added Rust Sync Plan Shadow card in Dry Run UI.
- Added `docs/RUST_CORE_V07_SYNC_PLAN.md`.
- Python remains authoritative for cleanup, writes, and LibreQoS apply.


## v2.78.0-rc1 - Rust Core v0.8 Authority Gates

- Added opt-in `rust_core.enforce_sync_plan` authority gate.
- Added `rust_core.authority_mode` with `shadow` and `enforce_blockers`.
- Added fail-closed behavior when enforced Rust core is unavailable.
- Dry Run remains preview-only; Python remains default authority unless enforcement is enabled.
- Added documentation: `docs/RUST_CORE_V08_AUTHORITY_GATES.md`.


## v2.79.0-rc1 — Rust Core v0.9 Apply Manifest Preview

- Adds `build-apply-manifest` to `lqosync-core`.
- Adds Dry Run visibility for backup/write/pending-apply/LibreQoS apply transaction intent.
- Keeps Python authoritative; manifest is non-destructive and diagnostic by default.


## 2.80.0-rc1

- Add Rust Core v1.0 apply transaction executor operation `execute-apply-transaction`.
- Keep transaction execution disabled by default; Dry Run shows rehearsal status.
- Add config flags for future opt-in Rust file-write authority.



## v2.81.1-rc1 — Rust Core v1.1.1 Self-Test Build Hotfix

- Fixes the Rust self-test no-change apply manifest check by using `mode="apply"` instead of `mode="dry_run"` for that specific internal check.
- Keeps dry-run manifest behavior unchanged: dry-run manifests still report `preview_only`.
- Updates `scripts/build-rust-core.sh` to delete stale release binaries before test/build so a failed build cannot leave an old binary ready for accidental install.
- Updates `scripts/install-rust-core-daemon.sh` to restart an already-running `lqosync-core.service` after installing a new binary.
- Bumps `lqosync-core` to `1.1.1`.

## v2.81.0-rc1 — Rust Core v1.1 Runtime Self-Test and Capability Audit

This package adds a safe Rust core `self-test` operation and `/api/rust-core/self-test` endpoint. It also routes `execute-apply-transaction` through the CLI/daemon protocol and centralizes advertised Rust operations so future operation-list mismatches are easier to catch before enabling authority flags.

Read: `docs/RUST_CORE_V11_SELF_TEST.md`.

## v2.82.0-rc1 — Rust Core v1.2 Transaction Journal and Rollback Manifest

- Adds `build-transaction-journal` to create a non-mutating transaction journal event from the Rust apply manifest and transaction result.
- Adds `build-rollback-manifest` to preview restore operations from transaction backup paths.
- Adds `/opt/lqosync/logs/transaction_journal.jsonl` as the canonical future transaction journal path.
- Adds Dry Run visibility for Rust transaction journal and rollback preview.
- Bumps `lqosync-core` to `1.2.0`.

## v2.83.0-rc1 — Rust Core v1.3 Transaction Journal Persistence

- Added `append-transaction-journal` Rust operation.
- Added opt-in transaction journal persistence flags.
- Dry Run now shows journal append status.
- Python remains authoritative; journal writes are disabled by default.


## v2.86.0-rc1 — Rust Core v1.6 Authority Readiness Report

- Adds `evaluate-authority-readiness` to score whether Rust authority flags are safe to pilot.
- Adds `/api/rust-core/authority-readiness` for read-only operator visibility.
- Keeps Python authoritative by default and treats partial authority flags as blockers.
- Documents readiness verdicts before sync-plan enforcement, file-write authority, journal persistence, or rollback authority are enabled.


## v2.87.0-rc1 — Rust Core v1.7 Full Backend Readiness + Authority Pilot Plan

- Added `evaluate-full-rust-readiness` and `build-authority-pilot-plan`.
- Added read-only APIs for full backend readiness and staged authority pilot planning.
- Documented that the branch is still a hybrid Rust safety core + Python authority system by default, not a full Rust backend yet.
- Added self-test coverage for the new readiness and pilot-plan operations.

## v2.88.0-rc1 - Rust Core v1.8 Collector Bundle Shadow Builder

- Added `build-collector-circuit-bundle` to lqosync-core.
- Added read-only `/api/rust-core/collector-bundle-shadow`.
- Added Rust self-test coverage for collector-bundle shadow normalization.
- Python remains authoritative; Rust collector bundle output is diagnostic only.


## Rust Core v1.9 Collector Bundle Parity Report

Adds `compare-collector-bundle-parity`, a diagnostic operation and API endpoint for comparing Python-authoritative rows with Rust-shadow collector bundle rows before any collector authority migration.


## Rust Core v2.0 RouterOS Collector Plan

This package adds `build-routeros-collector-plan`, a read-only Rust operation that derives the RouterOS resource/field plan for enabled PPPoE, DHCP, and Hotspot sources. It does not connect to MikroTik and does not replace Python collectors. It is a bridge toward a future Rust RouterOS transport while keeping Python authoritative by default.

New API:

```text
GET /api/rust-core/routeros-collector-plan
POST /api/rust-core/routeros-collector-plan
```


## v2.90.1-rc1 — Rust Core v2.0.1 Script Permission Hotfix

- Marks install/build helper scripts as executable in the package.
- Adds `scripts/repair-script-permissions.sh`.
- Documents `bash scripts/...` fallback commands.
- Clarifies that a v2.0+ install should advertise `build-routeros-collector-plan` in `self-test`.
