# LQoSync Documentation Index

This index is the GitHub-friendly map for the consolidated LQoSync documentation. The same topic files are searchable inside the WebUI Documentation Center.

## Main entry points

- [README](../README.md) — compact project landing page
- [Full Documentation](../FULL_DOCUMENTATION.md) — complete single-file manual
- [AI-Assisted Development Disclosure](AI_ASSISTED_DEVELOPMENT.md)
- [Command Reference](COMMANDS.md)

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

- [Config Truth Layer + Live Save Audit](content/config_truth_layer.md) — v2.70.11-rc1 canonical config writes, stale-write rejection, field-level audit diffs, and inline effectivity.
- [Config Field Guide — WH/HOW Reference](content/config_field_guide.md) — install/operator guide for config.json fields using the same What/Why/When/Who/Where/How registry as Advanced JSON.
- [Config Guidance + Role-Aware Navigation](content/config_guidance_role_navigation.md) — v2.70.12-rc1 Advanced JSON guide inspector and hidden admin-only sidebar links for operator/viewer roles.
- [Advanced JSON + Field Guide UI Polish](content/advanced_json_field_guide_ui_polish.md) — v2.70.13-rc1 wider admin workspace, wider guide pane, aligned WH/HOW rows, and smaller JSON editor text.
- [Policy Tree Desktop Alignment Hotfix](content/policy_tree_desktop_alignment_hotfix.md) — v2.70.14-rc1 restores desktop horizontal icon/label alignment without changing mobile layout.
- [Telegram Notifications](content/telegram_notifications.md) — v2.71 Safety Alerts plus digest-first Activity Journal delivery.
- [Telegram Runtime Feed — Safety Alerts + Activity Journal](content/telegram_runtime_feed.md) — v2.71 live runtime event wiring and audit interpretation.
