"""Smart Setup / Repair helpers for LQoSync.

This module is intentionally rule-based and read-only by default. It inspects
configuration, runtime paths, service status, Git status, and recent runtime
state, then returns operator-facing setup/repair guidance. It does not perform
system changes; WebUI actions still show safe SSH commands so operators can run
repair steps deliberately.
"""
from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from engine.policy_defaults import smart_policy_defaults
from engine.release_integrity import compute_release_integrity


STATUS_RANK = {"ok": 0, "info": 0, "warn": 1, "fail": 2}


def _status(ok: bool | None, warn: bool = False) -> str:
    if ok is None:
        return "info"
    if ok is False:
        return "fail"
    return "warn" if warn else "ok"


def _add_check(checks: list[dict[str, Any]], *, key: str, title: str, status: str, detail: str, why: str = "", fix: str = "", command: str = "", category: str = "system") -> None:
    checks.append({
        "key": key,
        "title": title,
        "status": status,
        "detail": detail,
        "why": why,
        "fix": fix,
        "command": command,
        "category": category,
    })


def _path_check(path: str | None, *, key: str, title: str, expected: str = "file", write_test: bool = False) -> dict[str, Any]:
    p = Path(path or "") if path else Path("")
    if not path:
        return {"key": key, "title": title, "status": "fail", "detail": "Path is empty", "category": "paths"}
    exists = p.exists()
    if expected == "dir":
        valid_type = p.is_dir() if exists else False
    else:
        valid_type = p.is_file() if exists else False
    if not exists:
        return {
            "key": key,
            "title": title,
            "status": "warn",
            "detail": f"Missing: {p}",
            "why": "Fresh LibreQoS/LQoSync installs can create missing managed files, but live systems should verify paths before enabling auto-apply.",
            "fix": "Run the installer with preserve_existing or create missing files from templates.",
            "command": "cd /opt/LQoSync && sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh",
            "category": "paths",
        }
    if not valid_type:
        return {"key": key, "title": title, "status": "fail", "detail": f"Wrong type: {p}", "fix": "Check the path and repair the install.", "category": "paths"}
    writable = os.access(str(p if expected == "dir" else p.parent), os.W_OK)
    readable = os.access(str(p), os.R_OK)
    status = "ok" if readable and (not write_test or writable) else "warn"
    return {
        "key": key,
        "title": title,
        "status": status,
        "detail": f"{p} exists" + (" and parent is writable" if writable else "; parent may not be writable by current process"),
        "why": "LQoSync needs read/write access for generated files and state paths.",
        "fix": "If this warns on bare-metal, reapply LQoSync permissions and ACLs.",
        "command": "cd /opt/LQoSync && sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh",
        "category": "paths",
    }


def setup_steps(cfg: dict) -> list[dict[str, Any]]:
    """Return guided first-install / repair setup steps."""
    routers = cfg.get("routers") or []
    return [
        {"step": 1, "title": "Confirm LibreQoS base path", "status_hint": "/opt/libreqos/src should exist", "description": "LQoSync writes LibreQoS-managed config.json, ShapedDevices.csv, and network.json under the LibreQoS src directory."},
        {"step": 2, "title": "Create restricted MikroTik API user", "status_hint": "API read user configured", "description": "Use a read/sensitive/api-only RouterOS user such as libreqosyncAPI and restrict it to the LibreQoS/LQoSync host IP."},
        {"step": 3, "title": "Add or verify routers", "status_hint": f"{len(routers)} router(s) configured", "description": "Each enabled router needs name, address, API port, username, password, root bandwidth, and enabled PPP/DHCP/Hotspot sources."},
        {"step": 4, "title": "Discover DHCP servers", "status_hint": "optional", "description": "Use Config Center DHCP discovery to add MikroTik DHCP server names as disabled-by-default entries, then enable only production access servers."},
        {"step": 5, "title": "Choose network layout mode", "status_hint": cfg.get("network_mode", "router_children"), "description": "Simple flat, router-root, normal hierarchy, or deep/custom hierarchy should match how LibreQoS should group parent nodes."},
        {"step": 6, "title": "Select Smart Policy preset", "status_hint": (cfg.get("policies") or {}).get("mode", "balanced"), "description": "Conservative is safest, Balanced is recommended, Aggressive is for lab/dynamic environments."},
        {"step": 7, "title": "Run Dry Run", "status_hint": "safe simulation", "description": "Dry Run previews CSV/network changes, policy verdict, risk, recommendations, and Smart Insights without writing files or applying LibreQoS."},
        {"step": 8, "title": "Enable scheduler only after clean dry-run", "status_hint": "production step", "description": "Enable scheduler and auto-apply only after Policy Center and Dry Run show safe/expected behavior."},
    ]


