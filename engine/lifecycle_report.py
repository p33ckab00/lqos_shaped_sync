"""Client Lifecycle Timeline reporting for LQoSync v2.53.

This module is read-only. It summarizes policy_state.json lifecycle data into
operator-friendly tables, timelines, exports, and dashboard/API payloads.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any


def _safe(v: Any) -> str:
    return "" if v is None else str(v)


def _parse_dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _client_display(code: str, item: dict[str, Any]) -> str:
    return str(item.get("circuit_name") or item.get("device_name") or code)


def _event_label(event: str) -> str:
    return {
        "client_added": "Added",
        "client_updated": "Updated",
        "client_removed": "Removed",
        "client_returned": "Returned",
        "cleanup_queued": "Queued cleanup",
        "cleanup_preserved": "Marked stale",
        "cleanup_applied": "Cleanup applied",
    }.get(str(event), str(event).replace("_", " ").title())


def client_status_bucket(status: str) -> str:
    status = str(status or "unknown")
    if status == "active":
        return "active"
    if status in {"queued_cleanup", "confirmed_cleanup"}:
        return "pending_cleanup"
    if status == "stale":
        return "stale"
    if status == "removed":
        return "removed"
    return "unknown"


def filter_lifecycle_clients(
    policy_state: dict[str, Any],
    *,
    status: str = "all",
    source: str = "all",
    search: str = "",
    limit: int = 500,
) -> list[tuple[str, dict[str, Any]]]:
    clients = policy_state.get("client_lifecycle", {}) or {}
    status = str(status or "all").lower()
    source = str(source or "all").upper()
    query = str(search or "").strip().lower()
    out: list[tuple[str, dict[str, Any]]] = []
    for code, item in clients.items():
        st = str(item.get("status") or "unknown")
        src = str(item.get("source") or "UNKNOWN").upper()
        if status != "all" and st != status and client_status_bucket(st) != status:
            continue
        if source != "ALL" and src != source:
            continue
        if query:
            hay = " ".join([
                str(code), _client_display(code, item), str(item.get("parent_node", "")),
                str(item.get("ipv4", "")), str(item.get("mac", "")), str(item.get("source", "")),
                str(item.get("status", "")), str(item.get("comment", "")),
            ]).lower()
            if query not in hay:
                continue
        out.append((str(code), item))
    out.sort(key=lambda kv: _parse_dt(kv[1].get("last_event_at") or kv[1].get("last_seen_at") or ""), reverse=True)
    return out[: max(1, int(limit or 500))]


def lifecycle_events(policy_state: dict[str, Any], *, code: str = "", event: str = "all", limit: int = 300) -> list[dict[str, Any]]:
    events = policy_state.get("client_events", []) or []
    if code:
        events = [e for e in events if str(e.get("code")) == str(code)]
    if event and event != "all":
        events = [e for e in events if str(e.get("event")) == str(event)]
    events = sorted(events, key=lambda e: _parse_dt(e.get("ts", "")), reverse=True)
    return events[: max(1, int(limit or 300))]


def compute_lifecycle_report(
    policy_state: dict[str, Any],
    *,
    status: str = "all",
    source: str = "all",
    search: str = "",
    code: str = "",
    limit: int = 500,
) -> dict[str, Any]:
    clients_all = policy_state.get("client_lifecycle", {}) or {}
    clients_filtered = filter_lifecycle_clients(policy_state, status=status, source=source, search=search, limit=limit)
    events = lifecycle_events(policy_state, code=code, limit=300)
    status_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    bucket_counts: dict[str, int] = {}
    for _code, item in clients_all.items():
        st = str(item.get("status") or "unknown")
        src = str(item.get("source") or "UNKNOWN")
        status_counts[st] = status_counts.get(st, 0) + 1
        source_counts[src] = source_counts.get(src, 0) + 1
        b = client_status_bucket(st)
        bucket_counts[b] = bucket_counts.get(b, 0) + 1

    selected_client = None
    if code and code in clients_all:
        selected_client = {"code": code, **(clients_all.get(code) or {})}

    cleanup_history = list(reversed((policy_state.get("cleanup_history", []) or [])[-100:]))
    confirmation_history = list(reversed((policy_state.get("confirmation_history", []) or [])[-100:]))
    cleanup_queue = policy_state.get("cleanup_queue", []) or []
    pending_confirmations = policy_state.get("pending_confirmations", []) or []

    recommendations: list[dict[str, Any]] = []
    if bucket_counts.get("stale", 0):
        recommendations.append({"severity": "warning", "title": "Review stale clients", "message": f"{bucket_counts.get('stale', 0)} clients are stale and waiting policy cleanup."})
    if bucket_counts.get("pending_cleanup", 0):
        recommendations.append({"severity": "warning", "title": "Review pending cleanup", "message": f"{bucket_counts.get('pending_cleanup', 0)} clients are queued/confirmed for cleanup."})
    if pending_confirmations:
        recommendations.append({"severity": "warning", "title": "Pending cleanup confirmations", "message": f"{len(pending_confirmations)} confirmations are waiting for operator action."})
    if bucket_counts.get("removed", 0) > 0:
        recommendations.append({"severity": "info", "title": "Removed client history present", "message": "Use the client timeline to confirm whether removals were expected."})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "tracked_clients": len(clients_all),
            "filtered_clients": len(clients_filtered),
            "events": len(policy_state.get("client_events", []) or []),
            "cleanup_queue": len(cleanup_queue),
            "pending_confirmations": len(pending_confirmations),
            "cleanup_history": len(policy_state.get("cleanup_history", []) or []),
            "confirmation_history": len(policy_state.get("confirmation_history", []) or []),
            "status_counts": status_counts,
            "bucket_counts": bucket_counts,
            "source_counts": source_counts,
        },
        "filters": {"status": status, "source": source, "search": search, "code": code, "limit": limit},
        "selected_client": selected_client,
        "clients": [{"code": c, **item} for c, item in clients_filtered],
        "events": events,
        "cleanup_history": cleanup_history,
        "confirmation_history": confirmation_history,
        "cleanup_queue": cleanup_queue,
        "pending_confirmations": pending_confirmations,
        "source_lifecycle": policy_state.get("source_lifecycle", {}) or {},
        "recommendations": recommendations,
    }


def lifecycle_report_to_csv(report: dict[str, Any]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["section", "code", "client", "status", "source", "parent_node", "ipv4", "mac", "down", "up", "last_seen", "last_event"])
    for c in report.get("clients", []) or []:
        writer.writerow([
            "client", c.get("code", ""), c.get("circuit_name", ""), c.get("status", ""), c.get("source", ""),
            c.get("parent_node", ""), c.get("ipv4", ""), c.get("mac", ""), c.get("download_mbps", ""), c.get("upload_mbps", ""),
            c.get("last_seen_at", ""), c.get("last_event_at", ""),
        ])
    writer.writerow([])
    writer.writerow(["section", "event", "code", "client", "source", "reason", "timestamp", "details"])
    for e in report.get("events", []) or []:
        writer.writerow(["event", e.get("event", ""), e.get("code", ""), e.get("circuit_name", ""), e.get("source", ""), e.get("reason", ""), e.get("ts", ""), json.dumps(e, ensure_ascii=False)])
    return out.getvalue()


def lifecycle_report_to_markdown(report: dict[str, Any]) -> str:
    s = report.get("summary", {}) or {}
    lines = [
        "# LQoSync Client Lifecycle Timeline Report",
        "",
        f"Generated: {report.get('generated_at')}",
        "",
        "## Summary",
        "",
        f"- Tracked clients: {s.get('tracked_clients', 0)}",
        f"- Filtered clients: {s.get('filtered_clients', 0)}",
        f"- Events: {s.get('events', 0)}",
        f"- Cleanup queue: {s.get('cleanup_queue', 0)}",
        f"- Pending confirmations: {s.get('pending_confirmations', 0)}",
        "",
        "## Recommendations",
        "",
    ]
    for rec in report.get("recommendations", []) or []:
        lines.append(f"- **{rec.get('title')}** ({rec.get('severity')}): {rec.get('message')}")
    if not report.get("recommendations"):
        lines.append("- No lifecycle recommendations at this time.")
    lines += ["", "## Clients", "", "| Client | Status | Source | Parent | IP | Last event |", "|---|---|---|---|---|---|"]
    for c in (report.get("clients", []) or [])[:200]:
        lines.append(f"| {_safe(c.get('circuit_name') or c.get('code'))} | {_safe(c.get('status'))} | {_safe(c.get('source'))} | {_safe(c.get('parent_node'))} | {_safe(c.get('ipv4'))} | {_safe(c.get('last_event_at'))} |")
    lines += ["", "## Recent Events", ""]
    for e in (report.get("events", []) or [])[:100]:
        lines.append(f"- {e.get('ts')} — **{_event_label(e.get('event'))}** — {e.get('circuit_name') or e.get('code')} — {e.get('source','')} {e.get('reason','')}")
    return "\n".join(lines) + "\n"
