#!/usr/bin/env python3
"""Remove known stale LQoSync files left behind by older ZIP/manual installs.

Default mode is dry-run. Use --apply to delete known stale files.
The list is intentionally conservative and only includes files that are no
longer canonical and are safe to remove after the compact information
architecture/de-duplication releases.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STALE_FILES = [
    {
        "path": "templates/routers.html",
        "reason": "Standalone Router page removed; /routers now redirects to Config Center → Routers and Router Insight is embedded there.",
        "introduced_by": "pre-v2.69.1 ZIP/manual installs",
    },
]


def scan(root: Path) -> list[dict]:
    rows = []
    for item in STALE_FILES:
        p = root / item["path"]
        rows.append({**item, "exists": p.exists(), "absolute_path": str(p)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="LQoSync stale-file cleanup")
    parser.add_argument("--apply", action="store_true", help="Delete known stale files. Default is dry-run.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    args = parser.parse_args()

    rows = scan(ROOT)
    deleted = []
    failed = []
    if args.apply:
        for row in rows:
            if not row["exists"]:
                continue
            p = Path(row["absolute_path"])
            try:
                p.unlink()
                row["exists_after"] = False
                deleted.append(row["path"])
            except Exception as exc:
                row["error"] = str(exc)
                failed.append(row["path"])
    report = {
        "mode": "apply" if args.apply else "dry_run",
        "root": str(ROOT),
        "stale_found": [r["path"] for r in rows if r["exists"]],
        "deleted": deleted,
        "failed": failed,
        "rows": rows,
        "ok": not failed,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("LQoSync Stale File Cleanup")
        print("==========================")
        print(f"Mode: {report['mode']}")
        if not report["stale_found"]:
            print("No known stale files found.")
        else:
            print("Known stale files found:")
            for row in rows:
                if row["exists"]:
                    print(f" - {row['path']}: {row['reason']}")
            if not args.apply:
                print("\nRun with --apply to remove them.")
        if deleted:
            print("Deleted:")
            for path in deleted:
                print(f" - {path}")
        if failed:
            print("Failed:")
            for path in failed:
                print(f" - {path}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
