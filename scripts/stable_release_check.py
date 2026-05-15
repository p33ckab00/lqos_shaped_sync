#!/usr/bin/env python3
"""LQoSync v2.70 Stable Release Candidate check.

Run before publishing a stable candidate or after update:

    cd /opt/lqosync
    python3 scripts/stable_release_check.py
    python3 scripts/stable_release_check.py --json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.stable_release import compute_stable_release_check  # noqa: E402


def main() -> int:
    report = compute_stable_release_check(ROOT)
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["summary"].get("fail", 0) == 0 else 1
    print("LQoSync Stable Release Candidate Check")
    print("=" * 43)
    print(f"Target: {report['target']}")
    print(f"Verdict: {report['verdict']}")
    print(f"OK={report['summary']['ok']} WARN={report['summary']['warn']} FAIL={report['summary']['fail']}")
    print()
    print("Feature freeze: active")
    print("Allowed: " + ", ".join(report["feature_freeze"]["allowed"]))
    print("Not allowed: " + ", ".join(report["feature_freeze"]["not_allowed"]))
    print()
    for item in report["items"]:
        print(f"[{item['status'].upper()}] {item['title']} ({item.get('category','stable')})")
        print(f"       {item['detail']}")
        if item.get("fix"):
            print(f"       Fix: {item['fix']}")
    return 0 if report["summary"].get("fail", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