def repair_commands() -> list[dict[str, Any]]:
    return [
        {
            "title": "Repair / reinstall bare-metal safely",
            "description": "Reapplies service file, sudoers, ACLs, config migration, and runtime folders while preserving live LibreQoS files.",
            "command": "cd /opt/LQoSync\nsudo systemctl stop lqosync\nsudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh\nsudo systemctl start lqosync",
        },
        {
            "title": "Restore LibreQoS permissions after uninstall or stale ACLs",
            "description": "Returns LQoSync-managed LibreQoS files to root ownership and removes stale lqosync ACL entries.",
            "command": "sudo bash /opt/LQoSync/scripts/restore_libreqos_permissions.sh",
        },
        {
            "title": "Run environment doctor",
            "description": "Checks config, paths, permissions, LibreQoS command path, and optional router API reachability.",
            "command": "cd /opt/LQoSync\nsudo CONFIG_PATH=/opt/libreqos/src/config.json python3 scripts/doctor.py",
        },
        {
            "title": "Safe GitHub update",
            "description": "Pulls code and migrates missing safe defaults while preserving config, users, logs, state, generated files, and LibreQoS operational data.",
            "command": "cd /opt/LQoSync\nsudo UPDATE_POLICY=preserve_and_migrate bash upgrade.sh",
        },
        {
            "title": "Adopt existing ZIP/manual install into GitHub-managed install",
            "description": "Backs up existing /opt/LQoSync, clones GitHub source, restores local data, and runs preserve-existing install.",
            "command": "curl -fsSL https://raw.githubusercontent.com/p33ckab00/LQoSync/lqosync-in-rust/install-from-github.sh -o /tmp/install-lqosync.sh\nsudo EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh",
        },
        {
            "title": "Check LibreQoS core services",
            "description": "Verifies the main LibreQoS services expected by modern LibreQoS installations.",
            "command": "sudo systemctl status lqosd lqos_scheduler --no-pager",
        },
    ]


def apply_policy_preset(cfg: dict, preset: str) -> dict:
    """Return a config copy with a known policy preset applied."""
    preset = (preset or "balanced").strip().lower()
    if preset not in {"conservative", "balanced", "aggressive"}:
        raise ValueError("preset must be conservative, balanced, or aggressive")
    out = deepcopy(cfg)
    policies = smart_policy_defaults()
    policies["mode"] = preset
    sources = policies["cleanup_sources"]
    if preset == "conservative":
        for s in sources.values():
            s["normal_inactive_action"] = "cleanup_next_run"
            s["source_disabled_action"] = "require_confirm_next_run"
            s["collector_failed_action"] = "preserve_rows"
            s["zero_result_action"] = "block_cleanup"
            s["mass_removal_action"] = "require_confirm_next_run"
            s["respect_percentage_guards"] = True
        policies["apply_guard"]["require_manual_confirm_on_medium_risk"] = True
    elif preset == "aggressive":
        for name, s in sources.items():
            if name == "static":
                continue
            s["normal_inactive_action"] = "cleanup_immediate"
            s["source_disabled_action"] = "cleanup_next_run"
            s["collector_failed_action"] = "preserve_rows"
            # Even in Aggressive mode, a full zero-result from an enabled source
            # is not treated like a normal inactive client. Zero-result can be
            # caused by API/query/VLAN trouble, so cleanup remains blocked.
            s["zero_result_action"] = "block_cleanup"
            s["mass_removal_action"] = "require_confirm_next_run"
            s["respect_percentage_guards"] = name == "pppoe"
        policies["apply_guard"]["require_manual_confirm_on_medium_risk"] = False
    out["policies"] = policies
    return out


