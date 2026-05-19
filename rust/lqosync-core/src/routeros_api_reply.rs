use crate::protocol::Diagnostic;
use serde_json::{json, Map, Value};

fn as_bool(payload: &Value, key: &str, default: bool) -> bool {
    payload.get(key).and_then(Value::as_bool).unwrap_or(default)
}

fn as_str<'a>(payload: &'a Value, key: &str, default: &'a str) -> &'a str {
    payload.get(key).and_then(Value::as_str).unwrap_or(default)
}

fn sensitive_key(name: &str) -> bool {
    let n = name.to_ascii_lowercase();
    n.contains("password") || n.contains("secret") || n.contains("token") || n.contains("key")
}

fn collect_words(payload: &Value) -> Vec<String> {
    if let Some(words) = payload.get("words").and_then(Value::as_array) {
        return words.iter().filter_map(Value::as_str).map(|s| s.to_string()).collect();
    }
    if let Some(sentences) = payload.get("sentences").and_then(Value::as_array) {
        let mut out = Vec::new();
        for sentence in sentences {
            if let Some(items) = sentence.as_array() {
                for item in items {
                    if let Some(word) = item.as_str() {
                        out.push(word.to_string());
                    }
                }
            }
        }
        return out;
    }
    if let Some(text) = payload.get("raw_text").and_then(Value::as_str) {
        return text.lines().map(str::trim).filter(|s| !s.is_empty()).map(|s| s.to_string()).collect();
    }
    Vec::new()
}

fn flush_sentence(sentence_type: &mut Option<String>, fields: &mut Map<String, Value>, rows: &mut Vec<Value>, traps: &mut Vec<Value>, dones: &mut usize, unknowns: &mut Vec<Value>) {
    let Some(kind) = sentence_type.take() else { return; };
    let current = Value::Object(std::mem::take(fields));
    match kind.as_str() {
        "!re" => rows.push(current),
        "!trap" | "!fatal" => traps.push(current),
        "!done" => *dones += 1,
        other => unknowns.push(json!({"type": other, "fields": current})),
    }
}

fn parse_attribute(word: &str) -> Option<(String, String)> {
    // RouterOS API attribute words normally look like =name=value.
    // Some values may contain '='; only the first key/value split matters.
    if !word.starts_with('=') {
        return None;
    }
    let rest = &word[1..];
    let idx = rest.find('=')?;
    let key = rest[..idx].trim();
    let value = &rest[idx + 1..];
    if key.is_empty() {
        return None;
    }
    Some((key.to_string(), value.to_string()))
}

