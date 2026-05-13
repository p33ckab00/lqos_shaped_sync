"""Source health and performance trend helpers for LQoSync.

This module is read-only. It summarizes the latest collector metrics, router/API
latency, LibreQoS apply behavior, and notification-worthy conditions for the
WebUI. It intentionally uses existing runtime state, policy state, audit events,
and apply logs rather than introducing a database.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from engine.audit import audit_path


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or 0)
    except Exception:
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return default


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _read_audit_events(config: dict, limit: int = 1500) -> list[dict[str, Any]]:
    path = audit_path(config)
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
    for line in lines:
        try:
            ev = json.loads(line)
            if isinstance(ev, dict):
                out.append(ev)
        except Exception:
            continue
    return out


def _details(ev: dict[str, Any]) -> dict[str, Any]:
    d = ev.get("details")
    return d if isinstance(d, dict) else {}


def _window(events: list[dict[str, Any]], hours: int) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return [ev for ev in events if (ts := _parse_ts(ev.get("ts"))) and ts >= cutoff]


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _pct(part: float, total: float) -> float:
    return round((part / total) * 100.0, 2) if total else 0.0


def _latest_run(state: dict[str, Any]) -> dict[str, Any]:
    return state.get("last_run") or state.get("last_dry_run") or {}


def _source_policy(config: dict, source: str) -> dict[str, Any]:
    policies = config.get("policies") or {}
    sources = policies.get("cleanup_sources") or {}
    return sources.get(source, {}) if isinstance(sources, dict) else {}


def _source_status(active: int, metrics: dict[str, Any], policy_state: dict[str, Any], source: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if not metrics:
        return "idle", ["No collector metrics recorded yet."]
    if metrics.get("error") or metrics.get("failed"):
        return "error", [str(metrics.get("error") or "Collector reported failure.")]
    if source in {"pppoe", "dhcp", "hotspot"} and active == 0:
        warnings.append("Source produced zero active rows in the latest result.")
    pending = policy_state.get("pending_confirmations") if isinstance(policy_state, dict) else []
    if isinstance(pending, list):
        count = sum(1 for item in pending if isinstance(item, dict) and str(item.get("source") or "").lower() in {source, source.replace("pppoe", "ppoe")})
        if count:
            warnings.append(f"{count} pending cleanup confirmation(s) for this source.")
    if warnings:
        return "warning", warnings
    return "ok", []


def source_health(config: dict, state: dict[str, Any], policy_state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Build per-source health cards from last collector metrics and policies."""
    policy_state = policy_state or {}
    last = _latest_run(state)
    diff = last.get("diff") or {}
    metrics = diff.get("collector_metrics") or {}
    counts = last.get("counts") or {}
    lifecycle = ((diff.get("policy_decision") or {}).get("lifecycle_summary") or diff.get("lifecycle_summary") or {})
    sources = [
        ("pppoe", "PPPoE", "ti-plug-connected", _as_int(counts.get("pppoe"), 0), metrics.get("pppoe") or metrics.get("PPP") or metrics.get("PPPoE") or {}),
        ("dhcp", "DHCP", "ti-affiliate", _as_int(counts.get("dhcp"), 0), metrics.get("dhcp") or metrics.get("DHCP") or {}),
        ("hotspot", "Hotspot", "ti-wifi", _as_int(counts.get("hotspot"), 0), metrics.get("hotspot") or metrics.get("Hotspot") or {}),
    ]
    out: list[dict[str, Any]] = []
    for key, label, icon, active, m in sources:
        status, warnings = _source_status(active, m if isinstance(m, dict) else {}, policy_state, key)
        policy = _source_policy(config, key)
        stale_count = 0
        queued_count = 0
        if isinstance(lifecycle, dict):
            src_life = lifecycle.get(key) or lifecycle.get(label) or {}
            if isinstance(src_life, dict):
                stale_count = _as_int(src_life.get("stale"), 0)
                queued_count = _as_int(src_life.get("queued"), 0)
        out.append({
            "source": key,
            "label": label,
            "icon": icon,
            "status": status,
            "active": active,
            "stale": stale_count,
            "queued": queued_count,
            "cleanup_policy": policy.get("normal_inactive_action") or "unknown",
            "zero_result_policy": policy.get("zero_result_action") or "unknown",
            "collector_failed_policy": policy.get("collector_failed_action") or "unknown",
            "respect_percentage_guards": policy.get("respect_percentage_guards"),
            "warnings": warnings,
            "metrics": m if isinstance(m, dict) else {},
        })
    return out


