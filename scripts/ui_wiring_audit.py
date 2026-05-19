#!/usr/bin/env python3
"""Run the LQoSync UI wiring audit."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.ui_wiring_audit import audit_ui_wiring  # noqa: E402


def main() -> int:
    report = audit_ui_wiring(ROOT)
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["summary"]["fail"] == 0 else 1
    print("LQoSync UI Wiring Audit")
    print("=======================")
    print(f"Verdict: {report['verdict']}")
    print(f"OK={report['summary']['ok']} WARN={report['summary']['warn']} FAIL={report['summary']['fail']}")
    print()
    for item in report["items"]:
        print(f"[{item['status'].upper()}] {item['title']} ({item.get('category','ui_wiring')})")
        print(f"       {item['detail']}")
        if item.get("fix"):
            print(f"       Fix: {item['fix']}")
    return 0 if report["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
