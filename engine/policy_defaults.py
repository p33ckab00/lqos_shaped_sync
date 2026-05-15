"""Default Smart Policy Center configuration for LQoSync.

The policy defaults are intentionally conservative/balanced: normal stale rows
can be cleaned safely, but source-disabled, zero-result, collector-failed, and
mass-removal situations are protected before file write and LibreQoS apply.
"""
from copy import deepcopy

CLEANUP_ACTIONS = (
    "preserve_rows",
    "warn_only",
    "cleanup_immediate",
    "cleanup_next_run",
    "require_confirm_immediate",
    "require_confirm_next_run",
    "block_cleanup",
    "block_apply",
)

POLICY_PRESETS = ("conservative", "balanced", "aggressive", "custom")

SMART_POLICY_DEFAULTS = {
    "mode": "balanced",
    "cleanup": {
        "enabled": True,
        "global_default_action": "require_confirm_next_run",
        "confirmation_expires_hours": 24,
        "apply_confirmed_cleanup": "next_run",
        "normal_inactive_default_action": "cleanup_next_run",
        "source_disabled_default_action": "require_confirm_next_run",
        "collector_failed_default_action": "preserve_rows",
        "source_zero_result_default_action": "block_cleanup",
        "allow_immediate_cleanup": True,
    },
    "cleanup_sources": {
        "pppoe": {
            "enabled": True,
            "normal_inactive_action": "cleanup_next_run",
            "source_disabled_action": "require_confirm_next_run",
            "collector_failed_action": "preserve_rows",
            "zero_result_action": "block_cleanup",
            "mass_removal_action": "require_confirm_next_run",
            "respect_percentage_guards": True,
        },
        "dhcp": {
            "enabled": True,
            "normal_inactive_action": "cleanup_immediate",
            "source_disabled_action": "require_confirm_next_run",
            "collector_failed_action": "preserve_rows",
            "zero_result_action": "block_cleanup",
            "mass_removal_action": "require_confirm_next_run",
            "respect_percentage_guards": False,
        },
        "hotspot": {
            "enabled": True,
            "normal_inactive_action": "cleanup_immediate",
            "source_disabled_action": "cleanup_next_run",
            "collector_failed_action": "preserve_rows",
            "zero_result_action": "warn_only",
            "mass_removal_action": "require_confirm_next_run",
            "respect_percentage_guards": False,
        },
        "static": {
            "enabled": True,
            "normal_inactive_action": "preserve_rows",
            "source_disabled_action": "preserve_rows",
            "collector_failed_action": "preserve_rows",
            "zero_result_action": "preserve_rows",
            "mass_removal_action": "preserve_rows",
            "respect_percentage_guards": True,
        },
    },
    "node_cleanup_guard": {
        "enabled": True,
        "threshold_percent": 30,
        "min_node_size": 10,
        "min_removed_count": 3,
        "action": "require_confirm_next_run",
    },
    "small_node_guard": {
        "enabled": True,
        "max_node_size": 5,
        "partial_removal_action": "cleanup_next_run",
        "full_removal_action": "require_confirm_next_run",
    },
    "source_cleanup_guard": {
        "enabled": True,
        "threshold_percent": 30,
        "min_removed_count": 5,
        "action": "require_confirm_next_run",
    },
    "apply_guard": {
        "block_apply_on_collector_failure": True,
        "block_apply_on_missing_parent": True,
        "block_apply_on_duplicate_ip": True,
        "block_apply_on_invalid_speed": True,
        "require_manual_confirm_on_medium_risk": True,
        "allow_auto_apply_on_low_risk": True,
    },
    "collector_guard": {
        "block_cleanup_if_source_failed": True,
        "block_cleanup_if_enabled_source_returns_zero": True,
        "block_cleanup_if_source_returns_zero_after_previous_success": True,
        "zero_source_drop_threshold_percent": 80,
        "warn_if_router_api_slow_ms": 2000,
    },
    "data_quality": {
        "warn_on_fallback_speed": True,
        "fallback_speed_warning_threshold_percent": 10,
        "block_if_fallback_speed_threshold_percent": 50,
        "warn_on_missing_mac": True,
        "warn_on_missing_ip": True,
    },
    "topology_guard": {
        "block_missing_parent_nodes": True,
        "block_duplicate_node_names": True,
        "warn_on_virtual_node_promotion": True,
        "warn_on_deep_hierarchy_depth": True,
        "max_recommended_depth": 4,
    },
    "backup_guard": {
        "require_backup_before_apply": False,
        "warn_if_backup_disabled_while_auto_apply_enabled": False,
        "minimum_backup_retention": 10,
    },
    "anomaly_detection": {
        "enabled": True,
        "compare_with_last_successful_run": True,
        "warn_if_client_count_drops_percent": 30,
        "warn_if_sync_duration_increases_multiplier": 5,
        "warn_if_apply_duration_increases_multiplier": 5,
    },
    "recommendations": {
        "enabled": True,
        "show_why_fix_messages": True,
        "show_operator_next_action": True,
    },
    "auto_apply_policy": {
        "enabled": True,
        "allow_low_risk": True,
        "allow_medium_risk": False,
        "allow_high_risk": False,
        "allow_critical_risk": False,
        "when_blocked": "keep_pending_manual_apply",
    },
    "decision_trace": {
        "enabled": True,
        "max_items": 200,
    },
    "stale_lifecycle": {
        "enabled": True,
        "sources": {
            "pppoe": {
                "identity": "username",
                "grace_enabled": False,
                "grace_runs": 1,
                "return_cancels_cleanup": True,
            },
            "dhcp": {
                "identity": "server_mac",
                "grace_enabled": False,
                "grace_runs": 0,
                "return_cancels_cleanup": False,
            },
            "hotspot": {
                "identity": "username_or_mac",
                "grace_enabled": False,
                "grace_runs": 0,
                "return_cancels_cleanup": False,
            },
            "static": {
                "identity": "manual",
                "grace_enabled": False,
                "grace_runs": 0,
                "return_cancels_cleanup": False,
            },
        },
    },
    "policy_overrides": {
        "dhcp_servers": {},
        "hotspot_servers": {},
        "pppoe_profiles": {},
    },
}


def smart_policy_defaults() -> dict:
    return deepcopy(SMART_POLICY_DEFAULTS)


def apply_policy_preset_defaults(preset: str) -> dict:
    """Return policy defaults adjusted to a named preset."""
    from engine.setup_repair import apply_policy_preset
    return apply_policy_preset({"policies": smart_policy_defaults()}, preset)["policies"]
