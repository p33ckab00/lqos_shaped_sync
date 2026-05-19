use crate::protocol::Diagnostic;
use serde_json::{json, Value};
use std::net::{TcpStream, ToSocketAddrs};
use std::time::{Duration, Instant};

fn config<'a>(payload: &'a Value) -> &'a Value {
    payload.get("config").unwrap_or(payload)
}

fn rust_core<'a>(payload: &'a Value) -> &'a Value {
    config(payload).get("rust_core").unwrap_or(&Value::Null)
}

fn bool_value(v: Option<&Value>, default: bool) -> bool {
    v.and_then(Value::as_bool).unwrap_or(default)
}

fn string_value(v: Option<&Value>, default: &str) -> String {
    v.and_then(Value::as_str).unwrap_or(default).to_string()
}

fn u16_value(v: Option<&Value>, default: u16) -> u16 {
    v.and_then(Value::as_u64)
        .and_then(|n| u16::try_from(n).ok())
        .unwrap_or(default)
}

fn timeout_seconds(payload: &Value) -> u64 {
    let from_payload = payload.get("timeout_seconds").and_then(Value::as_u64);
    let from_config = rust_core(payload)
        .get("routeros_tcp_connect_timeout_seconds")
        .or_else(|| rust_core(payload).get("routeros_live_read_timeout_seconds"))
        .and_then(Value::as_u64);
    from_payload.or(from_config).unwrap_or(3).clamp(1, 10)
}

fn selected_router(payload: &Value) -> Value {
    if let Some(router) = payload.get("router").filter(|v| v.is_object()) {
        return router.clone();
    }
    let router_name = payload.get("router").and_then(Value::as_str).unwrap_or("");
    let routers = config(payload).get("routers").and_then(Value::as_array);
    if let Some(routers) = routers {
        for router in routers {
            if !router.get("enabled").and_then(Value::as_bool).unwrap_or(true) {
                continue;
            }
            if router_name.is_empty() || router.get("name").and_then(Value::as_str).unwrap_or("") == router_name {
                return router.clone();
            }
        }
    }
    json!({})
}

fn connection_allowed(payload: &Value) -> bool {
    let rc = rust_core(payload);
    bool_value(payload.get("allow_tcp_connect"), false)
        || bool_value(rc.get("allow_rust_routeros_tcp_connect"), false)
        || bool_value(rc.get("routeros_tcp_connect_pilot"), false)
}

fn authority(payload: &Value) -> String {
    string_value(
        payload
            .get("routeros_transport_authority")
            .or_else(|| rust_core(payload).get("routeros_transport_authority")),
        "plan_only",
    )
}

fn wants_execute(payload: &Value) -> bool {
    bool_value(payload.get("execute"), false)
        || matches!(payload.get("mode").and_then(Value::as_str).unwrap_or("rehearsal"), "tcp_connect" | "live" | "execute")
}

