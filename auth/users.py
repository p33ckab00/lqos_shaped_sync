import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import bcrypt

from applier.atomic_writer import atomic_write_text

DEFAULT_ADMIN_PASSWORD = "adminpass"

# Role model introduced for v2.67. Older installs with only admin/viewer remain
# valid; the first admin is promoted to owner when no owner exists so that owner-
# only user/update controls do not lock out preserved installations.
VALID_ROLES = {"owner", "admin", "operator", "viewer"}
ROLE_ORDER = {"viewer": 10, "operator": 20, "admin": 30, "owner": 40}
ROLE_DEFINITIONS = {
    "owner": {
        "label": "Owner",
        "description": "Full control including users, updates, setup/repair, config, policies, backups, and live actions.",
    },
    "admin": {
        "label": "Admin",
        "description": "Can manage config, policies, scheduler, operations, backups, and live apply actions, but not owner-only user/update controls.",
    },
    "operator": {
        "label": "Operator",
        "description": "Can monitor, run/view dry-runs and reports, and inspect operations. Cannot edit config/policies/users or perform destructive actions.",
    },
    "viewer": {
        "label": "Viewer",
        "description": "Read-only access to dashboards, reports, devices, documentation, and status pages.",
    },
}


def users_path():
    return os.getenv("USERS_PATH") or "users.json"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def _blank_store() -> dict:
    return {"users": []}


def _default_store() -> dict:
    return {
        "users": [
            {
                "username": "admin",
                "password_hash": hash_password(DEFAULT_ADMIN_PASSWORD),
                "role": "owner",
            }
        ]
    }


def ensure_users_file(path=None):
    path = path or users_path()
    p = Path(path)
    if p.exists():
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(p, json.dumps(_default_store(), indent=2) + "\n")
    try:
        p.chmod(0o600)
    except Exception:
        pass


