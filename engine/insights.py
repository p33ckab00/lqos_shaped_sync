"""Smart Insights helpers for LQoSync.

This module turns raw sync/policy metrics into operator-facing guidance. It is
rule-based and intentionally explainable: every recommendation should tell the
operator what happened, why it matters, and what to do next.
"""
from __future__ import annotations

from typing import Any


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or 0)
    except Exception:
        return default


def _pct(part: float, total: float) -> float:
    if not total:
        return 0.0
    return round((part / total) * 100.0, 2)


def _severity_rank(severity: str) -> int:
    return {"critical": 4, "high": 3, "warning": 2, "info": 1, "ok": 0}.get(str(severity or "info"), 1)


def _add_recommendation(items: list[dict[str, Any]], title: str, reason: str, action: str, severity: str = "info", **extra: Any) -> None:
    rec = {"title": title, "reason": reason, "action": action, "severity": severity, **extra}
    # Deduplicate by title+action while preserving strongest severity.
    for existing in items:
        if existing.get("title") == title and existing.get("action") == action:
            if _severity_rank(severity) > _severity_rank(existing.get("severity")):
                existing.update(rec)
            return
    items.append(rec)


def speed_fallback_review(result: Any) -> dict[str, Any]:
    """Return fallback/default speed usage summary from result.meta."""
    meta = getattr(result, "meta", {}) or {}
    fallback_rows = []
    by_source: dict[str, int] = {}
    for code, m in meta.items():
        src = str(m.get("speed_source") or "unknown")
        by_source[src] = by_source.get(src, 0) + 1
        src_l = src.lower()
        if "default" in src_l or "fallback" in src_l or src_l in {"config_default", "unknown"}:
            fallback_rows.append({
                "code": code,
                "source_type": m.get("source_type") or "unknown",
                "router": m.get("router") or "unknown",
                "server": m.get("server") or "",
                "profile": m.get("profile") or "",
                "speed_source": src,
                "speed_raw_value": m.get("speed_raw_value") or "",
                "download_mbps": m.get("base_rx"),
                "upload_mbps": m.get("base_tx"),
            })
    total = len(meta)
    return {
        "total_rows_with_metadata": total,
        "fallback_count": len(fallback_rows),
        "fallback_percent": _pct(len(fallback_rows), total),
        "fallback_rows": fallback_rows[:100],
        "source_breakdown": by_source,
    }


