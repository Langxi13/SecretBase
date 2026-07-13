use std::collections::HashSet;

use serde_json::Value;

use super::super::types::ParsedField;
use crate::mobile::error::MobileError;

const FORBIDDEN_KEYS: [&str; 5] = ["value", "field_value", "new_value", "old_value", "values"];

pub(super) fn has_forbidden_key(value: &Value) -> bool {
    match value {
        Value::Object(object) => object.iter().any(|(key, value)| {
            FORBIDDEN_KEYS.contains(&key.trim().to_ascii_lowercase().as_str())
                || has_forbidden_key(value)
        }),
        Value::Array(values) => values.iter().any(has_forbidden_key),
        _ => false,
    }
}

pub(super) fn normalize_empty_fields(value: Option<&Value>) -> Vec<ParsedField> {
    let mut names = HashSet::new();
    value
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|field| {
            let object = field.as_object()?;
            let name = clean_name(object.get("name")?.as_str()?);
            if name.is_empty() || !names.insert(name.clone()) {
                return None;
            }
            let copyable = object
                .get("copyable")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            Some(ParsedField {
                name,
                value: String::new(),
                copyable,
                hidden: object
                    .get("hidden")
                    .and_then(Value::as_bool)
                    .unwrap_or(copyable),
            })
        })
        .take(30)
        .collect()
}

pub(super) fn clean_text(value: Option<&Value>, maximum: usize) -> String {
    value
        .and_then(Value::as_str)
        .unwrap_or("")
        .replace(['\0', '\r'], "")
        .trim()
        .chars()
        .take(maximum)
        .collect()
}

pub(super) fn optional_text(value: Option<&Value>, maximum: usize) -> Option<String> {
    let value = clean_text(value, maximum);
    (!value.is_empty()).then_some(value)
}

fn clean_name(value: &str) -> String {
    value
        .replace(['\0', '\r', '\n'], " ")
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .chars()
        .take(50)
        .collect()
}

pub(super) fn optional_name(value: Option<&Value>) -> Option<String> {
    value
        .and_then(Value::as_str)
        .map(clean_name)
        .filter(|value| !value.is_empty())
}

pub(super) fn clean_names(value: Option<&Value>) -> Vec<String> {
    let mut result = Vec::new();
    for name in clean_string_list(value, 100) {
        let name = clean_name(&name);
        if !name.is_empty() && !result.contains(&name) {
            result.push(name);
        }
        if result.len() >= 50 {
            break;
        }
    }
    result
}

pub(super) fn clean_string_list(value: Option<&Value>, maximum: usize) -> Vec<String> {
    let values = match value {
        Some(Value::Array(values)) => values.iter().filter_map(Value::as_str).collect(),
        Some(Value::String(value)) => vec![value.as_str()],
        _ => Vec::new(),
    };
    values
        .into_iter()
        .map(|value| value.trim().chars().take(maximum).collect::<String>())
        .filter(|value| !value.is_empty())
        .collect()
}

pub(super) fn clean_color(value: Option<&Value>) -> Option<String> {
    let color = clean_text(value, 20).to_ascii_lowercase();
    (color.len() == 7
        && color.starts_with('#')
        && color
            .chars()
            .skip(1)
            .all(|character| character.is_ascii_hexdigit()))
    .then_some(color)
}

pub(super) fn require_name<'a>(
    value: Option<&'a str>,
    message: &str,
) -> Result<&'a str, MobileError> {
    value
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| MobileError::new("AI_RESPONSE_INVALID", message))
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    #[test]
    fn forbidden_value_key_is_rejected_recursively() {
        assert!(has_forbidden_key(&json!({
            "message": "x",
            "actions": [{"type": "rename_entry", "value": "secret"}]
        })));
    }
}
