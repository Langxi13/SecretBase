use serde_json::Value;

pub(super) fn outbound_metadata_looks_sensitive(
    entries: &[Value],
    tags: &[Value],
    groups: &[Value],
) -> bool {
    entries
        .iter()
        .chain(tags)
        .chain(groups)
        .flat_map(metadata_strings)
        .any(|value| looks_sensitive(&value))
}

fn metadata_strings(value: &Value) -> Vec<String> {
    match value {
        Value::String(value) => vec![value.clone()],
        Value::Array(values) => values.iter().flat_map(metadata_strings).collect(),
        Value::Object(object) => object
            .iter()
            .filter(|(key, _)| !matches!(key.as_str(), "id" | "ref"))
            .flat_map(|(_, value)| metadata_strings(value))
            .collect(),
        _ => Vec::new(),
    }
}

pub(in crate::mobile::ai) fn looks_sensitive(value: &str) -> bool {
    let lower = value.to_ascii_lowercase();
    let labeled = [
        "password:",
        "password=",
        "passwd:",
        "passwd=",
        "token:",
        "token=",
        "secret:",
        "secret=",
        "api_key:",
        "api_key=",
        "api key:",
    ];
    if labeled.iter().any(|pattern| lower.contains(pattern))
        || lower.contains("-----begin private key-----")
        || lower.contains("-----begin rsa private key-----")
    {
        return true;
    }
    value.split_whitespace().any(|part| {
        let compact = part.trim_matches(|character: char| !character.is_ascii_alphanumeric());
        compact.len() >= 32
            && compact.chars().all(|character| {
                character.is_ascii_alphanumeric()
                    || matches!(character, '_' | '-' | '+' | '/' | '=')
            })
            && compact.chars().any(|character| character.is_ascii_digit())
            && compact
                .chars()
                .any(|character| character.is_ascii_alphabetic())
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sensitive_detector_blocks_labeled_secrets() {
        assert!(looks_sensitive("password: correct-horse-battery-staple"));
        assert!(looks_sensitive("token=abcdefghijklmnopqrstuvwxyz123456"));
        assert!(!looks_sensitive("请整理开发相关条目的标签"));
    }
}