def data_quality_score(config: dict, result: Any, policy_decision: dict[str, Any], preflight: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compute a simple operator-readable data quality score."""
    preflight = preflight or {}
    errors = list(getattr(result, "errors", []) or []) + list(preflight.get("errors", []) or [])
    warnings = list(getattr(result, "warnings", []) or []) + list(preflight.get("warnings", []) or [])
    router_errors = list(getattr(result, "router_errors", []) or [])
    fallback = speed_fallback_review(result)
    counts = getattr(result, "counts", {}) or {}
    rows = _as_int(counts.get("csv_rows"), 0)
    score = 100
    factors: list[dict[str, Any]] = []

    def penalize(points: int, title: str, message: str, severity: str = "warning"):
        nonlocal score
        score -= points
        factors.append({"title": title, "message": message, "penalty": points, "severity": severity})

    if errors:
        penalize(min(40, 12 * len(errors)), "Validation errors", f"{len(errors)} error(s) were reported by preflight or sync.", "critical")
    if router_errors:
        penalize(min(30, 10 * len(router_errors)), "Collector/router errors", f"{len(router_errors)} router/source collector error(s) were reported.", "high")
    if warnings:
        penalize(min(15, 3 * len(warnings)), "Warnings", f"{len(warnings)} warning(s) were reported.", "warning")
    fp = fallback.get("fallback_percent", 0)
    if fp >= 50:
        penalize(25, "Many fallback speeds", f"{fp}% of metadata-backed rows used default/fallback speed sources.", "high")
    elif fp >= 10:
        penalize(10, "Fallback speeds detected", f"{fp}% of metadata-backed rows used default/fallback speed sources.", "warning")
    if policy_decision.get("verdict") == "blocked_by_policy":
        penalize(35, "Policy blocked output", "Policy Center blocked file write/apply for safety.", "critical")
    elif policy_decision.get("verdict") == "requires_confirmation":
        penalize(18, "Confirmation required", "A cleanup/apply action requires operator confirmation.", "high")
    if rows <= 0 and getattr(result, "routers_processed", 0):
        penalize(20, "No generated rows", "Routers were processed but no CSV rows were generated.", "high")

    score = max(0, min(100, score))
    if score >= 90:
        level = "excellent"
    elif score >= 75:
        level = "good"
    elif score >= 50:
        level = "needs_attention"
    else:
        level = "poor"
    return {"score": score, "level": level, "factors": factors, "rows": rows}


def backup_readiness(config: dict, result: Any | None = None) -> dict[str, Any]:
    app = config.get("app", {}) or {}
    enabled = bool(app.get("backup_before_apply", True))
    retention = _as_int(app.get("backup_retention"), 30)
    auto_apply = bool(app.get("auto_apply", True))
    status = "ready" if enabled and retention >= 1 else "warning"
    message = "Backups are enabled before file writes/apply." if enabled else "backup_before_apply is disabled."
    if enabled and retention < 30:
        status = "warning"
        message = "Backups are enabled but retention is lower than the recommended 30 backups."
    return {
        "enabled": enabled,
        "retention": retention,
        "auto_apply": auto_apply,
        "status": status,
        "message": message,
        "recommended_retention": 30,
    }


def anomaly_detection(config: dict, result: Any, state_before: dict[str, Any] | None = None) -> dict[str, Any]:
    """Detect simple anomalies against the last successful/known run."""
    state_before = state_before or {}
    settings = ((config.get("policies") or {}).get("anomaly_detection") or {})
    if settings and not settings.get("enabled", True):
        return {"enabled": False, "anomalies": []}
    last = state_before.get("last_run") or {}
    anomalies: list[dict[str, Any]] = []
    counts = getattr(result, "counts", {}) or {}
    current_clients = _as_int(counts.get("csv_rows"), 0)
    previous_clients = _as_int(((last.get("counts") or {}).get("csv_rows")), 0)
    drop_threshold = _as_float(settings.get("warn_if_client_count_drops_percent", 30), 30)
    if previous_clients > 0 and current_clients < previous_clients:
        dropped = previous_clients - current_clients
        pct = _pct(dropped, previous_clients)
        if pct >= drop_threshold:
            anomalies.append({
                "title": "Client count dropped",
                "severity": "high",
                "message": f"Generated CSV row count dropped from {previous_clients} to {current_clients} ({pct}% drop).",
                "why": "A sudden drop may indicate collector failure, disabled source, topology/config change, or API issue.",
                "next_action": "Review Policy Center, Dry Run verdict, source collector status, and pending cleanup confirmations before applying.",
            })
    current_cycle_ms = _as_float((getattr(result, "timings", {}) or {}).get("cycle_total"), 0)
    previous_cycle_ms = _as_float(((last.get("timings") or {}).get("cycle_total")), 0)
    mult = _as_float(settings.get("warn_if_sync_duration_increases_multiplier", 5), 5)
    if previous_cycle_ms > 0 and current_cycle_ms > previous_cycle_ms * mult:
        anomalies.append({
            "title": "Sync duration increased",
            "severity": "warning",
            "message": f"Current sync took {round(current_cycle_ms,2)}ms vs previous {round(previous_cycle_ms,2)}ms.",
            "why": "A sudden sync slowdown usually points to MikroTik API latency, large table growth, DNS/system load, or LibreQoS apply delay.",
            "next_action": "Check Performance Breakdown and Data Source Status cards to locate the slow step.",
        })
    current_apply_ms = _as_float((getattr(result, "timings", {}) or {}).get("libreqos_apply"), 0)
    previous_apply_ms = _as_float(((last.get("timings") or {}).get("libreqos_apply")), 0)
    apply_mult = _as_float(settings.get("warn_if_apply_duration_increases_multiplier", 5), 5)
    if previous_apply_ms > 0 and current_apply_ms > previous_apply_ms * apply_mult:
        anomalies.append({
            "title": "LibreQoS apply duration increased",
            "severity": "warning",
            "message": f"Current apply took {round(current_apply_ms,2)}ms vs previous {round(previous_apply_ms,2)}ms.",
            "why": "A longer apply may indicate more queues/IP mappings, kernel/CPU pressure, or larger topology changes.",
            "next_action": "Open Services & Journals and inspect the latest LibreQoS apply stdout/stderr and elapsed time.",
        })
    return {"enabled": True, "anomalies": anomalies}


def smart_warning_explanations(result: Any, policy_decision: dict[str, Any]) -> list[dict[str, Any]]:
    """Map common warnings/errors to Why/Fix/Next Action cards."""
    entries: list[dict[str, Any]] = []
    raw_items = []
    raw_items.extend(str(x) for x in getattr(result, "warnings", []) or [])
    raw_items.extend(str(x) for x in getattr(result, "errors", []) or [])
    for item in raw_items[:25]:
        low = item.lower()
        if "fallback" in low or "default speed" in low:
            entries.append({"title": "Fallback speed used", "what": item, "why": "The speed resolver could not find a higher-priority speed source for one or more clients.", "fix": "Add speed to PPP secret comment/profile comment/profile name, DHCP server speed_comment/name, or Hotspot user/profile metadata."})
        elif "parent" in low:
            entries.append({"title": "Parent node problem", "what": item, "why": "LibreQoS requires CSV Parent Node values to exist in network.json when hierarchy is used.", "fix": "Open Network Layout, validate topology, and ensure generated Parent Node names exist before applying."})
        elif "duplicate" in low and "ip" in low:
            entries.append({"title": "Duplicate IP detected", "what": item, "why": "Two circuits sharing one IPv4 can cause incorrect shaping/IP mapping.", "fix": "Check PPP/DHCP leases and stale rows; resolve duplicate addresses before applying."})
        elif "collector" in low or "router" in low or "api" in low:
            entries.append({"title": "Collector/API warning", "what": item, "why": "Incomplete MikroTik data can cause stale row cleanup or missing generated clients.", "fix": "Check MikroTik API service, credentials, firewall rules, router address, and source-specific collector status."})
    for b in (policy_decision.get("blocked_reasons") or [])[:10]:
        entries.append({"title": b.get("title") or "Policy blocked action", "what": b.get("message") or "Policy blocked file write/apply.", "why": "Policy Center blocks risky output before files are written or LibreQoS is applied.", "fix": "Review Policy Center verdict, run Dry Run, and address the blocked reason before applying."})
    return entries[:12]


def compute_smart_insights(config: dict, result: Any, policy_decision: dict[str, Any] | None = None, state_before: dict[str, Any] | None = None, preflight: dict[str, Any] | None = None, policy_state: dict[str, Any] | None = None, git_status: dict[str, Any] | None = None) -> dict[str, Any]:
    policy_decision = policy_decision or {}
    recommendations: list[dict[str, Any]] = []
    fallback = speed_fallback_review(result)
    quality = data_quality_score(config, result, policy_decision, preflight=preflight)
    backup = backup_readiness(config, result)
    anomalies = anomaly_detection(config, result, state_before=state_before)
    explanations = smart_warning_explanations(result, policy_decision)

    # Carry recommendations from policy engine first.
    for rec in policy_decision.get("recommendations") or []:
        _add_recommendation(recommendations, rec.get("title") or "Policy recommendation", rec.get("reason") or "Policy Center generated a recommendation.", rec.get("action") or "Open Policy Center for details.", rec.get("severity") or "info", source="policy")

    if fallback.get("fallback_count", 0):
        sev = "high" if fallback.get("fallback_percent", 0) >= 50 else "warning"
        _add_recommendation(
            recommendations,
            "Review fallback-speed clients",
            f"{fallback['fallback_count']} client(s) used default/fallback speed sources ({fallback['fallback_percent']}%).",
            "Open Shaped Devices and filter Speed Source for default/fallback, then add better speed data to comments/profile/server names.",
            sev,
            source="speed_resolver",
        )
    if not backup.get("enabled") and backup.get("auto_apply"):
        _add_recommendation(recommendations, "Enable backup_before_apply", "Auto-apply is enabled but backups before apply are disabled.", "Enable backup_before_apply in Config Center before relying on unattended scheduler applies.", "warning", source="backup_guard")
    elif backup.get("enabled") and backup.get("retention", 0) < backup.get("recommended_retention", 30):
        _add_recommendation(recommendations, "Increase backup retention", "Backup retention is below the recommended value for production rollbacks.", "Set backup_retention to at least 30 in Config Center.", "info", source="backup_guard")
    if quality.get("level") in {"needs_attention", "poor"}:
        _add_recommendation(recommendations, "Improve data quality before auto-apply", f"Data Quality is {quality['score']}% ({quality['level'].replace('_',' ')}).", "Review validation errors, collector errors, fallback speeds, and Policy Center warnings before applying.", "high", source="data_quality")
    for a in anomalies.get("anomalies", [])[:5]:
        _add_recommendation(recommendations, a.get("title") or "Anomaly detected", a.get("message") or "Anomaly detected.", a.get("next_action") or "Review Dashboard metrics and Dry Run details.", a.get("severity") or "warning", source="anomaly_detection")
    if git_status and git_status.get("relation") in {"behind", "diverged"}:
        _add_recommendation(recommendations, "Update available or Git diverged", f"Git relation is {git_status.get('relation')}.", "Open Update Center and run the recommended SSH-safe update command.", "info", source="update_center")

    verdict = policy_decision.get("verdict") or "unknown"
    if verdict == "blocked_by_policy":
        summary = "Action blocked by policy. Fix blocked reasons before writing files/applying LibreQoS."
    elif verdict == "requires_confirmation":
        summary = "Operator confirmation required before cleanup/write/apply can continue."
    elif recommendations:
        summary = "Sync is usable, but Smart Insights found recommendations to review."
    else:
        summary = "No major smart-insight recommendations. Current sync state looks healthy."

    return {
        "summary": summary,
        "data_quality": quality,
        "backup_readiness": backup,
        "fallback_speed_review": fallback,
        "anomaly_detection": anomalies,
        "warning_explanations": explanations,
        "recommendations": sorted(recommendations, key=lambda x: _severity_rank(x.get("severity")), reverse=True),
    }
