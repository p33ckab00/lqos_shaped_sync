# Config Field Guide — WH/HOW Reference

This is the install/operator guide for `config.json`. The WebUI Advanced JSON inspector uses the same registry, so the documentation and live UI answer the same questions:

- **What** is this field?
- **Why** does it exist?
- **When** does it become effective?
- **Who** should change it?
- **Where** is it used?
- **How** should it be changed safely?

For dynamic arrays such as routers and DHCP servers, `[]` means “each item in the list”. The live WebUI expands these guide patterns against the current saved `config.json`, so every concrete leaf path receives a guide entry.

## `app.` — Application behavior

- **Section:** App / live apply
- **What:** Stores system-wide behavior such as application name, default dry-run mode, and file-drift handling.
- **Why:** These fields describe the operating personality of the service rather than one source or one policy.
- **When effective:** Next config read. config.json is the source of truth; readers use the saved value on their next read.
- **Who should change it:** Admin or owner
- **Where used:** Advanced JSON
- **How to use it safely:** Change only after reading the matching field help; preview output-affecting changes with Dry Run.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Varies by field; app.* values can change live-write and apply behavior.
- **Related paths:** `scheduler.`, `libreqos.`

## `app.auto_apply` — Auto apply

- **Section:** App / live apply
- **What:** Allows future live cycles to apply generated LibreQoS file changes automatically.
- **Why:** It separates preview-only operation from production automation.
- **When effective:** Next live cycle. Controls whether generated file changes may be applied to LibreQoS automatically.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Overview
- **How to use it safely:** Keep disabled until router sources, policies, and Dry Run results are verified. Automatic mode requires this enabled.
- **Default / recommended:** `true`
- **Risk:** High: enabling too early can push unintended output into LibreQoS.
- **Example:** `true after successful commissioning`
- **Related paths:** `app.operation_mode`, `policies.auto_apply_policy.`

## `app.backup_before_apply` — Optional auto backup

- **Section:** App / live apply
- **What:** Controls whether generated LibreQoS files are backed up before later live applies.
- **Why:** It trades extra rollback safety for storage growth.
- **When effective:** Next live apply. Controls whether generated LibreQoS files are backed up before future live applies.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Overview
- **How to use it safely:** Enable when rollback speed matters more than disk usage; if disabled, keep a manual backup habit before major changes.
- **Default / recommended:** `false`
- **Risk:** Medium: disabling removes one automatic rollback layer, but remains an allowed operator choice.
- **Example:** `true on high-value production nodes`
- **Related paths:** `app.backup_retention`, `policies.backup_guard.`

## `app.backup_retention` — Backup retention

- **Section:** App / live apply
- **What:** Sets how many generated-file backup directories are retained when pruning runs.
- **Why:** It limits storage growth while preserving rollback history.
- **When effective:** Next backup prune. Controls how many generated-file backup directories are kept when pruning runs.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Overview
- **How to use it safely:** Increase for slower review cycles; reduce only after confirming backup size and rollback requirements.
- **Default / recommended:** `10`
- **Risk:** Medium: a very low value shortens the recovery window.
- **Example:** `10`
- **Related paths:** `app.backup_before_apply`, `paths.backup_dir`

## `app.operation_mode` — Operation mode

- **Section:** App / live apply
- **What:** Chooses whether production flow expects automatic or operator-triggered apply behavior.
- **Why:** It defines the operating contract for the whole system before scheduler and auto-apply decisions are made.
- **When effective:** Next scheduler/manual action. Changes whether production flow expects automatic or operator-triggered apply behavior.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Overview
- **How to use it safely:** Use automatic only when auto_apply is intentionally enabled and Dry Run is clean; use manual while commissioning or troubleshooting.
- **Default / recommended:** `automatic`
- **Risk:** High if set incorrectly: the system can appear safer or more automated than the operator intends.
- **Example:** `"manual" during first commissioning`
- **Related paths:** `app.auto_apply`, `scheduler.enabled`

## `libreqos.` — LibreQoS apply runner

- **Section:** Apply engine
- **What:** Controls how LQoSync invokes LibreQoS.py after output files change.
- **Why:** It connects generated files to the actual LibreQoS runtime update.
- **When effective:** Next live apply. Changes how LibreQoS.py is invoked after generated files are written.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Apply Policy
- **How to use it safely:** Keep working_dir and run_mode aligned with the install type; use direct mode for bare metal unless deployment docs say otherwise.
- **Default / recommended:** `Varies by deployment`
- **Risk:** High: wrong command, working directory, or mode can make applies fail or run in the wrong place.
- **Related paths:** `app.auto_apply`, `paths.`

## `scheduler.` — Scheduler

- **Section:** Automation
- **What:** Controls recurring sync cadence, retry timing, and apply cooldown.
- **Why:** It decides when the engine wakes up and how aggressively it revisits work.
- **When effective:** Next scheduler loop. The scheduler rereads config.json before deciding its next run/interval.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Scheduler
- **How to use it safely:** Use slower intervals while commissioning; tighten only after collection and apply times are known.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Medium: too-fast loops create churn; too-slow loops delay network truth.
- **Related paths:** `app.operation_mode`, `app.auto_apply`

## `collector.` — Collector behavior

- **Section:** Collection
- **What:** Controls how source data is read from RouterOS.
- **Why:** Collection quality determines the truth available to builders and policy decisions.
- **When effective:** Next sync cycle. Changes how MikroTik source data is collected on the next cycle.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Collectors
- **How to use it safely:** Prefer the least broad successful read mode; change DHCP/Hotspot behavior only when you understand the source data shape.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Medium to high: poor collector settings can create false zero results or missing metadata.
- **Related paths:** `routers[].`, `policies.collector_guard.`

## `paths.` — Filesystem paths

- **Section:** Filesystem
- **What:** Maps LQoSync to config, generated files, logs, runtime state, backups, and caches.
- **Why:** The engine needs exact paths to read truth and write generated artifacts atomically.
- **When effective:** Next use. Changes the next read/write that uses this path; verify carefully before live operation.
- **Who should change it:** Owner or install admin
- **Where used:** Config Center → Paths / install documentation
- **How to use it safely:** Change only when moving a real file location; verify service-user permissions immediately afterward.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Critical: wrong paths can read stale files, fail writes, or update the wrong LibreQoS tree.
- **Related paths:** `libreqos.working_dir`

## `defaults.` — Generated-row defaults

- **Section:** Generation defaults
- **What:** Provides fallback values when source data does not carry a complete plan or row value.
- **Why:** Builders need deterministic defaults rather than silently emitting incomplete output.
- **When effective:** Next sync cycle. Changes fallback values used while generating future rows/nodes.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Defaults
- **How to use it safely:** Set defaults to safe business values; watch fallback-speed warnings if they are being used often.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Medium: bad defaults can quietly shape many clients at the wrong speed.
- **Related paths:** `policies.data_quality.`

## `flat_network` — Flat-network compatibility flag

- **Section:** Network topology
- **What:** Compatibility flag kept in sync with network_mode for flat layouts.
- **Why:** Older code/configs still read this flag while network_mode carries the richer intent.
- **When effective:** Next sync cycle. Compatibility flag kept consistent with network_mode for flat layout behavior.
- **Who should change it:** Admin or owner
- **Where used:** Advanced JSON
- **How to use it safely:** Do not hand-edit independently; let the Config Center normalize it from network_mode.
- **Default / recommended:** `false`
- **Risk:** High when inconsistent with network_mode because generated Parent Node behavior can become misleading.
- **Related paths:** `network_mode`, `no_parent`

## `network_mode` — Network layout mode

- **Section:** Network topology
- **What:** Defines the high-level hierarchy model used while generating network.json.
- **Why:** It determines Parent Node semantics, not just a visual preference.
- **When effective:** Next sync cycle. Controls Parent Node behavior and generated network.json topology.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Overview / Network Layout
- **How to use it safely:** Keep the mode that matches the real network hierarchy; review generated network.json and Dry Run after changing it.
- **Default / recommended:** `router_children`
- **Risk:** High: the wrong mode can reshape parent/child topology.
- **Example:** `"router_children"`
- **Related paths:** `flat_network`, `no_parent`, `routers[].parent_node`

## `no_parent` — No-parent compatibility flag

