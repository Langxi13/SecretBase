use std::collections::{HashMap, HashSet};

use serde_json::Value;
use uuid::Uuid;

use super::super::{
    normalize,
    types::{
        AiKind, NormalizedAssistantResponse, PendingAiPreview, PendingAiRequest,
        PendingAssistantRequest, PreviewData,
    },
};
use super::{
    actions::{action_domain, parse_action},
    preview::preview_item,
    sanitize::{clean_string_list, clean_text, has_forbidden_key},
};
use crate::mobile::{error::MobileError, models::AiPreview};

const MAX_ASSISTANT_ACTIONS: usize = 100;

pub(crate) fn normalize_response(
    document: &Value,
    pending: &PendingAssistantRequest,
    content: &str,
) -> Result<NormalizedAssistantResponse, MobileError> {
    if pending.mode == "sensitive_create" {
        let parse_pending = PendingAiRequest {
            token: pending.token.clone(),
            kind: AiKind::Parse,
            source_revision: pending.source_revision,
            input_chars: pending.input_chars,
            input_lines: pending.input_lines,
            entry_aliases: HashMap::new(),
        };
        let preview = normalize::normalize_response(document, &parse_pending, content)?;
        let message = format!(
            "已生成 {} 个新条目建议，请逐项核对字段值后再应用。",
            preview.preview.items.len()
        );
        return Ok(NormalizedAssistantResponse {
            message,
            warnings: preview.preview.warnings.clone(),
            preview: Some(preview),
            navigation_entry_id: None,
            navigation_entry_title: None,
        });
    }

    let payload = normalize::extract_chat_payload(content)?;
    if !payload.is_object() || has_forbidden_key(&payload) {
        return Err(MobileError::new(
            "AI_RESPONSE_FORBIDDEN",
            "AI 返回包含禁止的字段值或无效结构",
        ));
    }
    let message = clean_text(payload.get("message"), 4000);
    let message = if message.is_empty() {
        "已生成建议，请检查后再应用。".to_string()
    } else {
        message
    };
    let declared_domain = clean_text(payload.get("domain"), 40);
    let raw_actions = payload
        .get("actions")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    if raw_actions.len() > MAX_ASSISTANT_ACTIONS {
        return Err(MobileError::new(
            "AI_RESPONSE_INVALID",
            "AI 返回的操作数量过多",
        ));
    }

    let entries = entry_titles(document);
    let mut actions = Vec::new();
    let mut items = Vec::new();
    let mut domains = HashSet::new();
    let mut navigation_entry_id = None;
    let mut navigation_entry_title = None;
    for (index, raw) in raw_actions.iter().enumerate() {
        let object = raw
            .as_object()
            .ok_or_else(|| MobileError::new("AI_RESPONSE_INVALID", "AI 返回了无效操作"))?;
        let action_type = clean_text(object.get("type"), 50);
        let domain = action_domain(&action_type).ok_or_else(|| {
            MobileError::new(
                "AI_ACTION_FORBIDDEN",
                format!("AI 返回了不允许的操作：{action_type}"),
            )
        })?;
        domains.insert(domain);
        let mut action = parse_action(index, &action_type, object, pending)?;
        if action_type == "open_entry" {
            if navigation_entry_id.is_none() {
                navigation_entry_id = action.entry_id.clone();
                navigation_entry_title = action
                    .entry_id
                    .as_ref()
                    .and_then(|id| entries.get(id))
                    .cloned();
            }
            continue;
        }
        let item = preview_item(&action, &entries);
        action.id = item.id.clone();
        items.push(item);
        actions.push(action);
    }
    if domains.len() > 1 {
        return Err(MobileError::new(
            "AI_DOMAIN_CONFLICT",
            "AI 将不同类型的管理任务混在同一计划中，已拒绝",
        ));
    }
    let actual_domain = domains.iter().next().copied().unwrap_or("none");
    if !declared_domain.is_empty() && declared_domain != "none" && declared_domain != actual_domain
    {
        return Err(MobileError::new(
            "AI_DOMAIN_CONFLICT",
            "AI 返回的计划类型与操作不一致",
        ));
    }
    let warnings = clean_string_list(payload.get("warnings"), 300);
    let preview = if actions.is_empty() {
        None
    } else {
        let public = AiPreview {
            token: Uuid::new_v4().to_string(),
            kind: "assistant".to_string(),
            title: "AI 管家操作计划".to_string(),
            source_revision: pending.source_revision,
            items,
            warnings: warnings.clone(),
            privacy_note: "计划不包含字段值；所有写入将在本机确认后执行。".to_string(),
        };
        Some(PendingAiPreview {
            preview: public,
            data: PreviewData::Assistant(actions),
            conversation_id: Some(pending.conversation_id.clone()),
        })
    };
    Ok(NormalizedAssistantResponse {
        message,
        preview,
        warnings,
        navigation_entry_id,
        navigation_entry_title,
    })
}

fn entry_titles(document: &Value) -> HashMap<String, String> {
    document
        .get("entries")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|entry| {
            Some((
                entry.get("id")?.as_str()?.to_string(),
                entry.get("title")?.as_str()?.to_string(),
            ))
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;
    use crate::mobile::{
        document,
        models::{EntryDraft, FieldRecord},
    };

    const NOW: &str = "2026-07-14T00:00:00.000000Z";

    fn sample_document() -> Value {
        let mut value = document::new_document(NOW);
        document::save_entry(
            &mut value,
            None,
            &EntryDraft {
                title: "生产控制台".to_string(),
                url: "https://console.example.test/private/path?account=owner".to_string(),
                starred: false,
                tags: vec!["开发".to_string()],
                groups: vec!["服务器".to_string()],
                fields: vec![FieldRecord {
                    name: "登录密码".to_string(),
                    value: "never-send-this-value".to_string(),
                    copyable: true,
                    hidden: true,
                }],
                remarks: "never-send-this-remark".to_string(),
            },
            NOW,
        )
        .unwrap();
        value
    }

    #[test]
    fn mixed_management_domains_are_rejected() {
        let document = sample_document();
        let real_id = document["entries"][0]["id"].as_str().unwrap().to_string();
        let pending = PendingAssistantRequest {
            token: "token".to_string(),
            source_revision: 1,
            conversation_id: "conversation".to_string(),
            user_message: "整理分类".to_string(),
            mode: "assistant".to_string(),
            input_chars: 4,
            input_lines: 1,
            entry_aliases: HashMap::from([("E001".to_string(), real_id)]),
            field_aliases: HashMap::new(),
        };
        let content = json!({
            "choices": [{"message": {"content": json!({
                "message": "建议",
                "domain": "tags",
                "actions": [
                    {"type": "create_tag", "name": "开发"},
                    {"type": "create_group", "name": "工作"}
                ],
                "warnings": []
            }).to_string()}}]
        })
        .to_string();
        let error = normalize_response(&document, &pending, &content)
            .err()
            .unwrap();
        assert!(matches!(
            error,
            MobileError::Failure { ref code, .. } if code == "AI_DOMAIN_CONFLICT"
        ));
    }
}
