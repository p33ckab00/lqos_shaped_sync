"""Guided first-run setup wizard helpers for LQoSync.

The wizard is intentionally light-touch. It does not contact routers or mutate
systems while loading the page. It reads config/runtime state and turns it into
a step-by-step first-run checklist with current status, blockers, and safe next
actions. Write actions remain explicit form submissions from the UI.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


DONE = "done"
WARN = "warn"
TODO = "todo"
BLOCKED = "blocked"


def _exists(path: str | None, expected: str = "file") -> bool:
    if not path:
        return False
    p = Path(path)
    return p.is_dir() if expected == "dir" else p.is_file()


def _source_summary(cfg: dict) -> dict[str, Any]:
    routers = cfg.get("routers") or []
    out = {"routers": len(routers), "enabled_routers": 0, "pppoe": 0, "dhcp": 0, "hotspot": 0, "dhcp_servers": 0}
    for r in routers:
        if r.get("enabled", True):
            out["enabled_routers"] += 1
        if (r.get("pppoe") or {}).get("enabled", False):
            out["pppoe"] += 1
        dhcp = r.get("dhcp") or {}
        if dhcp.get("enabled", False):
            out["dhcp"] += 1
            out["dhcp_servers"] += len([s for s in dhcp.get("servers", []) if s.get("enabled", True)])
        if (r.get("hotspot") or {}).get("enabled", False):
            out["hotspot"] += 1
    return out


def _router_complete(router: dict) -> bool:
    return bool(router.get("name") and router.get("address") and router.get("port") and router.get("username") and router.get("password"))


def compute_setup_wizard(cfg: dict, state: dict | None = None, setup_report: dict | None = None) -> dict[str, Any]:
    state = state or {}
    setup_report = setup_report or {}
    paths = cfg.get("paths") or {}
    routers = cfg.get("routers") or []
    source = _source_summary(cfg)
    scheduler = cfg.get("scheduler") or {}
    app_cfg = cfg.get("app") or {}
    policies = cfg.get("policies") or {}

    checks_failed = int(setup_report.get("fails") or 0)
    checks_warn = int(setup_report.get("warnings") or 0)
    dry_run = state.get("last_dry_run") or {}
    last_run = state.get("last_run") or {}

    steps: list[dict[str, Any]] = []

    def add(key: str, title: str, status: str, summary: str, description: str, action: str = "", href: str = "", command: str = ""):
        steps.append({
            "key": key,
            "number": len(steps) + 1,
            "title": title,
            "status": status,
            "summary": summary,
            "description": description,
            "action": action,
            "href": href,
            "command": command,
        })

    libre_src_ok = _exists(paths.get("libreqos_src") or paths.get("libreqos_dir") or "/opt/libreqos/src", "dir") or _exists(paths.get("network_json")) or _exists(paths.get("shaped_devices_csv"))
    add(
        "libreqos_paths",
        "Confirm LibreQoS paths",
        DONE if libre_src_ok else WARN,
        "LibreQoS paths look available" if libre_src_ok else "LibreQoS path/files need verification",
        "The wizard expects LibreQoS.py, ShapedDevices.csv, network.json, and config.json to be under the configured LibreQoS source directory. Fresh installs can create missing generated files, but production should verify paths before auto-apply.",
        "Open Setup & Repair" if not libre_src_ok else "Review paths",
        "/setup-repair",
    )

    router_complete = bool(routers) and all(_router_complete(r) for r in routers)
    add(
        "routers",
        "Configure MikroTik router access",
        DONE if router_complete else TODO,
        f"{source['enabled_routers']} enabled router(s), {source['routers']} configured",
        "Add each MikroTik router with name, address, API port, restricted read/sensitive/api user, password, and root bandwidth. Router test remains explicit from Config Center so the wizard does not contact routers on page load.",
        "Open Config Center",
        "/config",
    )

    sources_enabled = (source["pppoe"] + source["dhcp"] + source["hotspot"]) > 0
    add(
        "sources",
        "Choose PPPoE / DHCP / Hotspot sources",
        DONE if sources_enabled else TODO,
        f"PPP={source['pppoe']} · DHCP={source['dhcp']} ({source['dhcp_servers']} server entries) · Hotspot={source['hotspot']}",
        "Enable only the sources that should generate ShapedDevices rows. Source lifecycle and cleanup policies decide how disabled/failed/zero-result sources are handled.",
        "Edit sources",
        "/config",
    )

    layout_mode = cfg.get("network_mode", "router_children")
    add(
        "network_layout",
        "Choose Network Layout mode",
        DONE if layout_mode else TODO,
        f"Current mode: {layout_mode}",
        "Select flat/no-parent, router-root flat, normal hierarchy, deep hierarchy, or custom hierarchy. Run Dry Run after changing layout to check parent nodes and generated network.json.",
        "Open Network Layout",
        "/network",
    )

    preset = policies.get("mode", "balanced")
    add(
        "policy_preset",
        "Select Smart Policy preset",
        DONE if preset else TODO,
        f"Current policy mode: {preset}",
        "Conservative is safest for production, Balanced is the recommended default, Aggressive is for labs or highly dynamic access networks, and Custom means the operator edited individual policy settings.",
        "Open Policy Center",
        "/policy",
    )

    dry_status = dry_run.get("status") if isinstance(dry_run, dict) else None
    add(
        "dry_run",
        "Run first Dry Run simulation",
        DONE if dry_status else TODO,
        f"Last dry-run status: {dry_status or 'not run yet'}",
        "Dry Run previews generated files, policy verdict, Smart Insights, lifecycle effects, cleanup decisions, and LibreQoS apply behavior without writing generated files or applying LibreQoS.",
        "Run Dry Run",
        "/sync/dry-run",
    )

    scheduler_enabled = bool(scheduler.get("enabled", False))
    auto_apply = bool(app_cfg.get("auto_apply", True))
    prod_ready = router_complete and sources_enabled and bool(dry_status) and checks_failed == 0
    add(
        "go_live",
        "Enable production scheduler deliberately",
        DONE if scheduler_enabled else (TODO if prod_ready else BLOCKED),
        f"scheduler={scheduler_enabled} · auto_apply={auto_apply}",
        "Enable scheduler only after router access, sources, layout, policy preset, and Dry Run results are clean and expected. Auto-apply remains governed by risk-aware policies.",
        "Open Dashboard" if scheduler_enabled else "Enable from Dashboard/Config",
        "/",
    )

    done = sum(1 for s in steps if s["status"] == DONE)
    blocked = sum(1 for s in steps if s["status"] == BLOCKED)
    warnings = checks_warn + sum(1 for s in steps if s["status"] == WARN)
    progress = round((done / len(steps)) * 100) if steps else 0
    if blocked or checks_failed:
        readiness = "blocked"
        next_action = "Repair failed checks, configure routers/sources, then run Dry Run."
    elif progress >= 85 and not scheduler_enabled:
        readiness = "ready_for_go_live"
        next_action = "Review Dry Run and enable scheduler when production-ready."
    elif progress >= 65:
        readiness = "nearly_ready"
        next_action = "Run Dry Run and review policy/layout results."
    else:
        readiness = "setup_in_progress"
        next_action = "Complete router/source/layout/policy setup."

    return {
        "readiness": readiness,
        "progress": progress,
        "done_steps": done,
        "total_steps": len(steps),
        "blocked_steps": blocked,
        "warnings": warnings,
        "next_action": next_action,
        "steps": steps,
        "source_summary": source,
        "policy_mode": preset,
        "network_mode": layout_mode,
        "scheduler_enabled": scheduler_enabled,
        "auto_apply": auto_apply,
        "has_dry_run": bool(dry_status),
        "last_dry_run_status": dry_status,
        "last_run_status": last_run.get("status") if isinstance(last_run, dict) else None,
    }


NETWORK_MODE_OPTIONS = [
    ("flat_no_parent", "Simple flat — no Parent Node"),
    ("flat_router_root", "Simple flat — router root"),
    ("router_children", "Normal hierarchy — recommended default"),
    ("deep_hierarchy", "Deep hierarchy — nested routers"),
    ("custom_hierarchy", "Custom hierarchy — topology editor"),
]
