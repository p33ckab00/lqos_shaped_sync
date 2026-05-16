"""Policy preset alignment audit for LQoSync.

Read-only checks that verify Conservative/Balanced/Aggressive presets are
internally consistent, preserve operator preferences outside the policy block,
and do not ship risky zero-result/immediate-cleanup combinations.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import json

from engine.policy_conflicts import evaluate_policy_conflicts
from engine.policy_defaults import smart_policy_defaults, apply_policy_preset_defaults
from engine.policy_schema import reconcile_policy_mode
from engine.setup_repair import apply_policy_preset


@dataclass
class PresetAuditItem:
    key: str
    title: str
    status: str
    detail: str
    category: str = "policy_preset"
    fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _summary(items: list[PresetAuditItem]) -> dict[str, int]:
    return {
        "ok": sum(1 for i in items if i.status == "ok"),
        "warn": sum(1 for i in items if i.status == "warn"),
        "fail": sum(1 for i in items if i.status == "fail"),
    }


def _base_config() -> dict[str, Any]:
    return {
        "app": {
            "operation_mode": "automatic",
            "auto_apply": True,
            "backup_before_apply": False,
            "backup_retention": 10,
        },
        "notifications": {"telegram": {"enabled": True, "base_url": "https://example.invalid"}},
        "policies": smart_policy_defaults(),
    }


def audit_policy_presets(root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root or Path(__file__).resolve().parents[1])
    items: list[PresetAuditItem] = []
    presets = ("conservative", "balanced", "aggressive")

    mode_failures = []
    conflict_failures = []
    zero_failures = []
    preservation_failures = []
    reconcile_failures = []

    for preset in presets:
        cfg = _base_config()
        cfg["app"]["backup_before_apply"] = False
        cfg["notifications"]["telegram"]["base_url"] = "https://operator.example"
        applied = apply_policy_preset(cfg, preset)
        policies = applied.get("policies") or {}
        if policies.get("mode") != preset:
            mode_failures.append(f"{preset}: mode={policies.get('mode')}")

        # Presets must not overwrite operator preferences outside policies.
        if (applied.get("app") or {}).get("backup_before_apply") is not False:
            preservation_failures.append(f"{preset}: app.backup_before_apply changed")
        if ((applied.get("notifications") or {}).get("telegram") or {}).get("base_url") != "https://operator.example":
            preservation_failures.append(f"{preset}: notification settings changed")

        for source in ("pppoe", "dhcp", "hotspot"):
            src = ((policies.get("cleanup_sources") or {}).get(source) or {})
            if src.get("normal_inactive_action") == "cleanup_immediate" and src.get("zero_result_action") != "block_cleanup":
                zero_failures.append(f"{preset}.{source}: immediate cleanup with zero_result_action={src.get('zero_result_action')}")
            if src.get("collector_failed_action") != "preserve_rows":
                zero_failures.append(f"{preset}.{source}: collector_failed_action={src.get('collector_failed_action')}")

        conflicts = evaluate_policy_conflicts(applied)
        bad = [c for c in conflicts.get("conflicts", []) if c.get("severity") in {"critical", "high"}]
        if bad:
            conflict_failures.append(f"{preset}: " + "; ".join(c.get("title", "conflict") for c in bad[:3]))

        # Server-side save reconciliation: exact named preset remains preset; edited preset becomes custom; explicit custom is preserved.
        exact = reconcile_policy_mode(applied.copy())
        if ((exact.get("policies") or {}).get("mode") != preset):
            reconcile_failures.append(f"{preset}: exact named preset reconciled to {(exact.get('policies') or {}).get('mode')}")
        edited = json.loads(json.dumps(applied))
        edited.setdefault("policies", {}).setdefault("cleanup_sources", {}).setdefault("dhcp", {})["zero_result_action"] = "warn_only"
        edited = reconcile_policy_mode(edited)
        if ((edited.get("policies") or {}).get("mode") != "custom"):
            reconcile_failures.append(f"{preset}: edited named preset did not reconcile to custom")
        explicit_custom = json.loads(json.dumps(applied))
        explicit_custom.setdefault("policies", {})["mode"] = "custom"
        explicit_custom = reconcile_policy_mode(explicit_custom)
        if ((explicit_custom.get("policies") or {}).get("mode") != "custom"):
            reconcile_failures.append(f"{preset}: explicit custom mode was not preserved")

    if mode_failures:
        items.append(PresetAuditItem("preset.mode", "Preset mode alignment", "fail", "; ".join(mode_failures), "policy_preset", "Ensure apply_policy_preset sets policies.mode to the selected preset."))
    else:
        items.append(PresetAuditItem("preset.mode", "Preset mode alignment", "ok", "Conservative, Balanced, and Aggressive set policies.mode correctly."))

    if zero_failures:
        items.append(PresetAuditItem("preset.zero_result", "Preset zero-result safety", "fail", "; ".join(zero_failures[:12]), "policy_preset", "Set zero_result_action=block_cleanup and collector_failed_action=preserve_rows for subscriber sources."))
    else:
        items.append(PresetAuditItem("preset.zero_result", "Preset zero-result safety", "ok", "All presets block zero-result cleanup and preserve rows on collector failure for PPPoE/DHCP/Hotspot."))

    if conflict_failures:
        items.append(PresetAuditItem("preset.conflicts", "Preset conflict cleanliness", "fail", "; ".join(conflict_failures), "policy_preset", "Adjust preset defaults so presets do not create high/critical conflicts immediately after apply."))
    else:
        items.append(PresetAuditItem("preset.conflicts", "Preset conflict cleanliness", "ok", "No preset produces high/critical Policy Conflict Resolver findings."))

    if preservation_failures:
        items.append(PresetAuditItem("preset.preference_preservation", "Preset preserves user preferences", "fail", "; ".join(preservation_failures), "policy_preset", "Preset apply should only replace config.json → policies, not app/notifications/user preferences."))
    else:
        items.append(PresetAuditItem("preset.preference_preservation", "Preset preserves user preferences", "ok", "Preset apply preserves app.backup_before_apply and notification preferences outside policies."))

    if reconcile_failures:
        items.append(PresetAuditItem("preset.custom_reconcile", "Custom mode reconciliation", "fail", "; ".join(reconcile_failures), "policy_preset", "Server-side Config Center save should keep exact named presets, mark edited named presets as custom, and preserve explicit custom mode."))
    else:
        items.append(PresetAuditItem("preset.custom_reconcile", "Custom mode reconciliation", "ok", "Exact named presets remain named presets; manual edits reconcile to custom; explicit custom mode is preserved."))

    return {"items": [i.to_dict() for i in items], "summary": _summary(items), "verdict": "pass" if not any(i.status == "fail" for i in items) else "fail"}