def compute_setup_repair_report(
    cfg: dict,
    state: dict | None = None,
    *,
    git_status: dict | None = None,
    services: dict | None = None,
    config_errors: list[str] | None = None,
    config_warnings: list[str] | None = None,
) -> dict[str, Any]:
    state = state or {}
    git_status = git_status or {}
    services = services or {}
    checks: list[dict[str, Any]] = []

    config_errors = config_errors or []
    config_warnings = config_warnings or []
    if config_errors:
        _add_check(checks, key="config_valid", title="config.json validation", status="fail", detail=f"{len(config_errors)} error(s)", why="Invalid config can prevent sync or cause unsafe output.", fix="Open Config Center and fix the listed validation errors.", category="config")
    elif config_warnings:
        _add_check(checks, key="config_valid", title="config.json validation", status="warn", detail=f"Valid with {len(config_warnings)} warning(s)", why="Warnings usually indicate incomplete router/source settings.", fix="Review Config Center warnings before enabling scheduler.", category="config")
    else:
        _add_check(checks, key="config_valid", title="config.json validation", status="ok", detail="Config validation passed", category="config")

    paths = cfg.get("paths") or {}
    for key, title in (
        ("shaped_devices_csv", "ShapedDevices.csv"),
        ("network_json", "network.json"),
        ("runtime_state", "runtime_state.json"),
        ("policy_state", "policy_state.json"),
        ("audit_log", "audit.jsonl"),
    ):
        checks.append(_path_check(paths.get(key), key=f"path_{key}", title=title, write_test=True))
    checks.append(_path_check(paths.get("backup_dir"), key="path_backup_dir", title="Backup directory", expected="dir", write_test=True))

    lib = cfg.get("libreqos") or {}
    lq_cmd = Path(str(lib.get("cmd") or ""))
    wd = Path(str(lib.get("working_dir") or ""))
    _add_check(
        checks,
        key="libreqos_cmd",
        title="LibreQoS.py command",
        status="ok" if lq_cmd.exists() else "warn",
        detail=str(lq_cmd) + (" exists" if lq_cmd.exists() else " missing"),
        why="LQoSync calls LibreQoS.py --updateonly after safe file changes.",
        fix="Install LibreQoS or fix libreqos.cmd in Config Center.",
        command="ls -lah /opt/libreqos/src/LibreQoS.py",
        category="libreqos",
    )
    _add_check(
        checks,
        key="libreqos_working_dir",
        title="LibreQoS working directory",
        status="ok" if wd.exists() and wd.is_dir() else "fail",
        detail=str(wd) + (" exists" if wd.exists() else " missing"),
        why="LibreQoS.py resolves ShapedDevices.csv and network.json relative to its working directory.",
        fix="Set libreqos.working_dir to /opt/libreqos/src and rerun install.sh preserve_existing.",
        command="grep -A12 '\"libreqos\"' /opt/libreqos/src/config.json",
        category="libreqos",
    )
    mode = str(lib.get("run_mode") or "")
    _add_check(
        checks,
        key="runner_mode",
        title="Bare-metal runner mode",
        status="ok" if mode == "direct" else "warn",
        detail=f"run_mode={mode}",
        why="Bare-metal installs should use direct mode. Docker-only host_nsenter causes permission errors on systemd installs.",
        fix="Set libreqos.run_mode=direct and HOST_CONTROL_MODE=direct for bare-metal.",
        category="libreqos",
    )

    routers = cfg.get("routers") or []
    enabled_routers = [r for r in routers if r.get("enabled", True)]
    _add_check(
        checks,
        key="routers_configured",
        title="Routers configured",
        status="ok" if enabled_routers else "warn",
        detail=f"{len(enabled_routers)} enabled router(s), {len(routers)} total",
        why="At least one enabled MikroTik router is needed for live sync.",
        fix="Add or enable a router in Config Center, then test its API connection.",
        category="mikrotik",
    )
    missing_credentials = [r.get("name") or r.get("address") or "router" for r in enabled_routers if not r.get("address") or not r.get("username") or not r.get("password")]
    if missing_credentials:
        _add_check(checks, key="router_credentials", title="Router API credentials", status="warn", detail=", ".join(missing_credentials[:5]), why="Missing address/username/password prevents API collection.", fix="Configure restricted RouterOS API user and credentials in Config Center.", category="mikrotik")
    else:
        _add_check(checks, key="router_credentials", title="Router API credentials", status="ok" if enabled_routers else "info", detail="Enabled routers have address/username/password fields", category="mikrotik")

    required_services = ["lqosd", "lqos_scheduler", "lqosync"]
    for unit in required_services:
        st = (services.get(unit) or {}).get("active") if isinstance(services.get(unit), dict) else None
        _add_check(checks, key=f"service_{unit}", title=f"Service {unit}", status="ok" if st == "active" else "warn", detail=f"active={st or 'unknown'}", why="Required services should be active for production operation.", fix=f"Inspect and restart {unit} if needed.", command=f"sudo systemctl status {unit} --no-pager", category="services")

    relation = git_status.get("relation") or "unknown"
    update_needed = relation in {"behind", "diverged"} or git_status.get("version_relation") == "different"
    _add_check(
        checks,
        key="git_status",
        title="Git/update status",
        status="warn" if update_needed else ("ok" if relation == "up_to_date" else "info"),
        detail=f"relation={relation}, local={git_status.get('local_version','unknown')}, remote={git_status.get('remote_version','unknown')}",
        why="Git-managed installs can be updated safely with preserve-and-migrate policy.",
        fix="Use Update Center commands if update is available or history diverged.",
        command="cd /opt/LQoSync && sudo UPDATE_POLICY=preserve_and_migrate bash upgrade.sh",
        category="updates",
    )

    release_report = compute_release_integrity()
    rel_summary = release_report.get("summary", {})
    _add_check(
        checks,
        key="release_integrity",
        title="Package route/template integrity",
        status="fail" if rel_summary.get("fail", 0) else ("warn" if rel_summary.get("warn", 0) else "ok"),
        detail=f"OK={rel_summary.get('ok',0)} WARN={rel_summary.get('warn',0)} FAIL={rel_summary.get('fail',0)}",
        why="Navigation links, Flask routes, templates, engine files, and config defaults must be internally consistent before production use.",
        fix="Run python3 scripts/release_check.py and repair any missing routes/templates/defaults.",
        command="cd /opt/LQoSync && python3 scripts/release_check.py",
        category="release",
    )

    backup_enabled = bool((cfg.get("app") or {}).get("backup_before_apply", False))
    auto_apply = bool((cfg.get("app") or {}).get("auto_apply", True))
    _add_check(
        checks,
        key="backup_readiness",
        title="Optional auto-backup before apply",
        status="ok",
        detail=f"backup_before_apply={backup_enabled}, auto_apply={auto_apply}",
        why="Auto-backup before apply is optional. Disabling it reduces storage growth but also reduces automatic rollback convenience.",
        fix="Leave disabled for storage-saving mode, or enable app.backup_before_apply when you want automatic rollback points for every apply.",
        category="safety",
    )

    worst = max((STATUS_RANK.get(c.get("status"), 1) for c in checks), default=0)
    fails = sum(1 for c in checks if c.get("status") == "fail")
    warns = sum(1 for c in checks if c.get("status") == "warn")
    score = max(0, 100 - fails * 20 - warns * 7)
    readiness = "ready" if worst == 0 else ("needs_attention" if fails == 0 else "repair_required")

    return {
        "readiness": readiness,
        "score": score,
        "fails": fails,
        "warnings": warns,
        "checks": checks,
        "setup_steps": setup_steps(cfg),
        "repair_commands": repair_commands(),
        "recommended_next_action": _recommended_next_action(readiness, checks),
        "release_integrity": release_report,
    }


def _recommended_next_action(readiness: str, checks: list[dict[str, Any]]) -> str:
    if readiness == "ready":
        return "Run Dry Run, review Policy Center verdict, then enable scheduler when output is expected."
    first_fail = next((c for c in checks if c.get("status") == "fail"), None)
    if first_fail:
        return first_fail.get("fix") or "Fix failed checks first, then rerun Setup / Repair Center."
    first_warn = next((c for c in checks if c.get("status") == "warn"), None)
    if first_warn:
        return first_warn.get("fix") or "Review warnings before enabling production scheduler."
    return "Review setup checklist and run a safe dry-run simulation."