- **Section:** Network topology
- **What:** Compatibility flag that represents blank Parent Node behavior for flat_no_parent mode.
- **Why:** It preserves legacy behavior required by generated network.json output.
- **When effective:** Next sync cycle. Compatibility flag kept consistent with network_mode for blank Parent Node behavior.
- **Who should change it:** Admin or owner
- **Where used:** Advanced JSON
- **How to use it safely:** Do not hand-edit independently; let the Config Center normalize it from network_mode.
- **Default / recommended:** `false`
- **Risk:** High when inconsistent with network_mode because hierarchy output changes.
- **Related paths:** `network_mode`, `flat_network`

## `preserve_network_config` — Preserve network config

- **Section:** Network topology
- **What:** Compatibility behavior that preserves existing network topology instead of regenerating it in selected flows.
- **Why:** Some deployments intentionally manage network.json outside the normal generated path.
- **When effective:** Next config read. config.json is the source of truth; readers use the saved value on their next read.
- **Who should change it:** Admin or owner
- **Where used:** Advanced JSON
- **How to use it safely:** Use only when the operator has a deliberate external network.json workflow.
- **Default / recommended:** `false`
- **Risk:** High if misunderstood: generated topology may not follow current source data.
- **Related paths:** `network_mode`, `paths.network_json`

## `topology.` — Topology editor behavior

- **Section:** Network topology
- **What:** Controls advanced topology editing and validation affordances.
- **Why:** It keeps custom/deep hierarchy features explicit rather than silently available.
- **When effective:** Next config read. config.json is the source of truth; readers use the saved value on their next read.
- **Who should change it:** Admin or owner
- **Where used:** Advanced JSON / Network Layout
- **How to use it safely:** Keep validation enabled; enable advanced topology only when the network model needs it.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Medium to high depending on hierarchy complexity.
- **Related paths:** `network_mode`

## `notifications.` — Notification behavior

- **Section:** Notifications
- **What:** Controls internal notification surfaces and optional external delivery.
- **Why:** Operators need timely signals without coupling alert display to every engine decision.
- **When effective:** Next notification dispatch. Changes future notification generation or delivery behavior.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Notifications
- **How to use it safely:** Keep internal center enabled; tune external delivery after verifying real events.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Low to medium: mostly affects visibility rather than generation.

## `notifications.telegram.` — Telegram delivery

- **Section:** Notifications
- **What:** Controls outbound Telegram delivery, filtering, dedupe, Safety Alerts, and the Activity Journal.
- **Why:** It decides which runtime events leave the WebUI, which are urgent, and which become quiet operator-journal entries.
- **When effective:** Next notification dispatch. Changes Telegram delivery behavior for future notifications.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Notifications
- **How to use it safely:** Keep Safety Alerts enabled for urgent conditions, keep Activity Journal digest-first for operational visibility, test once, then tune noise controls.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Low to medium except for secret fields; bad settings mostly create silence or alert fatigue.
- **Related paths:** `notifications.`

## `notifications.telegram.activity_journal_enabled` — Telegram activity journal

- **Section:** Notifications
- **What:** Turns the digest-first operator journal lane on or off.
- **Why:** Operators often need proof of what changed even when nothing is wrong.
- **When effective:** Next notification dispatch. Changes Telegram delivery behavior for future notifications.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Notifications → Activity Journal
- **How to use it safely:** Keep enabled when you want client-change/apply-success visibility; prefer digest mode for low-noise operation.
- **Default / recommended:** `true`
- **Risk:** Low: disabling it removes convenience/history, not safety gates.
- **Related paths:** `notifications.telegram.notify_on_client_changes`, `notifications.telegram.notify_on_apply_success`

## `notifications.telegram.bot_token` — Telegram bot token

- **Section:** Notifications
- **What:** Secret token used to authenticate outbound Telegram messages.
- **Why:** Telegram delivery cannot work without bot authentication.
- **When effective:** Next notification dispatch. Changes Telegram delivery behavior for future notifications.
- **Who should change it:** Owner or trusted admin
- **Where used:** Config Center → Notifications
- **How to use it safely:** Store only the real bot token, keep file permissions tight, and rotate if exposed.
- **Default / recommended:** `empty until configured`
- **Risk:** Critical secret: disclosure allows message-sending abuse through the bot.
- **Related paths:** `notifications.telegram.chat_id`

## `notifications.telegram.notify_on_apply_success` — Telegram successful-apply journal events

- **Section:** Notifications
- **What:** Allows successful LibreQoS apply confirmations into the Activity Journal.
- **Why:** A successful file write is not the same as a successful LibreQoS apply; this confirms the final actuation step.
- **When effective:** Next notification dispatch. Changes Telegram delivery behavior for future notifications.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Notifications → Activity Journal
- **How to use it safely:** Keep enabled when operators need positive confirmation that live shaping was applied.
- **Default / recommended:** `true`
- **Risk:** Low: visibility-only.

## `notifications.telegram.notify_on_client_changes` — Telegram client-change journal events

- **Section:** Notifications
- **What:** Allows client add/update/remove summaries into the Activity Journal.
- **Why:** This makes the runtime feed explain what changed in shaped client records after a real cycle.
- **When effective:** Next notification dispatch. Changes Telegram delivery behavior for future notifications.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Notifications → Activity Journal
- **How to use it safely:** Keep enabled if operators should see client movement without opening Audit Logs.
- **Default / recommended:** `true`
- **Risk:** Low: can add message volume on busy networks.

## `notifications.telegram.safety_alerts_enabled` — Telegram safety alerts

- **Section:** Notifications
- **What:** Turns the urgent Telegram lane on or off.
- **Why:** Policy blocks, confirmation holds, and failed applies need a delivery lane that is hard to miss.
- **When effective:** Next notification dispatch. Changes Telegram delivery behavior for future notifications.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Notifications → Safety Alerts
- **How to use it safely:** Keep enabled in production; tune exact event filters below it rather than disabling the whole lane.
- **Default / recommended:** `true`
- **Risk:** Medium: disabling it can hide time-sensitive failures outside the WebUI.
- **Related paths:** `notifications.telegram.notify_on_apply_failed`, `notifications.telegram.notify_on_policy_block`

## `insights.` — Smart insights

- **Section:** Observability
- **What:** Controls explanatory cards and recommendation surfaces.
- **Why:** It separates explanation from enforcement while helping operators understand engine behavior.
- **When effective:** Next config read. config.json is the source of truth; readers use the saved value on their next read.
- **Who should change it:** Admin or owner
- **Where used:** Advanced JSON / Dashboard
- **How to use it safely:** Keep enabled unless deliberately simplifying a constrained UI deployment.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Low: affects explanation, not enforcement.

## `monitoring.` — Monitoring behavior

- **Section:** Observability
- **What:** Controls health/trend collection and how much operational history is summarized.
- **Why:** It shapes the signal available to dashboards and recommendations.
- **When effective:** Next config read. config.json is the source of truth; readers use the saved value on their next read.
- **Who should change it:** Admin or owner
- **Where used:** Advanced JSON / Dashboard
- **How to use it safely:** Keep enabled in production; reduce sample sizes only when resource limits require it.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Low to medium: disabling reduces visibility.

## `setup_repair.` — Setup and repair

- **Section:** Onboarding
- **What:** Controls guided diagnostics and safe repair affordances.
- **Why:** It gives admins recovery tools without making repair actions the default operating path.
- **When effective:** Next config read. config.json is the source of truth; readers use the saved value on their next read.
- **Who should change it:** Owner or install admin
- **Where used:** Advanced JSON / Setup & Repair
- **How to use it safely:** Keep repair read-only by default; use write repairs deliberately and with backups.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Medium to high when write repair actions are enabled casually.

## `setup_wizard.` — Setup wizard

- **Section:** Onboarding
- **What:** Controls first-run onboarding behavior and scheduler-readiness requirements.
- **Why:** It protects fresh installs from jumping directly into unsafe automation.
- **When effective:** Next config read. config.json is the source of truth; readers use the saved value on their next read.
- **Who should change it:** Owner or install admin
- **Where used:** Advanced JSON / Setup Wizard
- **How to use it safely:** Keep first-run protections enabled until commissioning is complete.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Medium: bypassing gates can normalize incomplete setup.

## `services.` — Service monitoring

