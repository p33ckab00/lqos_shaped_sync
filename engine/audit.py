"""Structured audit log writer.

No database is used. Audit events are appended as JSONL to logs/audit.jsonl.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def audit_path(config: dict) -> Path:
    explicit = config.get("paths", {}).get("audit_log")
    if explicit:
        return Path(explicit)
    log_file = Path(config.get("paths", {}).get("log_file", "logs/lqos_shaped_sync.log"))
    return log_file.parent / "audit.jsonl"


def write_audit(config: dict, action: str, actor: str = "system", details: dict[str, Any] | None = None, summary: str | None = None):
    path = audit_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor or "system",
        "action": action,
        "summary": summary or "",
        "details": details or {},
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def tail_audit(config: dict, limit: int = 100) -> list[dict[str, Any]]:
    path = audit_path(config)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            out.append({"ts": "", "actor": "", "action": "parse_error", "details": {"line": line}})
    return out
