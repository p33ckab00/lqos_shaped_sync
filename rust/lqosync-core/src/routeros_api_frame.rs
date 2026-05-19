use crate::protocol::Diagnostic;
use serde_json::{json, Value};

fn as_bool(payload: &Value, key: &str, default: bool) -> bool {
    payload.get(key).and_then(Value::as_bool).unwrap_or(default)
}

fn as_str<'a>(payload: &'a Value, key: &str, default: &'a str) -> &'a str {
    payload.get(key).and_then(Value::as_str).unwrap_or(default)
}

fn sensitive_attr_word(word: &str) -> bool {
    if !word.starts_with('=') {
        return false;
    }
    let rest = &word[1..];
    let Some(idx) = rest.find('=') else {
        return false;
    };
    let key = rest[..idx].to_ascii_lowercase();
    key.contains("password") || key.contains("secret") || key.contains("token") || key.contains("key")
}

fn collect_words(payload: &Value) -> Vec<String> {
    if let Some(words) = payload.get("words").and_then(Value::as_array) {
        return words.iter().filter_map(Value::as_str).map(|s| s.to_string()).collect();
    }
    if let Some(sentence) = payload.get("sentence_words").and_then(Value::as_array) {
        return sentence.iter().filter_map(Value::as_str).map(|s| s.to_string()).collect();
    }
    if let Some(text) = payload.get("raw_words").and_then(Value::as_str) {
        return text.lines().map(str::trim).filter(|s| !s.is_empty()).map(|s| s.to_string()).collect();
    }
    Vec::new()
}

fn encode_length(len: usize) -> Vec<u8> {
    if len < 0x80 {
        vec![len as u8]
    } else if len < 0x4000 {
        vec![((len >> 8) as u8) | 0x80, (len & 0xff) as u8]
    } else if len < 0x20_0000 {
        vec![((len >> 16) as u8) | 0xC0, ((len >> 8) & 0xff) as u8, (len & 0xff) as u8]
    } else if len < 0x1000_0000 {
        vec![
            ((len >> 24) as u8) | 0xE0,
            ((len >> 16) & 0xff) as u8,
            ((len >> 8) & 0xff) as u8,
            (len & 0xff) as u8,
        ]
    } else {
        vec![
            0xF0,
            ((len >> 24) & 0xff) as u8,
            ((len >> 16) & 0xff) as u8,
            ((len >> 8) & 0xff) as u8,
            (len & 0xff) as u8,
        ]
    }
}

fn decode_length(bytes: &[u8], pos: &mut usize) -> Result<usize, String> {
    if *pos >= bytes.len() {
        return Err("Unexpected end of frame while reading word length.".to_string());
    }
    let first = bytes[*pos];
    *pos += 1;
    if (first & 0x80) == 0x00 {
        Ok(first as usize)
    } else if (first & 0xC0) == 0x80 {
        if *pos >= bytes.len() { return Err("Truncated two-byte RouterOS word length.".to_string()); }
        let len = (((first & !0xC0) as usize) << 8) | bytes[*pos] as usize;
        *pos += 1;
        Ok(len)
    } else if (first & 0xE0) == 0xC0 {
        if *pos + 1 >= bytes.len() { return Err("Truncated three-byte RouterOS word length.".to_string()); }
        let len = (((first & !0xE0) as usize) << 16) | ((bytes[*pos] as usize) << 8) | bytes[*pos + 1] as usize;
        *pos += 2;
        Ok(len)
    } else if (first & 0xF0) == 0xE0 {
        if *pos + 2 >= bytes.len() { return Err("Truncated four-byte RouterOS word length.".to_string()); }
        let len = (((first & !0xF0) as usize) << 24)
            | ((bytes[*pos] as usize) << 16)
            | ((bytes[*pos + 1] as usize) << 8)
            | bytes[*pos + 2] as usize;
        *pos += 3;
        Ok(len)
    } else {
        if *pos + 3 >= bytes.len() { return Err("Truncated five-byte RouterOS word length.".to_string()); }
        let len = ((bytes[*pos] as usize) << 24)
            | ((bytes[*pos + 1] as usize) << 16)
            | ((bytes[*pos + 2] as usize) << 8)
            | bytes[*pos + 3] as usize;
        *pos += 4;
        Ok(len)
    }
}

