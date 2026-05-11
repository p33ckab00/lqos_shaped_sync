"""Build operator-friendly client change summaries for dashboard and audit logs.

The sync engine already computes precise CSV diffs. This module converts those
raw diffs into concise records that are easy to read in the Dashboard timeline
and Logs/Audit table: client name, speed, parent node, source type, and changed
fields.
"""
from __future__ import annotations

from typing import Any

IMPORTANT_FIELDS = (
    "Parent Node",
    "Download Max Mbps",
    "Upload Max Mbps",
    "Download Min Mbps",
    "Upload Min Mbps",
    "IPv4",
    "MAC",
    "Comment",
)


def _num_or_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        try:
            return str(int(float(text)))
        except Exception:
            return text
    return text


def _speed(row: dict[str, Any]) -> str:
    down = _num_or_text(row.get("Download Max Mbps"))
    up = _num_or_text(row.get("Upload Max Mbps"))
    if down or up:
        return f"{down or '0'}/{up or '0'} Mbps"
    return "—"


def _source(row: dict[str, Any], meta: dict[str, Any] | None = None) -> str:
    meta = meta or {}
    src = str(meta.get("source_type") or "").strip()
    if src:
        return src
    comment = str(row.get("Comment") or "").strip()
    parent = str(row.get("Parent Node") or "").strip()
    name = str(row.get("Circuit Name") or "").strip()
    if comment.upper() == "PPP" or parent.startswith(("Tier-", "PPP-")):
        return "PPP"
    if comment.upper() == "DHCP" or name.startswith("DHCP-") or parent.startswith("DHCP-"):
        return "DHCP"
    if comment.upper() == "HS" or name.startswith("HS-") or parent.startswith("HS-"):
        return "Hotspot"
    return comment or "Unknown"


def _row_record(kind: str, row: dict[str, Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = meta or {}
    return {
        "change_type": kind,
        "client": row.get("Circuit Name") or row.get("Device Name") or "",
        "device": row.get("Device Name") or "",
        "parent_node": row.get("Parent Node") or "",
        "speed": _speed(row),
        "download_mbps": _num_or_text(row.get("Download Max Mbps")),
        "upload_mbps": _num_or_text(row.get("Upload Max Mbps")),
        "ipv4": row.get("IPv4") or "",
        "mac": row.get("MAC") or "",
        "source_type": _source(row, meta),
        "speed_source": meta.get("speed_source") or "file/comment",
        "speed_raw_value": meta.get("speed_raw_value") or "",
        "speed_priority": meta.get("speed_priority") or "",
        "router": meta.get("router") or "",
        "profile_or_server": meta.get("profile") or meta.get("server") or "",
    }


def _updated_record(item: dict[str, Any], meta_by_client: dict[str, Any]) -> dict[str, Any]:
    before = item.get("before") or {}
    after = item.get("after") or {}
    client = item.get("key") or after.get("Circuit Name") or before.get("Circuit Name") or ""
    meta = meta_by_client.get(client, {})
    record = _row_record("updated", after, meta)
    changed_fields: dict[str, dict[str, str]] = {}
    for field in IMPORTANT_FIELDS:
        b = _num_or_text(before.get(field))
        a = _num_or_text(after.get(field))
        if b != a:
            changed_fields[field] = {"before": b, "after": a}
    record["before_parent_node"] = before.get("Parent Node") or ""
    record["before_speed"] = _speed(before)
    record["changed_fields"] = changed_fields
    return record


def build_client_change_summary(csv_diff: dict[str, Any], meta_by_client: dict[str, Any] | None = None, limit: int = 80) -> dict[str, Any]:
    meta_by_client = meta_by_client or {}
    changes: list[dict[str, Any]] = []
    for row in csv_diff.get("added", []) or []:
        client = row.get("Circuit Name") or row.get("Device Name") or ""
        changes.append(_row_record("added", row, meta_by_client.get(client, {})))
    for item in csv_diff.get("updated", []) or []:
        changes.append(_updated_record(item, meta_by_client))
    for row in csv_diff.get("removed", []) or []:
        client = row.get("Circuit Name") or row.get("Device Name") or ""
        changes.append(_row_record("removed", row, meta_by_client.get(client, {})))

    counts = dict(csv_diff.get("counts") or {})
    counts.setdefault("added", len(csv_diff.get("added", []) or []))
    counts.setdefault("updated", len(csv_diff.get("updated", []) or []))
    counts.setdefault("removed", len(csv_diff.get("removed", []) or []))
    total = int(counts.get("added", 0)) + int(counts.get("updated", 0)) + int(counts.get("removed", 0))
    counts["total"] = total

    shown = changes[:limit]
    parts = []
    if counts.get("added"):
        parts.append(f"+{counts['added']} added")
    if counts.get("updated"):
        parts.append(f"~{counts['updated']} updated")
    if counts.get("removed"):
        parts.append(f"-{counts['removed']} removed")
    summary_text = ", ".join(parts) if parts else "No client changes"

    clients_preview = ", ".join([c.get("client") or "unknown" for c in shown[:8]])
    if total > 8:
        clients_preview += f", +{total-8} more"

    return {
        "counts": counts,
        "summary_text": summary_text,
        "clients_preview": clients_preview,
        "changes": shown,
        "truncated": len(changes) > len(shown),
        "total_changes": len(changes),
    }
