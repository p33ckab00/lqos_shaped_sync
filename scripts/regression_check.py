#!/usr/bin/env python3
"""LQoSync offline regression suite.

Run this before publishing or after updating from GitHub:

    cd /opt/lqosync
    python3 scripts/regression_check.py
    python3 scripts/regression_check.py --json

It is read-only and does not require RouterOS, LibreQoS, Flask, or network
access. It checks route/template wiring, key template contexts, config
migration, policy safety behavior, Operations Center compatibility, and docs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.regression import compute_regression_suite  # noqa: E402


def main() -> int:
    json_mode = "--json" in sys.argv
    report = compute_regression_suite(ROOT)
    if json_mode:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["summary"]["fail"] == 0 else 1

    print("LQoSync Regression Check")
    print("=" * 28)
    print(f"Verdict: {report['verdict']}")
    print(f"OK={report['summary']['ok']} WARN={report['summary']['warn']} FAIL={report['summary']['fail']}")
    print()
    for item in report["items"]:
        status = item["status"].upper()
        print(f"[{status}] {item['title']} ({item.get('category','regression')})")
        print(f"       {item['detail']}")
        if item.get("fix"):
            print(f"       Fix: {item['fix']}")
    return 0 if report["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