fn parse_hex_bytes(hex: &str) -> Result<Vec<u8>, String> {
    let compact: String = hex.chars().filter(|c| !c.is_whitespace() && *c != ':' && *c != '-').collect();
    if compact.len() % 2 != 0 {
        return Err("Hex frame must contain an even number of hex digits.".to_string());
    }
    let mut out = Vec::new();
    let chars: Vec<char> = compact.chars().collect();
    for i in (0..chars.len()).step_by(2) {
        let pair = [chars[i], chars[i + 1]].iter().collect::<String>();
        let byte = u8::from_str_radix(&pair, 16).map_err(|_| format!("Invalid hex byte: {pair}"))?;
        out.push(byte);
    }
    Ok(out)
}

fn bytes_to_hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect::<Vec<_>>().join("")
}

fn encode_words(words: &[String]) -> (Vec<u8>, usize) {
    let mut bytes = Vec::new();
    let mut dropped = 0usize;
    for word in words {
        if sensitive_attr_word(word) {
            dropped += 1;
            continue;
        }
        let word_bytes = word.as_bytes();
        bytes.extend(encode_length(word_bytes.len()));
        bytes.extend(word_bytes);
    }
    bytes.push(0);
    (bytes, dropped)
}

fn decode_words(bytes: &[u8]) -> Result<Vec<String>, String> {
    let mut pos = 0usize;
    let mut words = Vec::new();
    while pos < bytes.len() {
        let len = decode_length(bytes, &mut pos)?;
        if len == 0 {
            break;
        }
        if pos + len > bytes.len() {
            return Err("RouterOS frame word length exceeds remaining bytes.".to_string());
        }
        let word = std::str::from_utf8(&bytes[pos..pos + len])
            .map_err(|_| "RouterOS frame contains a non-UTF-8 word.".to_string())?
            .to_string();
        pos += len;
        if !sensitive_attr_word(&word) {
            words.push(word);
        }
    }
    Ok(words)
}

