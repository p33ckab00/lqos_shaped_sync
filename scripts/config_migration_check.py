#!/usr/bin/env python3
"""LQoSync config migration regression check.

This is a focused wrapper around the regression suite config-migration cases.
It verifies that preserved older configs can be migrated to the current schema
without missing policy/default warnings.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.regression import check_config_migration_regressions  # noqa: E402


def main() -> int:
    json_mode = "--json" in sys.argv
    report = check_config_migration_regressions(ROOT)
    if json_mode:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["summary"]["fail"] == 0 else 1
    print("LQoSync Config Migration Check")
    print("=" * 34)
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
