import re
from typing import Optional, Tuple

RE_PIPE = re.compile(r"\|(\d+(?:\.\d+)?)M/(\d+(?:\.\d+)?)M", re.IGNORECASE)
RE_PAIR = re.compile(r"(\d+(?:\.\d+)?)M/(\d+(?:\.\d+)?)M", re.IGNORECASE)
RE_SINGLE = re.compile(r"(\d+(?:\.\d+)?)M", re.IGNORECASE)
RE_UNIT = re.compile(r"^(\d+(?:\.\d+)?)([kKmMgG]?)$")
RE_PLAN_NAME = re.compile(r"^([^|]+)\|")

def convert_to_mbps(value_str: str) -> float:
    if not value_str:
        return 0.0
    value_str = str(value_str).strip()
    match = RE_UNIT.match(value_str)
    if not match:
        return 0.0
    number = float(match.group(1))
    unit = match.group(2).lower()
    return number * {"": 1.0, "k": 0.001, "m": 1.0, "g": 1000.0}.get(unit, 1.0)

def parse_rate_limit(rate_limit: str) -> Tuple[float, float]:
    if not rate_limit:
        return 0.0, 0.0
    try:
        primary = str(rate_limit).strip().split()[0]
        rx_raw, tx_raw = primary.split("/")
        return convert_to_mbps(rx_raw), convert_to_mbps(tx_raw)
    except Exception:
        return 0.0, 0.0

def parse_comment_bandwidth(comment: str) -> Optional[Tuple[float, float]]:
    if not comment:
        return None
    comment = str(comment).strip()
    for regex in (RE_PIPE, RE_PAIR):
        m = regex.search(comment)
        if m:
            return float(m.group(1)), float(m.group(2))
    m = RE_SINGLE.search(comment)
    if m:
        speed = float(m.group(1))
        return speed, speed
    return None
