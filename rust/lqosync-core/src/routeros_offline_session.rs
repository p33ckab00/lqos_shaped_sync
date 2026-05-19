use crate::protocol::Diagnostic;
use crate::routeros_api_codec::build_routeros_api_sentence_payload;
use crate::routeros_api_frame::codec_routeros_api_frame_payload;
use crate::routeros_api_reply::decode_routeros_api_reply_payload;
use serde_json::{json, Value};

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

fn make_fixture_reply_words(rows: &[Value]) -> (Vec<String>, usize) {
    let mut words = Vec::new();
    let mut dropped = 0usize;
    for row in rows {
        let Some(obj) = row.as_object() else { continue; };
        words.push("!re".to_string());
        for (key, value) in obj {
            if sensitive_key(key) {
                dropped += 1;
                continue;
            }
            let value_text = match value {
                Value::String(s) => s.clone(),
                Value::Number(n) => n.to_string(),
                Value::Bool(b) => b.to_string(),
                Value::Null => String::new(),
                other => other.to_string(),
            };
            words.push(format!("={key}={value_text}"));
        }
    }
    words.push("!done".to_string());
    (words, dropped)
}

fn response_words_from_payload(payload: &Value) -> (Vec<String>, usize, String) {
    if let Some(words) = payload.get("reply_words").and_then(Value::as_array) {
        let mut dropped = 0usize;
        let out = words.iter().filter_map(Value::as_str).filter_map(|word| {
            if word.starts_with('=') {
                let rest = &word[1..];
                if let Some(idx) = rest.find('=') {
                    if sensitive_key(&rest[..idx]) {
                        dropped += 1;
                        return None;
                    }
                }
            }
            Some(word.to_string())
        }).collect::<Vec<_>>();
        return (out, dropped, "reply_words".to_string());
    }
    if let Some(rows) = payload.get("fixture_rows").and_then(Value::as_array) {
        let (words, dropped) = make_fixture_reply_words(rows);
        return (words, dropped, "fixture_rows".to_string());
    }
    (vec!["!done".to_string()], 0, "empty_done".to_string())
}

fn merge_diags(target: &mut Vec<Diagnostic>, mut source: Vec<Diagnostic>) {
    target.append(&mut source);
}

