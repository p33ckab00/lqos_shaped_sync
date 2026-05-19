# LQoSync Documentation Index

This index is the GitHub-friendly map for the consolidated LQoSync documentation. The same topic files are searchable inside the WebUI Documentation Center.

## Main entry points

- [Runtime Rename Migration](RUNTIME_RENAME_MIGRATION.md) — canonical `lqosync` service/log/container naming and safe migration behavior.

- [Repository Rename Guide](REPOSITORY_RENAME.md) — rename GitHub repository from lqosync to LQoSync while preserving runtime compatibility names.
- [README](../README.md) — compact project landing page
- [Full Documentation](../FULL_DOCUMENTATION.md) — complete single-file manual
- [AI-Assisted Development Disclosure](AI_ASSISTED_DEVELOPMENT.md)
- [Command Reference](COMMANDS.md)



## LQoSync-in-Rust branch documentation

- [LQoSync-in-Rust Core Migration Plan](RUST_CORE_MIGRATION.md) — phased plan for adding a Rust safety core while preserving the Python Flask WebUI, pure JSON/files, and autosave behavior.
- [Rust Core v0.3 Atomic State and File Engine](RUST_CORE_V03_ATOMIC_STATE.md) — includes v2.73.1 Rust build hotfix for CSV LF terminator compatibility.
- [Rust Core Protocol](RUST_CORE_PROTOCOL.md) — stable JSON request/response envelope shared by subprocess CLI and future Unix socket daemon.
- [Rust Core v0.2 Trust and Diff Update](RUST_CORE_V02_TRUST_DIFF.md) — Collector trust guard, suspicious zero protection, and Rust diff operations.
- [Collector Output Contract](COLLECTOR_OUTPUT_CONTRACT.md) — typed source trust contract to prevent silent RouterOS partial/zero results from triggering unsafe cleanup.
- [Autosave and Atomic State Model](AUTOSAVE_AND_ATOMIC_STATE.md) — no-save-button flow, dangerous-change confirmation, atomic file/state writes, and rollback guidance.
- [Commit and Push Guide](COMMIT_AND_PUSH_GUIDE.md) — branch workflow and commit/push instructions for `lqosync-in-rust`.

## Topic index

- [Policy Settings Integration](content/policy_settings_integration.md)
- [Setup & Repair Center](content/setup_repair_center.md)
- [Smart Policy Center](SMART_POLICY_CENTER.md)
- [Smart Setup / Repair](SMART_SETUP_REPAIR.md)
- [Policy-Aware Cleanup Intelligence](content/policy_aware_cleanup_intelligence.md)
  - v2.50 source-aware stale lifecycle, optional grace, risk-aware auto apply, and decision trace.
- [Config Schema + Policy Simulation Engine](content/config_schema_policy_simulation.md)
  - v2.51 config_schema_version, config health, unsaved config preview, policy simulation, and impact verdicts.
- [Smart Reports + Operator Audit](content/smart_reports_operator_audit.md)
  - v2.52 operator report page with 24h summary, policy decision report, cleanup report, client changes, config audit, and exports.
- [Client Lifecycle Timeline](content/client_lifecycle_timeline.md)
  - v2.53 client lifecycle timeline, active/stale/queued/removed/returned states, cleanup queue, confirmations, and exports.
- [First Run Setup Wizard](content/setup_wizard_first_run.md)
  - v2.54 guided first-run onboarding for paths, routers, sources, layout, policy preset, Dry Run, and scheduler readiness.
- [Smart Reports route hotfix](content/smart_reports_route_hotfix.md)
- [Policy Center Settings Guidelines](content/policy_center_settings_guidelines.md)
  - Atomic operator explanations for every editable Policy Center setting.
- [Network Layout Drag-and-Drop](content/network_layout_drag_drop.md)
  - v2.54.3 wired desktop drag-and-drop for moving topology nodes with safe validation and preview-before-save behavior.
- [AI-Assisted Development Disclosure and Acknowledgement](../AI_ASSISTED_DEVELOPMENT.md)
- [Privacy Icon Polish](content/privacy_icon_polish.md)
- [Package Quality + Environment Doctor](content/package_quality_environment_doctor.md)
  - v2.55 release integrity checks, environment doctor, route/template validation, and Smart Defaults Repair.
