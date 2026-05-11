#!/usr/bin/env python3
"""Set or create a local LQoSync user in users.json.

Usage:
  USERS_PATH=/opt/lqosync/users.json ./scripts/set_password.py admin newpass admin
  ./scripts/set_password.py viewer viewpass viewer
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth.users import hash_password, ensure_users_file, users_path  # noqa: E402
from applier.atomic_writer import atomic_write_text  # noqa: E402


def main():
    if len(sys.argv) < 3:
        print("Usage: set_password.py USERNAME PASSWORD [admin|viewer]", file=sys.stderr)
        return 2
    username, password = sys.argv[1], sys.argv[2]
    role = sys.argv[3] if len(sys.argv) > 3 else "admin"
    if role not in ("admin", "viewer"):
        print("role must be admin or viewer", file=sys.stderr)
        return 2
    path = Path(os.getenv("USERS_PATH") or users_path())
    ensure_users_file(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    users = data.setdefault("users", [])
    for u in users:
        if u.get("username") == username:
            u["password_hash"] = hash_password(password)
            u["role"] = role
            break
    else:
        users.append({"username": username, "password_hash": hash_password(password), "role": role})
    atomic_write_text(path, json.dumps(data, indent=2) + "\n")
    try:
        path.chmod(0o600)
    except Exception:
        pass
    print(f"Updated {username} ({role}) in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
