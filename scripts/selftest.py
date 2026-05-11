#!/usr/bin/env python3
"""Offline self-test for LQoSync. Does not require RouterOS or LibreQoS."""
import csv
import json
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import engine.run_cycle as rc
from builders.shaped_devices import FIELDNAMES
try:
    from auth.users import add_user, update_user, set_user_password, delete_user, list_users, authenticate
except Exception:
    add_user = update_user = set_user_password = delete_user = list_users = authenticate = None

class FakeResource:
    def __init__(self, rows):
        self.rows = rows
    def get(self, **filters):
        return self.rows

class FakeAPI:
    def __init__(self):
        self.data = {
            "/ppp/profile": [{"name": "Tier-15M", "rate-limit": "15M/15M"}],
            "/ppp/secret": [{"name": "juan", "disabled": "false", "inactive": "false", "profile": "Tier-15M", "comment": ""}],
            "/ppp/active": [{"name": "juan", "address": "10.0.100.10", "caller-id": "AA:BB:CC:DD:EE:01", "comment": ""}],
            "/ip/hotspot/active": [],
            "/ip/dhcp-server/lease": [{"server": "LAN", "mac-address": "AA:BB:CC:DD:EE:02", "active-address": "10.17.0.20", "host-name": "mesh", "status": "bound"}],
        }
    def get_resource(self, path):
        return FakeResource(self.data[path])

class FakePool:
    def disconnect(self):
        pass

def fake_connect(router, retries=3):
    return FakePool(), FakeAPI(), None

def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        csv_path = td / "ShapedDevices.csv"
        net_path = td / "network.json"
        cfg_path = td / "config.json"
        state_path = td / "state.json"
        log_path = td / "test.log"
        csv_path.write_text(",".join(FIELDNAMES) + "\n", encoding="utf-8")
        net_path.write_text("{}\n", encoding="utf-8")
        cfg = {
            "app": {"auto_apply": False, "backup_before_apply": True},
            "paths": {"shaped_devices_csv": str(csv_path), "network_json": str(net_path), "backup_dir": str(td / "backups"), "log_file": str(log_path), "runtime_state": str(state_path)},
            "scheduler": {"enabled": False},
            "libreqos": {"cmd": "/opt/libreqos/src/LibreQoS.py", "args": ["--updateonly"], "timeout_seconds": 1, "run_only_when_files_changed": True, "sudo": False},
            "routers": [{
                "name": "RB5k9-Distro", "enabled": True, "address": "127.0.0.1", "port": 8728, "username": "x", "password": "x",
                "root_download_mbps": 115, "root_upload_mbps": 115,
                "pppoe": {"enabled": True, "per_plan_node": True, "factor_rules": [{"max_plan_mbps": 15, "download_factor": 0.31, "upload_factor": 0.31}, {"max_plan_mbps": 9999, "download_factor": 1.0, "upload_factor": 1.0}]},
                "dhcp": {"enabled": True, "servers": [{"name": "LAN", "enabled": True, "mode": "per_site", "default_plan_down_mbps": 15, "default_plan_up_mbps": 15, "download_factor": 0.3, "upload_factor": 0.3}]},
                "hotspot": {"enabled": False}
            }]
        }
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        old = rc.connect_to_router
        rc.connect_to_router = fake_connect
        try:
            dry = rc.run_cycle("dry_run", str(cfg_path))
            assert dry.status == "dry_run_complete", dry.to_dict()
            assert dry.files_changed is True
            assert dry.counts["pppoe"] == 1
            assert dry.counts["dhcp"] == 1
            assert "juan" not in csv_path.read_text(), "dry-run must not write"
            applied = rc.run_cycle("manual", str(cfg_path))
            assert applied.status == "success", applied.to_dict()
            text = csv_path.read_text()
            assert "juan" in text and "DHCP-mesh" in text, text
            net = json.loads(net_path.read_text())
            assert "RB5k9-Distro" in net
            assert "Tier-15M-RB5k9-Distro" in net["RB5k9-Distro"]["children"]
            assert "DHCP-LAN-RB5k9-Distro" in net["RB5k9-Distro"]["children"]


            # User-management JSON store: no database, bcrypt password hashes.
            # This block runs when optional dependency bcrypt is installed. Docker/bare-metal installs include it.
            if add_user:
                users_path = td / "users.json"
                add_user("viewer1", "viewpass", "viewer", users_path)
                assert authenticate("viewer1", "viewpass") is None  # authenticate() uses env/default path, not explicit path
                assert any(u["username"] == "viewer1" and u["role"] == "viewer" for u in list_users(users_path))
                update_user("viewer1", "viewer2", "admin", users_path)
                assert any(u["username"] == "viewer2" and u["role"] == "admin" for u in list_users(users_path))
                set_user_password("viewer2", "newpass", users_path)
                delete_user("viewer2", current_username="admin", path=users_path)
                assert not any(u["username"] == "viewer2" for u in list_users(users_path))

            # Flat under router root: all generated rows point directly to the router root,
            # and network.json contains only the router root with no child nodes.
            for mode, expected_parent, expect_empty_network in (
                ("flat_router_root", "RB5k9-Distro", False),
                ("flat_no_parent", "", True),
            ):
                csv_path.write_text(",".join(FIELDNAMES) + "\n", encoding="utf-8")
                net_path.write_text("{}\n", encoding="utf-8")
                cfg["network_mode"] = mode
                cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
                flat_res = rc.run_cycle("manual", str(cfg_path))
                assert flat_res.status == "success", flat_res.to_dict()
                rows = list(csv.DictReader(csv_path.open(newline="", encoding="utf-8")))
                assert rows, mode
                assert {row.get("Parent Node", "") for row in rows} == {expected_parent}, rows
                net2 = json.loads(net_path.read_text())
                if expect_empty_network:
                    assert net2 == {}, net2
                else:
                    assert net2.get("RB5k9-Distro", {}).get("children") == {}, net2
        finally:
            rc.connect_to_router = old
    print("LQoSync self-test passed")

if __name__ == "__main__":
    main()