- **Section:** Operations
- **What:** Defines which systemd units and restart groups appear in Operations Center.
- **Why:** Installations can have slightly different service names while the UI still needs a reliable map.
- **When effective:** Next status refresh. Changes future service status/journal lookups in the UI.
- **Who should change it:** Admin or owner
- **Where used:** Advanced JSON / Operations Center
- **How to use it safely:** Edit only when the real systemd unit names differ from defaults, then verify Operations Center status.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Medium: wrong units make monitoring or restart buttons misleading.

## `policies.anomaly_detection.compare_with_last_successful_run` — Compare with last successful run

- **Section:** Policy / Anomaly Detection
- **What:** Uses last successful run as baseline for anomaly checks.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled.
- **Default / recommended:** `true`
- **Risk:** Without baseline comparison, sudden changes are harder to classify.

## `policies.anomaly_detection.enabled` — Anomaly detection

- **Section:** Policy / Anomaly Detection
- **What:** Enables rule-based anomaly detection from previous successful runs.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled for smart warnings.
- **Default / recommended:** `true`
- **Risk:** Disabling removes early warning for unusual drops/slowness.

## `policies.anomaly_detection.warn_if_apply_duration_increases_multiplier` — Warn if apply duration multiplier

- **Section:** Policy / Anomaly Detection
- **What:** Warns when LibreQoS apply takes much longer than baseline.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 5x is a practical starting point.
- **Default / recommended:** `5`
- **Risk:** Slow apply can indicate host/load/config growth problems.

## `policies.anomaly_detection.warn_if_client_count_drops_percent` — Warn if client count drops percent

- **Section:** Policy / Anomaly Detection
- **What:** Warns when client count drops by this percentage compared with baseline.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 30% is a practical default.
- **Default / recommended:** `30`
- **Risk:** Too low can be noisy; too high may miss incidents.

## `policies.anomaly_detection.warn_if_sync_duration_increases_multiplier` — Warn if sync duration multiplier

- **Section:** Policy / Anomaly Detection
- **What:** Warns when sync duration is many times slower than usual.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 5x is a practical starting point.
- **Default / recommended:** `5`
- **Risk:** Slow sync may indicate API/router/system issues.

## `policies.apply_guard.allow_auto_apply_on_low_risk` — Allow auto-apply on low risk

- **Section:** Policy / Apply Guards
- **What:** Allows low-risk changes to run LibreQoS automatically.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Enable for efficient normal operations.
- **Default / recommended:** `true`
- **Risk:** Disable if you want every apply to be manual.

## `policies.apply_guard.block_apply_on_collector_failure` — Block apply on collector failure

- **Section:** Policy / Apply Guards
- **What:** Prevents LibreQoS apply when a source collector failed and output may be incomplete.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled in production.
- **Default / recommended:** `true`
- **Risk:** Applying after collector failure can remove valid clients from shaping.

## `policies.apply_guard.block_apply_on_duplicate_ip` — Block apply on duplicate IP

- **Section:** Policy / Apply Guards
- **What:** Blocks apply when duplicate IPv4 values are detected in generated rows.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled unless duplicates are intentionally handled elsewhere.
- **Default / recommended:** `true`
- **Risk:** Duplicate IPs can cause wrong shaping assignment.

## `policies.apply_guard.block_apply_on_invalid_speed` — Block apply on invalid speed

- **Section:** Policy / Apply Guards
- **What:** Blocks apply when speed values cannot be parsed or are invalid.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled. Fix plan comments/profile names/default speeds.
- **Default / recommended:** `true`
- **Risk:** Invalid speeds can create bad or failed LibreQoS config.

## `policies.apply_guard.block_apply_on_missing_parent` — Block apply on missing parent

- **Section:** Policy / Apply Guards
- **What:** Blocks apply when ShapedDevices rows reference Parent Nodes missing from network.json.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled. Fix topology or parent naming before applying.
- **Default / recommended:** `true`
- **Risk:** Missing parents can break expected hierarchy/shaping placement.

## `policies.apply_guard.require_manual_confirm_on_medium_risk` — Require manual confirm on medium risk

- **Section:** Policy / Apply Guards
- **What:** Requires operator review for medium-risk policy outcomes.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled for production. Disable only if you want more automation.
- **Default / recommended:** `true`
- **Risk:** Disabling lets medium-risk changes auto-apply if other settings allow it.

## `policies.backup_guard.minimum_backup_retention` — Minimum backup retention when enabled

- **Section:** Policy / Backup Policy
- **What:** Minimum retention count considered healthy when automatic backups are enabled.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use 5–10 for storage-saving deployments, higher only when you need more rollback history.
- **Default / recommended:** `10`
- **Risk:** Retention only matters when automatic or manual backups are being created.

## `policies.backup_guard.require_backup_before_apply` — Require backup before apply

- **Section:** Policy / Backup Policy
- **What:** Controls whether backup_before_apply is treated as required. LQoSync defaults this off because auto-backup is an operator storage/rollback choice.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep disabled for storage-saving automatic deployments; enable only if every apply must create a rollback point.
- **Default / recommended:** `false`
- **Risk:** If enabled while app.backup_before_apply is off, policy conflicts will warn or block according to your guards.

## `policies.backup_guard.warn_if_backup_disabled_while_auto_apply_enabled` — Warn if optional backups are disabled

- **Section:** Policy / Backup Policy
- **What:** Controls whether optional auto-backup disabled should produce policy warnings while auto-apply is enabled.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep disabled if backup_before_apply is intentionally optional. Enable only when your operation requires automatic rollback points.
- **Default / recommended:** `false`
- **Risk:** Enabling this can make storage-saving mode look unhealthy.

## `policies.cleanup.allow_immediate_cleanup` — Allow immediate cleanup

- **Section:** Policy / Cleanup Core
- **What:** Master permission that allows any policy to delete stale rows in the same sync cycle.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Enable if DHCP/Hotspot should update quickly. Disable if all deletions must be staged or confirmed first.
- **Default / recommended:** `true`
- **Risk:** If enabled with aggressive source policies, dynamic clients can cause more file churn and LibreQoS applies.

## `policies.cleanup.apply_confirmed_cleanup` — Confirmed cleanup apply mode

- **Section:** Policy / Cleanup Core
- **What:** Controls when cleanup happens after the operator confirms a pending cleanup decision.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use next_run for production so LQoSync re-checks current config and source state before deleting. Use immediate for urgent manual cleanup.
- **Default / recommended:** `next_run`
- **Risk:** Immediate confirmed cleanup can remove rows before another full collection confirms the condition.

## `policies.cleanup.confirmation_expires_hours` — Confirmation expiry hours

- **Section:** Policy / Cleanup Core
- **What:** Controls how long a pending cleanup confirmation remains valid before the operator must confirm again.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 24 hours is a good default. Use shorter values if many operators change config; use longer values for planned migrations.
- **Default / recommended:** `24`
- **Risk:** Very long expiry can apply an old confirmation after the network/config has changed.

## `policies.cleanup.enabled` — Cleanup policy engine

- **Section:** Policy / Cleanup Core
- **What:** Turns the Smart Cleanup Policy Engine on or off. When enabled, LQoSync classifies why rows are stale before deciding whether to delete, preserve, confirm, or block.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled. Disabling this returns cleanup behavior closer to simple sync logic and removes important protection.
- **Default / recommended:** `true`
- **Risk:** Disabling cleanup intelligence can allow unintended stale-row removal depending on older code paths.

## `policies.cleanup.global_default_action` — Global default cleanup action

- **Section:** Policy / Cleanup Core
- **What:** Fallback cleanup action used when no source-specific or reason-specific policy matches a cleanup candidate.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use require_confirm_next_run for conservative production behavior. Use cleanup_next_run for a faster but still staged workflow.
- **Default / recommended:** `require_confirm_next_run`
- **Risk:** Avoid cleanup_immediate as the global default unless the operator accepts fast deletion for all sources.

## `policies.collector_guard.block_cleanup_if_enabled_source_returns_zero` — Block cleanup if enabled source returns zero

- **Section:** Policy / Collector Guards
- **What:** Stops cleanup when an enabled source returns zero rows.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled unless a source naturally returns zero often.
- **Default / recommended:** `true`
- **Risk:** A zero result can be a collector/router/VLAN problem.

## `policies.collector_guard.block_cleanup_if_source_failed` — Block cleanup if source failed