/// Decode offline RouterOS API reply words into sentences/rows.
///
/// This is an offline parser only. It does not read from a socket and does not
/// authenticate to MikroTik. It accepts already-captured words/fixtures and
/// returns sanitized rows/traps for the future live read adapter.
pub fn decode_routeros_api_reply_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();
    let execute = as_bool(payload, "execute", false);
    let adapter = as_str(payload, "adapter", "offline_words");

    if execute || adapter == "live" || as_str(payload, "mode", "decode_only") == "live" {
        errors.push(Diagnostic::error(
            "routeros_api_reply_decode_is_offline_only",
            Some("execute".to_string()),
            "RouterOS API reply decoder is offline-only in v2.6 and cannot read from live sockets.",
        ));
    }

    let words = collect_words(payload);
    if words.is_empty() {
        errors.push(Diagnostic::error(
            "routeros_api_reply_missing_words",
            Some("words".to_string()),
            "RouterOS API reply decoder requires words, sentences, or raw_text.",
        ));
    }

    let mut rows: Vec<Value> = Vec::new();
    let mut traps: Vec<Value> = Vec::new();
    let mut unknowns: Vec<Value> = Vec::new();
    let mut dones: usize = 0;
    let mut fields = Map::new();
    let mut sentence_type: Option<String> = None;
    let mut dropped_sensitive_field_count = 0usize;

    for word in &words {
        if word.starts_with('!') {
            flush_sentence(&mut sentence_type, &mut fields, &mut rows, &mut traps, &mut dones, &mut unknowns);
            sentence_type = Some(word.to_string());
            continue;
        }
        if sentence_type.is_none() {
            warnings.push(Diagnostic::warning(
                "routeros_api_reply_orphan_word",
                Some("words".to_string()),
                "RouterOS API reply contained an attribute before a sentence marker; it was ignored.",
            ));
            continue;
        }
        if let Some((key, value)) = parse_attribute(word) {
            if sensitive_key(&key) {
                dropped_sensitive_field_count += 1;
                continue;
            }
            fields.insert(key, Value::String(value));
        } else {
            warnings.push(Diagnostic::warning(
                "routeros_api_reply_unparsed_word",
                Some("words".to_string()),
                "RouterOS API reply contained a word that was neither a sentence marker nor key/value attribute.",
            ));
        }
    }
    flush_sentence(&mut sentence_type, &mut fields, &mut rows, &mut traps, &mut dones, &mut unknowns);

    if dropped_sensitive_field_count > 0 {
        warnings.push(Diagnostic::warning(
            "routeros_api_reply_sensitive_fields_redacted",
            Some("words".to_string()),
            "Sensitive RouterOS reply fields were removed from decoded rows/traps.",
        ));
    }

    let trap_count = traps.len();
    let status = if !errors.is_empty() {
        "blocked"
    } else if trap_count > 0 {
        "trap"
    } else if !rows.is_empty() {
        "decoded"
    } else if dones > 0 {
        "done"
    } else {
        "empty"
    };

    let result = json!({
        "mode": "routeros_api_reply_decoder",
        "status": status,
        "authority": "none",
        "full_rust_backend": false,
        "live_transport_supported": false,
        "connection_attempt_count": 0,
        "adapter": adapter,
        "word_count": words.len(),
        "row_count": rows.len(),
        "trap_count": trap_count,
        "done_count": dones,
        "unknown_sentence_count": unknowns.len(),
        "rows": rows,
        "traps": traps,
        "unknown_sentences": unknowns,
        "dropped_sensitive_field_count": dropped_sensitive_field_count,
        "dropped_sensitive_fields_redacted": true,
        "credential_material": "redacted_or_absent",
        "next_stage": "rust_routeros_readonly_socket_transport",
        "note": "v2.6 decodes already-captured RouterOS API reply words offline. It does not open sockets or authenticate."
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn decodes_reply_rows_without_network() {
        let payload = json!({
            "words": ["!re", "=name=selftest", "=address=10.0.0.2", "!done"]
        });
        let (result, errors, warnings) = decode_routeros_api_reply_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert!(warnings.is_empty(), "{warnings:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("decoded"));
        assert_eq!(result.get("row_count").and_then(Value::as_u64), Some(1));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
    }

    #[test]
    fn redacts_sensitive_reply_fields() {
        let payload = json!({
            "words": ["!re", "=name=selftest", "=password=super-secret", "=api-key=abc", "!done"]
        });
        let (result, errors, warnings) = decode_routeros_api_reply_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert!(!warnings.is_empty());
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("super-secret"));
        assert!(!text.contains("api-key"));
        assert_eq!(result.get("dropped_sensitive_field_count").and_then(Value::as_u64), Some(2));
    }

    #[test]
    fn detects_trap_sentence() {
        let payload = json!({"words": ["!trap", "=message=bad command", "!done"]});
        let (result, errors, _warnings) = decode_routeros_api_reply_payload(&payload);
        assert!(errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("trap"));
        assert_eq!(result.get("trap_count").and_then(Value::as_u64), Some(1));
    }

    #[test]
    fn blocks_live_decode() {
        let payload = json!({"adapter":"live", "execute": true, "words": ["!done"]});
        let (result, errors, _warnings) = decode_routeros_api_reply_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
    }
}
