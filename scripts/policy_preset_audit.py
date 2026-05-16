#!/usr/bin/env python3
"""Audit policy preset alignment and custom-save semantics."""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.policy_preset_audit import audit_policy_presets  # noqa: E402

def main() -> int:
    json_mode = "--json" in sys.argv
    report = audit_policy_presets(ROOT)
    if json_mode:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["summary"].get("fail", 0) == 0 else 1
    print("LQoSync Policy Preset Audit")
    print("============================")
    print(f"Verdict: {report['verdict']}")
    print(f"OK={report['summary']['ok']} WARN={report['summary']['warn']} FAIL={report['summary']['fail']}")
    print()
    for item in report["items"]:
        print(f"[{item['status'].upper()}] {item['title']} ({item.get('category','policy_preset')})")
        print(f"       {item['detail']}")
        if item.get("fix"):
            print(f"       Fix: {item['fix']}")
    return 0 if report["summary"].get("fail", 0) == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
