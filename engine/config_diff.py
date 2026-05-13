"""Config diff helpers for Config Center preview and simulation.

These helpers are intentionally generic and side-effect free. They compare the
saved config with an in-browser/proposed config and produce readable changed
paths for UI, audit, and simulation engines.
"""
from __future__ import annotations

from typing import Any

SENSITIVE_KEYS = {"password", "token", "secret", "api_key", "key"}


def _is_sensitive_path(path: str) -> bool:
    parts = [p.lower() for p in path.split(".")]
    return any(part in SENSITIVE_KEYS or part.endswith("password") for part in parts)


def mask_if_sensitive(path: str, value: Any) -> Any:
    if _is_sensitive_path(path) and value not in (None, ""):
        return "********"
    return value


def flatten_config(obj: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten_config(value, path))
    elif isinstance(obj, list):
        # Lists are kept as a single unit. This keeps router/DHCP diffs compact
        # and avoids unstable path churn when operators reorder entries.
        out[prefix] = obj
    else:
        out[prefix] = obj
    return out


def diff_configs(before: dict, after: dict, limit: int = 300) -> list[dict[str, Any]]:
    b = flatten_config(before or {})
    a = flatten_config(after or {})
    paths = sorted(set(b) | set(a))
    changes: list[dict[str, Any]] = []
    for path in paths:
        old = b.get(path, None)
        new = a.get(path, None)
        if old != new:
            if path not in b:
                ctype = "added"
            elif path not in a:
                ctype = "removed"
            else:
                ctype = "changed"
            changes.append({
                "path": path,
                "type": ctype,
                "before": mask_if_sensitive(path, old),
                "after": mask_if_sensitive(path, new),
            })
            if len(changes) >= limit:
                break
    return changes


def summarize_config_changes(changes: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, int] = {}
    for c in changes:
        root = str(c.get("path", "")).split(".", 1)[0] or "root"
        groups[root] = groups.get(root, 0) + 1
    return {"total": len(changes), "groups": groups}
