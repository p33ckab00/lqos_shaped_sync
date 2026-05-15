import hashlib
import json
import shutil
from pathlib import Path
from datetime import datetime


def sha256_file(path):
    p = Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def prune_backups(config: dict):
    root = Path(config["paths"].get("backup_dir", "backups"))
    retention = int(config.get("app", {}).get("backup_retention", 30) or 30)
    if retention <= 0 or not root.exists():
        return
    backups = sorted([p for p in root.iterdir() if p.is_dir()], reverse=True)
    for old in backups[retention:]:
        shutil.rmtree(old, ignore_errors=True)


def create_backup(config: dict, reason="sync"):
    paths = config["paths"]
    backup_root = Path(paths.get("backup_dir", "backups"))
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dest = backup_root / stamp
    # Avoid collision if two backups happen within the same second.
    n = 1
    while dest.exists():
        dest = backup_root / f"{stamp}_{n}"
        n += 1
    dest.mkdir(parents=True, exist_ok=True)
    files = {
        "ShapedDevices.csv": paths.get("shaped_devices_csv"),
        "network.json": paths.get("network_json"),
    }
    hashes = {}
    for name, src in files.items():
        if src and Path(src).exists():
            shutil.copy2(src, dest / name)
            hashes[name] = sha256_file(src)
    meta = {"timestamp": dest.name, "reason": reason, "hashes": hashes}
    (dest / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    prune_backups(config)
    return str(dest)


def list_backups(config: dict):
    root = Path(config["paths"].get("backup_dir", "backups"))
    if not root.exists():
        return []
    backups = []
    for p in sorted([p for p in root.iterdir() if p.is_dir()], reverse=True):
        meta = {}
        try:
            meta = json.loads((p / "metadata.json").read_text(encoding="utf-8"))
        except Exception:
            pass
        backups.append({"id": p.name, "path": str(p), "metadata": meta})
    return backups



def delete_backup(config: dict, backup_id: str):
    """Delete a single backup directory safely from the configured backup_dir.

    The backup_id must be a direct child directory name. Path traversal is
    blocked by resolving the requested path and verifying it remains under the
    configured backup root.
    """
    root = Path(config["paths"].get("backup_dir", "backups")).resolve()
    target = (root / backup_id).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Backup root not found: {root}")
    if target.parent != root:
        raise ValueError("Invalid backup id")
    if not target.exists() or not target.is_dir():
        raise FileNotFoundError(f"Backup not found: {backup_id}")
    shutil.rmtree(target)
    return {"id": backup_id, "path": str(target)}


def _backup_root(config: dict) -> Path:
    return Path(config["paths"].get("backup_dir", "backups")).resolve()


def _backup_path(config: dict, backup_id: str) -> Path:
    root = _backup_root(config)
    target = (root / backup_id).resolve()
    if target.parent != root:
        raise ValueError("Invalid backup id")
    if not target.exists() or not target.is_dir():
        raise FileNotFoundError(f"Backup not found: {backup_id}")
    return target


def inspect_backup(config: dict, backup_id: str):
    """Return backup integrity/details without modifying live files."""
    target = _backup_path(config, backup_id)
    meta = {}
    try:
        meta = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}

    files = []
    expected = ["ShapedDevices.csv", "network.json"]
    stored_hashes = meta.get("hashes", {}) if isinstance(meta, dict) else {}
    for name in expected:
        p = target / name
        exists = p.exists()
        digest = sha256_file(p) if exists else None
        files.append({
            "name": name,
            "exists": exists,
            "size_bytes": p.stat().st_size if exists else 0,
            "sha256": digest,
            "metadata_sha256": stored_hashes.get(name),
            "hash_ok": (stored_hashes.get(name) in (None, digest)) if exists else False,
        })
    ok = all(f["exists"] and f["hash_ok"] for f in files)
    return {"id": backup_id, "path": str(target), "metadata": meta, "files": files, "ok": ok}


def compare_backup_to_live(config: dict, backup_id: str):
    """Compare backup files against live target files without restoring."""
    target = _backup_path(config, backup_id)
    paths = config.get("paths", {})
    mapping = {
        "ShapedDevices.csv": paths.get("shaped_devices_csv"),
        "network.json": paths.get("network_json"),
    }
    comparisons = []
    for name, live_path in mapping.items():
        backup_file = target / name
        live = Path(live_path) if live_path else None
        backup_hash = sha256_file(backup_file) if backup_file.exists() else None
        live_hash = sha256_file(live) if live and live.exists() else None
        comparisons.append({
            "name": name,
            "backup_exists": backup_file.exists(),
            "live_path": str(live) if live else "",
            "live_exists": bool(live and live.exists()),
            "backup_size_bytes": backup_file.stat().st_size if backup_file.exists() else 0,
            "live_size_bytes": live.stat().st_size if live and live.exists() else 0,
            "backup_sha256": backup_hash,
            "live_sha256": live_hash,
            "changed": backup_hash != live_hash,
            "restore_action": "replace_live" if backup_file.exists() else "skip_missing_backup_file",
        })
    changed_count = sum(1 for c in comparisons if c["changed"])
    return {"id": backup_id, "comparisons": comparisons, "changed_count": changed_count, "would_restore": [c for c in comparisons if c["backup_exists"]]}


def retention_preview(config: dict):
    """Return what prune_backups would delete based on configured retention."""
    root = Path(config["paths"].get("backup_dir", "backups"))
    retention = int(config.get("app", {}).get("backup_retention", 30) or 30)
    backups = []
    if root.exists():
        backups = sorted([p for p in root.iterdir() if p.is_dir()], reverse=True)
    keep = backups[:retention] if retention > 0 else backups
    delete = backups[retention:] if retention > 0 else []
    return {
        "backup_dir": str(root),
        "retention": retention,
        "total": len(backups),
        "keep_count": len(keep),
        "delete_count": len(delete),
        "keep": [p.name for p in keep],
        "would_delete": [p.name for p in delete],
    }
