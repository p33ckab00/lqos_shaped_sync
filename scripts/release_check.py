#!/usr/bin/env python3
"""LQoSync package quality / release integrity checker.

Run before publishing a package or after GitHub update:

    cd /opt/LQoSync
    python3 scripts/release_check.py

The checker is read-only. It verifies common packaging gaps such as missing
routes for navigation links, missing templates, missing feature engine modules,
and incomplete config defaults.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.release_integrity import compute_release_integrity  # noqa: E402


def main() -> int:
    json_mode = "--json" in sys.argv
    report = compute_release_integrity(ROOT)
    if json_mode:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["summary"]["fail"] == 0 else 1

    print("LQoSync Release Integrity Check")
    print("=" * 36)
    print(f"Verdict: {report['verdict']}")
    print(f"OK={report['summary']['ok']} WARN={report['summary']['warn']} FAIL={report['summary']['fail']}")
    print()
    for item in report["items"]:
        status = item["status"].upper()
        print(f"[{status}] {item['title']} ({item.get('category','release')})")
        print(f"       {item['detail']}")
        if item.get("fix"):
            print(f"       Fix: {item['fix']}")
    return 0 if report["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
