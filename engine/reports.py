"""Smart Reports and Operator Audit helpers.

This module is intentionally read-only. It summarizes runtime state, audit
JSONL, policy decisions, lifecycle/cleanup data, client changes, and backup
readiness into operator-facing reports that can be rendered in the WebUI or
exported as JSON/CSV/Markdown.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from engine.audit import audit_path


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


def _read_audit_events(config: dict, limit: int = 5000) -> list[dict[str, Any]]:
    path = audit_path(config)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
    out: list[dict[str, Any]] = []
    for idx, line in enumerate(lines):
        try:
            ev = json.loads(line)
            ev["_idx"] = idx
            out.append(ev)
        except Exception:
            out.append({"ts": "", "actor": "system", "action": "parse_error", "details": {"line": line}, "_idx": idx})
    return out


def _in_window(events: list[dict[str, Any]], hours: int = 24) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    filtered = []
    for ev in events:
        ts = _parse_ts(ev.get("ts"))
        if ts and ts >= cutoff:
            filtered.append(ev)
    return filtered


def _count(events: list[dict[str, Any]], predicate) -> int:
    return sum(1 for ev in events if predicate(ev))


def _details(ev: dict[str, Any]) -> dict[str, Any]:
    d = ev.get("details")
    return d if isinstance(d, dict) else {}


def _action(ev: dict[str, Any]) -> str:
    return str(ev.get("action") or "")


def _latest(events: list[dict[str, Any]], predicate) -> dict[str, Any] | None:
    for ev in reversed(events):
        if predicate(ev):
            return ev
    return None


def _client_change_rows(last_run: dict[str, Any]) -> list[dict[str, Any]]:
    diff = last_run.get("diff") or {}
    rows = diff.get("client_changes") or []
    if not isinstance(rows, list):
        return []
    out = []
    for item in rows[:500]:
        if not isinstance(item, dict):
            continue
        out.append({
            "client": item.get("client") or item.get("circuit_name") or item.get("Circuit Name") or "unknown",
            "change_type": item.get("change_type") or item.get("type") or "changed",
            "speed": item.get("speed") or item.get("after_speed") or item.get("before_speed") or "",
            "parent_node": item.get("parent_node") or item.get("after_parent_node") or item.get("before_parent_node") or "",
            "speed_source": item.get("speed_source") or "",
            "fields": ", ".join(sorted((item.get("changed_fields") or {}).keys())) if isinstance(item.get("changed_fields"), dict) else "",
        })
    return out


def _cleanup_report(state: dict[str, Any], policy_state: dict[str, Any], audit_events: list[dict[str, Any]]) -> dict[str, Any]:
    last = state.get("last_run") or state.get("last_dry_run") or {}
    diff = last.get("diff") or {}
    pd = diff.get("policy_decision") or (policy_state.get("last_policy_decision") if isinstance(policy_state, dict) else {}) or {}
    cleanup_decisions = pd.get("cleanup_decisions") or []
    lifecycle = diff.get("lifecycle_summary") or {}
    pending = policy_state.get("pending_confirmations") if isinstance(policy_state, dict) else []
    if not isinstance(pending, list):
        pending = []
    recent_cleanup_events = [ev for ev in audit_events if _action(ev) in {"cleanup_confirmed", "cleanup_confirmation_dismissed", "cleanup_confirm_required", "policy_blocked"}][-50:]
    counts = {
        "remove": len(pd.get("remove_codes") or []),
        "queued": len(pd.get("queued_codes") or []),
        "preserve": len(pd.get("preserve_codes") or []),
        "pending_confirmations": len(pending),
        "decisions": len(cleanup_decisions),
    }
    return {
        "counts": counts,
        "verdict": pd.get("verdict") or "unknown",
        "risk_level": pd.get("risk_level") or "unknown",
        "risk_score": pd.get("risk_score", 0),
        "cleanup_decisions": cleanup_decisions[:200] if isinstance(cleanup_decisions, list) else [],
        "pending_confirmations": pending[:100],
        "lifecycle_summary": lifecycle,
        "recent_events": recent_cleanup_events,
    }


def _policy_report(state: dict[str, Any], policy_state: dict[str, Any]) -> dict[str, Any]:
    last = state.get("last_run") or state.get("last_dry_run") or {}
    pd = ((last.get("diff") or {}).get("policy_decision") or (policy_state.get("last_policy_decision") if isinstance(policy_state, dict) else {}) or {})
    return {
        "verdict": pd.get("verdict") or "unknown",
        "risk_level": pd.get("risk_level") or "unknown",
        "risk_score": pd.get("risk_score", 0),
        "write_allowed": pd.get("write_allowed"),
        "apply_allowed": pd.get("apply_allowed"),
        "requires_confirmation": pd.get("requires_confirmation"),
        "blocked_reasons": pd.get("blocked_reasons") or [],
        "warnings": pd.get("warnings") or [],
        "recommendations": pd.get("recommendations") or [],
        "decision_trace": pd.get("decision_trace") or [],
    }


def _config_change_report(audit_events: list[dict[str, Any]]) -> dict[str, Any]:
    actions = {"config_saved", "policy_settings_saved", "policy_preset_applied", "scheduler_settings_saved", "dhcp_server_toggled", "network_layout_saved"}
    events = [ev for ev in audit_events if _action(ev) in actions][-100:]
    by_action: dict[str, int] = {}
    by_actor: dict[str, int] = {}
    for ev in events:
        by_action[_action(ev)] = by_action.get(_action(ev), 0) + 1
        actor = str(ev.get("actor") or "system")
        by_actor[actor] = by_actor.get(actor, 0) + 1
    return {"events": events, "by_action": by_action, "by_actor": by_actor}


def compute_operator_report(config: dict, state: dict[str, Any], policy_state: dict[str, Any] | None = None, services: dict[str, Any] | None = None, backups: list[dict[str, Any]] | None = None, audit_limit: int = 5000) -> dict[str, Any]:
    policy_state = policy_state or {}
    services = services or {}
    backups = backups or []
    audit_events = _read_audit_events(config, limit=audit_limit)
    last24 = _in_window(audit_events, hours=24)
    last = state.get("last_run") or {}
    diff = last.get("diff") or {}
    smart = diff.get("smart_insights") or {}
    policy = _policy_report(state, policy_state)
    cleanup = _cleanup_report(state, policy_state, audit_events)
    client_changes = _client_change_rows(last)
    config_changes = _config_change_report(audit_events)
    sync_finished = [ev for ev in last24 if _action(ev) == "sync_finished"]
    dry_runs = [ev for ev in last24 if _action(ev) == "dry_run_complete"]
    failed_sync = [ev for ev in sync_finished if str((_details(ev).get("status") or "")).lower() not in {"success", ""}]
    applies = [ev for ev in last24 if "libreqos" in _action(ev) or (_details(ev).get("libreqos_triggered") is True)]
    policy_blocked = [ev for ev in last24 if _action(ev) == "policy_blocked"]
    confirmations = [ev for ev in last24 if _action(ev) in {"cleanup_confirmed", "cleanup_confirmation_dismissed"}]
    service_summary = {name: (info.get("active") if isinstance(info, dict) else str(info)) for name, info in services.items()}
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": 24,
        "summary": {
            "audit_events_24h": len(last24),
            "sync_finished_24h": len(sync_finished),
            "dry_runs_24h": len(dry_runs),
            "failed_sync_24h": len(failed_sync),
            "libreqos_related_events_24h": len(applies),
            "policy_blocked_24h": len(policy_blocked),
            "cleanup_confirmations_24h": len(confirmations),
            "config_changes_recorded": len(config_changes["events"]),
            "backups_available": len(backups),
        },
        "last_run": {
            "status": last.get("status"),
            "started_at": last.get("started_at"),
            "finished_at": last.get("finished_at"),
            "duration_seconds": last.get("duration_seconds"),
            "files_changed": last.get("files_changed"),
            "libreqos_triggered": last.get("libreqos_triggered"),
            "libreqos_exit_code": last.get("libreqos_exit_code"),
            "counts": last.get("counts") or {},
            "timings": last.get("timings") or {},
        },
        "policy_report": policy,
        "cleanup_report": cleanup,
        "client_change_report": {
            "summary": diff.get("client_change_summary") or {},
            "rows": client_changes,
        },
        "smart_insights": smart,
        "config_change_report": config_changes,
        "services": service_summary,
        "backups": backups[:50],
    }
    return report


def report_to_csv(report: dict[str, Any]) -> str:
    """Flatten major report sections into CSV rows."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "key", "value", "extra"])
    for k, v in (report.get("summary") or {}).items():
        writer.writerow(["summary", k, v, ""])
    for k, v in (report.get("last_run") or {}).items():
        if isinstance(v, (dict, list)):
            writer.writerow(["last_run", k, json.dumps(v, ensure_ascii=False), ""])
        else:
            writer.writerow(["last_run", k, v, ""])
    policy = report.get("policy_report") or {}
    for k in ["verdict", "risk_level", "risk_score", "write_allowed", "apply_allowed", "requires_confirmation"]:
        writer.writerow(["policy", k, policy.get(k), ""])
    for r in (report.get("client_change_report") or {}).get("rows") or []:
        writer.writerow(["client_change", r.get("client"), r.get("change_type"), json.dumps(r, ensure_ascii=False)])
    for ev in (report.get("config_change_report") or {}).get("events") or []:
        writer.writerow(["config_change", ev.get("ts"), ev.get("action"), json.dumps(ev.get("details") or {}, ensure_ascii=False)])
    for item in (report.get("cleanup_report") or {}).get("cleanup_decisions") or []:
        writer.writerow(["cleanup_decision", item.get("code") or item.get("client") or "", item.get("action") or item.get("decision") or "", json.dumps(item, ensure_ascii=False)])
    return buf.getvalue()