- **Section:** Policy / Collector Guards
- **What:** Stops cleanup for a source when its collection failed.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled. Preserve rows until a successful scan confirms state.
- **Default / recommended:** `true`
- **Risk:** Disabling can delete clients because of temporary API failure.

## `policies.collector_guard.block_cleanup_if_source_returns_zero_after_previous_success` — Block zero-after-success cleanup

- **Section:** Policy / Collector Guards
- **What:** Blocks cleanup when a source that previously had rows suddenly returns zero.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled. This catches sudden source loss.
- **Default / recommended:** `true`
- **Risk:** Disabling can wipe a source after an anomaly.

## `policies.collector_guard.warn_if_router_api_slow_ms` — Warn if router API slow ms

- **Section:** Policy / Collector Guards
- **What:** Warns when MikroTik API collection time is slower than expected.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 2000 ms is a practical warning threshold.
- **Default / recommended:** `2000`
- **Risk:** Slow API can indicate router load, network issue, or timeout risk.

## `policies.collector_guard.zero_source_drop_threshold_percent` — Zero-source drop threshold percent

- **Section:** Policy / Collector Guards
- **What:** Defines the drop percentage considered suspicious when a source goes near-zero.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 80% catches extreme drops while allowing normal changes.
- **Default / recommended:** `80`
- **Risk:** Too low causes noise; too high may miss failures.

## `policies.cleanup_sources.dhcp.collector_failed_action` — Collector failed action

- **Section:** Policy / DHCP Cleanup
- **What:** Action when DHCP is enabled but lease collection fails.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use preserve_rows. Failure to read leases is not proof that clients are gone.
- **Default / recommended:** `preserve_rows`
- **Risk:** Deleting rows on failed collection can remove valid clients.

## `policies.cleanup_sources.dhcp.enabled` — DHCP cleanup policy

- **Section:** Policy / DHCP Cleanup
- **What:** Enables the source-specific cleanup policy block for DHCP. When disabled, global cleanup defaults are used for this source.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled if DHCP should have its own behavior for inactive, disabled, failed, zero-result, and mass-removal cases.
- **Default / recommended:** `true`
- **Risk:** Disabling source-specific policies can make the source follow broader defaults that may be too aggressive or too conservative.

## `policies.cleanup_sources.dhcp.mass_removal_action` — Mass-removal action

- **Section:** Policy / DHCP Cleanup
- **What:** Action when DHCP removal exceeds source/node guard thresholds.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** require_confirm_next_run is safest. If DHCP is intentionally dynamic, adjust respect_percentage_guards.
- **Default / recommended:** `require_confirm_next_run`
- **Risk:** Mass DHCP cleanup can be normal in guest networks but dangerous in subscriber networks.

## `policies.cleanup_sources.dhcp.normal_inactive_action` — Normal inactive action

- **Section:** Policy / DHCP Cleanup
- **What:** Action when a DHCP lease/client disappears during normal operation.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use cleanup_immediate for dynamic/PisoWiFi-style DHCP, or cleanup_next_run for subscriber DHCP.
- **Default / recommended:** `cleanup_immediate`
- **Risk:** Immediate cleanup is fast but can increase LibreQoS apply frequency if leases flap.

## `policies.cleanup_sources.dhcp.respect_percentage_guards` — Respect percentage/count guards

- **Section:** Policy / DHCP Cleanup
- **What:** Controls whether mass-removal guards can override DHCP normal cleanup.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Disable for highly dynamic DHCP; enable for subscriber DHCP.
- **Default / recommended:** `false`
- **Risk:** Disabling guards makes DHCP cleanup faster but less protected.

## `policies.cleanup_sources.dhcp.source_disabled_action` — Source disabled action

- **Section:** Policy / DHCP Cleanup
- **What:** Action when DHCP collection or a DHCP server source is disabled and existing DHCP rows would disappear.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use require_confirm_next_run because disabling a source can remove many rows intentionally.
- **Default / recommended:** `require_confirm_next_run`
- **Risk:** Immediate cleanup can remove rows because of a config mistake.

## `policies.cleanup_sources.dhcp.zero_result_action` — Zero-result action

- **Section:** Policy / DHCP Cleanup
- **What:** Action when DHCP scan succeeds but returns zero leases while DHCP is enabled.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use block_cleanup by default. A zero result may mean VLAN/API/DHCP source issue.
- **Default / recommended:** `block_cleanup`
- **Risk:** cleanup_immediate can wipe DHCP rows if the scan result is wrong.

## `policies.stale_lifecycle.sources.dhcp.grace_enabled` — DHCP optional grace

- **Section:** Policy / DHCP Stale Lifecycle
- **What:** Enables optional grace behavior so a missing client is held for configured runs before cleanup.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep disabled by default for DHCP/Hotspot random-MAC environments. Consider enabling only for stable PPPoE usernames.
- **Default / recommended:** `false`
- **Risk:** Grace can preserve ghost rows if devices change MAC/IP.

## `policies.stale_lifecycle.sources.dhcp.grace_runs` — DHCP grace runs

- **Section:** Policy / DHCP Stale Lifecycle
- **What:** Number of consecutive missing runs required before cleanup when grace is enabled.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use 1 for PPPoE if you want short reconnect tolerance; use 0 for DHCP/Hotspot unless identities are stable.
- **Default / recommended:** `0`
- **Risk:** Higher values delay cleanup and may preserve stale rows.

## `policies.stale_lifecycle.sources.dhcp.identity` — DHCP identity key

- **Section:** Policy / DHCP Stale Lifecycle
- **What:** Identity used to decide whether a missing client is the same client if it returns later.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use username for PPPoE, server_mac for DHCP, username_or_mac for Hotspot, and manual for static rows.
- **Default / recommended:** `server_mac`
- **Risk:** Grace should only be enabled when identity is stable.

## `policies.stale_lifecycle.sources.dhcp.return_cancels_cleanup` — DHCP return cancels cleanup

- **Section:** Policy / DHCP Stale Lifecycle
- **What:** If the same identity returns before cleanup is applied, pending cleanup is cancelled.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Enable for PPPoE/stable identities. Disable for unstable DHCP identities.
- **Default / recommended:** `false`
- **Risk:** If identity is unstable, returns may not match the old row anyway.

## `policies.data_quality.block_if_fallback_speed_threshold_percent` — Block if fallback speed threshold

- **Section:** Policy / Data Quality Guards
- **What:** Percentage of fallback-speed clients that blocks apply.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 50% catches severe speed-source failures.
- **Default / recommended:** `50`
- **Risk:** Blocking too low can interrupt normal migration; too high may allow bad speeds.

## `policies.data_quality.fallback_speed_warning_threshold_percent` — Fallback speed warning threshold

- **Section:** Policy / Data Quality Guards
- **What:** Percentage of fallback-speed clients that triggers warning.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 10% is good for production.
- **Default / recommended:** `10`
- **Risk:** Too high can hide plan-detection issues.

## `policies.data_quality.warn_on_fallback_speed` — Warn on fallback speed

- **Section:** Policy / Data Quality Guards
- **What:** Warns when clients use default/fallback speed instead of comment/profile/server-derived speed.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled so incorrect plan detection is visible.
- **Default / recommended:** `true`
- **Risk:** Fallback speeds can silently assign wrong shaping.

## `policies.data_quality.warn_on_missing_ip` — Warn on missing IP

- **Section:** Policy / Data Quality Guards
- **What:** Warns when generated rows have no IPv4 address.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled because LibreQoS shaping generally needs IP mapping.
- **Default / recommended:** `true`
- **Risk:** Missing IP rows may not shape correctly.

## `policies.data_quality.warn_on_missing_mac` — Warn on missing MAC

- **Section:** Policy / Data Quality Guards
- **What:** Warns when generated rows have no MAC address.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled for better audit/identity quality.
- **Default / recommended:** `true`
- **Risk:** Some sources may not always provide MAC; this is usually warning-only.

## `policies.cleanup_sources.hotspot.collector_failed_action` — Collector failed action

- **Section:** Policy / Hotspot Cleanup
- **What:** Action when Hotspot is enabled but active-user collection fails.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use preserve_rows because a read failure is not proof users are gone.
- **Default / recommended:** `preserve_rows`
- **Risk:** Deleting on failure can remove valid active sessions.

## `policies.cleanup_sources.hotspot.enabled` — Hotspot cleanup policy

