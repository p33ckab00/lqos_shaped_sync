use crate::protocol::Diagnostic;
use serde_json::{json, Value};

fn as_str<'a>(value: Option<&'a Value>, default: &'a str) -> &'a str {
    value.and_then(Value::as_str).unwrap_or(default)
}


fn sensitive_field(name: &str) -> bool {
    let n = name.to_ascii_lowercase();
    n.contains("password") || n.contains("secret") || n.contains("token") || n.contains("key")
}

fn normalize_print_command(path: &str) -> String {
    let p = path.trim();
    if p.is_empty() {
        return String::new();
    }
    if p.ends_with("/print") {
        p.to_string()
    } else {
        format!("{}/print", p.trim_end_matches('/'))
    }
}

/// RouterOS API word-length encoding, returned as bytes for offline inspection.
/// This is the variable-length length prefix used by the RouterOS API protocol.
pub fn encode_word_length(mut len: usize) -> Vec<u8> {
    if len < 0x80 {
        vec![len as u8]
    } else if len < 0x4000 {
        len |= 0x8000;
        vec![(len >> 8) as u8, len as u8]
    } else if len < 0x20_0000 {
        len |= 0xC0_0000;
        vec![(len >> 16) as u8, (len >> 8) as u8, len as u8]
    } else if len < 0x1000_0000 {
        len |= 0xE000_0000;
        vec![(len >> 24) as u8, (len >> 16) as u8, (len >> 8) as u8, len as u8]
    } else {
        vec![0xF0, (len >> 24) as u8, (len >> 16) as u8, (len >> 8) as u8, len as u8]
    }
}

fn hex_bytes(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{:02x}", b)).collect::<Vec<_>>().join("")
}

fn command_from_payload(payload: &Value) -> (String, Vec<String>, Vec<String>) {
    let command = payload.get("command").and_then(Value::as_object);
    let path = as_str(payload.get("path").or_else(|| command.and_then(|m| m.get("path"))), "");

    let fields_value = payload.get("fields").or_else(|| command.and_then(|m| m.get("fields")));
    let fields = fields_value
        .and_then(Value::as_array)
        .map(|items| items.iter().filter_map(Value::as_str).map(|s| s.to_string()).collect::<Vec<_>>())
        .unwrap_or_default();

    let queries_value = payload.get("queries").or_else(|| payload.get("query"));
    let queries = queries_value
        .and_then(Value::as_array)
        .map(|items| items.iter().filter_map(Value::as_str).map(|s| s.to_string()).collect::<Vec<_>>())
        .unwrap_or_default();

    (path.to_string(), fields, queries)
}