- [Policy UX + Conflict Intelligence](content/policy_ux_conflict_identity.md)
  - v2.56 Policy Conflict Resolver, richer preset comparison, and client identity handling guidance.
- [Source Health + Performance Trends](content/source_health_performance_trends.md)
  - v2.57 source health dashboard, RouterOS API timing trends, LibreQoS apply health, and internal notification candidates.
- [Source Health & Performance Trends](content/source_health_performance_trends.md)
  - Dashboard-consolidated source health, RouterOS API timing, LibreQoS apply health, and internal notification candidates.
- [Telegram Notifications](content/telegram_notifications.md)
  - v2.58 optional Telegram delivery for internal health, policy, apply, and source notification candidates.
- [Documentation Search + UI/Mobile Polish](content/documentation_search_ui_polish.md)
  - v2.59 local documentation search, docs view pages, read-only docs API, and reusable UI/mobile consistency helpers.
- [Better Fresh Install Experience](content/better_fresh_install_experience.md)
  - v2.60 first-run gate, scheduler readiness protection, setup wizard redirect, and fresh install workflow.
- [Client Lifecycle View and Filter Hotfix](content/client_lifecycle_timeline.md)
  - v2.60.1 fixes Lifecycle View button wiring, adds instant table/card filtering, and adds timeline pagination/row limits.
- [Backup Pagination and Actions](content/backup_pagination_actions.md)
- [Compact Information Architecture](content/compact_information_architecture.md)
  - v2.61 Operations Center consolidation, compact sidebar, Dashboard/Reports separation, and documentation source-of-truth cleanup.
- [Config + Policy + Notification Unification](content/config_policy_notification_unification.md)
  - v2.62 consolidates Policy Center and Telegram notification delivery settings into Config Center while keeping compatibility redirects.
- [Documentation Consolidation and Source of Truth](content/documentation_consolidation.md)
  - v2.63 consolidates GitHub and WebUI documentation into docs/content, docs_manifest, README, and FULL_DOCUMENTATION as one coherent source-of-truth system.

- [Production Hardening + Regression Suite](content/production_hardening_regression_suite.md)

- [Backup / Restore Center Polish](content/backup_restore_center_polish.md) — backup preview, integrity, live diff, zip download, and retention preview.


## v2.67 Access Control + Role Hardening

LQoSync v2.67 adds a clearer owner/admin/operator/viewer role model. Owner controls users, updates, and high-trust repair actions. Admin controls config, policies, scheduler, backups, operations, and live apply actions. Operator can monitor and run dry-run previews. Viewer remains read-only. Older installs with only an admin account are upgraded safely by promoting the first admin to owner if no owner exists. See `docs/content/access_control_role_hardening.md`.

- [Production Readiness Score](content/production_readiness_score.md) — v2.68 Dashboard go-live confidence score and readiness API.

- [Router Overview + Multi-Router UX Polish](content/router_overview_multi_router_ux.md) — v2.69/v2.69.1 Router Insight now lives inside Config Center; /routers is a redirect alias.

- [Router Insight De-duplication + Policy/Path Audit](content/router_insight_dedup_policy_path_audit.md) — v2.69.1 removes duplicate Router page UI and adds policy/path audit checks.

- [Stable Release Candidate](content/stable_release_candidate.md) — v2.70 feature freeze and validation chain.
- [Route Compatibility Map](ROUTE_COMPATIBILITY.md) — compact canonical routes and compatibility aliases.
- [Stable Release Checklist](STABLE_RELEASE_CHECKLIST.md) — preflight/operator checklist for stable candidates.
- [Upgrade Guide](UPGRADE_GUIDE.md) — safe GitHub update and post-upgrade checks.
- [Policy / Path Reference](POLICY_PATH_REFERENCE.md) — policy/path audit and important policy groups.

- [Config Policy Hierarchy UI](content/policy_hierarchy_ui.md) — v2.70.2-rc1 compact policy hierarchy and auto-apply/optional backup interpretation.

- [Policy Preset Wiring Hotfix](content/policy_preset_wiring_hotfix.md) — Config Center policy preset apply controls and managed preset-mode behavior.

