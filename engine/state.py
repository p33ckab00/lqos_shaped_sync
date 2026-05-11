import json
import os
from pathlib import Path
from datetime import datetime, timezone
from applier.atomic_writer import atomic_write_text

DEFAULT_STATE = {
    "scheduler_state": "idle",
    "scheduler_enabled": False,
    "sync_running": False,
    "libreqos_running": False,
    "last_run": None,
    "last_dry_run": None,
    "last_error": None,
    "last_libreqos_apply_success": None,
    "last_libreqos_apply_failed": False,
    "pending_libreqos_apply": False,
    "last_libreqos_apply_reason": None,
    "last_libreqos_exit_code": None,
    "updated_at": None,
}

def load_state(path):
    p = Path(path)
    if not p.exists():
        return dict(DEFAULT_STATE)
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        out = dict(DEFAULT_STATE)
        out.update(data)
        return out
    except Exception:
        return dict(DEFAULT_STATE)

def save_state(path, state):
    state = dict(state)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(state, indent=2, ensure_ascii=False) + "\n")

def update_state(path, **kwargs):
    st = load_state(path)
    st.update(kwargs)
    save_state(path, st)
    return st
