"""Read-only Config Center simulation engine for v2.51."""
from __future__ import annotations

from typing import Any

from engine.config_diff import diff_configs, summarize_config_changes
from engine.config_schema import migrate_config_schema, validate_schema
from engine.policy_simulator import policy_simulation


IMPORTANT_PATH_PREFIXES = (
    "network_mode",
    "flat_network",
    "no_parent",
    "app.auto_apply",
    "app.backup_before_apply",
    "libreqos.",
    "collector.",
    "policies.",
    "routers",
    "scheduler.enabled",
)


def simulate_config_change(saved_cfg: dict, proposed_cfg: dict, state: dict | None = None) -> dict[str, Any]:
    state = state or {}
    migrated, migration_notes = migrate_config_schema(proposed_cfg)
    schema = validate_schema(migrated)
    changes = diff_configs(saved_cfg, migrated, limit=500)
    important = [c for c in changes if any(c["path"] == p.rstrip(".") or c["path"].startswith(p) for p in IMPORTANT_PATH_PREFIXES)]
    impacts = derive_impacts(saved_cfg, migrated, changes, state)
    policy = policy_simulation(saved_cfg, migrated, state)
    risk = combine_risk(schema, impacts, policy)
    verdict = verdict_for(schema, risk, policy)

    return {
        "ok": True,
        "verdict": verdict,
        "risk_level": risk,
        "schema": schema,
        "migration_notes": migration_notes,
        "changes": changes[:200],
        "important_changes": important[:100],
        "summary": summarize_config_changes(changes),
        "impacts": impacts,
        "policy_simulation": policy,
        "recommendations": recommendations_for(schema, impacts, policy),
    }


def derive_impacts(saved: dict, proposed: dict, changes: list[dict[str, Any]], state: dict) -> list[dict[str, str]]:
    impacts: list[dict[str, str]] = []
    changed_paths = {c["path"] for c in changes}
    if "network_mode" in changed_paths or "flat_network" in changed_paths or "no_parent" in changed_paths:
        impacts.append({"severity": "medium", "title": "Network layout behavior changed", "detail": "Parent Node behavior or network.json generation may change. Run Dry Run before live scheduler/apply."})
    if "app.auto_apply" in changed_paths:
        impacts.append({"severity": "high" if proposed.get("app", {}).get("auto_apply") else "medium", "title": "Auto-apply setting changed", "detail": "LibreQoS.py apply behavior may change after file writes."})
    if "app.backup_before_apply" in changed_paths and not proposed.get("app", {}).get("backup_before_apply", True):
        impacts.append({"severity": "high", "title": "Backups disabled", "detail": "backup_before_apply is disabled. Rollback safety is reduced."})
    if any(p.startswith("routers") for p in changed_paths):
        impacts.append({"severity": "medium", "title": "Router/source settings changed", "detail": "MikroTik collector sources, credentials, or PPP/DHCP/Hotspot inputs may change. Dry Run is recommended."})

    # Source enable/disable impact hints.
    before_sources = source_enable_map(saved)
    after_sources = source_enable_map(proposed)
    for key, before in before_sources.items():
        after = after_sources.get(key)
        if before and after is False:
            impacts.append({"severity": "high", "title": f"Source disabled: {key}", "detail": "Existing rows from this source may become stale. Cleanup policy should decide whether confirmation or next-run cleanup is required."})
        if before is False and after:
            impacts.append({"severity": "medium", "title": f"Source enabled: {key}", "detail": "New rows may be generated from this source on the next sync."})

    if not impacts:
        impacts.append({"severity": "low", "title": "No major config impact detected", "detail": "No high-risk setting changes were detected. Saving still normalizes config.json."})
    return impacts


def source_enable_map(cfg: dict) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for idx, router in enumerate(cfg.get("routers", []) or []):
        rname = router.get("name") or f"router[{idx}]"
        out[f"{rname}.pppoe"] = bool((router.get("pppoe") or {}).get("enabled"))
        out[f"{rname}.dhcp"] = bool((router.get("dhcp") or {}).get("enabled"))
        out[f"{rname}.hotspot"] = bool((router.get("hotspot") or {}).get("enabled"))
        for sidx, server in enumerate(((router.get("dhcp") or {}).get("servers") or [])):
            sname = server.get("name") or f"server[{sidx}]"
            out[f"{rname}.dhcp.{sname}"] = bool(server.get("enabled", True))
    return out


def combine_risk(schema: dict, impacts: list[dict[str, str]], policy: dict) -> str:
    risk = "low"
    if schema.get("errors"):
        risk = "critical"
    elif schema.get("warnings"):
        risk = "medium"
    for item in impacts + policy.get("impacts", []):
        risk = max_risk(risk, item.get("severity", "low"))
    return risk


def verdict_for(schema: dict, risk: str, policy: dict) -> str:
    if schema.get("errors"):
        return "cannot_save"
    if risk == "critical":
        return "blocked_or_requires_repair"
    if risk == "high":
        return "save_with_caution_and_dry_run"
    if risk == "medium":
        return "dry_run_recommended"
    return "safe_to_save"


def recommendations_for(schema: dict, impacts: list[dict[str, str]], policy: dict) -> list[str]:
    out = []
    out.extend(schema.get("recommendations", []) or [])
    out.extend(policy.get("recommendations", []) or [])
    if any(i.get("severity") in {"medium", "high", "critical"} for i in impacts):
        out.append("Run Dry Run after saving before enabling scheduler or auto-apply.")
    if not out:
        out.append("Config looks safe to save. Dry Run remains recommended for production changes.")
    # Keep order but remove duplicates.
    seen = set(); clean = []
    for item in out:
        if item not in seen:
            seen.add(item); clean.append(item)
    return clean


def max_risk(a: str, b: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    return a if order.get(a, 0) >= order.get(b, 0) else b
