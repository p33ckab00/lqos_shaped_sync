#!/usr/bin/env python3
"""Audit LQoSync required runtime paths and policy schema/default coverage."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.policy_path_audit import audit_policy_and_paths  # noqa: E402


def main() -> int:
    report = audit_policy_and_paths(ROOT)
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["summary"]["fail"] == 0 else 1
    print("LQoSync Policy/Path Audit")
    print("=" * 29)
    print(f"Verdict: {report['verdict']}")
    print(f"OK={report['summary']['ok']} WARN={report['summary']['warn']} FAIL={report['summary']['fail']}")
    print()
    for item in report["items"]:
        print(f"[{item['status'].upper()}] {item['title']}")
        print(f"       {item['detail']}")
        if item.get("fix"):
            print(f"       Fix: {item['fix']}")
    return 0 if report["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
