def check_duplicate_ip(existing_data: dict, ip: str, code: str, context=None) -> bool:
    if not ip:
        return False
    for existing_code, row in existing_data.items():
        if existing_code == code:
            continue
        if row.get("IPv4", "").strip() == ip.strip():
            msg = f"Duplicate IP {ip} between {existing_code} and {code}"
            if context is not None:
                context.warnings.append(msg)
            return True
    return False