/// Build an offline RouterOS API sentence from a planned read command.
///
/// This is not a network adapter. It only prepares command words and length
/// prefixes so the next transport phase has deterministic, tested protocol
/// encoding. Sensitive field names are rejected from `.proplist`.
pub fn build_routeros_api_sentence_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();
    let (path, fields, queries) = command_from_payload(payload);
    let execute = payload.get("execute").and_then(Value::as_bool).unwrap_or(false);
    let mode = as_str(payload.get("mode"), "encode_only");

    let print_command = normalize_print_command(&path);
    if print_command.is_empty() {
        errors.push(Diagnostic::error(
            "routeros_api_sentence_missing_path",
            Some("path".to_string()),
            "RouterOS API sentence requires a command path such as /ppp/active.",
        ));
    }

    let mut clean_fields: Vec<String> = Vec::new();
    let mut dropped_fields: Vec<String> = Vec::new();
    for field in fields {
        let f = field.trim();
        if f.is_empty() {
            continue;
        }
        if sensitive_field(f) {
            dropped_fields.push(f.to_string());
            continue;
        }
        if !clean_fields.iter().any(|x| x == f) {
            clean_fields.push(f.to_string());
        }
    }
    if !dropped_fields.is_empty() {
        warnings.push(Diagnostic::warning(
            "routeros_api_sentence_sensitive_fields_dropped",
            Some("fields".to_string()),
            "Sensitive field names were removed from the RouterOS API sentence proplist.",
        ));
    }

    let mut words: Vec<String> = Vec::new();
    if !print_command.is_empty() {
        words.push(print_command.clone());
    }
    if !clean_fields.is_empty() {
        words.push(format!("=.proplist={}", clean_fields.join(",")));
    }
    for q in queries {
        let item = q.trim();
        if item.is_empty() {
            continue;
        }
        if item.to_ascii_lowercase().contains("password") || item.to_ascii_lowercase().contains("secret") {
            warnings.push(Diagnostic::warning(
                "routeros_api_sentence_sensitive_query_dropped",
                Some("queries".to_string()),
                "A sensitive query word was dropped from the offline RouterOS API sentence.",
            ));
            continue;
        }
        words.push(item.to_string());
    }

    if execute || mode == "live" {
        errors.push(Diagnostic::error(
            "routeros_api_sentence_is_offline_only",
            Some("execute".to_string()),
            "RouterOS API sentence codec is offline-only in v2.5 and cannot execute live reads.",
        ));
    }

    let length_prefixes: Vec<Value> = words.iter().map(|word| {
        let encoded = encode_word_length(word.as_bytes().len());
        json!({
            "word": word,
            "length": word.as_bytes().len(),
            "length_prefix_hex": hex_bytes(&encoded),
            "encoded_length_bytes": encoded.len()
        })
    }).collect();
    let total_payload_bytes: usize = words.iter().map(|w| encode_word_length(w.as_bytes().len()).len() + w.as_bytes().len()).sum::<usize>() + 1;

    let result = json!({
        "mode": "routeros_api_sentence_codec",
        "status": if errors.is_empty() { "encoded" } else { "blocked" },
        "authority": "none",
        "full_rust_backend": false,
        "live_transport_supported": false,
        "connection_attempt_count": 0,
        "execute_requested": execute,
        "path": path,
        "command_word": print_command,
        "sentence_words": words,
        "length_prefixes": length_prefixes,
        "word_count": length_prefixes.len(),
        "total_payload_bytes_with_zero_terminator": total_payload_bytes,
        "dropped_sensitive_field_count": dropped_fields.len(),
        "dropped_sensitive_fields_redacted": true,
        "credential_material": "redacted_or_absent",
        "next_stage": "rust_routeros_readonly_socket_transport",
        "note": "v2.5 encodes RouterOS API sentences offline only. It does not open sockets or send credentials."
    });
    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn encodes_short_word_length() {
        assert_eq!(encode_word_length(0x7f), vec![0x7f]);
    }

    #[test]
    fn encodes_medium_word_length() {
        assert_eq!(encode_word_length(0x80), vec![0x80, 0x80]);
    }

    #[test]
    fn builds_print_sentence_without_network() {
        let payload = json!({"path":"/ppp/active","fields":["name","address","caller-id"]});
        let (result, errors, warnings) = build_routeros_api_sentence_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert!(warnings.is_empty(), "{warnings:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("encoded"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
        let words = result.get("sentence_words").and_then(Value::as_array).unwrap();
        assert_eq!(words[0].as_str(), Some("/ppp/active/print"));
        assert!(words.iter().any(|v| v.as_str() == Some("=.proplist=name,address,caller-id")));
    }

    #[test]
    fn drops_sensitive_proplist_fields() {
        let payload = json!({"path":"/ppp/secret","fields":["name","password","profile","api-key"]});
        let (result, errors, warnings) = build_routeros_api_sentence_payload(&payload);
        assert!(errors.is_empty());
        assert!(!warnings.is_empty());
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("=.proplist=name,password"));
        assert!(!text.contains("api-key"));
        assert!(!text.contains("\"password\""));
        assert!(text.contains("/ppp/secret/print"));
        assert_eq!(result.get("dropped_sensitive_field_count").and_then(Value::as_u64), Some(2));
        assert_eq!(result.get("dropped_sensitive_fields_redacted").and_then(Value::as_bool), Some(true));
    }

    #[test]
    fn blocks_live_execution() {
        let payload = json!({"path":"/ppp/active","fields":["name"],"mode":"live","execute":true});
        let (result, errors, _warnings) = build_routeros_api_sentence_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
    }
}