- [UI Wiring Audit + Role Visibility Hotfix](content/ui_wiring_audit_role_visibility.md) — v2.70.4-rc1 role visibility, compact route ownership, policy preset wiring, and stale file checks.

- [Settings UI State Wiring Hotfix](content/settings_ui_state_wiring_hotfix.md) — v2.70.5-rc1 Config Center preset active-state and settings UI wiring audit fix.

- [Checkbox State Wiring Hotfix](content/checkbox_state_wiring_hotfix.md) — v2.70.6 Config Center checkbox checked-state binding and visual-state fix.

- [LibreQoS Apply Failure Visibility](content/apply_failure_visibility.md) — v2.70.7-rc1 diagnostic workflow for failed LibreQoS apply runs.

- [Policy Preset Alignment + Save Semantics](content/policy_preset_alignment_save_semantics.md) — preset alignment, custom-save reconciliation, and policy preset audit.

- [Custom Policy Mode Persistence Hotfix](content/custom_policy_mode_persistence.md) — v2.70.9 visible Custom policy state and save semantics.

- [Install and Update Safety](content/install_update_safety.md) — backup-first fresh install, preserve-existing update behavior, and operator verification.

- [Operator Overview](content/operator_overview.md) — atomic explanation of the collection/build/policy/apply workflow.

## Rust core scaffold implementation

The `lqosync-in-rust` branch now includes the first optional Rust sidecar implementation.

Key files:

```text
rust/lqosync-core/
engine/rust_core.py
scripts/build-rust-core.sh
scripts/install-rust-core.sh
```

Read these docs first:

- [LQoSync-in-Rust Core Migration Plan](RUST_CORE_MIGRATION.md)
- [Rust Core v0.3 Atomic State and File Engine](RUST_CORE_V03_ATOMIC_STATE.md) — includes v2.73.1 Rust build hotfix for CSV LF terminator compatibility.
- [Rust Core Protocol](RUST_CORE_PROTOCOL.md)
- [Collector Output Contract](COLLECTOR_OUTPUT_CONTRACT.md)
- [Autosave and Atomic State Model](AUTOSAVE_AND_ATOMIC_STATE.md)
- [Commit and Push Guide](COMMIT_AND_PUSH_GUIDE.md)

- [Rust Core v0.3 Atomic State and File Engine](RUST_CORE_V03_ATOMIC_STATE.md)

- [Rust Core v0.4 Daemon Mode](RUST_CORE_V04_DAEMON.md)

- [Rust Core v0.5 Policy Shadow Engine](RUST_CORE_V05_POLICY_SHADOW.md) — Shadow Rust policy decision engine, risk scoring, and Python/Rust parity checks.

- [Rust Core v0.6 Circuit Shadow Normalizer](RUST_CORE_V06_CIRCUIT_SHADOW.md) — Shadow Rust circuit normalization and Dry Run visibility.
- [Rust Core v0.7 Sync Plan Shadow Engine](RUST_CORE_V07_SYNC_PLAN.md) - End-to-end shadow sync planner for collector trust, diff, validation, circuit shadow, policy shadow, and preflight diagnostics.

- [Rust Core v0.8 Authority Gates](RUST_CORE_V08_AUTHORITY_GATES.md) — opt-in Rust sync-plan enforcement gate for blocking unsafe non-dry-run writes.

- [Rust Core v0.9 Apply Manifest Preview](RUST_CORE_V09_APPLY_MANIFEST.md) — transaction manifest before backup/write/apply.

- [Rust Core v1.0 Apply Transaction Executor](RUST_CORE_V10_APPLY_TRANSACTION.md)

- [Rust Core v1.1 Runtime Self-Test and Capability Audit](RUST_CORE_V11_SELF_TEST.md) — self-test operation, capability audit, and WebUI endpoint for validating Rust core runtime availability.

- [Rust Core v1.2 Transaction Journal and Rollback Manifest](RUST_CORE_V12_TRANSACTION_JOURNAL.md) — non-mutating journal and rollback previews for Rust transaction accountability.