def _read_store(path=None) -> dict:
    path = path or users_path()
    ensure_users_file(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = _blank_store()
    if not isinstance(data, dict):
        data = _blank_store()
    users = data.get("users")
    if not isinstance(users, list):
        data["users"] = []
    return data


def _write_store(data: dict, path=None) -> None:
    path = path or users_path()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    users = data.get("users", [])
    if not isinstance(users, list):
        users = []
    data = {"users": users}
    atomic_write_text(p, json.dumps(data, indent=2, sort_keys=True) + "\n")
    try:
        p.chmod(0o600)
    except Exception:
        pass


def _normalize_username(username: str) -> str:
    return str(username or "").strip()


def _normalize_role(role: str) -> str:
    role = str(role or "viewer").strip().lower()
    # Backward-compatible aliases from older/other naming conventions.
    aliases = {
        "superadmin": "owner",
        "super_admin": "owner",
        "read_only": "viewer",
        "readonly": "viewer",
        "ops": "operator",
    }
    role = aliases.get(role, role)
    return role if role in VALID_ROLES else "viewer"


def role_rank(role: str) -> int:
    return ROLE_ORDER.get(_normalize_role(role), 0)


def role_at_least(role: str, minimum: str) -> bool:
    return role_rank(role) >= role_rank(minimum)


def _public_user(user: dict) -> dict:
    return {
        "username": user.get("username", ""),
        "role": user.get("role", "viewer"),
        "role_label": ROLE_DEFINITIONS.get(user.get("role", "viewer"), {}).get("label", user.get("role", "viewer")),
        "has_password": bool(user.get("password_hash")),
    }


def load_users(path=None) -> List[dict]:
    data = _read_store(path)
    # De-duplicate while preserving order. Invalid usernames are skipped.
    seen = set()
    normalized = []
    changed = False
    for user in data.get("users", []):
        if not isinstance(user, dict):
            changed = True
            continue
        username = _normalize_username(user.get("username"))
        if not username or username in seen:
            changed = True
            continue
        role = _normalize_role(user.get("role"))
        password_hash = str(user.get("password_hash", ""))
        normalized.append({"username": username, "password_hash": password_hash, "role": role})
        seen.add(username)
        if username != user.get("username") or role != user.get("role"):
            changed = True
    # Always keep at least one owner-capable account. Existing old installs with
    # a single admin are promoted to owner to avoid locking out user/update flows.
    if normalized and not any(u.get("role") == "owner" for u in normalized):
        admin_idx = next((i for i, u in enumerate(normalized) if u.get("role") == "admin"), 0)
        normalized[admin_idx]["role"] = "owner"
        changed = True
    if not normalized:
        normalized.append({"username": "admin", "password_hash": hash_password(DEFAULT_ADMIN_PASSWORD), "role": "owner"})
        changed = True
    if changed:
        _write_store({"users": normalized}, path)
    return normalized


def list_users(path=None) -> List[dict]:
    return [_public_user(u) for u in load_users(path)]


def role_options() -> List[dict]:
    return [{"value": r, **ROLE_DEFINITIONS[r]} for r in ("owner", "admin", "operator", "viewer")]


def authenticate(username: str, password: str):
    username = _normalize_username(username)
    for user in load_users():
        if user.get("username") == username and check_password(password, user.get("password_hash", "")):
            return {"username": user["username"], "role": user.get("role", "viewer")}
    return None


def _find_user(users: List[dict], username: str) -> Tuple[int, dict | None]:
    for idx, user in enumerate(users):
        if user.get("username") == username:
            return idx, user
    return -1, None


def admin_count(users: List[dict]) -> int:
    # Backward compatibility: owner is also admin-capable.
    return sum(1 for u in users if u.get("role") in {"owner", "admin"})


def owner_count(users: List[dict]) -> int:
    return sum(1 for u in users if u.get("role") == "owner")


def add_user(username: str, password: str, role: str = "viewer", path=None) -> dict:
    username = _normalize_username(username)
    if not username:
        raise ValueError("Username is required.")
    if not password:
        raise ValueError("Password is required for new users.")
    role = _normalize_role(role)
    data = _read_store(path)
    users = load_users(path)
    if any(u.get("username") == username for u in users):
        raise ValueError(f"User '{username}' already exists.")
    users.append({"username": username, "password_hash": hash_password(password), "role": role})
    data["users"] = users
    _write_store(data, path)
    return {"username": username, "role": role}


def update_user(old_username: str, new_username: str, role: str, path=None) -> dict:
    old_username = _normalize_username(old_username)
    new_username = _normalize_username(new_username)
    if not old_username:
        raise ValueError("Original username is required.")
    if not new_username:
        raise ValueError("Username is required.")
    role = _normalize_role(role)
    users = load_users(path)
    idx, user = _find_user(users, old_username)
    if user is None:
        raise KeyError(f"User '{old_username}' was not found.")
    if new_username != old_username and any(u.get("username") == new_username for u in users):
        raise ValueError(f"User '{new_username}' already exists.")
    if user.get("role") == "owner" and role != "owner" and owner_count(users) <= 1:
        raise ValueError("Cannot demote the last owner user.")
    if user.get("role") in {"owner", "admin"} and role not in {"owner", "admin"} and admin_count(users) <= 1:
        raise ValueError("Cannot remove the last admin-capable user.")
    users[idx] = {"username": new_username, "password_hash": user.get("password_hash", ""), "role": role}
    _write_store({"users": users}, path)
    return {"username": new_username, "role": role}


def set_user_password(username: str, password: str, path=None) -> dict:
    username = _normalize_username(username)
    if not password:
        raise ValueError("Password is required.")
    users = load_users(path)
    idx, user = _find_user(users, username)
    if user is None:
        raise KeyError(f"User '{username}' was not found.")
    users[idx]["password_hash"] = hash_password(password)
    _write_store({"users": users}, path)
    return {"username": username, "role": users[idx].get("role", "viewer")}


def delete_user(username: str, current_username: str | None = None, path=None) -> dict:
    username = _normalize_username(username)
    current_username = _normalize_username(current_username)
    users = load_users(path)
    idx, user = _find_user(users, username)
    if user is None:
        raise KeyError(f"User '{username}' was not found.")
    if current_username and username == current_username:
        raise ValueError("You cannot delete the currently logged-in user.")
    if user.get("role") == "owner" and owner_count(users) <= 1:
        raise ValueError("Cannot delete the last owner user.")
    if user.get("role") in {"owner", "admin"} and admin_count(users) <= 1:
        raise ValueError("Cannot delete the last admin-capable user.")
    deleted = users.pop(idx)
    _write_store({"users": users}, path)
    return {"username": deleted.get("username"), "role": deleted.get("role", "viewer")}