def report_to_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    policy = report.get("policy_report") or {}
    cleanup = report.get("cleanup_report") or {}
    last_run = report.get("last_run") or {}
    client_rows = (report.get("client_change_report") or {}).get("rows") or []
    lines = [
        "# LQoSync Operator Report",
        "",
        f"Generated at: `{report.get('generated_at')}`",
        "",
        "## 24h Summary",
    ]
    for k, v in summary.items():
        lines.append(f"- **{k.replace('_',' ').title()}**: {v}")
    lines += ["", "## Last Run"]
    for k, v in last_run.items():
        lines.append(f"- **{k.replace('_',' ').title()}**: `{v}`")
    lines += ["", "## Policy Decision", f"- Verdict: `{policy.get('verdict')}`", f"- Risk: `{policy.get('risk_level')}` ({policy.get('risk_score')})", f"- Write allowed: `{policy.get('write_allowed')}`", f"- Apply allowed: `{policy.get('apply_allowed')}`"]
    if policy.get("blocked_reasons"):
        lines.append("- Blocked reasons:")
        for b in policy.get("blocked_reasons")[:10]:
            lines.append(f"  - {b.get('title') or 'Blocked'}: {b.get('message') or b}")
    lines += ["", "## Cleanup Report"]
    for k, v in (cleanup.get("counts") or {}).items():
        lines.append(f"- **{k.replace('_',' ').title()}**: {v}")
    lines += ["", "## Client Changes"]
    if client_rows:
        for row in client_rows[:50]:
            lines.append(f"- `{row.get('change_type')}` {row.get('client')} · {row.get('speed')} · {row.get('parent_node')}")
    else:
        lines.append("- No client change rows recorded in the last run.")
    return "\n".join(lines) + "\n"