- [Rust Core v1.3 Transaction Journal Persistence](RUST_CORE_V13_TRANSACTION_JOURNAL_PERSISTENCE.md) — opt-in JSONL persistence for Rust transaction journal events.

- [Rust Core v1.4 Transaction History and Rollback Plan Viewer](RUST_CORE_V14_TRANSACTION_HISTORY.md) — Read-only journal history and rollback plan API.

- [Rust Core v1.5 Rollback Execution Rehearsal](RUST_CORE_V15_ROLLBACK_EXECUTOR.md) — gated `execute-rollback` operation and confirmation-based file restore preview/execution model.

- [Rust Core v1.6 Authority Readiness Report](RUST_CORE_V16_AUTHORITY_READINESS.md)

- [Rust Core v1.7 Full Backend Readiness + Authority Pilot Plan](RUST_CORE_V17_FULL_BACKEND_READINESS.md)

- [Rust Core v1.8 Collector Bundle Shadow Builder](RUST_CORE_V18_COLLECTOR_BUNDLE.md) - Shadow Rust normalization of raw collector snapshots into ShapedDevices-compatible rows.


## Rust Core v1.9 Collector Bundle Parity Report

Adds `compare-collector-bundle-parity`, a diagnostic operation and API endpoint for comparing Python-authoritative rows with Rust-shadow collector bundle rows before any collector authority migration.

- [Rust Core v2.0 RouterOS Collector Plan](RUST_CORE_V20_ROUTEROS_COLLECTOR_PLAN.md) — Read-only RouterOS resource/field command planning before live Rust transport migration.

- [Rust Core v2.0.1 Script Permission Hotfix](RUST_CORE_V201_SCRIPT_PERMISSION_HOTFIX.md) — Repairs lost shell script executable bits and prevents accidentally testing an older installed Rust core.

- [Rust Core v2.1 RouterOS Read Result Contract](RUST_CORE_V21_ROUTEROS_READ_RESULTS.md)

- [Rust Core v2.2 RouterOS Transport Session Rehearsal](RUST_CORE_V22_ROUTEROS_TRANSPORT_SESSION.md)

- [Rust Core v2.3 RouterOS Live Read Pilot Gate](RUST_CORE_V23_ROUTEROS_LIVE_READ_PILOT.md)

- [Rust Core v2.4 RouterOS Read Pilot Fixture Adapter](RUST_CORE_V24_ROUTEROS_READ_PILOT_FIXTURE.md)

- [Rust Core v2.5 RouterOS API Sentence Codec](RUST_CORE_V25_ROUTEROS_API_CODEC.md) - Offline RouterOS API sentence/proplist codec for future read-only Rust transport.

- [Rust Core v2.6 RouterOS API Reply Codec](RUST_CORE_V26_ROUTEROS_API_REPLY_CODEC.md) — Offline RouterOS API reply word decoder for future live Rust transport.

- [Rust Core v2.7 RouterOS API Frame Codec](RUST_CORE_V27_ROUTEROS_API_FRAME_CODEC.md) — Offline RouterOS API binary frame encoder/decoder before live Rust socket transport.

- [Rust Core v2.8 RouterOS Offline Session Pipeline](RUST_CORE_V28_ROUTEROS_OFFLINE_SESSION.md) — Offline end-to-end RouterOS API protocol session rehearsal using fixtures only.

- [Rust Core v2.9 RouterOS TCP Connectivity Pilot](RUST_CORE_V29_ROUTEROS_TCP_CONNECTIVITY.md) — gated TCP reachability pilot before RouterOS authentication/live API reads.

- [Rust Core v3.0 RouterOS Authentication Plan](RUST_CORE_V30_ROUTEROS_AUTH_PLAN.md) — redacted RouterOS auth planning before live Rust authentication or collector authority.


## Rust Core v3.1 RouterOS Auth Handshake Fixture

Adds `run-routeros-auth-handshake`, an offline fixture operation that models RouterOS authentication reply handling without opening sockets, emitting credentials, or replacing Python collectors.


## Rust Core v3.2 RouterOS Auth Session Contract

Adds `build-routeros-auth-session-contract`, a redacted authenticated-session contract built from fixture auth replies. It performs zero socket/auth attempts, emits no credentials or tokens, and keeps Python collectors authoritative.