- **Section:** Policy / Hotspot Cleanup
- **What:** Enables the source-specific cleanup policy block for Hotspot. When disabled, global cleanup defaults are used for this source.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled if Hotspot should have its own behavior for inactive, disabled, failed, zero-result, and mass-removal cases.
- **Default / recommended:** `true`
- **Risk:** Disabling source-specific policies can make the source follow broader defaults that may be too aggressive or too conservative.

## `policies.cleanup_sources.hotspot.mass_removal_action` — Mass-removal action

- **Section:** Policy / Hotspot Cleanup
- **What:** Action when Hotspot removal exceeds thresholds.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** require_confirm_next_run is safest if Hotspot users are subscribers; warn_only/cleanup_next_run may fit guest sessions.
- **Default / recommended:** `require_confirm_next_run`
- **Risk:** Mass Hotspot removal may be normal after vouchers expire but should be visible.

## `policies.cleanup_sources.hotspot.normal_inactive_action` — Normal inactive action

- **Section:** Policy / Hotspot Cleanup
- **What:** Action when Hotspot active users/sessions disappear normally.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** cleanup_immediate is usually acceptable for session-style Hotspot. Use cleanup_next_run if users flap often.
- **Default / recommended:** `cleanup_immediate`
- **Risk:** Immediate cleanup may cause more applies in busy captive/session environments.

## `policies.cleanup_sources.hotspot.respect_percentage_guards` — Respect percentage/count guards

- **Section:** Policy / Hotspot Cleanup
- **What:** Controls whether mass-removal guards can override Hotspot cleanup.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Disable for highly dynamic sessions; enable for subscriber-like Hotspot use.
- **Default / recommended:** `false`
- **Risk:** Disabling guards favors speed over safety.

## `policies.cleanup_sources.hotspot.source_disabled_action` — Source disabled action

- **Section:** Policy / Hotspot Cleanup
- **What:** Action when Hotspot collection is disabled and existing Hotspot rows would disappear.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** cleanup_next_run or require_confirm_next_run are safer than immediate deletion.
- **Default / recommended:** `require_confirm_next_run`
- **Risk:** Immediate deletion can remove all Hotspot rows if disabled accidentally.

## `policies.cleanup_sources.hotspot.zero_result_action` — Zero-result action

- **Section:** Policy / Hotspot Cleanup
- **What:** Action when Hotspot scan succeeds but returns zero users.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use block_cleanup by default. If Hotspot sessions naturally become empty, override intentionally and document why.
- **Default / recommended:** `block_cleanup`
- **Risk:** warn_only with immediate cleanup can hide collector/source mistakes.

## `policies.stale_lifecycle.sources.hotspot.grace_enabled` — Hotspot optional grace

- **Section:** Policy / Hotspot Stale Lifecycle
- **What:** Enables optional grace behavior so a missing client is held for configured runs before cleanup.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep disabled by default for DHCP/Hotspot random-MAC environments. Consider enabling only for stable PPPoE usernames.
- **Default / recommended:** `false`
- **Risk:** Grace can preserve ghost rows if devices change MAC/IP.

## `policies.stale_lifecycle.sources.hotspot.grace_runs` — Hotspot grace runs

- **Section:** Policy / Hotspot Stale Lifecycle
- **What:** Number of consecutive missing runs required before cleanup when grace is enabled.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use 1 for PPPoE if you want short reconnect tolerance; use 0 for DHCP/Hotspot unless identities are stable.
- **Default / recommended:** `0`
- **Risk:** Higher values delay cleanup and may preserve stale rows.

## `policies.stale_lifecycle.sources.hotspot.identity` — Hotspot identity key

- **Section:** Policy / Hotspot Stale Lifecycle
- **What:** Identity used to decide whether a missing client is the same client if it returns later.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use username for PPPoE, server_mac for DHCP, username_or_mac for Hotspot, and manual for static rows.
- **Default / recommended:** `username_or_mac`
- **Risk:** Grace should only be enabled when identity is stable.

## `policies.stale_lifecycle.sources.hotspot.return_cancels_cleanup` — Hotspot return cancels cleanup

- **Section:** Policy / Hotspot Stale Lifecycle
- **What:** If the same identity returns before cleanup is applied, pending cleanup is cancelled.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Enable for PPPoE/stable identities. Disable for unstable DHCP identities.
- **Default / recommended:** `false`
- **Risk:** If identity is unstable, returns may not match the old row anyway.

## `policies.node_cleanup_guard.action` — Node guard action

- **Section:** Policy / Mass Removal Guards
- **What:** Action taken when one generated node exceeds node removal thresholds.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** require_confirm_next_run is safest. cleanup_next_run is faster. block_cleanup is strictest.
- **Default / recommended:** `require_confirm_next_run`
- **Risk:** cleanup_immediate here can delete many rows from one node without review.

## `policies.node_cleanup_guard.enabled` — Node removal guard

- **Section:** Policy / Mass Removal Guards
- **What:** Enables protection for individual generated nodes such as a DHCP server node, PPP plan node, or Hotspot node.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled so one node losing many clients is detected before cleanup/apply.
- **Default / recommended:** `true`
- **Risk:** Disabling can allow a broken source/node to delete many rows.

## `policies.node_cleanup_guard.min_node_size` — Minimum node size

- **Section:** Policy / Mass Removal Guards
- **What:** Minimum previous node size required before percentage-based node protection applies.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use 10 so a small node with 3 clients does not block just because 1 client disappeared.
- **Default / recommended:** `10`
- **Risk:** Too low makes small nodes noisy; too high may miss medium-size node failures.

## `policies.node_cleanup_guard.min_removed_count` — Minimum removed count

- **Section:** Policy / Mass Removal Guards
- **What:** Minimum number of removed rows required before percentage-based node protection applies.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use 3 to avoid blocking normal 1-client movement in small DHCP nodes.
- **Default / recommended:** `3`
- **Risk:** Too low causes false alarms; too high can miss real removals.

## `policies.node_cleanup_guard.threshold_percent` — Node removal threshold percent

- **Section:** Policy / Mass Removal Guards
- **What:** Percentage of clients removed from one node before the node guard can trigger.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 30% is a good default. Lower is stricter; higher is more permissive.
- **Default / recommended:** `30`
- **Risk:** Percentage alone is not enough for small nodes; min_node_size and min_removed_count also apply.

## `policies.small_node_guard.enabled` — Small-node guard

- **Section:** Policy / Mass Removal Guards
- **What:** Uses special behavior for small nodes so raw percentages do not overreact to one client disappearing.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled. It prevents cases like 1 of 3 clients removed from being treated as a dangerous 33% mass removal.
- **Default / recommended:** `true`
- **Risk:** Disabling means percentage thresholds may be noisy on tiny nodes.

## `policies.small_node_guard.full_removal_action` — Small-node full removal

- **Section:** Policy / Mass Removal Guards
- **What:** Action when all clients disappear from a small node.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** require_confirm_next_run is recommended because 100% removal, even on a small node, may indicate source/config trouble.
- **Default / recommended:** `require_confirm_next_run`
- **Risk:** cleanup_immediate can delete all rows from a small node without review.

## `policies.small_node_guard.max_node_size` — Small-node max size

- **Section:** Policy / Mass Removal Guards
- **What:** Defines what counts as a small node for small-node handling.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 5 is a practical default for small DHCP/Hotspot groups.
- **Default / recommended:** `5`
- **Risk:** Higher values make more nodes bypass normal percentage logic.

## `policies.small_node_guard.partial_removal_action` — Small-node partial removal

- **Section:** Policy / Mass Removal Guards
- **What:** Action when only some clients disappear from a small node.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** cleanup_next_run is a balanced default. cleanup_immediate is acceptable for dynamic DHCP/Hotspot if operator wants fast cleanup.
- **Default / recommended:** `cleanup_next_run`
- **Risk:** require_confirm for every small-node partial removal can create too many prompts.

## `policies.source_cleanup_guard.action` — Source guard action

- **Section:** Policy / Mass Removal Guards
- **What:** Action taken when source-wide mass-removal threshold is exceeded.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** require_confirm_next_run is recommended. block_cleanup is stricter. cleanup_immediate is not recommended for production.
- **Default / recommended:** `require_confirm_next_run`
- **Risk:** This can override source-specific immediate cleanup if respect_percentage_guards is enabled.

