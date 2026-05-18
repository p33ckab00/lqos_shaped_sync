"""Schema, presets, and helpers for visible Smart Policy Center settings.

The schema is the single source of truth for Policy Center UI, config
migration/validation, preset comparison, and documentation helpers. Runtime
policy decisions are still evaluated by ``engine.policy_engine``; this module is
for operator-configurable policy settings.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from engine.policy_defaults import CLEANUP_ACTIONS, POLICY_PRESETS, smart_policy_defaults
from engine.setup_repair import apply_policy_preset

POLICY_ACTION_CHOICES = list(CLEANUP_ACTIONS)
PRESET_CHOICES = ["conservative", "balanced", "aggressive", "custom"]


def field(path: str, label: str, field_type: str, *, section: str, description: str = "", choices: list[str] | None = None, recommended: Any = None, risk: str = "medium", minimum: int | float | None = None, maximum: int | float | None = None, setup_guidance: str = "", risk_note: str = "") -> dict[str, Any]:
    return {
        "path": path,
        "label": label,
        "type": field_type,
        "section": section,
        "description": description,
        "setup_guidance": setup_guidance,
        "risk_note": risk_note,
        "choices": choices or [],
        "recommended": recommended,
        "risk": risk,
        "min": minimum,
        "max": maximum,
    }


POLICY_SCHEMA: list[dict[str, Any]] = [
    field("policies.mode", "Preset mode", "select", section="Preset", choices=PRESET_CHOICES, recommended="balanced", risk="low", description="Preset or custom policy profile. Manual edits should switch this to Custom."),
    field("policies.cleanup.enabled", "Cleanup policy engine", "bool", section="Cleanup Core", recommended=True, risk="high", description="When enabled, cleanup actions are evaluated by source/reason before file write/apply."),
    field("policies.cleanup.global_default_action", "Global default cleanup action", "select", section="Cleanup Core", choices=POLICY_ACTION_CHOICES, recommended="require_confirm_next_run", risk="high", description="Fallback action when no source-specific cleanup policy matches."),
    field("policies.cleanup.confirmation_expires_hours", "Confirmation expiry hours", "number", section="Cleanup Core", recommended=24, risk="medium", minimum=1, maximum=720, description="How long pending cleanup confirmations remain valid."),
    field("policies.cleanup.apply_confirmed_cleanup", "Confirmed cleanup apply mode", "select", section="Cleanup Core", choices=["immediate", "next_run"], recommended="next_run", risk="medium", description="Whether confirmed cleanup should happen immediately or on the next successful run."),
    field("policies.cleanup.allow_immediate_cleanup", "Allow immediate cleanup", "bool", section="Cleanup Core", recommended=True, risk="high", description="Master switch allowing policies to delete absent rows in the same sync cycle."),
]

for source, label in [
    ("pppoe", "PPPoE"),
    ("dhcp", "DHCP"),
    ("hotspot", "Hotspot"),
    ("static", "Static/manual rows"),
]:
    sec = f"{label} Cleanup"
    POLICY_SCHEMA.extend([
        field(f"policies.cleanup_sources.{source}.enabled", f"{label} cleanup policy", "bool", section=sec, recommended=True, risk="medium", description=f"Enable source-specific cleanup policy for {label}."),
        field(f"policies.cleanup_sources.{source}.normal_inactive_action", "Normal inactive action", "select", section=sec, choices=POLICY_ACTION_CHOICES, recommended="cleanup_next_run" if source == "pppoe" else ("cleanup_immediate" if source in {"dhcp", "hotspot"} else "preserve_rows"), risk="high", description="Action when a previously active row is absent for normal/expected reasons."),
        field(f"policies.cleanup_sources.{source}.source_disabled_action", "Source disabled action", "select", section=sec, choices=POLICY_ACTION_CHOICES, recommended="require_confirm_next_run", risk="high", description="Action when this source is disabled in config and existing rows would disappear."),
        field(f"policies.cleanup_sources.{source}.collector_failed_action", "Collector failed action", "select", section=sec, choices=POLICY_ACTION_CHOICES, recommended="preserve_rows", risk="critical", description="Action when the source is enabled but collection failed. Preserve rows is safest."),
        field(f"policies.cleanup_sources.{source}.zero_result_action", "Zero-result action", "select", section=sec, choices=POLICY_ACTION_CHOICES, recommended="block_cleanup" if source in {"pppoe", "dhcp", "hotspot"} else "preserve_rows", risk="critical", description="Action when a source is enabled and scan succeeds but returns zero rows."),
        field(f"policies.cleanup_sources.{source}.mass_removal_action", "Mass-removal action", "select", section=sec, choices=POLICY_ACTION_CHOICES, recommended="require_confirm_next_run", risk="high", description="Action when source/node removal thresholds are exceeded."),
        field(f"policies.cleanup_sources.{source}.respect_percentage_guards", "Respect percentage/count guards", "bool", section=sec, recommended=(source in {"pppoe", "static"}), risk="medium", description="When enabled, node/source mass-removal percentage guards can override normal cleanup behavior."),
    ])

POLICY_SCHEMA.extend([
    field("policies.node_cleanup_guard.enabled", "Node removal guard", "bool", section="Mass Removal Guards", recommended=True, risk="high", description="Protect individual generated nodes from large unexpected removals."),
    field("policies.node_cleanup_guard.threshold_percent", "Node removal threshold percent", "number", section="Mass Removal Guards", recommended=30, risk="high", minimum=1, maximum=100, description="Percentage of a node that must disappear before the node guard can trigger."),
    field("policies.node_cleanup_guard.min_node_size", "Minimum node size", "number", section="Mass Removal Guards", recommended=10, risk="medium", minimum=1, description="Ignore percentage guard for nodes smaller than this size."),
    field("policies.node_cleanup_guard.min_removed_count", "Minimum removed count", "number", section="Mass Removal Guards", recommended=3, risk="medium", minimum=1, description="Ignore percentage guard unless at least this many rows are removed."),
    field("policies.node_cleanup_guard.action", "Node guard action", "select", section="Mass Removal Guards", choices=POLICY_ACTION_CHOICES, recommended="require_confirm_next_run", risk="high", description="Action when node removal threshold is exceeded."),
    field("policies.small_node_guard.enabled", "Small-node guard", "bool", section="Mass Removal Guards", recommended=True, risk="medium", description="Use count/full-removal behavior for small nodes instead of raw percentage only."),
    field("policies.small_node_guard.max_node_size", "Small-node max size", "number", section="Mass Removal Guards", recommended=5, risk="medium", minimum=1, description="Nodes at or below this size use small-node behavior."),
    field("policies.small_node_guard.partial_removal_action", "Small-node partial removal", "select", section="Mass Removal Guards", choices=POLICY_ACTION_CHOICES, recommended="cleanup_next_run", risk="medium", description="Action when part of a small node disappears."),
    field("policies.small_node_guard.full_removal_action", "Small-node full removal", "select", section="Mass Removal Guards", choices=POLICY_ACTION_CHOICES, recommended="require_confirm_next_run", risk="high", description="Action when all clients from a small node disappear."),
    field("policies.source_cleanup_guard.enabled", "Source removal guard", "bool", section="Mass Removal Guards", recommended=True, risk="high", description="Protect whole PPP/DHCP/Hotspot sources from large unexpected removals."),
    field("policies.source_cleanup_guard.threshold_percent", "Source threshold percent", "number", section="Mass Removal Guards", recommended=30, risk="high", minimum=1, maximum=100, description="Percentage of a whole source that must disappear before source guard can trigger."),
    field("policies.source_cleanup_guard.min_removed_count", "Source minimum removed count", "number", section="Mass Removal Guards", recommended=5, risk="medium", minimum=1, description="Ignore source percentage guard unless at least this many rows are removed."),
    field("policies.source_cleanup_guard.action", "Source guard action", "select", section="Mass Removal Guards", choices=POLICY_ACTION_CHOICES, recommended="require_confirm_next_run", risk="high", description="Action when source removal threshold is exceeded."),
])

for section_key, section_label, entries in [
    ("apply_guard", "Apply Guards", [
        ("block_apply_on_collector_failure", "Block apply on collector failure", "bool", True, "critical"),
        ("block_apply_on_missing_parent", "Block apply on missing parent", "bool", True, "critical"),
        ("block_apply_on_duplicate_ip", "Block apply on duplicate IP", "bool", True, "critical"),
        ("block_apply_on_invalid_speed", "Block apply on invalid speed", "bool", True, "critical"),
        ("require_manual_confirm_on_medium_risk", "Require manual confirm on medium risk", "bool", True, "high"),
        ("allow_auto_apply_on_low_risk", "Allow auto-apply on low risk", "bool", True, "medium"),
    ]),
    ("collector_guard", "Collector Guards", [
        ("block_cleanup_if_source_failed", "Block cleanup if source failed", "bool", True, "critical"),
        ("block_cleanup_if_enabled_source_returns_zero", "Block cleanup if enabled source returns zero", "bool", True, "critical"),
        ("block_cleanup_if_source_returns_zero_after_previous_success", "Block zero-after-success cleanup", "bool", True, "critical"),
        ("zero_source_drop_threshold_percent", "Zero-source drop threshold percent", "number", 80, "high"),
        ("warn_if_router_api_slow_ms", "Warn if router API slow ms", "number", 2000, "medium"),
    ]),
    ("data_quality", "Data Quality Guards", [
        ("warn_on_fallback_speed", "Warn on fallback speed", "bool", True, "medium"),
        ("fallback_speed_warning_threshold_percent", "Fallback speed warning threshold", "number", 10, "medium"),
        ("block_if_fallback_speed_threshold_percent", "Block if fallback speed threshold", "number", 50, "high"),
        ("warn_on_missing_mac", "Warn on missing MAC", "bool", True, "low"),
        ("warn_on_missing_ip", "Warn on missing IP", "bool", True, "medium"),
    ]),
    ("topology_guard", "Topology Guards", [
        ("block_missing_parent_nodes", "Block missing parent nodes", "bool", True, "critical"),
        ("block_duplicate_node_names", "Block duplicate node names", "bool", True, "critical"),
        ("warn_on_virtual_node_promotion", "Warn on virtual node promotion", "bool", True, "medium"),
        ("warn_on_deep_hierarchy_depth", "Warn on deep hierarchy depth", "bool", True, "medium"),
        ("max_recommended_depth", "Max recommended hierarchy depth", "number", 4, "medium"),
    ]),
    ("backup_guard", "Backup Policy", [
        ("require_backup_before_apply", "Require backup before apply", "bool", False, "medium"),
        ("warn_if_backup_disabled_while_auto_apply_enabled", "Warn if optional backups are disabled", "bool", False, "low"),
        ("minimum_backup_retention", "Minimum backup retention when enabled", "number", 10, "low"),
    ]),
    ("anomaly_detection", "Anomaly Detection", [
        ("enabled", "Anomaly detection", "bool", True, "medium"),
        ("compare_with_last_successful_run", "Compare with last successful run", "bool", True, "medium"),
        ("warn_if_client_count_drops_percent", "Warn if client count drops percent", "number", 30, "high"),
        ("warn_if_sync_duration_increases_multiplier", "Warn if sync duration multiplier", "number", 5, "medium"),
        ("warn_if_apply_duration_increases_multiplier", "Warn if apply duration multiplier", "number", 5, "medium"),
    ]),
    ("recommendations", "Recommendations", [
        ("enabled", "Recommendations", "bool", True, "low"),
        ("show_why_fix_messages", "Show Why/Fix messages", "bool", True, "low"),
        ("show_operator_next_action", "Show operator next action", "bool", True, "low"),
    ]),
]:
    for key, label, typ, rec, risk in entries:
        POLICY_SCHEMA.append(field(f"policies.{section_key}.{key}", label, typ, section=section_label, recommended=rec, risk=risk, description="Visible operator policy setting saved to config.json."))


# v2.50 policy intelligence settings: optional stale/grace lifecycle and risk-aware auto apply.
for source, label, default_identity in [
    ("pppoe", "PPPoE", "username"),
    ("dhcp", "DHCP", "server_mac"),
    ("hotspot", "Hotspot", "username_or_mac"),
    ("static", "Static/manual rows", "manual"),
]:
    sec = f"{label} Stale Lifecycle"
    POLICY_SCHEMA.extend([
        field(f"policies.stale_lifecycle.sources.{source}.identity", f"{label} identity key", "select", section=sec, choices=["username", "server_mac", "username_or_mac", "manual"], recommended=default_identity, risk="medium", description="Identity used when reasoning about stale/returned clients. Grace is safest only when identity is stable."),
        field(f"policies.stale_lifecycle.sources.{source}.grace_enabled", f"{label} optional grace", "bool", section=sec, recommended=False, risk="high", description="When enabled, normal inactive cleanup waits for the configured grace runs before removal. Disabled by default for DHCP/Hotspot to avoid ghost rows with randomized MACs."),
        field(f"policies.stale_lifecycle.sources.{source}.grace_runs", f"{label} grace runs", "number", section=sec, recommended=1 if source == "pppoe" else 0, risk="medium", minimum=0, maximum=10, description="How many consecutive missing runs are required before cleanup is allowed when optional grace is enabled."),
        field(f"policies.stale_lifecycle.sources.{source}.return_cancels_cleanup", f"{label} return cancels cleanup", "bool", section=sec, recommended=(source == "pppoe"), risk="low", description="If the same identity returns before cleanup, clear stale/pending cleanup lifecycle state."),
    ])

POLICY_SCHEMA.extend([
    field("policies.stale_lifecycle.enabled", "Stale lifecycle policy", "bool", section="Stale Lifecycle Core", recommended=True, risk="medium", description="Enables optional source-aware stale lifecycle behavior. Grace remains disabled by default per source unless operator enables it."),
    field("policies.auto_apply_policy.enabled", "Risk-aware auto apply", "bool", section="Policy-Aware Auto Apply", recommended=True, risk="high", description="When enabled, LibreQoS auto-apply is allowed or held pending based on policy risk level."),
    field("policies.auto_apply_policy.allow_low_risk", "Auto apply low risk", "bool", section="Policy-Aware Auto Apply", recommended=True, risk="low", description="Allow automatic LibreQoS apply when policy risk is low."),
    field("policies.auto_apply_policy.allow_medium_risk", "Auto apply medium risk", "bool", section="Policy-Aware Auto Apply", recommended=False, risk="medium", description="Allow automatic LibreQoS apply when policy risk is medium. Recommended off for production."),
    field("policies.auto_apply_policy.allow_high_risk", "Auto apply high risk", "bool", section="Policy-Aware Auto Apply", recommended=False, risk="high", description="Allow automatic LibreQoS apply when policy risk is high. Recommended off."),
    field("policies.auto_apply_policy.allow_critical_risk", "Auto apply critical risk", "bool", section="Policy-Aware Auto Apply", recommended=False, risk="critical", description="Allow automatic LibreQoS apply when policy risk is critical. Recommended off."),
    field("policies.auto_apply_policy.when_blocked", "When auto apply is held", "select", section="Policy-Aware Auto Apply", choices=["keep_pending_manual_apply", "block_write", "dry_run_only"], recommended="keep_pending_manual_apply", risk="high", description="Behavior when files are written but policy risk does not allow auto LibreQoS apply. keep_pending_manual_apply is safest."),
    field("policies.decision_trace.enabled", "Decision trace", "bool", section="Policy Decision Trace", recommended=True, risk="low", description="Store explainable policy trace entries showing which rules influenced cleanup/write/apply decisions."),
    field("policies.decision_trace.max_items", "Max trace items", "number", section="Policy Decision Trace", recommended=200, risk="low", minimum=10, maximum=2000, description="Maximum number of decision trace entries to keep in a single policy decision."),
])



# v2.54.2: Atomic operator explanations for every Policy Center setting.
# The UI and documentation use these fields so Policy Center is a setup guide,
# not just a list of raw config keys.
ACTION_EXPLANATIONS = {
    "preserve_rows": "Keep existing rows and do not delete stale entries. Safest when the source may be temporarily unavailable.",
    "warn_only": "Show a warning but do not remove rows. Useful while tuning policies.",
    "cleanup_immediate": "Remove stale rows in the same sync cycle. Fastest, but can cause more LibreQoS applies if clients flap.",
    "cleanup_next_run": "Mark stale rows and remove them on the next successful run. Safer than immediate cleanup.",
    "require_confirm_immediate": "Ask operator confirmation first, then allow same-cycle cleanup after confirmation.",
    "require_confirm_next_run": "Ask operator confirmation first, then apply cleanup on the next successful run. Recommended for risky changes.",
    "block_cleanup": "Prevent cleanup. Existing rows are preserved until the issue is fixed or policy is changed.",
    "block_apply": "Block LibreQoS apply for this condition. Used for dangerous validation failures.",
}

ATOMIC_POLICY_EXPLANATIONS = {
    "policies.mode": (
        "Selects the active policy preset. Conservative is strict, Balanced is recommended for production, Aggressive prioritizes speed, and Custom means the operator manually changed individual settings.",
        "Start with Balanced. Use Conservative for live networks where accidental deletion is unacceptable. Use Aggressive only for lab/highly dynamic environments. Any manual policy edit should save as Custom.",
        "Changing presets can modify many cleanup/apply rules at once. Run Dry Run after applying a preset."
    ),
    "policies.cleanup.enabled": (
        "Turns the Smart Cleanup Policy Engine on or off. When enabled, LQoSync classifies why rows are stale before deciding whether to delete, preserve, confirm, or block.",
        "Keep enabled. Disabling this returns cleanup behavior closer to simple sync logic and removes important protection.",
        "Disabling cleanup intelligence can allow unintended stale-row removal depending on older code paths."
    ),
    "policies.cleanup.global_default_action": (
        "Fallback cleanup action used when no source-specific or reason-specific policy matches a cleanup candidate.",
        "Use require_confirm_next_run for conservative production behavior. Use cleanup_next_run for a faster but still staged workflow.",
        "Avoid cleanup_immediate as the global default unless the operator accepts fast deletion for all sources."
    ),
    "policies.cleanup.confirmation_expires_hours": (
        "Controls how long a pending cleanup confirmation remains valid before the operator must confirm again.",
        "24 hours is a good default. Use shorter values if many operators change config; use longer values for planned migrations.",
        "Very long expiry can apply an old confirmation after the network/config has changed."
    ),
    "policies.cleanup.apply_confirmed_cleanup": (
        "Controls when cleanup happens after the operator confirms a pending cleanup decision.",
        "Use next_run for production so LQoSync re-checks current config and source state before deleting. Use immediate for urgent manual cleanup.",
        "Immediate confirmed cleanup can remove rows before another full collection confirms the condition."
    ),
    "policies.cleanup.allow_immediate_cleanup": (
        "Master permission that allows any policy to delete stale rows in the same sync cycle.",
        "Enable if DHCP/Hotspot should update quickly. Disable if all deletions must be staged or confirmed first.",
        "If enabled with aggressive source policies, dynamic clients can cause more file churn and LibreQoS applies."
    ),
    "policies.node_cleanup_guard.enabled": (
        "Enables protection for individual generated nodes such as a DHCP server node, PPP plan node, or Hotspot node.",
        "Keep enabled so one node losing many clients is detected before cleanup/apply.",
        "Disabling can allow a broken source/node to delete many rows."
    ),
    "policies.node_cleanup_guard.threshold_percent": (
        "Percentage of clients removed from one node before the node guard can trigger.",
        "30% is a good default. Lower is stricter; higher is more permissive.",
        "Percentage alone is not enough for small nodes; min_node_size and min_removed_count also apply."
    ),
    "policies.node_cleanup_guard.min_node_size": (
        "Minimum previous node size required before percentage-based node protection applies.",
        "Use 10 so a small node with 3 clients does not block just because 1 client disappeared.",
        "Too low makes small nodes noisy; too high may miss medium-size node failures."
    ),
    "policies.node_cleanup_guard.min_removed_count": (
        "Minimum number of removed rows required before percentage-based node protection applies.",
        "Use 3 to avoid blocking normal 1-client movement in small DHCP nodes.",
        "Too low causes false alarms; too high can miss real removals."
    ),
    "policies.node_cleanup_guard.action": (
        "Action taken when one generated node exceeds node removal thresholds.",
        "require_confirm_next_run is safest. cleanup_next_run is faster. block_cleanup is strictest.",
        "cleanup_immediate here can delete many rows from one node without review."
    ),
    "policies.small_node_guard.enabled": (
        "Uses special behavior for small nodes so raw percentages do not overreact to one client disappearing.",
        "Keep enabled. It prevents cases like 1 of 3 clients removed from being treated as a dangerous 33% mass removal.",
        "Disabling means percentage thresholds may be noisy on tiny nodes."
    ),
    "policies.small_node_guard.max_node_size": (
        "Defines what counts as a small node for small-node handling.",
        "5 is a practical default for small DHCP/Hotspot groups.",
        "Higher values make more nodes bypass normal percentage logic."
    ),
    "policies.small_node_guard.partial_removal_action": (
        "Action when only some clients disappear from a small node.",
        "cleanup_next_run is a balanced default. cleanup_immediate is acceptable for dynamic DHCP/Hotspot if operator wants fast cleanup.",
        "require_confirm for every small-node partial removal can create too many prompts."
    ),
    "policies.small_node_guard.full_removal_action": (
        "Action when all clients disappear from a small node.",
        "require_confirm_next_run is recommended because 100% removal, even on a small node, may indicate source/config trouble.",
        "cleanup_immediate can delete all rows from a small node without review."
    ),
    "policies.source_cleanup_guard.enabled": (
        "Protects an entire source, such as all PPPoE, all DHCP, or all Hotspot rows, from large unexpected removal.",
        "Keep enabled in production. Source-wide drops are usually high-risk unless intentionally disabled.",
        "Disabling removes protection against source-wide API/config mistakes."
    ),
    "policies.source_cleanup_guard.threshold_percent": (
        "Percentage of a whole source that must disappear before the source guard triggers.",
        "30% is a good production default. Adjust higher if the source is naturally volatile.",
        "A threshold too high may allow accidental mass cleanup."
    ),
    "policies.source_cleanup_guard.min_removed_count": (
        "Minimum removed rows required before source percentage protection applies.",
        "5 prevents small source groups from constantly requiring confirmation.",
        "Too high may ignore meaningful losses in small deployments."
    ),
    "policies.source_cleanup_guard.action": (
        "Action taken when source-wide mass-removal threshold is exceeded.",
        "require_confirm_next_run is recommended. block_cleanup is stricter. cleanup_immediate is not recommended for production.",
        "This can override source-specific immediate cleanup if respect_percentage_guards is enabled."
    ),
}

SOURCE_EXPLANATIONS = {
    "pppoe": {
        "normal_inactive_action": ("Action when a PPPoE account that was previously active is no longer active during a normal scan.", "cleanup_next_run is recommended because PPPoE usernames are stable but sessions can reconnect shortly.", "cleanup_immediate can remove/add the same subscriber if PPP reconnects quickly."),
        "source_disabled_action": ("Action when PPPoE collection is disabled in config and existing PPPoE rows would disappear.", "Use require_confirm_next_run because this is an intentional but high-impact operator change.", "cleanup_immediate can remove all PPPoE rows if the source is disabled by mistake."),
        "collector_failed_action": ("Action when PPPoE is enabled but MikroTik API collection fails.", "Use preserve_rows. API failure is not proof that subscribers are gone.", "Deleting on collector failure can wipe valid PPPoE clients from LibreQoS."),
        "zero_result_action": ("Action when PPPoE collection succeeds but returns zero rows while enabled.", "Use block_cleanup or require_confirm_next_run unless zero active PPP users is normal for your network.", "Zero result after previous success may indicate API/profile/query issues."),
        "mass_removal_action": ("Action when PPPoE removal exceeds node/source guard thresholds.", "Use require_confirm_next_run so the operator reviews the impact.", "Immediate mass PPPoE cleanup can remove many active subscribers if detection is wrong."),
        "respect_percentage_guards": ("Allows node/source percentage and count guards to override normal PPPoE cleanup behavior.", "Keep enabled for PPPoE because PPP usernames represent real subscribers.", "Turning off guards makes PPPoE cleanup more aggressive."),
    },
    "dhcp": {
        "normal_inactive_action": ("Action when a DHCP lease/client disappears during normal operation.", "Use cleanup_immediate for dynamic/PisoWiFi-style DHCP, or cleanup_next_run for subscriber DHCP.", "Immediate cleanup is fast but can increase LibreQoS apply frequency if leases flap."),
        "source_disabled_action": ("Action when DHCP collection or a DHCP server source is disabled and existing DHCP rows would disappear.", "Use require_confirm_next_run because disabling a source can remove many rows intentionally.", "Immediate cleanup can remove rows because of a config mistake."),
        "collector_failed_action": ("Action when DHCP is enabled but lease collection fails.", "Use preserve_rows. Failure to read leases is not proof that clients are gone.", "Deleting rows on failed collection can remove valid clients."),
        "zero_result_action": ("Action when DHCP scan succeeds but returns zero leases while DHCP is enabled.", "Use block_cleanup by default. A zero result may mean VLAN/API/DHCP source issue.", "cleanup_immediate can wipe DHCP rows if the scan result is wrong."),
        "mass_removal_action": ("Action when DHCP removal exceeds source/node guard thresholds.", "require_confirm_next_run is safest. If DHCP is intentionally dynamic, adjust respect_percentage_guards.", "Mass DHCP cleanup can be normal in guest networks but dangerous in subscriber networks."),
        "respect_percentage_guards": ("Controls whether mass-removal guards can override DHCP normal cleanup.", "Disable for highly dynamic DHCP; enable for subscriber DHCP.", "Disabling guards makes DHCP cleanup faster but less protected."),
    },
    "hotspot": {
        "normal_inactive_action": ("Action when Hotspot active users/sessions disappear normally.", "cleanup_immediate is usually acceptable for session-style Hotspot. Use cleanup_next_run if users flap often.", "Immediate cleanup may cause more applies in busy captive/session environments."),
        "source_disabled_action": ("Action when Hotspot collection is disabled and existing Hotspot rows would disappear.", "cleanup_next_run or require_confirm_next_run are safer than immediate deletion.", "Immediate deletion can remove all Hotspot rows if disabled accidentally."),
        "collector_failed_action": ("Action when Hotspot is enabled but active-user collection fails.", "Use preserve_rows because a read failure is not proof users are gone.", "Deleting on failure can remove valid active sessions."),
        "zero_result_action": ("Action when Hotspot scan succeeds but returns zero users.", "Use block_cleanup by default. If Hotspot sessions naturally become empty, override intentionally and document why.", "warn_only with immediate cleanup can hide collector/source mistakes."),
        "mass_removal_action": ("Action when Hotspot removal exceeds thresholds.", "require_confirm_next_run is safest if Hotspot users are subscribers; warn_only/cleanup_next_run may fit guest sessions.", "Mass Hotspot removal may be normal after vouchers expire but should be visible."),
        "respect_percentage_guards": ("Controls whether mass-removal guards can override Hotspot cleanup.", "Disable for highly dynamic sessions; enable for subscriber-like Hotspot use.", "Disabling guards favors speed over safety."),
    },
    "static": {
        "normal_inactive_action": ("Action when static/manual rows appear absent from generated data.", "preserve_rows is recommended because manual/static rows are operator-managed.", "Automatic deletion of manual rows can remove intentionally preserved devices."),
        "source_disabled_action": ("Action when static/manual source behavior is disabled or excluded.", "preserve_rows unless the operator explicitly confirms removal.", "Immediate cleanup can delete hand-maintained entries."),
        "collector_failed_action": ("Action when manual/static source loading fails.", "preserve_rows. Manual rows should not disappear due to a read error.", "Deleting on load failure is unsafe."),
        "zero_result_action": ("Action when static/manual source returns no rows.", "preserve_rows by default.", "Zero result may be a file/path/config problem."),
        "mass_removal_action": ("Action when many static/manual rows would be removed.", "preserve_rows or require_confirm_next_run.", "Manual rows should not be mass-deleted automatically."),
        "respect_percentage_guards": ("Allows mass-removal guards to protect manual/static rows.", "Keep enabled.", "Disabling can allow aggressive cleanup of manual data."),
    },
}

GENERAL_EXPLANATIONS = {
    "apply_guard.block_apply_on_collector_failure": ("Prevents LibreQoS apply when a source collector failed and output may be incomplete.", "Keep enabled in production.", "Applying after collector failure can remove valid clients from shaping."),
    "apply_guard.block_apply_on_missing_parent": ("Blocks apply when ShapedDevices rows reference Parent Nodes missing from network.json.", "Keep enabled. Fix topology or parent naming before applying.", "Missing parents can break expected hierarchy/shaping placement."),
    "apply_guard.block_apply_on_duplicate_ip": ("Blocks apply when duplicate IPv4 values are detected in generated rows.", "Keep enabled unless duplicates are intentionally handled elsewhere.", "Duplicate IPs can cause wrong shaping assignment."),
    "apply_guard.block_apply_on_invalid_speed": ("Blocks apply when speed values cannot be parsed or are invalid.", "Keep enabled. Fix plan comments/profile names/default speeds.", "Invalid speeds can create bad or failed LibreQoS config."),
    "apply_guard.require_manual_confirm_on_medium_risk": ("Requires operator review for medium-risk policy outcomes.", "Keep enabled for production. Disable only if you want more automation.", "Disabling lets medium-risk changes auto-apply if other settings allow it."),
    "apply_guard.allow_auto_apply_on_low_risk": ("Allows low-risk changes to run LibreQoS automatically.", "Enable for efficient normal operations.", "Disable if you want every apply to be manual."),
    "collector_guard.block_cleanup_if_source_failed": ("Stops cleanup for a source when its collection failed.", "Keep enabled. Preserve rows until a successful scan confirms state.", "Disabling can delete clients because of temporary API failure."),
    "collector_guard.block_cleanup_if_enabled_source_returns_zero": ("Stops cleanup when an enabled source returns zero rows.", "Keep enabled unless a source naturally returns zero often.", "A zero result can be a collector/router/VLAN problem."),
    "collector_guard.block_cleanup_if_source_returns_zero_after_previous_success": ("Blocks cleanup when a source that previously had rows suddenly returns zero.", "Keep enabled. This catches sudden source loss.", "Disabling can wipe a source after an anomaly."),
    "collector_guard.zero_source_drop_threshold_percent": ("Defines the drop percentage considered suspicious when a source goes near-zero.", "80% catches extreme drops while allowing normal changes.", "Too low causes noise; too high may miss failures."),
    "collector_guard.warn_if_router_api_slow_ms": ("Warns when MikroTik API collection time is slower than expected.", "2000 ms is a practical warning threshold.", "Slow API can indicate router load, network issue, or timeout risk."),
    "data_quality.warn_on_fallback_speed": ("Warns when clients use default/fallback speed instead of comment/profile/server-derived speed.", "Keep enabled so incorrect plan detection is visible.", "Fallback speeds can silently assign wrong shaping."),
    "data_quality.fallback_speed_warning_threshold_percent": ("Percentage of fallback-speed clients that triggers warning.", "10% is good for production.", "Too high can hide plan-detection issues."),
    "data_quality.block_if_fallback_speed_threshold_percent": ("Percentage of fallback-speed clients that blocks apply.", "50% catches severe speed-source failures.", "Blocking too low can interrupt normal migration; too high may allow bad speeds."),
    "data_quality.warn_on_missing_mac": ("Warns when generated rows have no MAC address.", "Keep enabled for better audit/identity quality.", "Some sources may not always provide MAC; this is usually warning-only."),
    "data_quality.warn_on_missing_ip": ("Warns when generated rows have no IPv4 address.", "Keep enabled because LibreQoS shaping generally needs IP mapping.", "Missing IP rows may not shape correctly."),
    "topology_guard.block_missing_parent_nodes": ("Blocks apply when generated Parent Node values do not exist in network.json.", "Keep enabled when using hierarchy modes.", "Disabling can produce unclear or broken topology placement."),
    "topology_guard.block_duplicate_node_names": ("Blocks topology/apply when duplicate node names could collide.", "Keep enabled, especially with virtual/deep hierarchy.", "Duplicate names can confuse hierarchy and promotion behavior."),
    "topology_guard.warn_on_virtual_node_promotion": ("Warns when virtual nodes may promote children to nearest physical ancestor.", "Keep enabled so operators understand LibreQoS virtual-node behavior.", "Virtual nodes are useful but can surprise operators if not explained."),
    "topology_guard.warn_on_deep_hierarchy_depth": ("Warns when topology depth grows beyond recommended levels.", "Keep enabled for readability and performance awareness.", "Very deep trees are harder to debug."),
    "topology_guard.max_recommended_depth": ("Recommended maximum hierarchy depth before warnings appear.", "4 is a good practical default.", "Higher depth may be valid but should be deliberate."),
    "backup_guard.require_backup_before_apply": ("Controls whether backup_before_apply is treated as required. LQoSync defaults this off because auto-backup is an operator storage/rollback choice.", "Keep disabled for storage-saving automatic deployments; enable only if every apply must create a rollback point.", "If enabled while app.backup_before_apply is off, policy conflicts will warn or block according to your guards."),
    "backup_guard.warn_if_backup_disabled_while_auto_apply_enabled": ("Controls whether optional auto-backup disabled should produce policy warnings while auto-apply is enabled.", "Keep disabled if backup_before_apply is intentionally optional. Enable only when your operation requires automatic rollback points.", "Enabling this can make storage-saving mode look unhealthy."),
    "backup_guard.minimum_backup_retention": ("Minimum retention count considered healthy when automatic backups are enabled.", "Use 5–10 for storage-saving deployments, higher only when you need more rollback history.", "Retention only matters when automatic or manual backups are being created."),
    "anomaly_detection.enabled": ("Enables rule-based anomaly detection from previous successful runs.", "Keep enabled for smart warnings.", "Disabling removes early warning for unusual drops/slowness."),
    "anomaly_detection.compare_with_last_successful_run": ("Uses last successful run as baseline for anomaly checks.", "Keep enabled.", "Without baseline comparison, sudden changes are harder to classify."),
    "anomaly_detection.warn_if_client_count_drops_percent": ("Warns when client count drops by this percentage compared with baseline.", "30% is a practical default.", "Too low can be noisy; too high may miss incidents."),
    "anomaly_detection.warn_if_sync_duration_increases_multiplier": ("Warns when sync duration is many times slower than usual.", "5x is a practical starting point.", "Slow sync may indicate API/router/system issues."),
    "anomaly_detection.warn_if_apply_duration_increases_multiplier": ("Warns when LibreQoS apply takes much longer than baseline.", "5x is a practical starting point.", "Slow apply can indicate host/load/config growth problems."),
    "recommendations.enabled": ("Enables operator recommendation cards.", "Keep enabled so the UI suggests the safest next action.", "Disabling removes helpful guidance but not enforcement."),
    "recommendations.show_why_fix_messages": ("Shows What/Why/Fix explanations for warnings and policy decisions.", "Keep enabled for operator clarity.", "Without explanations, policies can feel like hidden behavior."),
    "recommendations.show_operator_next_action": ("Shows the recommended next operator action.", "Keep enabled.", "Operators may need to inspect raw logs without this guidance."),
}

STALE_EXPLANATIONS = {
    "identity": ("Identity used to decide whether a missing client is the same client if it returns later.", "Use username for PPPoE, server_mac for DHCP, username_or_mac for Hotspot, and manual for static rows.", "Grace should only be enabled when identity is stable."),
    "grace_enabled": ("Enables optional grace behavior so a missing client is held for configured runs before cleanup.", "Keep disabled by default for DHCP/Hotspot random-MAC environments. Consider enabling only for stable PPPoE usernames.", "Grace can preserve ghost rows if devices change MAC/IP."),
    "grace_runs": ("Number of consecutive missing runs required before cleanup when grace is enabled.", "Use 1 for PPPoE if you want short reconnect tolerance; use 0 for DHCP/Hotspot unless identities are stable.", "Higher values delay cleanup and may preserve stale rows."),
    "return_cancels_cleanup": ("If the same identity returns before cleanup is applied, pending cleanup is cancelled.", "Enable for PPPoE/stable identities. Disable for unstable DHCP identities.", "If identity is unstable, returns may not match the old row anyway."),
    "enabled": ("Enables stale lifecycle features as a policy group.", "Keep enabled so source-aware lifecycle settings are available; per-source grace can remain disabled.", "Disabling removes lifecycle visibility and grace behavior."),
}

AUTO_APPLY_EXPLANATIONS = {
    "enabled": ("Enables risk-aware auto-apply decisions using policy risk level.", "Keep enabled so low risk can apply while higher risk is held by policy.", "If disabled, behavior may fall back to simpler auto_apply rules."),
    "allow_low_risk": ("Allows automatic LibreQoS apply for low-risk changes.", "Enable for normal efficient operation.", "Disable if all changes must be manually applied."),
    "allow_medium_risk": ("Allows automatic LibreQoS apply for medium-risk changes.", "Keep disabled for production unless operator accepts more automation.", "Medium risk may include meaningful cleanup or policy warnings."),
    "allow_high_risk": ("Allows automatic LibreQoS apply for high-risk changes.", "Keep disabled.", "High-risk changes should be manually reviewed."),
    "allow_critical_risk": ("Allows automatic LibreQoS apply for critical-risk changes.", "Keep disabled.", "Critical risk should not auto-apply in production."),
    "when_blocked": ("Action when file changes exist but policy risk does not allow automatic LibreQoS apply.", "keep_pending_manual_apply is safest because files can be staged while apply waits for review.", "block_write is stricter; dry_run_only is safest for testing but may prevent live updates."),
}

DECISION_TRACE_EXPLANATIONS = {
    "enabled": ("Stores explainable trace entries showing which policy rules influenced cleanup/write/apply decisions.", "Keep enabled for troubleshooting and support.", "Turning off reduces audit clarity."),
    "max_items": ("Limits how many trace items are kept per policy decision.", "200 is enough for most deployments; increase for large networks if traces are truncated.", "Very high values can make state/log output larger."),
}


def _explain_action_choices(item: dict[str, Any]) -> str:
    if item.get("choices") and set(item["choices"]).intersection(ACTION_EXPLANATIONS):
        return " Actions: " + " ".join(f"{choice}={ACTION_EXPLANATIONS.get(choice, choice)}" for choice in item["choices"] if choice in ACTION_EXPLANATIONS)
    return ""


def _apply_atomic_explanations() -> None:
    for item in POLICY_SCHEMA:
        path = item["path"]
        what = why = risk = ""
        if path in ATOMIC_POLICY_EXPLANATIONS:
            what, why, risk = ATOMIC_POLICY_EXPLANATIONS[path]
        elif path.startswith("policies.cleanup_sources."):
            parts = path.split(".")
            source = parts[2]
            key = parts[3]
            if key == "enabled":
                label = {"pppoe": "PPPoE", "dhcp": "DHCP", "hotspot": "Hotspot", "static": "Static/manual"}.get(source, source)
                what = f"Enables the source-specific cleanup policy block for {label}. When disabled, global cleanup defaults are used for this source."
                why = f"Keep enabled if {label} should have its own behavior for inactive, disabled, failed, zero-result, and mass-removal cases."
                risk = "Disabling source-specific policies can make the source follow broader defaults that may be too aggressive or too conservative."
            else:
                what, why, risk = SOURCE_EXPLANATIONS.get(source, {}).get(key, (item.get("description", ""), "Review based on source behavior.", "Changing this affects cleanup/write/apply decisions."))
        elif path.startswith("policies.stale_lifecycle.sources."):
            key = path.split(".")[-1]
            what, why, risk = STALE_EXPLANATIONS.get(key, (item.get("description", ""), "Review source identity stability before enabling grace.", "Grace on unstable identities can preserve ghost rows."))
        elif path.startswith("policies.stale_lifecycle."):
            key = path.split(".")[-1]
            what, why, risk = STALE_EXPLANATIONS.get(key, (item.get("description", ""), "Keep enabled, but leave grace disabled unless needed.", "Wrong lifecycle settings can delay cleanup."))
        elif path.startswith("policies.auto_apply_policy."):
            key = path.split(".")[-1]
            what, why, risk = AUTO_APPLY_EXPLANATIONS.get(key, (item.get("description", ""), "Review with your production risk tolerance.", "Auto-apply settings affect how quickly changes reach LibreQoS."))
        elif path.startswith("policies.decision_trace."):
            key = path.split(".")[-1]
            what, why, risk = DECISION_TRACE_EXPLANATIONS.get(key, (item.get("description", ""), "Keep enabled for supportability.", "Disabling trace reduces visibility."))
        else:
            short = path.replace("policies.", "")
            if short in GENERAL_EXPLANATIONS:
                what, why, risk = GENERAL_EXPLANATIONS[short]
            else:
                what = item.get("description") or "Visible operator policy setting saved to config.json."
                why = "Use the recommended value unless your network behavior requires a different policy."
                risk = "Manual changes can affect cleanup, validation, warnings, or LibreQoS apply behavior."
        item["description"] = what
        item["setup_guidance"] = why
        item["risk_note"] = risk
        item["action_choices_help"] = _explain_action_choices(item).strip()


_apply_atomic_explanations()

def get_by_path(obj: dict, path: str, default: Any = None) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def set_by_path(obj: dict, path: str, value: Any) -> None:
    cur = obj
    parts = path.split(".")
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value




# Config values outside the policies.* block that materially change policy
# semantics in Config Center. Presets are only accurate while these runtime
# controls still match the saved preset context. If an operator changes one of
# these while a named preset is active, the mode must become custom.
POLICY_CONTEXT_PATHS: tuple[str, ...] = (
    "app.operation_mode",
    "app.auto_apply",
    "app.backup_before_apply",
    "app.backup_retention",
    "scheduler.enabled",
    "scheduler.apply_cooldown_seconds",
    "libreqos.run_only_when_files_changed",
    "libreqos.retry_if_last_apply_failed",
    "libreqos.run_mode",
    "preflight.enabled",
    "preflight.duplicate_ip_policy",
    "preflight.missing_parent_policy",
    "preflight.invalid_bandwidth_policy",
    "defaults.duplicate_ip_policy",
)


def policy_context_changed(previous: dict | None, current: dict | None) -> bool:
    """Return True when a named policy preset no longer describes config.

    Policy Center has two kinds of controls:
    - the visible Smart Policy block under ``policies.*``; and
    - runtime/apply controls such as ``app.auto_apply`` and
      ``app.backup_before_apply`` that are shown in Policy Overview because
      they change how the selected policy behaves in production.

    This helper intentionally ignores ``policies.mode`` itself. The mode is the
    label we are deciding, not the setting that proves whether values changed.
    It is used as a server-side safety net so saves still become Custom even
    when browser-side markPolicyCustom() is missed or Advanced Raw JSON is used.
    """
    prev = deepcopy(previous or {})
    cur = deepcopy(current or {})

    # Merge missing policy defaults before comparing individual policy paths so
    # an upgrade/default merge does not look like an operator edit.
    normalize_policies(prev)
    normalize_policies(cur)

    tracked_policy_paths = tuple(
        item["path"] for item in POLICY_SCHEMA
        if item.get("path") and item.get("path") != "policies.mode"
    )
    for path in tracked_policy_paths + POLICY_CONTEXT_PATHS:
        if get_by_path(prev, path) != get_by_path(cur, path):
            return True
    return False


def grouped_policy_schema() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for item in POLICY_SCHEMA:
        out.setdefault(item["section"], []).append(item)
    return out


def normalize_policies(cfg: dict) -> dict:
    """Deep merge missing policy defaults without overwriting operator choices.

    v2.54.2 also normalizes the legacy stale-lifecycle key ``ppoe`` into
    the canonical ``pppoe`` key. Older v2.50-v2.54.1 schema builds could warn
    about ``policies.stale_lifecycle.sources.ppoe`` while the rest of LQoSync
    used ``pppoe``. Keeping this alias migration prevents both fresh-install and
    upgraded configs from showing false missing-policy warnings.
    """
    defaults = smart_policy_defaults()
    current = cfg.get("policies") or {}
    sources = (((current.get("stale_lifecycle") or {}).get("sources") or {}))
    if isinstance(sources, dict) and isinstance(sources.get("ppoe"), dict):
        canonical = sources.get("pppoe") if isinstance(sources.get("pppoe"), dict) else {}
        sources["pppoe"] = _deep_merge(canonical, sources["ppoe"])
    cfg["policies"] = _deep_merge(defaults, current)
    if cfg["policies"].get("mode") not in POLICY_PRESETS:
        cfg["policies"]["mode"] = "custom"
    return cfg


def _deep_merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def preset_config(preset: str) -> dict:
    cfg = {"policies": smart_policy_defaults()}
    return apply_policy_preset(cfg, preset)


def preset_policies(preset: str) -> dict:
    return preset_config(preset).get("policies", {})


def policy_diff_from_preset(cfg: dict, preset: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    preset = (preset or (cfg.get("policies") or {}).get("mode") or "balanced").lower()
    if preset == "custom" or preset not in {"conservative", "balanced", "aggressive"}:
        preset = "balanced"
    ref = {"policies": preset_policies(preset)}
    out = []
    for item in POLICY_SCHEMA:
        path = item["path"]
        cur = get_by_path(cfg, path)
        expected = get_by_path(ref, path)
        if cur != expected:
            out.append({"path": path, "label": item["label"], "current": cur, "preset": expected, "preset_name": preset, "risk": item.get("risk")})
            if len(out) >= limit:
                break
    return out


def closest_preset(cfg: dict) -> dict[str, Any]:
    scores = []
    for preset in ("conservative", "balanced", "aggressive"):
        diff = policy_diff_from_preset(cfg, preset, limit=10000)
        scores.append({"preset": preset, "differences": len(diff)})
    scores.sort(key=lambda x: x["differences"])
    best = scores[0] if scores else {"preset": "balanced", "differences": 0}
    return {"closest_preset": best["preset"], "differences": best["differences"], "all": scores}




def reconcile_policy_mode(cfg: dict) -> dict:
    """Normalize policies and preserve true Custom mode on save.

    Rules:
    - If policies.mode is ``custom``, keep it custom. Custom is an explicit
      operator preference and should not disappear just because the values happen
      to be close to, or even equal to, a named preset.
    - If policies.mode is conservative/balanced/aggressive and the policy block
      differs from that preset, change it to custom.
    - If policies.mode is invalid or missing, change it to custom after defaults
      are merged.

    This is a server-side safety net for Config Center saves, Advanced Raw JSON
    edits, browser edge cases, and old forms.
    """
    normalize_policies(cfg)
    mode = str(((cfg.get("policies") or {}).get("mode") or "balanced")).strip().lower()
    if mode == "custom":
        cfg.setdefault("policies", {})["mode"] = "custom"
        return cfg
    if mode in {"conservative", "balanced", "aggressive"}:
        diffs = [d for d in policy_diff_from_preset(cfg, mode, limit=10000) if d.get("path") != "policies.mode"]
        if diffs:
            cfg.setdefault("policies", {})["mode"] = "custom"
        else:
            cfg.setdefault("policies", {})["mode"] = mode
    else:
        cfg.setdefault("policies", {})["mode"] = "custom"
    return cfg


def parse_policy_form(form: dict, current_cfg: dict) -> dict:
    """Apply form values to cfg.policies. Manual save always sets mode=custom unless preset field explicitly selected."""
    cfg = deepcopy(current_cfg)
    normalize_policies(cfg)
    bool_paths = {item["path"] for item in POLICY_SCHEMA if item["type"] == "bool"}
    for item in POLICY_SCHEMA:
        path = item["path"]
        typ = item["type"]
        if typ == "bool":
            # Only booleans presented by Policy Center are intentionally false when absent.
            value = path in form or form.get(path) in {"true", "on", "1"}
        elif path in form:
            raw = form.get(path)
            if typ == "number":
                try:
                    value = int(raw) if str(raw).strip().isdigit() else float(raw)
                except Exception:
                    value = item.get("recommended", 0)
            else:
                value = raw
                if item.get("choices") and value not in item["choices"]:
                    value = item.get("recommended") or item["choices"][0]
        else:
            continue
        set_by_path(cfg, path, value)
    cfg.setdefault("policies", {})["mode"] = form.get("policies.mode") or "custom"
    if cfg["policies"]["mode"] not in PRESET_CHOICES:
        cfg["policies"]["mode"] = "custom"
    return cfg
