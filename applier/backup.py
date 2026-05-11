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