## `policies.source_cleanup_guard.enabled` — Source removal guard

- **Section:** Policy / Mass Removal Guards
- **What:** Protects an entire source, such as all PPPoE, all DHCP, or all Hotspot rows, from large unexpected removal.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled in production. Source-wide drops are usually high-risk unless intentionally disabled.
- **Default / recommended:** `true`
- **Risk:** Disabling removes protection against source-wide API/config mistakes.

## `policies.source_cleanup_guard.min_removed_count` — Source minimum removed count

- **Section:** Policy / Mass Removal Guards
- **What:** Minimum removed rows required before source percentage protection applies.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 5 prevents small source groups from constantly requiring confirmation.
- **Default / recommended:** `5`
- **Risk:** Too high may ignore meaningful losses in small deployments.

## `policies.source_cleanup_guard.threshold_percent` — Source threshold percent

- **Section:** Policy / Mass Removal Guards
- **What:** Percentage of a whole source that must disappear before the source guard triggers.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 30% is a good production default. Adjust higher if the source is naturally volatile.
- **Default / recommended:** `30`
- **Risk:** A threshold too high may allow accidental mass cleanup.

## `policies.cleanup_sources.pppoe.collector_failed_action` — Collector failed action

- **Section:** Policy / PPPoE Cleanup
- **What:** Action when PPPoE is enabled but MikroTik API collection fails.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use preserve_rows. API failure is not proof that subscribers are gone.
- **Default / recommended:** `preserve_rows`
- **Risk:** Deleting on collector failure can wipe valid PPPoE clients from LibreQoS.

## `policies.cleanup_sources.pppoe.enabled` — PPPoE cleanup policy

- **Section:** Policy / PPPoE Cleanup
- **What:** Enables the source-specific cleanup policy block for PPPoE. When disabled, global cleanup defaults are used for this source.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled if PPPoE should have its own behavior for inactive, disabled, failed, zero-result, and mass-removal cases.
- **Default / recommended:** `true`
- **Risk:** Disabling source-specific policies can make the source follow broader defaults that may be too aggressive or too conservative.

## `policies.cleanup_sources.pppoe.mass_removal_action` — Mass-removal action

- **Section:** Policy / PPPoE Cleanup
- **What:** Action when PPPoE removal exceeds node/source guard thresholds.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use require_confirm_next_run so the operator reviews the impact.
- **Default / recommended:** `require_confirm_next_run`
- **Risk:** Immediate mass PPPoE cleanup can remove many active subscribers if detection is wrong.

## `policies.cleanup_sources.pppoe.normal_inactive_action` — Normal inactive action

- **Section:** Policy / PPPoE Cleanup
- **What:** Action when a PPPoE account that was previously active is no longer active during a normal scan.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** cleanup_next_run is recommended because PPPoE usernames are stable but sessions can reconnect shortly.
- **Default / recommended:** `cleanup_next_run`
- **Risk:** cleanup_immediate can remove/add the same subscriber if PPP reconnects quickly.

## `policies.cleanup_sources.pppoe.respect_percentage_guards` — Respect percentage/count guards

- **Section:** Policy / PPPoE Cleanup
- **What:** Allows node/source percentage and count guards to override normal PPPoE cleanup behavior.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled for PPPoE because PPP usernames represent real subscribers.
- **Default / recommended:** `true`
- **Risk:** Turning off guards makes PPPoE cleanup more aggressive.

## `policies.cleanup_sources.pppoe.source_disabled_action` — Source disabled action

- **Section:** Policy / PPPoE Cleanup
- **What:** Action when PPPoE collection is disabled in config and existing PPPoE rows would disappear.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use require_confirm_next_run because this is an intentional but high-impact operator change.
- **Default / recommended:** `require_confirm_next_run`
- **Risk:** cleanup_immediate can remove all PPPoE rows if the source is disabled by mistake.

## `policies.cleanup_sources.pppoe.zero_result_action` — Zero-result action

- **Section:** Policy / PPPoE Cleanup
- **What:** Action when PPPoE collection succeeds but returns zero rows while enabled.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use block_cleanup or require_confirm_next_run unless zero active PPP users is normal for your network.
- **Default / recommended:** `block_cleanup`
- **Risk:** Zero result after previous success may indicate API/profile/query issues.

## `policies.stale_lifecycle.sources.pppoe.grace_enabled` — PPPoE optional grace

- **Section:** Policy / PPPoE Stale Lifecycle
- **What:** Enables optional grace behavior so a missing client is held for configured runs before cleanup.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep disabled by default for DHCP/Hotspot random-MAC environments. Consider enabling only for stable PPPoE usernames.
- **Default / recommended:** `false`
- **Risk:** Grace can preserve ghost rows if devices change MAC/IP.

## `policies.stale_lifecycle.sources.pppoe.grace_runs` — PPPoE grace runs

- **Section:** Policy / PPPoE Stale Lifecycle
- **What:** Number of consecutive missing runs required before cleanup when grace is enabled.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use 1 for PPPoE if you want short reconnect tolerance; use 0 for DHCP/Hotspot unless identities are stable.
- **Default / recommended:** `1`
- **Risk:** Higher values delay cleanup and may preserve stale rows.

## `policies.stale_lifecycle.sources.pppoe.identity` — PPPoE identity key

- **Section:** Policy / PPPoE Stale Lifecycle
- **What:** Identity used to decide whether a missing client is the same client if it returns later.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use username for PPPoE, server_mac for DHCP, username_or_mac for Hotspot, and manual for static rows.
- **Default / recommended:** `username`
- **Risk:** Grace should only be enabled when identity is stable.

## `policies.stale_lifecycle.sources.pppoe.return_cancels_cleanup` — PPPoE return cancels cleanup

- **Section:** Policy / PPPoE Stale Lifecycle
- **What:** If the same identity returns before cleanup is applied, pending cleanup is cancelled.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Enable for PPPoE/stable identities. Disable for unstable DHCP identities.
- **Default / recommended:** `true`
- **Risk:** If identity is unstable, returns may not match the old row anyway.

## `policies.decision_trace.enabled` — Decision trace

- **Section:** Policy / Policy Decision Trace
- **What:** Stores explainable trace entries showing which policy rules influenced cleanup/write/apply decisions.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled for troubleshooting and support.
- **Default / recommended:** `true`
- **Risk:** Turning off reduces audit clarity.

## `policies.decision_trace.max_items` — Max trace items

- **Section:** Policy / Policy Decision Trace
- **What:** Limits how many trace items are kept per policy decision.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 200 is enough for most deployments; increase for large networks if traces are truncated.
- **Default / recommended:** `200`
- **Risk:** Very high values can make state/log output larger.

## `policies.auto_apply_policy.allow_critical_risk` — Auto apply critical risk

- **Section:** Policy / Policy-Aware Auto Apply
- **What:** Allows automatic LibreQoS apply for critical-risk changes.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep disabled.
- **Default / recommended:** `false`
- **Risk:** Critical risk should not auto-apply in production.

## `policies.auto_apply_policy.allow_high_risk` — Auto apply high risk

- **Section:** Policy / Policy-Aware Auto Apply
- **What:** Allows automatic LibreQoS apply for high-risk changes.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep disabled.
- **Default / recommended:** `false`
- **Risk:** High-risk changes should be manually reviewed.

## `policies.auto_apply_policy.allow_low_risk` — Auto apply low risk

- **Section:** Policy / Policy-Aware Auto Apply
- **What:** Allows automatic LibreQoS apply for low-risk changes.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Enable for normal efficient operation.
- **Default / recommended:** `true`
- **Risk:** Disable if all changes must be manually applied.

## `policies.auto_apply_policy.allow_medium_risk` — Auto apply medium risk

- **Section:** Policy / Policy-Aware Auto Apply
- **What:** Allows automatic LibreQoS apply for medium-risk changes.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep disabled for production unless operator accepts more automation.
- **Default / recommended:** `false`
- **Risk:** Medium risk may include meaningful cleanup or policy warnings.

## `policies.auto_apply_policy.enabled` — Risk-aware auto apply

- **Section:** Policy / Policy-Aware Auto Apply
- **What:** Enables risk-aware auto-apply decisions using policy risk level.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled so low risk can apply while higher risk is held by policy.
- **Default / recommended:** `true`
- **Risk:** If disabled, behavior may fall back to simpler auto_apply rules.

