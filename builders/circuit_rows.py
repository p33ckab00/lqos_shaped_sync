import random
import string

def generate_short_id(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

def safe_int_mbps(value: float, minimum: float = 0.128) -> float:
    try:
        return max(round(float(value), 3), minimum)
    except Exception:
        return minimum

def calculate_user_min_max(base_rx: float, base_tx: float, min_rate_percentage: float):
    rx_max = safe_int_mbps(base_rx)
    tx_max = safe_int_mbps(base_tx)
    rx_min = safe_int_mbps(base_rx * min_rate_percentage)
    tx_min = safe_int_mbps(base_tx * min_rate_percentage)
    return str(rx_min), str(tx_min), str(rx_max), str(tx_max)

def create_new_entry(code: str, device_name: str, id_length: int, mac: str = "", ipv4: str = "", comment: str = "") -> dict:
    return {
        "Circuit ID": generate_short_id(id_length),
        "Circuit Name": code,
        "Device ID": generate_short_id(id_length),
        "Device Name": device_name,
        "Parent Node": "",
        "MAC": mac,
        "IPv4": ipv4,
        "IPv6": "",
        "Download Min Mbps": "0",
        "Upload Min Mbps": "0",
        "Download Max Mbps": "0",
        "Upload Max Mbps": "0",
        "Comment": comment,
    }

def update_entry_values(entry: dict, new_values: dict) -> bool:
    changed = False
    for key, value in new_values.items():
        if str(entry.get(key, "")) != str(value):
            entry[key] = value
            changed = True
    return changed
