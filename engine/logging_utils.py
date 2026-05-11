from datetime import datetime
from pathlib import Path

def log_event(config: dict, level: str, message: str):
    try:
        path = Path(config.get('paths', {}).get('log_file', 'logs/lqos_shaped_sync.log'))
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with path.open('a', encoding='utf-8') as f:
            f.write(f"{stamp} - {level.upper()} - {message}\n")
    except Exception:
        pass
