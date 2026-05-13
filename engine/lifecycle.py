"""Smart Lifecycle state tracking for LQoSync v2.47.

This module is intentionally lightweight and file-backed. It does not add a
separate database. It records client lifecycle state, cleanup history, source
lifecycle snapshots, and a bounded per-client event timeline inside the Smart
Policy Center runtime state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

EVENT_LIMIT = 1000
CLIENT_LIMIT = 20000
HISTORY_LIMIT = 500


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_from_row(row: dict[str, Any], static_value: str = "static") -> str:
    comment = str((row or {}).get("Comment", "")).strip().lower()
    name = str((row or {}).get("Circuit Name", "")).strip().upper()
    if comment == str(static_value or "static").strip().lower():
        return "STATIC"
    if comment == "ppp" or name.startswith("PPP-"):
        return "PPP"
    if comment == "hs" or name.startswith("HS-"):
        return "HS"
    if comment.startswith("dhcp") or name.startswith("DHCP-"):
        return "DHCP"
    return "DHCP" if comment and comment not in {"ppp", "hs", "static"} else "UNKNOWN"


def _row_fingerprint(row: dict[str, Any]) -> dict[str, str]:
    fields = [
        "Circuit Name", "Device Name", "Parent Node", "MAC", "IPv4", "IPv6",
        "Download Min Mbps", "Upload Min Mbps", "Download Max Mbps", "Upload Max Mbps", "Comment",
    ]
    return {f: str((row or {}).get(f, "")) for f in fields}


def _row_summary(row: dict[str, Any], static_value: str = "static") -> dict[str, Any]:
    return {
        "circuit_name": str((row or {}).get("Circuit Name", "")),
        "device_name": str((row or {}).get("Device Name", "")),
        "source": _source_from_row(row, static_value),
        "parent_node": str((row or {}).get("Parent Node", "")),
        "ipv4": str((row or {}).get("IPv4", "")),
        "mac": str((row or {}).get("MAC", "")),
        "download_mbps": str((row or {}).get("Download Max Mbps", "")),
        "upload_mbps": str((row or {}).get("Upload Max Mbps", "")),
        "comment": str((row or {}).get("Comment", "")),
    }


def ensure_lifecycle_state(policy_state: dict[str, Any]) -> dict[str, Any]:
    policy_state.setdefault("client_lifecycle", {})
    policy_state.setdefault("client_events", [])
    policy_state.setdefault("cleanup_history", [])
    policy_state.setdefault("confirmation_history", [])
    policy_state.setdefault("source_lifecycle", {})
    policy_state.setdefault("last_lifecycle_summary", {})
    policy_state.setdefault("returned_clients", [])
    return policy_state


def _append_bounded(container: list, item: dict[str, Any], limit: int = HISTORY_LIMIT) -> None:
    container.append(item)
    if len(container) > limit:
        del container[:-limit]


def add_client_event(policy_state: dict[str, Any], event_type: str, code: str, row: dict[str, Any] | None = None, **extra) -> dict[str, Any]:
    ensure_lifecycle_state(policy_state)
    event = {
        "ts": utcnow(),
        "event": event_type,
        "code": str(code),
    }
    if row:
        event.update(_row_summary(row))
    event.update(extra)
    _append_bounded(policy_state["client_events"], event, EVENT_LIMIT)
    return event


def add_cleanup_history(policy_state: dict[str, Any], action: str, **details) -> dict[str, Any]:
    ensure_lifecycle_state(policy_state)
    item = {"ts": utcnow(), "action": action, **details}
    _append_bounded(policy_state["cleanup_history"], item, HISTORY_LIMIT)
    return item


def add_confirmation_history(policy_state: dict[str, Any], action: str, confirmation_id: str, actor: str = "admin", **details) -> dict[str, Any]:
    ensure_lifecycle_state(policy_state)
    item = {"ts": utcnow(), "action": action, "confirmation_id": confirmation_id, "actor": actor, **details}
    _append_bounded(policy_state["confirmation_history"], item, HISTORY_LIMIT)
    return item


def _changed_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    bf = _row_fingerprint(before)
    af = _row_fingerprint(after)
    return [k for k in bf if bf.get(k) != af.get(k)]


def update_lifecycle_state(
    config: dict[str, Any],
    policy_state: dict[str, Any],
    before_rows: dict[str, dict[str, Any]],
    after_rows: dict[str, dict[str, Any]],
    cleanup_candidates: list[dict[str, Any]],
    policy_decision: dict[str, Any],
    cleanup_sources: set[str] | list[str],
    active_counts_by_source: dict[str, int],
    mode: str = "apply",
) -> dict[str, Any]:
    """Update lifecycle state after policy evaluation.

    This records what happened to every known client/circuit from the perspective
    of the proposed sync output. It is safe in dry-run mode; events are marked
    with mode=dry_run and do not imply that files were written.
    """
    ensure_lifecycle_state(policy_state)
    now = utcnow()
    static_value = ((config.get("defaults") or {}).get("static_comment_value") or "static")
    client_state = policy_state.setdefault("client_lifecycle", {})
    remove_codes = {str(c) for c in (policy_decision.get("remove_codes") or [])}
    queued_codes = {str(c) for c in (policy_decision.get("queued_codes") or [])}
    preserve_codes = {str(c) for c in (policy_decision.get("preserve_codes") or [])}

    before_keys = set(before_rows or {})
    after_keys = set(after_rows or {})
    added = after_keys - before_keys
    removed = before_keys - after_keys
    common = before_keys & after_keys
    returned_clients = []

    # Index cleanup candidates by code so stale/pending rows carry reason/source.
    cand_by_code = {str(c.get("code")): c for c in cleanup_candidates or []}

    for code in sorted(added):
        row = after_rows.get(code, {})
        old = client_state.get(code, {})
        event_type = "client_returned" if old.get("status") in {"stale", "queued_cleanup", "confirmed_cleanup", "removed"} else "client_added"
        if event_type == "client_returned":
            returned_clients.append({"code": code, **_row_summary(row, static_value)})
        add_client_event(policy_state, event_type, code, row, mode=mode)
        client_state[code] = {
            **old,
            **_row_summary(row, static_value),
            "first_seen_at": old.get("first_seen_at") or now,
            "last_seen_at": now,
            "last_event_at": now,
            "status": "active",
            "stale_since": None,
            "last_changed_fields": [],
        }

    for code in sorted(common):
        before = before_rows.get(code, {})
        after = after_rows.get(code, {})
        old = client_state.get(code, {})
        changed = _changed_fields(before, after)
        if changed:
            add_client_event(policy_state, "client_updated", code, after, mode=mode, changed_fields=changed[:20])
        client_state[code] = {
            **old,
            **_row_summary(after, static_value),
            "first_seen_at": old.get("first_seen_at") or now,
            "last_seen_at": now,
            "last_event_at": now if changed else old.get("last_event_at", now),
            "status": "active",
            "stale_since": None,
            "last_changed_fields": changed[:20],
        }

    for code in sorted(removed):
        row = before_rows.get(code, {})
        cand = cand_by_code.get(code, {})
        if code in remove_codes:
            status = "removed"
            event_type = "cleanup_applied"
        elif code in queued_codes:
            status = "queued_cleanup"
            event_type = "cleanup_queued"
        elif code in preserve_codes:
            status = "stale"
            event_type = "cleanup_preserved"
        else:
            status = "removed"
            event_type = "client_removed"
        add_client_event(policy_state, event_type, code, row, mode=mode, reason=cand.get("reason"), source=cand.get("source") or _source_from_row(row, static_value))
        old = client_state.get(code, {})
        client_state[code] = {
            **old,
            **_row_summary(row, static_value),
            "first_seen_at": old.get("first_seen_at") or now,
            "last_event_at": now,
            "status": status,
            "stale_since": old.get("stale_since") or now,
            "cleanup_reason": cand.get("reason"),
            "cleanup_source": cand.get("source") or _source_from_row(row, static_value),
        }

    # Also mark candidates preserved/queued that still remain in after_rows.
    for cand in cleanup_candidates or []:
        code = str(cand.get("code"))
        if code in after_keys and (code in queued_codes or code in preserve_codes):
            row = after_rows.get(code, cand.get("row", {}))
            status = "queued_cleanup" if code in queued_codes else "stale"
            event_type = "cleanup_queued" if code in queued_codes else "cleanup_preserved"
            add_client_event(policy_state, event_type, code, row, mode=mode, reason=cand.get("reason"), source=cand.get("source"))
            old = client_state.get(code, {})
            client_state[code] = {**old, **_row_summary(row, static_value), "status": status, "stale_since": old.get("stale_since") or now, "cleanup_reason": cand.get("reason"), "cleanup_source": cand.get("source")}

    # Keep client lifecycle bounded to avoid uncontrolled state-file growth.
    if len(client_state) > CLIENT_LIMIT:
        # Prefer keeping active clients and most recent stale clients.
        items = sorted(client_state.items(), key=lambda kv: (kv[1].get("status") != "active", kv[1].get("last_event_at") or kv[1].get("last_seen_at") or ""), reverse=True)
        policy_state["client_lifecycle"] = dict(items[:CLIENT_LIMIT])
        client_state = policy_state["client_lifecycle"]

    # Cleanup history from policy cleanup decisions.
    for item in policy_decision.get("cleanup_decisions") or []:
        add_cleanup_history(policy_state, "cleanup_decision", mode=mode, **item)

    # Source lifecycle snapshots.
    source_lifecycle = policy_state.setdefault("source_lifecycle", {})
    all_sources = {"PPP", "DHCP", "HS"}
    cleanup_sources_set = set(cleanup_sources or [])
    for src in sorted(all_sources):
        prev = source_lifecycle.get(src, {})
        active_count = int((active_counts_by_source or {}).get(src, 0) or 0)
        status = "success" if src in cleanup_sources_set else "not_successful_or_disabled"
        if status == "success" and active_count == 0 and int(prev.get("last_successful_count", 0) or 0) > 0:
            status = "zero_after_previous_success"
        snapshot = {
            **prev,
            "source": src,
            "last_status": status,
            "last_count": active_count,
            "last_seen_at": now,
            "cleanup_allowed": src in cleanup_sources_set,
        }
        if src in cleanup_sources_set:
            snapshot["last_successful_at"] = now
            snapshot["last_successful_count"] = active_count
        source_lifecycle[src] = snapshot

    summary = lifecycle_summary(policy_state)
    summary.update({
        "added": len(added),
        "updated": len([c for c in common if _changed_fields(before_rows.get(c, {}), after_rows.get(c, {}))]),
        "removed": len(removed),
        "queued_cleanup": len(queued_codes),
        "preserved_stale": len(preserve_codes),
        "returned": len(returned_clients),
        "mode": mode,
        "updated_at": now,
    })
    policy_state["returned_clients"] = returned_clients[:100]
    policy_state["last_lifecycle_summary"] = summary
    return summary


def lifecycle_summary(policy_state: dict[str, Any]) -> dict[str, Any]:
    ensure_lifecycle_state(policy_state)
    clients = policy_state.get("client_lifecycle", {}) or {}
    counts: dict[str, int] = {}
    by_source: dict[str, dict[str, int]] = {}
    for code, item in clients.items():
        status = str(item.get("status") or "unknown")
        source = str(item.get("source") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
        by_source.setdefault(source, {})[status] = by_source.setdefault(source, {}).get(status, 0) + 1
    return {
        "total_tracked_clients": len(clients),
        "status_counts": counts,
        "source_status_counts": by_source,
        "pending_confirmations": len(policy_state.get("pending_confirmations", []) or []),
        "cleanup_queue": len(policy_state.get("cleanup_queue", []) or []),
        "cleanup_history": len(policy_state.get("cleanup_history", []) or []),
        "client_events": len(policy_state.get("client_events", []) or []),
    }


def client_event_timeline(policy_state: dict[str, Any], code: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    ensure_lifecycle_state(policy_state)
    events = policy_state.get("client_events", []) or []
    if code:
        events = [e for e in events if str(e.get("code")) == str(code)]
    return list(reversed(events[-max(int(limit or 100), 1):]))