/// Run an offline, end-to-end RouterOS API session pipeline.
///
/// This composes the command sentence codec, binary frame codec, frame decoder,
/// and reply decoder using fixture data only. It does not open sockets, does not
/// authenticate, and does not replace Python RouterOS collectors. It exists so
/// the live read adapter has a deterministic protocol pipeline to plug into.
pub fn run_routeros_offline_session_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let mut warnings: Vec<Diagnostic> = Vec::new();
    let mode = as_str(payload, "mode", "offline_session");
    let adapter = as_str(payload, "adapter", "offline_fixture");
    let execute = as_bool(payload, "execute", false);

    if mode == "live" || adapter == "live" || (execute && adapter != "offline_fixture") {
        errors.push(Diagnostic::error(
            "routeros_offline_session_is_not_live_transport",
            Some("adapter".to_string()),
            "RouterOS offline session pipeline cannot open live sockets or authenticate to MikroTik.",
        ));
    }

    let mut sentence_payload = payload.clone();
    if let Value::Object(ref mut m) = sentence_payload {
        m.insert("mode".to_string(), json!("encode_only"));
        m.insert("execute".to_string(), json!(false));
    }
    let (sentence_result, sentence_errors, sentence_warnings) = build_routeros_api_sentence_payload(&sentence_payload);
    merge_diags(&mut errors, sentence_errors);
    merge_diags(&mut warnings, sentence_warnings);

    let sentence_words = sentence_result
        .get("sentence_words")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let command_words = sentence_words.iter().filter_map(Value::as_str).map(|s| s.to_string()).collect::<Vec<_>>();

    let frame_payload = json!({"direction":"encode", "words": command_words, "mode":"offline", "execute": false});
    let (frame_result, frame_errors, frame_warnings) = codec_routeros_api_frame_payload(&frame_payload);
    merge_diags(&mut errors, frame_errors);
    merge_diags(&mut warnings, frame_warnings);

    let command_frame_hex = frame_result.get("hex").and_then(Value::as_str).unwrap_or("");
    let frame_decode_payload = json!({"direction":"decode", "hex": command_frame_hex, "mode":"offline", "execute": false});
    let (frame_decode_result, frame_decode_errors, frame_decode_warnings) = codec_routeros_api_frame_payload(&frame_decode_payload);
    merge_diags(&mut errors, frame_decode_errors);
    merge_diags(&mut warnings, frame_decode_warnings);

    let (reply_words, dropped_fixture_sensitive_field_count, reply_source) = response_words_from_payload(payload);
    let reply_frame_payload = json!({"direction":"encode", "words": reply_words, "mode":"offline", "execute": false});
    let (reply_frame_result, reply_frame_errors, reply_frame_warnings) = codec_routeros_api_frame_payload(&reply_frame_payload);
    merge_diags(&mut errors, reply_frame_errors);
    merge_diags(&mut warnings, reply_frame_warnings);

    let reply_frame_hex = reply_frame_result.get("hex").and_then(Value::as_str).unwrap_or("");
    let reply_frame_decode_payload = json!({"direction":"decode", "hex": reply_frame_hex, "mode":"offline", "execute": false});
    let (reply_frame_decode_result, reply_frame_decode_errors, reply_frame_decode_warnings) = codec_routeros_api_frame_payload(&reply_frame_decode_payload);
    merge_diags(&mut errors, reply_frame_decode_errors);
    merge_diags(&mut warnings, reply_frame_decode_warnings);

    let decoded_reply_words = reply_frame_decode_result
        .get("words")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let reply_decode_payload = json!({"words": decoded_reply_words, "adapter":"offline_words", "mode":"decode_only", "execute": false});
    let (reply_decode_result, reply_decode_errors, reply_decode_warnings) = decode_routeros_api_reply_payload(&reply_decode_payload);
    merge_diags(&mut errors, reply_decode_errors);
    merge_diags(&mut warnings, reply_decode_warnings);

    if dropped_fixture_sensitive_field_count > 0 {
        warnings.push(Diagnostic::warning(
            "routeros_offline_session_fixture_sensitive_fields_redacted",
            Some("fixture_rows".to_string()),
            "Sensitive fixture fields were removed before building offline RouterOS reply words.",
        ));
    }

    let row_count = reply_decode_result.get("row_count").and_then(Value::as_u64).unwrap_or(0);
    let trap_count = reply_decode_result.get("trap_count").and_then(Value::as_u64).unwrap_or(0);
    let status = if !errors.is_empty() {
        "blocked"
    } else if trap_count > 0 {
        "offline_session_trap"
    } else {
        "offline_session_complete"
    };

    let result = json!({
        "mode": "routeros_offline_session_pipeline",
        "status": status,
        "authority": "none",
        "full_rust_backend": false,
        "live_transport_supported": false,
        "connection_attempt_count": 0,
        "adapter": adapter,
        "reply_source": reply_source,
        "command_word_count": sentence_result.get("word_count"),
        "command_frame_byte_count": frame_result.get("byte_count"),
        "command_frame_roundtrip_word_count": frame_decode_result.get("word_count"),
        "reply_frame_byte_count": reply_frame_result.get("byte_count"),
        "reply_frame_roundtrip_word_count": reply_frame_decode_result.get("word_count"),
        "row_count": row_count,
        "trap_count": trap_count,
        "dropped_sensitive_field_count": dropped_fixture_sensitive_field_count + reply_decode_result.get("dropped_sensitive_field_count").and_then(Value::as_u64).unwrap_or(0) as usize,
        "dropped_sensitive_fields_redacted": true,
        "sentence": sentence_result,
        "command_frame": frame_result,
        "command_frame_decode": frame_decode_result,
        "reply_frame": reply_frame_result,
        "reply_frame_decode": reply_frame_decode_result,
        "reply_decode": reply_decode_result,
        "credential_material": "redacted_or_absent",
        "next_stage": "rust_routeros_readonly_socket_transport",
        "note": "v2.8 runs an offline end-to-end RouterOS protocol session using fixtures only. It does not open sockets or authenticate."
    });

    (result, errors, warnings)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn runs_offline_session_pipeline_without_network() {
        let payload = json!({
            "path":"/ppp/active",
            "fields":["name", "address", "caller-id"],
            "fixture_rows":[{"name":"selftest", "address":"10.0.0.2", "caller-id":"AA:BB:CC:DD:EE:FF"}]
        });
        let (result, errors, _warnings) = run_routeros_offline_session_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("offline_session_complete"));
        assert_eq!(result.get("row_count").and_then(Value::as_u64), Some(1));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
        assert_eq!(result.get("live_transport_supported").and_then(Value::as_bool), Some(false));
    }

    #[test]
    fn blocks_live_offline_session_attempts() {
        let payload = json!({"path":"/ppp/active", "fields":["name"], "adapter":"live", "mode":"live", "execute":true});
        let (result, errors, _warnings) = run_routeros_offline_session_payload(&payload);
        assert!(!errors.is_empty());
        assert_eq!(result.get("status").and_then(Value::as_str), Some("blocked"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
    }

    #[test]
    fn redacts_sensitive_fixture_fields() {
        let payload = json!({
            "path":"/ppp/secret",
            "fields":["name", "profile"],
            "fixture_rows":[{"name":"selftest", "password":"super-secret", "api-key":"abc", "profile":"15M"}]
        });
        let (result, errors, warnings) = run_routeros_offline_session_payload(&payload);
        assert!(errors.is_empty(), "{errors:?}");
        assert!(!warnings.is_empty());
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("super-secret"));
        assert!(!text.contains("api-key"));
        assert!(text.contains("/ppp/secret/print"));
        assert_eq!(result.get("dropped_sensitive_fields_redacted").and_then(Value::as_bool), Some(true));
    }
}
