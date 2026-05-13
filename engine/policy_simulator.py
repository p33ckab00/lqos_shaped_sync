"""Policy simulation helpers for Config Center.

This module explains the likely impact of changing policy settings before the
operator saves config.json. It uses current runtime state and last sync data; it
is intentionally read-only and never writes config/output files.
"""
from __future__ import annotations

from typing import Any

from engine.config_diff import diff_configs
from engine.policy_schema import policy_diff_from_preset, closest_preset


def policy_simulation(saved_cfg: dict, proposed_cfg: dict, state: dict | None = None) -> dict[str, Any]:
    state = state or {}
    changes = [c for c in diff_configs(saved_cfg, proposed_cfg, limit=500) if c["path"].startswith("policies.")]
    last = state.get("last_run") or state.get("last_dry_run") or {}
    last_decision = ((last.get("diff") or {}).get("policy_decision") or {}) if isinstance(last, dict) else {}
    counts = last.get("counts", {}) if isinstance(last, dict) else {}

    impacts: list[dict[str, str]] = []
    recommendations: list[str] = []
    risk = "low"

    for c in changes:
        path = c["path"]
        after = c.get("after")
        before = c.get("before")
        if "normal_inactive_action" in path and after == "cleanup_immediate":
            impacts.append({"severity": "medium", "title": "Immediate cleanup enabled", "detail": f"{path} changed from {before} to cleanup_immediate. Missing rows from this source can be removed in the same sync cycle."})
            recommendations.append("Run Dry Run after saving policy changes, especially if scheduler auto-apply is enabled.")
            risk = max_risk(risk, "medium")
        elif "zero_result_action" in path and after in {"cleanup_immediate", "cleanup_next_run"}:
            impacts.append({"severity": "high", "title": "Zero-result cleanup is permissive", "detail": f"{path}={after}. If a source returns zero rows while enabled, cleanup may proceed instead of blocking."})
            risk = max_risk(risk, "high")
        elif "collector_failed_action" in path and after not in {"preserve_rows", "block_cleanup", "block_apply"}:
            impacts.append({"severity": "critical", "title": "Collector failure may remove rows", "detail": f"{path}={after}. This is risky because API failures are not operator intent."})
            risk = max_risk(risk, "critical")
        elif "allow_" in path and "risk" in path and after is True:
            impacts.append({"severity": "high", "title": "Risk auto-apply widened", "detail": f"{path} changed to true. LibreQoS may auto-apply more risky changes."})
            risk = max_risk(risk, "high")

    if not impacts and changes:
        impacts.append({"severity": "low", "title": "Policy settings changed", "detail": "No high-risk policy pattern was detected, but Dry Run is still recommended before live auto-apply."})
    if not changes:
        impacts.append({"severity": "low", "title": "No policy changes", "detail": "The proposed config does not change policy settings."})

    return {
        "changed_policy_fields": changes[:100],
        "changed_policy_count": len(changes),
        "closest_preset": closest_preset(proposed_cfg),
        "diff_from_current_preset": policy_diff_from_preset(proposed_cfg, (proposed_cfg.get("policies") or {}).get("mode"), limit=100),
        "last_policy_decision": last_decision,
        "last_counts": counts,
        "impacts": impacts,
        "recommendations": recommendations,
        "risk_level": risk,
    }


def max_risk(a: str, b: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    return a if order.get(a, 0) >= order.get(b, 0) else b
