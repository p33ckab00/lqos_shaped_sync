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


def field(path: str, label: str, field_type: str, *, section: str, description: str = "", choices: list[str] | None = None, recommended: Any = None, risk: str = "medium", minimum: int | float | None = None, maximum: int | float | None = None) -> dict[str, Any]:
    return {
        "path": path,
        "label": label,
        "type": field_type,
        "section": section,
        "description": description,
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
        field(f"policies.cleanup_sources.{source}.zero_result_action", "Zero-result action", "select", section=sec, choices=POLICY_ACTION_CHOICES, recommended="block_cleanup" if source in {"pppoe", "dhcp"} else "warn_only", risk="critical", description="Action when a source is enabled and scan succeeds but returns zero rows."),
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
    ("backup_guard", "Backup Guards", [
        ("require_backup_before_apply", "Require backup before apply", "bool", True, "high"),
        ("warn_if_backup_disabled_while_auto_apply_enabled", "Warn if backups disabled with auto-apply", "bool", True, "high"),
        ("minimum_backup_retention", "Minimum backup retention", "number", 30, "medium"),
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
    ("ppoe", "PPPoE", "username"),
    ("dhcp", "DHCP", "server_mac"),
    ("hotspot", "Hotspot", "username_or_mac"),
    ("static", "Static/manual rows", "manual"),
]:
    sec = f"{label} Stale Lifecycle"
    POLICY_SCHEMA.extend([
        field(f"policies.stale_lifecycle.sources.{source}.identity", f"{label} identity key", "select", section=sec, choices=["username", "server_mac", "username_or_mac", "manual"], recommended=default_identity, risk="medium", description="Identity used when reasoning about stale/returned clients. Grace is safest only when identity is stable."),
        field(f"policies.stale_lifecycle.sources.{source}.grace_enabled", f"{label} optional grace", "bool", section=sec, recommended=False, risk="high", description="When enabled, normal inactive cleanup waits for the configured grace runs before removal. Disabled by default for DHCP/Hotspot to avoid ghost rows with randomized MACs."),
        field(f"policies.stale_lifecycle.sources.{source}.grace_runs", f"{label} grace runs", "number", section=sec, recommended=1 if source == "ppoe" else 0, risk="medium", minimum=0, maximum=10, description="How many consecutive missing runs are required before cleanup is allowed when optional grace is enabled."),
        field(f"policies.stale_lifecycle.sources.{source}.return_cancels_cleanup", f"{label} return cancels cleanup", "bool", section=sec, recommended=(source == "ppoe"), risk="low", description="If the same identity returns before cleanup, clear stale/pending cleanup lifecycle state."),
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


def grouped_policy_schema() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for item in POLICY_SCHEMA:
        out.setdefault(item["section"], []).append(item)
    return out


def normalize_policies(cfg: dict) -> dict:
    """Deep merge missing policy defaults without overwriting operator choices."""
    defaults = smart_policy_defaults()
    current = cfg.get("policies") or {}
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
