def clean_mac(mac: str) -> str:
    return str(mac or "").replace(":", "").replace("-", "").upper()

def build_pppoe_code(username: str, mac: str) -> str:
    return str(username or "").strip() or clean_mac(mac)

def build_hotspot_code(username: str, mac: str, include_mac: bool) -> str | None:
    mac_clean = clean_mac(mac)
    if include_mac and mac_clean:
        return f"HS-{mac_clean}"
    if username:
        return f"HS-{username}"
    return None

def build_dhcp_code(hostname: str, mac: str) -> str:
    mac_clean = clean_mac(mac)
    return f"DHCP-{hostname}" if hostname else f"DHCP-{mac_clean}"

def render_template(template: str, **context) -> str:
    return str(template).format(**context)
