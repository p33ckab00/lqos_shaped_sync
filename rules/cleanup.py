def remove_inactive_entries(existing_data: dict, active_codes: set, static_comment_value="static") -> bool:
    updated = False
    static_value = str(static_comment_value or "static").lower()
    for code in list(existing_data.keys()):
        comment = str(existing_data[code].get("Comment", "")).strip().lower()
        if code not in active_codes and comment != static_value:
            del existing_data[code]
            updated = True
    return updated


def infer_row_source(code: str, row: dict) -> str:
    comment = str(row.get("Comment", "")).strip().upper()
    parent = str(row.get("Parent Node", "")).strip().upper()
    name = str(row.get("Circuit Name", code or "")).strip().upper()
    if comment == "PPP" or parent.startswith(("TIER-", "PPP-")):
        return "PPP"
    if name.startswith("DHCP-") or parent.startswith(("DHCP-", "PLAN-DHCP-")):
        return "DHCP"
    if comment == "HS" or name.startswith("HS-") or parent.startswith("HS-"):
        return "HS"
    return "UNKNOWN"


def remove_inactive_entries_by_source(existing_data: dict, active_codes_by_source: dict, cleanup_sources: set, static_comment_value="static") -> tuple[bool, dict]:
    """Remove stale rows only for sources that were scanned successfully.

    This prevents accidental mass removal when PPP/DHCP/Hotspot API reads fail.
    Sources are PPP, DHCP, and HS. Unknown rows are preserved unless full legacy
    cleanup is used.
    """
    updated = False
    stats = {"removed": 0, "preserved_unknown": 0, "sources": sorted(list(cleanup_sources or []))}
    static_value = str(static_comment_value or "static").lower()
    normalized = {str(k).upper(): set(v or set()) for k, v in (active_codes_by_source or {}).items()}
    for code in list(existing_data.keys()):
        row = existing_data[code]
        comment = str(row.get("Comment", "")).strip().lower()
        if comment == static_value:
            continue
        source = infer_row_source(code, row)
        if source not in cleanup_sources:
            if source == "UNKNOWN":
                stats["preserved_unknown"] += 1
            continue
        if code not in normalized.get(source, set()):
            del existing_data[code]
            updated = True
            stats["removed"] += 1
    return updated, stats
