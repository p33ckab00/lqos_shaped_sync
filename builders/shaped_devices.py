import csv
import io
from pathlib import Path

FIELDNAMES = [
    "Circuit ID", "Circuit Name", "Device ID", "Device Name", "Parent Node", "MAC", "IPv4", "IPv6",
    "Download Min Mbps", "Upload Min Mbps", "Download Max Mbps", "Upload Max Mbps", "Comment",
]

def read_shaped_devices_csv(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        data = {}
        for row in reader:
            circuit_name = row.get("Circuit Name", "").strip()
            if circuit_name:
                data[circuit_name] = row
        return data

def render_shaped_devices_csv(data: dict) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    cleaned_rows = []
    for row in data.values():
        cleaned_rows.append({field: str(row.get(field, "")) for field in FIELDNAMES})
    cleaned_rows.sort(key=lambda r: (r.get("Parent Node", ""), r.get("Circuit Name", ""), r.get("Device Name", ""), r.get("IPv4", ""), r.get("MAC", "")))
    writer.writerows(cleaned_rows)
    return output.getvalue()

def count_by_comment(data: dict):
    counts = {"pppoe":0, "dhcp":0, "hotspot":0, "static":0, "other":0}
    for row in data.values():
        c = str(row.get("Comment", "")).lower()
        if c == "ppp": counts["pppoe"] += 1
        elif c == "hs": counts["hotspot"] += 1
        elif c == "static": counts["static"] += 1
        elif c.startswith("dhcp") or c not in ("ppp", "hs", "static", ""):
            # DHCP rows often use hostname in Comment.
            counts["dhcp"] += 1
        else: counts["other"] += 1
    return counts
