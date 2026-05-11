from rules.network_mode import get_network_mode

def run_preflight(rows: dict, network: dict, config: dict):
    warnings = []
    errors = []
    network_mode = get_network_mode(config)
    seen_ips = {}
    for code, row in rows.items():
        if not row.get("Circuit Name"):
            errors.append("Empty Circuit Name")
        if not row.get("Parent Node") and network_mode != "flat_no_parent":
            policy = config.get("preflight", {}).get("missing_parent_policy", "block")
            msg = f"Missing Parent Node for {code}"
            (errors if policy == "block" else warnings).append(msg)
        ip = row.get("IPv4", "").strip()
        if ip:
            if ip in seen_ips:
                msg = f"Duplicate IP {ip}: {seen_ips[ip]} and {code}"
                pol = config.get("preflight", {}).get("duplicate_ip_policy", "warn_and_skip")
                (errors if pol == "block" else warnings).append(msg)
            else:
                seen_ips[ip] = code
        for key in ("Download Min Mbps", "Upload Min Mbps", "Download Max Mbps", "Upload Max Mbps"):
            try:
                float(row.get(key, 0) or 0)
            except Exception:
                errors.append(f"Invalid bandwidth {key} for {code}")
    return {"warnings": warnings, "errors": errors}
