"""Lightweight metadata cache for collector source hashes and parsed metadata.

This is intentionally a JSON state file, not a database. It lets LQoSync keep
track of source hashes, cache hits/misses, and parsed speed metadata between
cycles while preserving the database-free design.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any
from applier.atomic_writer import atomic_write_json


def _json_default(value: Any):
    try:
        return str(value)
    except Exception:
        return None


def stable_hash(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, default=_json_default, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def cache_path(config: dict) -> str:
    paths = config.setdefault("paths", {})
    return paths.get("collector_cache") or "/opt/LQoSync/state/collector_cache.json"


def load_cache(path: str | None) -> dict:
    if not path:
        return {"sources": {}, "updated_at": None}
    p = Path(path)
    if not p.exists():
        return {"sources": {}, "updated_at": None}
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("sources", {})
        return data
    except Exception:
        return {"sources": {}, "updated_at": None}


def save_cache(path: str | None, cache: dict) -> None:
    if not path:
        return
    from datetime import datetime, timezone
    cache = dict(cache or {})
    cache.setdefault("sources", {})
    cache["updated_at"] = datetime.now(timezone.utc).isoformat()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, cache, file_kind="collector_cache", sort_keys=True)


def get_source(cache: dict, key: str) -> dict:
    return (cache.get("sources") or {}).get(key) or {}


def set_source(cache: dict, key: str, payload: dict) -> None:
    cache.setdefault("sources", {})[key] = dict(payload or {})