/// Encode/decode offline RouterOS API frame bytes.
///
/// This is an offline frame codec only. It never opens a socket, never
/// authenticates to MikroTik, and never consumes credentials. It exists to
/// exercise the binary RouterOS API framing layer before a future live adapter.
pub fn codec_routeros_api_frame_payload(payload: &Value) -> (Value, Vec<Diagnostic>, Vec<Diagnostic>) {
    let mut errors: Vec<Diagnostic> = Vec::new();
    let warnings: Vec<Diagnostic> = Vec::new();
    let direction = as_str(payload, "direction", "encode");
    let mode = as_str(payload, "mode", "offline");
    let execute = as_bool(payload, "execute", false);

    if execute || mode == "live" || as_str(payload, "adapter", "offline_frame") == "live" {
        errors.push(Diagnostic::error(
            "routeros_api_frame_codec_is_offline_only",
            Some("execute".to_string()),
            "RouterOS API frame codec is offline-only in v2.7 and cannot read or write live sockets.",
        ));
    }

    match direction {
        "encode" => {
            let words = collect_words(payload);
            if words.is_empty() {
                errors.push(Diagnostic::error(
                    "routeros_api_frame_missing_words",
                    Some("words".to_string()),
                    "Frame encoding requires words or sentence_words.",
                ));
            }
            let (bytes, dropped) = encode_words(&words);
            let result = json!({
                "status": if errors.is_empty() { "frame_encoded" } else { "blocked" },
                "direction": "encode",
                "word_count": words.len().saturating_sub(dropped),
                "byte_count": bytes.len(),
                "hex": bytes_to_hex(&bytes),
                "zero_terminated": bytes.last().copied() == Some(0),
                "connection_attempt_count": 0,
                "live_transport_supported": false,
                "dropped_sensitive_field_count": dropped,
                "dropped_sensitive_fields_redacted": true,
            });
            (result, errors, warnings)
        }
        "decode" => {
            let hex = payload.get("hex").or_else(|| payload.get("frame_hex")).and_then(Value::as_str).unwrap_or("");
            if hex.trim().is_empty() {
                errors.push(Diagnostic::error(
                    "routeros_api_frame_missing_hex",
                    Some("hex".to_string()),
                    "Frame decoding requires a hex or frame_hex string.",
                ));
                return (json!({
                    "status": "blocked",
                    "direction": "decode",
                    "word_count": 0,
                    "connection_attempt_count": 0,
                    "live_transport_supported": false
                }), errors, warnings);
            }
            match parse_hex_bytes(hex) {
                Ok(bytes) => match decode_words(&bytes) {
                    Ok(words) => {
                        let result = json!({
                            "status": if errors.is_empty() { "frame_decoded" } else { "blocked" },
                            "direction": "decode",
                            "word_count": words.len(),
                            "words": words,
                            "byte_count": bytes.len(),
                            "zero_terminated": bytes.last().copied() == Some(0),
                            "connection_attempt_count": 0,
                            "live_transport_supported": false,
                        });
                        (result, errors, warnings)
                    }
                    Err(message) => {
                        errors.push(Diagnostic::error("routeros_api_frame_decode_failed", Some("hex".to_string()), message));
                        (json!({
                            "status": "blocked",
                            "direction": "decode",
                            "word_count": 0,
                            "connection_attempt_count": 0,
                            "live_transport_supported": false
                        }), errors, warnings)
                    }
                },
                Err(message) => {
                    errors.push(Diagnostic::error("routeros_api_frame_invalid_hex", Some("hex".to_string()), message));
                    (json!({
                        "status": "blocked",
                        "direction": "decode",
                        "word_count": 0,
                        "connection_attempt_count": 0,
                        "live_transport_supported": false
                    }), errors, warnings)
                }
            }
        }
        other => {
            errors.push(Diagnostic::error(
                "routeros_api_frame_unknown_direction",
                Some("direction".to_string()),
                format!("Unknown RouterOS API frame codec direction: {other}"),
            ));
            (json!({
                "status": "blocked",
                "direction": other,
                "word_count": 0,
                "connection_attempt_count": 0,
                "live_transport_supported": false
            }), errors, warnings)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn encodes_routeros_frame_without_network() {
        let (result, errors, _) = codec_routeros_api_frame_payload(&json!({
            "direction": "encode",
            "words": ["/ppp/active/print", "=.proplist=name,address"]
        }));
        assert!(errors.is_empty(), "errors: {errors:?}");
        assert_eq!(result.get("status").and_then(Value::as_str), Some("frame_encoded"));
        assert_eq!(result.get("connection_attempt_count").and_then(Value::as_u64), Some(0));
        assert_eq!(result.get("zero_terminated").and_then(Value::as_bool), Some(true));
        assert!(result.get("hex").and_then(Value::as_str).unwrap_or("").ends_with("00"));
    }

    #[test]
    fn decodes_routeros_frame_without_network() {
        let (encoded, errors, _) = codec_routeros_api_frame_payload(&json!({
            "direction": "encode",
            "words": ["!re", "=name=test", "!done"]
        }));
        assert!(errors.is_empty());
        let hex = encoded.get("hex").and_then(Value::as_str).unwrap();
        let (decoded, decode_errors, _) = codec_routeros_api_frame_payload(&json!({
            "direction": "decode",
            "hex": hex
        }));
        assert!(decode_errors.is_empty(), "errors: {decode_errors:?}");
        assert_eq!(decoded.get("status").and_then(Value::as_str), Some("frame_decoded"));
        assert_eq!(decoded.get("word_count").and_then(Value::as_u64), Some(3));
    }

    #[test]
    fn redacts_sensitive_attribute_words() {
        let (result, errors, _) = codec_routeros_api_frame_payload(&json!({
            "direction": "encode",
            "words": ["/login", "=name=admin", "=password=supersecret", "=api-key=abc123"]
        }));
        assert!(errors.is_empty());
        let text = serde_json::to_string(&result).unwrap();
        assert!(!text.contains("supersecret"));
        assert!(!text.contains("api-key"));
        assert_eq!(result.get("dropped_sensitive_field_count").and_then(Value::as_u64), Some(2));
    }

    #[test]
    fn blocks_live_frame_codec_attempts() {
        let (_result, errors, _) = codec_routeros_api_frame_payload(&json!({
            "direction": "encode",
            "execute": true,
            "words": ["/ppp/active/print"]
        }));
        assert!(errors.iter().any(|e| e.code == "routeros_api_frame_codec_is_offline_only"));
    }
}
