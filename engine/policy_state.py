"""Runtime state helpers for the Smart Policy Center.

This state is not operator config. It records pending confirmations, queued
cleanup items, and last successful source/node counts so policy decisions can be
safe across sync runs.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from applier.atomic_writer import atomic_write_json


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def default_policy_state() -> dict[str, Any]:
    return {
        "pending_confirmations": [],
        "cleanup_queue": [],
        "last_successful_source_counts": {},
        "last_successful_node_counts": {},
        "last_policy_decision": {},
        "client_lifecycle": {},
        "client_events": [],
        "cleanup_history": [],
        "confirmation_history": [],
        "source_lifecycle": {},
        "last_lifecycle_summary": {},
        "returned_clients": [],
    }


def policy_state_path(config: dict) -> str:
    paths = config.get("paths", {}) if isinstance(config, dict) else {}
    return paths.get("policy_state") or "/opt/LQoSync/state/policy_state.json"


def load_policy_state(path_or_config: str | dict) -> dict[str, Any]:
    path = policy_state_path(path_or_config) if isinstance(path_or_config, dict) else str(path_or_config)
    p = Path(path)
    if not p.exists():
        return default_policy_state()
    try:
        with p.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        state = default_policy_state()
        if isinstance(raw, dict):
            state.update(raw)
        return state
    except Exception:
        return default_policy_state()


def save_policy_state(path_or_config: str | dict, state: dict[str, Any]) -> None:
    path = policy_state_path(path_or_config) if isinstance(path_or_config, dict) else str(path_or_config)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state or default_policy_state(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)


def scope_hash(codes: list[str] | set[str]) -> str:
    data = "\n".join(sorted(str(c) for c in codes))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def cleanup_queue_key(code: str, source: str, reason: str) -> str:
    return f"{source}:{reason}:{code}"


def queued_cleanup_lookup(state: dict[str, Any]) -> set[str]:
    return {str(item.get("key")) for item in state.get("cleanup_queue", []) if item.get("key")}


def queued_cleanup_items(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return cleanup queue items keyed by queue key."""
    return {str(item.get("key")): item for item in state.get("cleanup_queue", []) if item.get("key")}


def upsert_cleanup_queue(state: dict[str, Any], code: str, source: str, reason: str, ttl_hours: int = 24) -> dict[str, Any]:
    key = cleanup_queue_key(code, source, reason)
    now = utcnow()
    expires = now + timedelta(hours=max(int(ttl_hours or 24), 1))
    existing = queued_cleanup_items(state).get(key, {})
    queue = [item for item in state.get("cleanup_queue", []) if item.get("key") != key]
    item = {
        **existing,
        "key": key,
        "code": code,
        "source": source,
        "reason": reason,
        "first_seen_at": existing.get("first_seen_at") or now.isoformat(),
        "last_seen_at": now.isoformat(),
        "seen_runs": int(existing.get("seen_runs", 0) or 0) + 1,
        "expires_at": expires.isoformat(),
    }
    queue.append(item)
    state["cleanup_queue"] = queue
    return item


def cleanup_queue_remove(state: dict[str, Any], codes: set[str]) -> None:
    codes = {str(c) for c in codes}
    state["cleanup_queue"] = [item for item in state.get("cleanup_queue", []) if str(item.get("code")) not in codes]


def confirmation_lookup(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in state.get("pending_confirmations", []) if item.get("id")}


def upsert_confirmation(state: dict[str, Any], item: dict[str, Any], expires_hours: int = 24) -> dict[str, Any]:
    now = utcnow()
    cid = item["id"]
    existing = confirmation_lookup(state).get(cid, {})
    merged = {**existing, **item}
    merged.setdefault("created_at", now.isoformat())
    merged.setdefault("confirmed", False)
    merged["updated_at"] = now.isoformat()
    merged["expires_at"] = (now + timedelta(hours=max(int(expires_hours or 24), 1))).isoformat()
    pending = [x for x in state.get("pending_confirmations", []) if x.get("id") != cid]
    pending.append(merged)
    state["pending_confirmations"] = pending
    return merged


def is_confirmation_confirmed(state: dict[str, Any], cid: str, expected_scope_hash: str | None = None) -> bool:
    item = confirmation_lookup(state).get(cid)
    if not item or not item.get("confirmed"):
        return False
    if expected_scope_hash and item.get("scope_hash") and item.get("scope_hash") != expected_scope_hash:
        return False
    try:
        expires = datetime.fromisoformat(str(item.get("expires_at")))
        if expires < utcnow():
            return False
    except Exception:
        pass
    return True


def confirm_cleanup(state: dict[str, Any], confirmation_id: str, actor: str = "admin") -> bool:
    found = False
    now = utcnow().isoformat()
    state.setdefault("confirmation_history", [])
    for item in state.get("pending_confirmations", []):
        if item.get("id") == confirmation_id:
            item["confirmed"] = True
            item["confirmed_by"] = actor
            item["confirmed_at"] = now
            state["confirmation_history"].append({
                "ts": now,
                "action": "confirmed",
                "confirmation_id": confirmation_id,
                "actor": actor,
                "source": item.get("source"),
                "reason": item.get("reason"),
                "affected_rows": item.get("affected_rows"),
                "apply_mode": item.get("apply_mode"),
            })
            state["confirmation_history"] = state["confirmation_history"][-500:]
            found = True
    return found


def dismiss_confirmation(state: dict[str, Any], confirmation_id: str, actor: str = "admin") -> bool:
    before_items = list(state.get("pending_confirmations", []))
    before = len(before_items)
    removed = [item for item in before_items if item.get("id") == confirmation_id]
    state["pending_confirmations"] = [item for item in before_items if item.get("id") != confirmation_id]
    changed = len(state.get("pending_confirmations", [])) != before
    if changed:
        state.setdefault("confirmation_history", [])
        now = utcnow().isoformat()
        for item in removed or [{"id": confirmation_id}]:
            state["confirmation_history"].append({
                "ts": now,
                "action": "dismissed",
                "confirmation_id": confirmation_id,
                "actor": actor,
                "source": item.get("source"),
                "reason": item.get("reason"),
                "affected_rows": item.get("affected_rows"),
            })
        state["confirmation_history"] = state["confirmation_history"][-500:]
    return changed


def prune_expired(state: dict[str, Any]) -> None:
    now = utcnow()
    def ok(item):
        try:
            return datetime.fromisoformat(str(item.get("expires_at"))) >= now
        except Exception:
            return True
    state["pending_confirmations"] = [x for x in state.get("pending_confirmations", []) if ok(x)]
    state["cleanup_queue"] = [x for x in state.get("cleanup_queue", []) if ok(x)]