## `policies.auto_apply_policy.when_blocked` — When auto apply is held

- **Section:** Policy / Policy-Aware Auto Apply
- **What:** Action when file changes exist but policy risk does not allow automatic LibreQoS apply.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** keep_pending_manual_apply is safest because files can be staged while apply waits for review.
- **Default / recommended:** `keep_pending_manual_apply`
- **Risk:** block_write is stricter; dry_run_only is safest for testing but may prevent live updates.

## `policies.mode` — Preset mode

- **Section:** Policy / Preset
- **What:** Selects the active policy preset. Conservative is strict, Balanced is recommended for production, Aggressive prioritizes speed, and Custom means the operator manually changed individual settings.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Start with Balanced. Use Conservative for live networks where accidental deletion is unacceptable. Use Aggressive only for lab/highly dynamic environments. Any manual policy edit should save as Custom.
- **Default / recommended:** `balanced`
- **Risk:** Changing presets can modify many cleanup/apply rules at once. Run Dry Run after applying a preset.

## `policies.recommendations.enabled` — Recommendations

- **Section:** Policy / Recommendations
- **What:** Enables operator recommendation cards.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled so the UI suggests the safest next action.
- **Default / recommended:** `true`
- **Risk:** Disabling removes helpful guidance but not enforcement.

## `policies.recommendations.show_operator_next_action` — Show operator next action

- **Section:** Policy / Recommendations
- **What:** Shows the recommended next operator action.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled.
- **Default / recommended:** `true`
- **Risk:** Operators may need to inspect raw logs without this guidance.

## `policies.recommendations.show_why_fix_messages` — Show Why/Fix messages

- **Section:** Policy / Recommendations
- **What:** Shows What/Why/Fix explanations for warnings and policy decisions.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled for operator clarity.
- **Default / recommended:** `true`
- **Risk:** Without explanations, policies can feel like hidden behavior.

## `policies.stale_lifecycle.enabled` — Stale lifecycle policy

- **Section:** Policy / Stale Lifecycle Core
- **What:** Enables stale lifecycle features as a policy group.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled so source-aware lifecycle settings are available; per-source grace can remain disabled.
- **Default / recommended:** `true`
- **Risk:** Disabling removes lifecycle visibility and grace behavior.

## `policies.cleanup_sources.static.collector_failed_action` — Collector failed action

- **Section:** Policy / Static/manual rows Cleanup
- **What:** Action when manual/static source loading fails.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** preserve_rows. Manual rows should not disappear due to a read error.
- **Default / recommended:** `preserve_rows`
- **Risk:** Deleting on load failure is unsafe.

## `policies.cleanup_sources.static.enabled` — Static/manual rows cleanup policy

- **Section:** Policy / Static/manual rows Cleanup
- **What:** Enables the source-specific cleanup policy block for Static/manual. When disabled, global cleanup defaults are used for this source.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled if Static/manual should have its own behavior for inactive, disabled, failed, zero-result, and mass-removal cases.
- **Default / recommended:** `true`
- **Risk:** Disabling source-specific policies can make the source follow broader defaults that may be too aggressive or too conservative.

## `policies.cleanup_sources.static.mass_removal_action` — Mass-removal action

- **Section:** Policy / Static/manual rows Cleanup
- **What:** Action when many static/manual rows would be removed.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** preserve_rows or require_confirm_next_run.
- **Default / recommended:** `require_confirm_next_run`
- **Risk:** Manual rows should not be mass-deleted automatically.

## `policies.cleanup_sources.static.normal_inactive_action` — Normal inactive action

- **Section:** Policy / Static/manual rows Cleanup
- **What:** Action when static/manual rows appear absent from generated data.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** preserve_rows is recommended because manual/static rows are operator-managed.
- **Default / recommended:** `preserve_rows`
- **Risk:** Automatic deletion of manual rows can remove intentionally preserved devices.

## `policies.cleanup_sources.static.respect_percentage_guards` — Respect percentage/count guards

- **Section:** Policy / Static/manual rows Cleanup
- **What:** Allows mass-removal guards to protect manual/static rows.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled.
- **Default / recommended:** `true`
- **Risk:** Disabling can allow aggressive cleanup of manual data.

## `policies.cleanup_sources.static.source_disabled_action` — Source disabled action

- **Section:** Policy / Static/manual rows Cleanup
- **What:** Action when static/manual source behavior is disabled or excluded.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** preserve_rows unless the operator explicitly confirms removal.
- **Default / recommended:** `require_confirm_next_run`
- **Risk:** Immediate cleanup can delete hand-maintained entries.

## `policies.cleanup_sources.static.zero_result_action` — Zero-result action

- **Section:** Policy / Static/manual rows Cleanup
- **What:** Action when static/manual source returns no rows.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** preserve_rows by default.
- **Default / recommended:** `preserve_rows`
- **Risk:** Zero result may be a file/path/config problem.

## `policies.stale_lifecycle.sources.static.grace_enabled` — Static/manual rows optional grace

- **Section:** Policy / Static/manual rows Stale Lifecycle
- **What:** Enables optional grace behavior so a missing client is held for configured runs before cleanup.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep disabled by default for DHCP/Hotspot random-MAC environments. Consider enabling only for stable PPPoE usernames.
- **Default / recommended:** `false`
- **Risk:** Grace can preserve ghost rows if devices change MAC/IP.

## `policies.stale_lifecycle.sources.static.grace_runs` — Static/manual rows grace runs

- **Section:** Policy / Static/manual rows Stale Lifecycle
- **What:** Number of consecutive missing runs required before cleanup when grace is enabled.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use 1 for PPPoE if you want short reconnect tolerance; use 0 for DHCP/Hotspot unless identities are stable.
- **Default / recommended:** `0`
- **Risk:** Higher values delay cleanup and may preserve stale rows.

## `policies.stale_lifecycle.sources.static.identity` — Static/manual rows identity key

- **Section:** Policy / Static/manual rows Stale Lifecycle
- **What:** Identity used to decide whether a missing client is the same client if it returns later.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Use username for PPPoE, server_mac for DHCP, username_or_mac for Hotspot, and manual for static rows.
- **Default / recommended:** `manual`
- **Risk:** Grace should only be enabled when identity is stable.

## `policies.stale_lifecycle.sources.static.return_cancels_cleanup` — Static/manual rows return cancels cleanup

- **Section:** Policy / Static/manual rows Stale Lifecycle
- **What:** If the same identity returns before cleanup is applied, pending cleanup is cancelled.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Enable for PPPoE/stable identities. Disable for unstable DHCP identities.
- **Default / recommended:** `false`
- **Risk:** If identity is unstable, returns may not match the old row anyway.

## `policies.topology_guard.block_duplicate_node_names` — Block duplicate node names

- **Section:** Policy / Topology Guards
- **What:** Blocks topology/apply when duplicate node names could collide.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled, especially with virtual/deep hierarchy.
- **Default / recommended:** `true`
- **Risk:** Duplicate names can confuse hierarchy and promotion behavior.

## `policies.topology_guard.block_missing_parent_nodes` — Block missing parent nodes

- **Section:** Policy / Topology Guards
- **What:** Blocks apply when generated Parent Node values do not exist in network.json.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled when using hierarchy modes.
- **Default / recommended:** `true`
- **Risk:** Disabling can produce unclear or broken topology placement.

## `policies.topology_guard.max_recommended_depth` — Max recommended hierarchy depth

- **Section:** Policy / Topology Guards
- **What:** Recommended maximum hierarchy depth before warnings appear.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** 4 is a good practical default.
- **Default / recommended:** `4`
- **Risk:** Higher depth may be valid but should be deliberate.

## `policies.topology_guard.warn_on_deep_hierarchy_depth` — Warn on deep hierarchy depth

- **Section:** Policy / Topology Guards
- **What:** Warns when topology depth grows beyond recommended levels.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled for readability and performance awareness.
- **Default / recommended:** `true`
- **Risk:** Very deep trees are harder to debug.

## `policies.topology_guard.warn_on_virtual_node_promotion` — Warn on virtual node promotion

