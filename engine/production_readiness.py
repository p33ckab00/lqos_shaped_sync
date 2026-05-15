"""Production readiness scoring for LQoSync.

This module is read-only. It turns existing setup, config, policy, source health,
backup, dry-run, and apply status into one operator-facing production readiness
score. It intentionally does not contact MikroTik, write files, run LibreQoS, or
change scheduler state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from engine.policy_conflicts import evaluate_policy_conflicts
except Exception:  # pragma: no cover - import safety for standalone checks
    evaluate_policy_conflicts = None  # type: ignore


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return default


def _is_ok_status(value: Any) -> bool:
    text = str(value or "").lower()
    return text not in {"", "failed", "error", "blocked", "blocked_by_policy", "critical"}


def _path_exists(path: Any, expected: str = "file") -> bool:
    if not path:
        return False
    p = Path(str(path))
    return p.is_dir() if expected == "dir" else p.exists()


def _add(items: list[dict[str, Any]], key: str, label: str, status: str, points: int, detail: str, recommendation: str = "", target: str = "") -> None:
    items.append({
        "key": key,
        "label": label,
        "status": status,
        "points": points,
        "detail": detail,
        "recommendation": recommendation,
        "target": target,
    })


def _level(score: int, blockers: int) -> str:
    if blockers:
        return "blocked"
    if score >= 95:
        return "production_ready"
    if score >= 85:
        return "ready_with_warnings"
    if score >= 70:
        return "needs_review"
    return "not_ready"


def compute_production_readiness(
    cfg: dict[str, Any],
    state: dict[str, Any] | None = None,
    *,
    setup_wizard: dict[str, Any] | None = None,
    health_report: dict[str, Any] | None = None,
    config_errors: list[str] | None = None,
    config_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Compute a compact production readiness report.

    The score is deliberately conservative. It should help operators see whether
    the system is safe to run unattended, but it never blocks anything by itself;
    scheduler/config/policy guards remain the enforcement points.
    """
    state = state or {}
    setup_wizard = setup_wizard or {}
    health_report = health_report or {}
    config_errors = config_errors or []
    config_warnings = config_warnings or []

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []
    score = 100

    def penalize(points: int, reason: str, *, blocker: bool = False, warning: bool = True) -> None:
        nonlocal score
        score -= points
        if blocker:
            blockers.append(reason)
        elif warning:
            warnings.append(reason)

    # 1. Config validity
    if config_errors:
        detail = f"{len(config_errors)} config error(s): " + "; ".join(config_errors[:3])
        penalize(35, detail, blocker=True)
        _add(checks, "config", "Config validity", "fail", -35, detail, "Fix Config Center errors before production go-live.", "/config")
    elif config_warnings:
        detail = f"{len(config_warnings)} config warning(s): " + "; ".join(config_warnings[:3])
        penalize(min(18, len(config_warnings) * 5), detail)
        _add(checks, "config", "Config validity", "warn", -min(18, len(config_warnings) * 5), detail, "Review warnings in Config Center.", "/config")
    else:
        _add(checks, "config", "Config validity", "ok", 0, "No config errors or warnings detected.", "", "/config")

    # 2. Setup wizard and dry-run readiness
    progress = _as_int(setup_wizard.get("progress"), 0)
    if setup_wizard and not setup_wizard.get("production_ready"):
        detail = "; ".join(setup_wizard.get("go_live_blockers") or []) or f"Setup progress is {progress}%."
        penalize(20 if setup_wizard.get("go_live_blockers") else 10, detail, blocker=bool(setup_wizard.get("go_live_blockers")))
        _add(checks, "setup", "First Run Setup", "fail" if setup_wizard.get("go_live_blockers") else "warn", -20, detail, "Finish Setup Wizard and run Dry Run.", "/setup-wizard")
    else:
        _add(checks, "setup", "First Run Setup", "ok", 0, f"Setup progress {progress or 100}% and production gate passed.", "", "/setup-wizard")

    dry = state.get("last_dry_run") or {}
    dry_status = dry.get("status") if isinstance(dry, dict) else None
    if not dry:
        penalize(12, "No Dry Run result is recorded.")
        _add(checks, "dry_run", "Dry Run", "warn", -12, "No Dry Run result is recorded.", "Run Dry Run before enabling unattended scheduler.", "/sync/dry-run")
    elif not _is_ok_status(dry_status):
        penalize(20, f"Last Dry Run status is {dry_status}.", blocker=True)
        _add(checks, "dry_run", "Dry Run", "fail", -20, f"Last Dry Run status is {dry_status}.", "Open Dry Run and review policy/data verdict.", "/sync/dry-run")
    else:
        _add(checks, "dry_run", "Dry Run", "ok", 0, f"Last Dry Run status is {dry_status or 'recorded'}.", "", "/sync/dry-run")

    # 3. Router/source readiness
    source_summary = setup_wizard.get("source_summary") or {}
    enabled_sources = _as_int(source_summary.get("pppoe")) + _as_int(source_summary.get("dhcp")) + _as_int(source_summary.get("hotspot"))
    enabled_routers = _as_int(source_summary.get("enabled_routers"))
    if not enabled_routers:
        penalize(18, "No enabled MikroTik router is configured.", blocker=True)
        _add(checks, "routers", "Router access", "fail", -18, "No enabled MikroTik router is configured.", "Add/test a router in Config Center.", "/config")
    elif not enabled_sources:
        penalize(16, "No PPPoE/DHCP/Hotspot source is enabled.", blocker=True)
        _add(checks, "sources", "Traffic sources", "fail", -16, "No PPPoE/DHCP/Hotspot source is enabled.", "Enable at least one source in Config Center.", "/config")
    else:
        _add(checks, "sources", "Router/source readiness", "ok", 0, f"{enabled_routers} enabled router(s); {enabled_sources} enabled source group(s).", "", "/config")

    # 4. Operation mode, auto-apply requirement, and optional backup policy.
    app_cfg = cfg.get("app") or {}
    operation_mode = str(app_cfg.get("operation_mode") or "automatic").strip().lower()
    auto_apply = bool(app_cfg.get("auto_apply", True))
    backup_before = bool(app_cfg.get("backup_before_apply", False))
    backup_retention = _as_int(app_cfg.get("backup_retention"), 10)
    if operation_mode == "automatic" and not auto_apply:
        penalize(30, "Automatic operation mode requires app.auto_apply=true.", blocker=True)
        _add(checks, "auto_apply", "Auto Apply Requirement", "fail", -30, "Operation mode is automatic but auto_apply is disabled.", "Enable app.auto_apply or switch app.operation_mode to manual.", "/config")
    elif operation_mode == "manual" and not auto_apply:
        _add(checks, "auto_apply", "Auto Apply Requirement", "ok", 0, "Manual operation mode: auto_apply is optional and currently disabled.", "", "/config")
    else:
        _add(checks, "auto_apply", "Auto Apply Requirement", "ok", 0, f"operation_mode={operation_mode}, auto_apply={auto_apply}.", "", "/config")

    if backup_before:
        backup_detail = f"Optional auto-backup is enabled; retention={backup_retention}."
        if backup_retention < 1:
            penalize(3, "Auto-backup is enabled but backup_retention is below 1.")
            _add(checks, "backup", "Auto Backup Policy", "warn", -3, backup_detail, "Set backup_retention to at least 1 or disable auto-backup.", "/config")
        else:
            _add(checks, "backup", "Auto Backup Policy", "ok", 0, backup_detail, "", "/config")
    else:
        _add(checks, "backup", "Auto Backup Policy", "ok", 0, "Optional auto-backup is disabled by operator choice. Storage use is reduced; rollback convenience is reduced.", "Use manual backup before major updates or enable backup_before_apply if you want automatic rollback points.", "/config")

    # 5. File/path readiness
    paths = cfg.get("paths") or {}
    path_failures = []
    for key in ("shaped_devices_csv", "network_json"):
        if not paths.get(key):
            path_failures.append(f"paths.{key} missing")
        elif not Path(str(paths.get(key))).is_absolute():
            path_failures.append(f"paths.{key} not absolute")
    lib = cfg.get("libreqos") or {}
    working_dir = lib.get("working_dir") or paths.get("libreqos_src") or "/opt/libreqos/src"
    if working_dir and not _path_exists(working_dir, "dir"):
        path_failures.append(f"LibreQoS working_dir not found: {working_dir}")
    if path_failures:
        penalize(18, "; ".join(path_failures[:3]), blocker=True)
        _add(checks, "paths", "LibreQoS paths", "fail", -18, "; ".join(path_failures[:3]), "Open Setup & Repair and verify LibreQoS paths.", "/setup-repair")
    else:
        _add(checks, "paths", "LibreQoS paths", "ok", 0, "Generated file paths and working_dir look usable.", "", "/setup-repair")

    # 6. Policy conflicts
    conflicts = []
    if evaluate_policy_conflicts is not None:
        try:
            conflicts = evaluate_policy_conflicts(cfg).get("conflicts", []) or []
        except Exception:
            conflicts = []
    critical_conflicts = [c for c in conflicts if str(c.get("severity") or "").lower() in {"critical", "high"}]
    warn_conflicts = [c for c in conflicts if str(c.get("severity") or "").lower() in {"warning", "medium"}]
    if critical_conflicts:
        detail = "; ".join(str(c.get("title") or c.get("summary") or "policy conflict") for c in critical_conflicts[:3])
        penalize(min(25, len(critical_conflicts) * 8), detail, blocker=False)
        _add(checks, "policy_conflicts", "Policy conflicts", "warn", -min(25, len(critical_conflicts) * 8), detail, "Open Config Center → Policies and resolve high-risk conflicts.", "/config?tab=policies")
    elif warn_conflicts:
        detail = "; ".join(str(c.get("title") or c.get("summary") or "policy warning") for c in warn_conflicts[:3])
        penalize(min(12, len(warn_conflicts) * 4), detail)
        _add(checks, "policy_conflicts", "Policy conflicts", "warn", -min(12, len(warn_conflicts) * 4), detail, "Review Policy Conflict Resolver.", "/config?tab=policies")
    else:
        _add(checks, "policy_conflicts", "Policy conflicts", "ok", 0, "No high-risk policy conflicts detected.", "", "/config?tab=policies")

    # 7. Health report integration
    health_score = _as_int(health_report.get("health_score"), 0) if health_report else 0
    if health_report:
        if health_score < 50:
            penalize(25, f"Dashboard health score is {health_score}%.", blocker=False)
            _add(checks, "health", "Dashboard health", "fail", -25, f"Dashboard health score is {health_score}%.", "Review Dashboard source/apply health.", "/#source-health-performance")
        elif health_score < 75:
            penalize(12, f"Dashboard health score is {health_score}%.")
            _add(checks, "health", "Dashboard health", "warn", -12, f"Dashboard health score is {health_score}%.", "Review warnings on Dashboard.", "/#source-health-performance")
        else:
            _add(checks, "health", "Dashboard health", "ok", 0, f"Dashboard health score is {health_score}%.", "", "/#source-health-performance")

        apply = health_report.get("libreqos_apply_health") or {}
        if apply.get("status") in {"error", "pending", "warning"}:
            points = 18 if apply.get("status") == "error" else 10
            msg = f"LibreQoS apply health is {apply.get('status')}."
            penalize(points, msg, blocker=False)
            _add(checks, "apply_health", "LibreQoS apply health", "warn" if apply.get("status") != "error" else "fail", -points, msg, "Open Operations Center apply history.", "/operations?tab=apply")

        service_counts = health_report.get("service_counts") or {}
        failed_services = _as_int(service_counts.get("failed"), 0)
        if failed_services:
            msg = f"{failed_services} monitored service(s) are failed/inactive."
            penalize(min(20, failed_services * 8), msg)
            _add(checks, "services", "Service health", "warn", -min(20, failed_services * 8), msg, "Open Operations Center services tab.", "/operations?tab=services")

    # Normalize and summarize
    score = max(0, min(100, score))
    level = _level(score, len(blockers))
    if blockers:
        next_action = "Resolve blockers before enabling unattended scheduler or relying on auto-apply."
    elif score < 85:
        next_action = "Review warnings and run Dry Run again before production go-live."
    elif warnings:
        next_action = "Production can proceed with caution after reviewing warnings."
    else:
        next_action = "Production readiness looks good. Continue monitoring Dashboard and Operations Center."

    recommendations.extend([item.get("recommendation") for item in checks if item.get("recommendation") and item.get("status") in {"warn", "fail"}])
    recommendations = [r for i, r in enumerate(recommendations) if r and r not in recommendations[:i]]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score": score,
        "level": level,
        "label": level.replace("_", " ").title(),
        "blockers": blockers,
        "warnings": warnings,
        "recommendations": recommendations[:8],
        "next_action": next_action,
        "checks": checks,
        "summary": {
            "checks": len(checks),
            "ok": sum(1 for c in checks if c.get("status") == "ok"),
            "warn": sum(1 for c in checks if c.get("status") == "warn"),
            "fail": sum(1 for c in checks if c.get("status") == "fail"),
        },
    }