def performance_trends(config: dict, state: dict[str, Any], audit_events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    audit_events = audit_events if audit_events is not None else _read_audit_events(config)
    events = [ev for ev in audit_events if ev.get("action") in {"sync_finished", "dry_run_complete", "policy_blocked", "files_written"}]
    samples = []
    for ev in events[-100:]:
        d = _details(ev)
        timings = d.get("timings") or {}
        if not isinstance(timings, dict):
            continue
        samples.append({
            "ts": ev.get("ts"),
            "cycle_total": _as_float(timings.get("cycle_total"), 0),
            "routers_total": _as_float(timings.get("routers_total"), 0),
            "libreqos_apply": _as_float(timings.get("libreqos_apply"), 0),
            "action": ev.get("action"),
        })
    latest = _latest_run(state)
    t = latest.get("timings") or {}
    current = {
        "cycle_total": _as_float(t.get("cycle_total"), 0),
        "routers_total": _as_float(t.get("routers_total"), 0),
        "libreqos_apply": _as_float(t.get("libreqos_apply"), 0),
    }
    if not current["cycle_total"] and samples:
        current = {k: samples[-1].get(k, 0) for k in ["cycle_total", "routers_total", "libreqos_apply"]}
    router_values = [s["routers_total"] for s in samples if s["routers_total"] > 0]
    cycle_values = [s["cycle_total"] for s in samples if s["cycle_total"] > 0]
    apply_values = [s["libreqos_apply"] for s in samples if s["libreqos_apply"] > 0]
    api_avg = _avg(router_values[-20:])
    cycle_avg = _avg(cycle_values[-20:])
    apply_avg = _avg(apply_values[-20:])
    multiplier = _as_float(((config.get("monitoring") or {}).get("slowdown_multiplier")), 5.0)

    def trend_status(current_value: float, average: float) -> str:
        if not current_value or not average:
            return "unknown"
        if current_value >= average * multiplier:
            return "slow"
        if current_value >= average * 2:
            return "watch"
        return "normal"

    return {
        "sample_count": len(samples),
        "window": "last 100 audit timing samples",
        "router_api": {
            "current_ms": round(current.get("routers_total", 0), 3),
            "average_ms": api_avg,
            "max_ms": round(max(router_values), 3) if router_values else 0,
            "status": trend_status(current.get("routers_total", 0), api_avg),
        },
        "cycle": {
            "current_ms": round(current.get("cycle_total", 0), 3),
            "average_ms": cycle_avg,
            "max_ms": round(max(cycle_values), 3) if cycle_values else 0,
            "status": trend_status(current.get("cycle_total", 0), cycle_avg),
        },
        "libreqos_apply": {
            "current_ms": round(current.get("libreqos_apply", 0), 3),
            "average_ms": apply_avg,
            "max_ms": round(max(apply_values), 3) if apply_values else 0,
            "status": trend_status(current.get("libreqos_apply", 0), apply_avg),
        },
        "samples": samples[-50:],
    }


def libreqos_apply_health(config: dict, state: dict[str, Any], apply_runs: list[dict[str, Any]] | None = None, audit_events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    apply_runs = apply_runs or []
    audit_events = audit_events if audit_events is not None else _read_audit_events(config)
    recent = apply_runs[:25] if isinstance(apply_runs, list) else []
    ok_count = sum(1 for r in recent if r.get("ok") is True)
    fail_count = sum(1 for r in recent if r.get("ok") is False)
    durations = [_as_float(r.get("duration_seconds"), 0) for r in recent if _as_float(r.get("duration_seconds"), 0) > 0]
    last_apply = recent[0] if recent else None
    audit_apply = [ev for ev in audit_events if ev.get("action") == "libreqos_apply"][-25:]
    repeated_failures = 0
    for r in recent:
        if r.get("ok") is False:
            repeated_failures += 1
        else:
            break
    status = "ok"
    warnings: list[str] = []
    if state.get("pending_libreqos_apply"):
        status = "pending"
        warnings.append("A pending LibreQoS apply is recorded in runtime state.")
    if repeated_failures >= 3:
        status = "error"
        warnings.append(f"{repeated_failures} recent LibreQoS apply failure(s) in a row.")
    elif fail_count:
        status = "warning"
        warnings.append(f"{fail_count} failed apply run(s) in the recent apply log list.")
    return {
        "status": status,
        "last_apply": last_apply,
        "recent_ok": ok_count,
        "recent_failed": fail_count,
        "repeated_failures": repeated_failures,
        "average_duration_seconds": round(sum(durations) / len(durations), 3) if durations else 0,
        "max_duration_seconds": round(max(durations), 3) if durations else 0,
        "audit_events": len(audit_apply),
        "warnings": warnings,
    }


def notification_candidates(config: dict, state: dict[str, Any], source_cards: list[dict[str, Any]], trends: dict[str, Any], apply_health: dict[str, Any], audit_events: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Return internal notification-worthy items. Telegram delivery is v2.58."""
    items: list[dict[str, Any]] = []
    for s in source_cards:
        if s.get("status") in {"warning", "error"}:
            items.append({
                "level": "critical" if s.get("status") == "error" else "warning",
                "title": f"{s.get('label')} source health: {s.get('status')}",
                "message": "; ".join(s.get("warnings") or []) or "Source requires review.",
                "target": "/#source-health-performance",
            })
    for name, data in [("Router API", trends.get("router_api") or {}), ("Sync cycle", trends.get("cycle") or {}), ("LibreQoS apply", trends.get("libreqos_apply") or {})]:
        if data.get("status") == "slow":
            items.append({"level": "warning", "title": f"{name} slower than baseline", "message": f"Current {data.get('current_ms')}ms vs average {data.get('average_ms')}ms.", "target": "/#source-health-performance"})
    if apply_health.get("status") in {"pending", "warning", "error"}:
        items.append({"level": "critical" if apply_health.get("status") == "error" else "warning", "title": "LibreQoS apply needs attention", "message": "; ".join(apply_health.get("warnings") or []) or "Review apply health.", "target": "/services"})
    return items[:25]


def compute_health_report(config: dict, state: dict[str, Any], policy_state: dict[str, Any] | None = None, services: dict[str, Any] | None = None, apply_runs: list[dict[str, Any]] | None = None, audit_limit: int = 1500) -> dict[str, Any]:
    policy_state = policy_state or {}
    events = _read_audit_events(config, limit=audit_limit)
    source_cards = source_health(config, state, policy_state=policy_state)
    trends = performance_trends(config, state, audit_events=events)
    apply = libreqos_apply_health(config, state, apply_runs=apply_runs or [], audit_events=events)
    notifications = notification_candidates(config, state, source_cards, trends, apply, audit_events=events)
    last24 = _window(events, 24)
    services = services or {}
    service_counts = {
        "total": len(services),
        "active": sum(1 for v in services.values() if isinstance(v, dict) and v.get("active") == "active"),
        "failed": sum(1 for v in services.values() if isinstance(v, dict) and v.get("active") in {"failed", "inactive"}),
    }
    health_score = 100
    health_score -= min(35, len([s for s in source_cards if s.get("status") == "error"]) * 20)
    health_score -= min(25, len([s for s in source_cards if s.get("status") == "warning"]) * 8)
    if apply.get("status") == "error":
        health_score -= 25
    elif apply.get("status") in {"pending", "warning"}:
        health_score -= 12
    if (trends.get("router_api") or {}).get("status") == "slow":
        health_score -= 10
    if service_counts["failed"]:
        health_score -= min(20, service_counts["failed"] * 10)
    health_score = max(0, min(100, health_score))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health_score": health_score,
        "health_level": "excellent" if health_score >= 90 else ("good" if health_score >= 75 else ("needs_attention" if health_score >= 50 else "poor")),
        "source_health": source_cards,
        "performance_trends": trends,
        "libreqos_apply_health": apply,
        "notifications": notifications,
        "service_counts": service_counts,
        "audit_24h": {
            "events": len(last24),
            "sync_finished": sum(1 for ev in last24 if ev.get("action") == "sync_finished"),
            "policy_blocked": sum(1 for ev in last24 if ev.get("action") == "policy_blocked"),
            "libreqos_apply": sum(1 for ev in last24 if ev.get("action") == "libreqos_apply"),
        },
        "notification_delivery": {
            "internal_center": True,
            "telegram": "planned_v2.58",
        },
    }