- **Section:** Policy / Topology Guards
- **What:** Warns when virtual nodes may promote children to nearest physical ancestor.
- **Why:** Makes cleanup/apply behavior explicit so engine decisions follow operator intent instead of hidden defaults.
- **When effective:** Next sync cycle. Changes cleanup, write, and apply decisions; use Dry Run after risky edits.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Policy Center / Advanced JSON
- **How to use it safely:** Keep enabled so operators understand LibreQoS virtual-node behavior.
- **Default / recommended:** `true`
- **Risk:** Virtual nodes are useful but can surprise operators if not explained.

## `production_readiness.` — Production readiness scoring

- **Section:** Readiness
- **What:** Controls Dashboard readiness scoring and optional scheduler blocking behavior.
- **Why:** It turns many safety signals into one go-live summary.
- **When effective:** Next config read. config.json is the source of truth; readers use the saved value on their next read.
- **Who should change it:** Admin or owner
- **Where used:** Advanced JSON / Dashboard
- **How to use it safely:** Treat scores as guidance; do not weaken checks merely to obtain a green card.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Medium: hiding checks can make the UI overstate readiness.

## `package_quality.` — Package quality checks

- **Section:** Release integrity
- **What:** Controls optional doctor/audit script locations and release-quality checks.
- **Why:** It lets installs self-check route wiring, migrations, and stale files.
- **When effective:** Next config read. config.json is the source of truth; readers use the saved value on their next read.
- **Who should change it:** Owner or maintainer
- **Where used:** Advanced JSON / Setup & Repair
- **How to use it safely:** Keep enabled unless packaging a deliberately stripped development build.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Medium: disabling reduces self-diagnosis.

## `stable_release.` — Stable-release policy

- **Section:** Release integrity
- **What:** Describes release-candidate guardrails such as feature freeze and required checks.
- **Why:** It keeps stabilization work disciplined before a stable release.
- **When effective:** Next config read. config.json is the source of truth; readers use the saved value on their next read.
- **Who should change it:** Owner or maintainer
- **Where used:** Advanced JSON / release documentation
- **How to use it safely:** Change only when the project release policy changes, not for ordinary operations.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Low operationally, but high for release discipline.

## `routers[].` — Router source

- **Section:** Router sources
- **What:** Represents one MikroTik router, its root node, credentials, and enabled source types.
- **Why:** Routers are the primary data sources that feed generated ShapedDevices.csv and network.json.
- **When effective:** Next sync cycle. Changes source collection, generated rows, and router-owned network nodes on the next cycle.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Routers / Selected Router
- **How to use it safely:** Add one real router at a time, test connectivity, then verify Dry Run output before enabling production automation.
- **Default / recommended:** `Varies by deployment`
- **Risk:** High: router edits directly affect collection scope and generated output.
- **Related paths:** `collector.`, `network_mode`

## `routers[].dhcp.` — Router DHCP source

- **Section:** Router sources
- **What:** Enables DHCP collection and holds the configured DHCP server list for one router.
- **Why:** It is the bridge between router lease data and generated subscriber rows.
- **When effective:** Next sync cycle. Changes source collection, generated rows, and router-owned network nodes on the next cycle.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Selected Router
- **How to use it safely:** Enable only where leases should be shaped; keep server entries explicit and test discovery before production use.
- **Default / recommended:** `Varies by deployment`
- **Risk:** High: wrong enablement can add or remove many dynamic rows.
- **Related paths:** `collector.dhcp.`, `routers[].dhcp.servers[].`

## `routers[].dhcp.servers[].` — Router DHCP server source

- **Section:** Router sources
- **What:** Describes one DHCP server feed, including speed source and generated node naming.
- **Why:** Different DHCP servers may represent different sites or plans and need separate treatment.
- **When effective:** Next sync cycle. Changes source collection, generated rows, and router-owned network nodes on the next cycle.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Selected Router
- **How to use it safely:** Name each server exactly as RouterOS reports it, choose the correct plan source, then verify output in Dry Run.
- **Default / recommended:** `Varies by deployment`
- **Risk:** High: a wrong server or speed source changes generated client rows.
- **Related paths:** `collector.dhcp.`, `policies.cleanup_sources.dhcp.`

## `routers[].hotspot.` — Router Hotspot source

- **Section:** Router sources
- **What:** Defines how one router contributes Hotspot sessions/users and generated Hotspot nodes.
- **Why:** Hotspot identities and session churn differ from subscriber PPPoE behavior.
- **When effective:** Next sync cycle. Changes source collection, generated rows, and router-owned network nodes on the next cycle.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Selected Router
- **How to use it safely:** Use node names and metadata behavior that match the real Hotspot design; preview before enabling cleanup automation.
- **Default / recommended:** `Varies by deployment`
- **Risk:** High: wrong settings can create unstable or misleading generated rows.
- **Related paths:** `collector.hotspot.`, `policies.cleanup_sources.hotspot.`

## `routers[].password` — RouterOS password

- **Section:** Router sources
- **What:** Credential used by the read-only RouterOS API client.
- **Why:** Without it the collector cannot read source data from that router.
- **When effective:** Next sync cycle. Changes source collection, generated rows, and router-owned network nodes on the next cycle.
- **Who should change it:** Owner or trusted admin
- **Where used:** Config Center → Selected Router / Advanced JSON
- **How to use it safely:** Use a least-privilege API account, protect config.json permissions, and never share raw screenshots containing secrets.
- **Default / recommended:** `No universal default`
- **Risk:** Critical secret: disclosure gives credential material to another actor.
- **Related paths:** `routers[].username`, `routers[].address`, `routers[].port`

## `routers[].pppoe.` — Router PPPoE source

- **Section:** Router sources
- **What:** Defines how one router contributes PPPoE clients and optional PPPoE grouping nodes.
- **Why:** Source-level settings decide which subscribers become generated rows and how they are grouped.
- **When effective:** Next sync cycle. Changes source collection, generated rows, and router-owned network nodes on the next cycle.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Selected Router
- **How to use it safely:** Enable only on routers where PPPoE data should feed LibreQoS; use Dry Run after changing node naming or factor rules.
- **Default / recommended:** `Varies by deployment`
- **Risk:** High: wrong source or naming settings change generated subscribers and topology.
- **Related paths:** `collector.pppoe.`, `policies.cleanup_sources.pppoe.`

## `access_control.` — Access-control summary

- **Section:** Security
- **What:** Documents role intent and owner-only route summaries inside config.json.
- **Why:** It keeps install metadata aligned with the role model shown to operators.
- **When effective:** Next config read. config.json is the source of truth; readers use the saved value on their next read.
- **Who should change it:** Owner or maintainer
- **Where used:** Advanced JSON / user-management docs
- **How to use it safely:** Treat this as descriptive metadata; route decorators remain the real enforcement layer.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Low runtime risk, but stale descriptions mislead operators.

## `config_validation.` — Config validation

- **Section:** Validation
- **What:** Controls schema validation, config health display, and save-time simulation behavior.
- **Why:** It protects config.json from structurally unsafe edits.
- **When effective:** Next config read. config.json is the source of truth; readers use the saved value on their next read.
- **Who should change it:** Owner or install admin
- **Where used:** Advanced JSON / Config Center
- **How to use it safely:** Keep validation and schema blocking enabled; disable only for a controlled migration window.
- **Default / recommended:** `Varies by deployment`
- **Risk:** High if weakened: malformed config can be saved more easily.

## `preflight.` — Preflight validation

- **Section:** Validation
- **What:** Controls validation gates before output write/apply decisions.
- **Why:** It catches structurally unsafe output before production state changes.
- **When effective:** Next sync cycle. Changes validation gates before file write/apply decisions.
- **Who should change it:** Admin or owner
- **Where used:** Config Center → Defaults / Preflight
- **How to use it safely:** Keep blocking behavior for invalid bandwidth or missing parents unless a qualified admin has a specific reason.
- **Default / recommended:** `Varies by deployment`
- **Risk:** High when weakened: malformed output can reach production.
- **Related paths:** `policies.apply_guard.`, `network_mode`

## `ui.` — UI preference

- **Section:** WebUI
- **What:** Controls presentation defaults such as theme, refresh rate, and advanced-view visibility.
- **Why:** Presentation should be configurable without changing engine truth.
- **When effective:** Next page render. Changes presentation defaults used on later page loads.
- **Who should change it:** Admin or owner
- **Where used:** Advanced JSON / WebUI
- **How to use it safely:** Use these for operator comfort only; do not treat UI values as engine policy.
- **Default / recommended:** `Varies by deployment`
- **Risk:** Low.
