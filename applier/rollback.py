import shutil
from pathlib import Path
from applier.backup import create_backup


def restore_backup(config: dict, backup_id: str):
    # Backup current live files before rollback so restore is reversible.
    create_backup(config, reason=f"before_restore_{backup_id}")
    root = Path(config["paths"].get("backup_dir", "backups")) / backup_id
    if not root.exists():
        raise FileNotFoundError(f"Backup not found: {backup_id}")
    mapping = {
        "ShapedDevices.csv": config["paths"].get("shaped_devices_csv"),
        "network.json": config["paths"].get("network_json"),
    }
    restored = []
    for name, dest in mapping.items():
        src = root / name
        if src.exists() and dest:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            restored.append(dest)
    return restored
