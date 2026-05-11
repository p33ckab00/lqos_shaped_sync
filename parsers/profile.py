import re
from typing import Optional, Tuple
from parsers.bandwidth import parse_comment_bandwidth, parse_rate_limit

RE_PROFILE_SPEED = re.compile(r"(\d+(?:\.\d+)?)([kKmMgG]?)\s*$", re.IGNORECASE)

def parse_speed_from_profile_name(profile_name: str) -> Optional[Tuple[float, float]]:
    if not profile_name:
        return None
    m = RE_PROFILE_SPEED.search(str(profile_name).strip())
    if not m:
        return None
    number = float(m.group(1))
    unit = m.group(2).lower()
    mbps = {"": 1.0, "k": 0.001, "m": 1.0, "g": 1000.0}.get(unit, 1.0) * number
    if mbps <= 0:
        return None
    return mbps, mbps

def resolve_pppoe_speed(secret: dict, active_row: dict, profile_name: str, profile_cache: dict, default_rate: str):
    secret_comment = str(secret.get("comment", "")).strip()
    active_comment = str(active_row.get("comment", "")).strip()
    parsed = parse_comment_bandwidth(secret_comment)
    if parsed:
        return parsed[0], parsed[1], "secret_comment"
    parsed = parse_comment_bandwidth(active_comment)
    if parsed:
        return parsed[0], parsed[1], "active_comment"
    if profile_name in profile_cache:
        rx, tx, source = profile_cache[profile_name]
        return rx, tx, source
    rx, tx = parse_rate_limit(default_rate)
    return rx, tx, "default"