pub fn run_routeros_tcp_connectivity_pilot_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();
    let router = selected_router(payload);
    let router_name = router.get("name").and_then(Value::as_str).unwrap_or("unknown");
    let address = payload
        .get("address")
        .and_then(Value::as_str)
        .or_else(|| router.get("address").and_then(Value::as_str))
        .unwrap_or("");
    let port = u16_value(payload.get("port").or_else(|| router.get("port")), 8728);
    let execute = wants_execute(payload);
    let allow_connect = connection_allowed(payload);
    let transport_authority = authority(payload);
    let timeout = timeout_seconds(payload);
    let mut connection_attempt_count = 0u64;
    let mut elapsed_ms: Option<f64> = None;
    let mut connected = false;
    let status: String;

    if address.trim().is_empty() {
        errors.push(Diagnostic::error(
            "routeros_tcp_address_missing",
            Some("router.address".to_string()),
            "RouterOS TCP connectivity pilot requires a router address.",
        ));
    }

    if port == 0 {
        errors.push(Diagnostic::error(
            "routeros_tcp_port_invalid",
            Some("router.port".to_string()),
            "RouterOS TCP connectivity pilot requires a non-zero TCP port.",
        ));
    }

    if execute && !allow_connect {
        errors.push(Diagnostic::error(
            "routeros_tcp_connect_not_allowed",
            Some("rust_core.allow_rust_routeros_tcp_connect".to_string()),
            "Rust RouterOS TCP connectivity pilot was requested, but TCP connect authority is disabled.",
        ));
    }

    if execute && transport_authority != "tcp_connect_pilot" && transport_authority != "live_read_pilot" {
        errors.push(Diagnostic::error(
            "routeros_tcp_authority_not_enabled",
            Some("rust_core.routeros_transport_authority".to_string()),
            "Rust RouterOS TCP connectivity pilot requires routeros_transport_authority=tcp_connect_pilot or live_read_pilot.",
        ));
    }

    if !execute {
        status = if errors.is_empty() { "tcp_connect_rehearsal".to_string() } else { "blocked".to_string() };
    } else if !errors.is_empty() {
        status = "blocked".to_string();
    } else {
        let start = Instant::now();
        connection_attempt_count = 1;
        let target = format!("{address}:{port}");
        match target.to_socket_addrs() {
            Ok(mut addrs) => {
                if let Some(sock_addr) = addrs.next() {
                    match TcpStream::connect_timeout(&sock_addr, Duration::from_secs(timeout)) {
                        Ok(stream) => {
                            connected = true;
                            status = "tcp_connect_success".to_string();
                            drop(stream);
                        }
                        Err(e) => {
                            status = "tcp_connect_failed".to_string();
                            warnings.push(Diagnostic::warning(
                                "routeros_tcp_connect_failed",
                                Some("router.address".to_string()),
                                format!("TCP connect attempt did not succeed: {e}"),
                            ));
                        }
                    }
                } else {
                    status = "tcp_connect_failed".to_string();
                    errors.push(Diagnostic::error(
                        "routeros_tcp_address_unresolved",
                        Some("router.address".to_string()),
                        "Router address did not resolve to any socket address.",
                    ));
                }
            }
            Err(e) => {
                status = "tcp_connect_failed".to_string();
                errors.push(Diagnostic::error(
                    "routeros_tcp_address_resolution_failed",
                    Some("router.address".to_string()),
                    format!("Router address resolution failed: {e}"),
                ));
            }
        }
        elapsed_ms = Some(start.elapsed().as_secs_f64() * 1000.0);
    }

    let result = json!({
        "mode": if execute { "tcp_connect_pilot" } else { "rehearsal" },
        "status": status,
        "router": router_name,
        "address_redacted": if address.is_empty() { "missing" } else { "configured" },
        "port": port,
        "timeout_seconds": timeout,
        "routeros_transport_authority": transport_authority,
        "allow_tcp_connect": allow_connect,
        "connection_attempt_count": connection_attempt_count,
        "connected": connected,
        "elapsed_ms": elapsed_ms,
        "credential_material": "not_requested",
        "authentication_attempt_count": 0,
        "api_sentence_write_count": 0,
        "api_reply_read_count": 0,
        "full_rust_backend": false,
        "live_api_transport_supported": false,
        "note": "This operation optionally tests TCP reachability only. It does not authenticate, send RouterOS API words, read API replies, or replace Python collectors."
    });
    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;
    use std::thread;

    #[test]
    fn rehearses_without_connection_attempt() {
        let payload = json!({
            "router": {"name": "R1", "address": "127.0.0.1", "port": 8728},
            "execute": false
        });
        let (result, errors, _warnings) = run_routeros_tcp_connectivity_pilot_payload(&payload);
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("tcp_connect_rehearsal"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
        assert_eq!(result.get("authentication_attempt_count").and_then(Value::as_u64), Some(0));
    }

    #[test]
    fn blocks_execute_without_authority() {
        let payload = json!({
            "router": {"name": "R1", "address": "127.0.0.1", "port": 8728},
            "execute": true,
            "config": {"rust_core": {"allow_rust_routeros_tcp_connect": false, "routeros_transport_authority": "plan_only"}}
        });
        let (result, errors, _warnings) = run_routeros_tcp_connectivity_pilot_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
    }

    #[test]
    fn can_connect_to_local_listener_when_explicitly_allowed() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind local listener");
        listener.set_nonblocking(true).expect("set nonblocking");
        let port = listener.local_addr().unwrap().port();
        let handle = thread::spawn(move || {
            let deadline = Instant::now() + Duration::from_secs(2);
            while Instant::now() < deadline {
                match listener.accept() {
                    Ok((_stream, _addr)) => return true,
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        thread::sleep(Duration::from_millis(10));
                    }
                    Err(_) => return false,
                }
            }
            false
        });
        let payload = json!({
            "router": {"name": "R1", "address": "127.0.0.1", "port": port},
            "execute": true,
            "config": {"rust_core": {"allow_rust_routeros_tcp_connect": true, "routeros_transport_authority": "tcp_connect_pilot"}}
        });
        let (result, errors, _warnings) = run_routeros_tcp_connectivity_pilot_payload(&payload);
        let accepted = handle.join().unwrap_or(false);
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("tcp_connect_success"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(1));
        assert_eq!(result.get("authentication_attempt_count").and_then(Value::as_u64), Some(0));
        assert!(result.get("connected").and_then(Value::as_bool).unwrap_or(false));
        assert!(accepted);
    }
}
