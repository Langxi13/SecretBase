mod apply;
pub(crate) mod assistant;
pub(crate) mod history;
mod normalize;
mod prompts;
mod types;

use std::collections::{BTreeSet, HashMap};

use chrono::{SecondsFormat, Utc};
use secretbase_vault_core::VaultSession;
use serde_json::{json, Value};
use url::Url;
use uuid::Uuid;

use super::{
    error::MobileError,
    models::{AiHttpHeader, AiHttpRequest, AiPreview, AiRequestPlan, AiSendSummary, AiStatus},
    storage,
};

pub(crate) use apply::apply_preview;
pub(crate) use normalize::normalize_response;
pub(crate) use types::{
    AiConfig, AiKind, PendingAiPreview, PendingAiRequest, PendingAssistantRequest,
};

const SETTINGS_PURPOSE: &str = "mobile-ai-settings";
const MAX_AI_ENTRIES: usize = 100;
const MAX_RESPONSE_BYTES: usize = 4 * 1024 * 1024;

pub fn empty_status() -> AiStatus {
    AiStatus {
        configured: false,
        base_url: String::new(),
        model: String::new(),
        api_key_mask: String::new(),
    }
}

pub fn status(config: Option<&AiConfig>) -> AiStatus {
    let Some(config) = config else {
        return empty_status();
    };
    AiStatus {
        configured: true,
        base_url: config.base_url.clone(),
        model: config.model.clone(),
        api_key_mask: mask_api_key(&config.api_key),
    }
}

pub fn load_config(
    root: &std::path::Path,
    session: &VaultSession,
) -> Result<Option<AiConfig>, MobileError> {
    let Some(content) = storage::read_secure_settings(root)? else {
        return Ok(None);
    };
    let plaintext = session
        .decrypt_scoped_bytes(SETTINGS_PURPOSE, &content)
        .map_err(|_| MobileError::new("AI_SETTINGS_INVALID", "本机 AI 设置无法解密，请重新配置"))?;
    let config: AiConfig = serde_json::from_slice(&plaintext)
        .map_err(|_| MobileError::new("AI_SETTINGS_INVALID", "本机 AI 设置格式无效"))?;
    validate_saved_config(&config)?;
    Ok(Some(config))
}

pub fn save_config(
    root: &std::path::Path,
    session: &VaultSession,
    base_url: &str,
    api_key: &str,
    model: &str,
) -> Result<AiStatus, MobileError> {
    let base_url = normalize_base_url(base_url)?;
    let api_key = api_key.trim();
    let model = model.trim();
    if api_key.is_empty() {
        return Err(MobileError::new("VALIDATION_FAILED", "API Key 不能为空"));
    }
    if api_key.chars().count() > 4096 {
        return Err(MobileError::new("VALIDATION_FAILED", "API Key 长度无效"));
    }
    if model.is_empty() || model.chars().count() > 200 {
        return Err(MobileError::new("VALIDATION_FAILED", "请选择有效模型"));
    }
    let config = AiConfig {
        base_url,
        api_key: api_key.to_string(),
        model: model.to_string(),
        saved_at: Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true),
    };
    let plaintext = serde_json::to_vec(&config)
        .map_err(|_| MobileError::new("AI_SETTINGS_INVALID", "无法序列化 AI 设置"))?;
    let encrypted = session.encrypt_scoped_bytes(SETTINGS_PURPOSE, &plaintext)?;
    storage::persist_secure_settings(root, &encrypted)?;
    Ok(status(Some(&config)))
}

pub fn clear_config(root: &std::path::Path) -> Result<AiStatus, MobileError> {
    storage::delete_secure_settings(root)?;
    Ok(empty_status())
}

pub fn prepare_models_request(
    saved: Option<&AiConfig>,
    base_url: &str,
    api_key: &str,
) -> Result<AiHttpRequest, MobileError> {
    let (base_url, api_key) = resolve_credentials(saved, base_url, api_key)?;
    Ok(AiHttpRequest {
        method: "GET".to_string(),
        url: endpoint(&base_url, "models")?,
        headers: auth_headers(&api_key, false),
        body: String::new(),
        timeout_seconds: 25,
    })
}

pub fn parse_models_response(content: &str) -> Result<Vec<String>, MobileError> {
    validate_response_size(content)?;
    let payload: Value = serde_json::from_str(content)
        .map_err(|_| MobileError::new("AI_RESPONSE_INVALID", "模型列表响应不是有效 JSON"))?;
    let raw = payload
        .get("data")
        .and_then(Value::as_array)
        .ok_or_else(|| MobileError::new("AI_RESPONSE_INVALID", "模型列表响应格式无效"))?;
    let mut models = BTreeSet::new();
    for item in raw {
        let model = item
            .get("id")
            .and_then(Value::as_str)
            .or_else(|| item.as_str())
            .unwrap_or("")
            .trim();
        if !model.is_empty() && model.chars().count() <= 200 {
            models.insert(model.to_string());
        }
    }
    if models.is_empty() {
        return Err(MobileError::new(
            "AI_RESPONSE_INVALID",
            "服务商未返回可用模型",
        ));
    }
    Ok(models.into_iter().collect())
}

pub fn prepare_verify_request(
    saved: Option<&AiConfig>,
    base_url: &str,
    api_key: &str,
    model: &str,
) -> Result<AiHttpRequest, MobileError> {
    let (base_url, api_key) = resolve_credentials(saved, base_url, api_key)?;
    let model = model.trim();
    if model.is_empty() {
        return Err(MobileError::new("VALIDATION_FAILED", "请选择模型"));
    }
    build_chat_request(
        &base_url,
        &api_key,
        model,
        vec![json!({"role": "user", "content": prompts::VERIFY_PROMPT})],
        100,
        60,
    )
}

pub fn verify_response(content: &str) -> Result<(), MobileError> {
    let payload = normalize::extract_chat_payload(content)?;
    if payload.get("ok").and_then(Value::as_bool) == Some(true) {
        return Ok(());
    }
    Err(MobileError::new(
        "AI_VERIFY_FAILED",
        "模型连通测试未返回预期结果",
    ))
}

#[allow(clippy::too_many_arguments)]
pub fn prepare_request(
    document: &Value,
    revision: u64,
    config: &AiConfig,
    kind_raw: &str,
    input: &str,
    entry_id: Option<&str>,
    user_prompt: &str,
) -> Result<(AiRequestPlan, PendingAiRequest), MobileError> {
    let kind = AiKind::parse(kind_raw)
        .ok_or_else(|| MobileError::new("INVALID_AI_KIND", "AI 功能类型无效"))?;
    let input = input.trim();
    let user_prompt = bounded_text(user_prompt, 1000, "用户偏好不能超过 1000 个字符")?;
    if kind != AiKind::Parse
        && (assistant::looks_sensitive(input) || assistant::looks_sensitive(user_prompt))
    {
        return Err(MobileError::new(
            "AI_SENSITIVE_INPUT",
            "普通 AI 工具检测到疑似密码或 Token；请改用文本解析或 AI 新建发送完整原文",
        ));
    }
    let (all_entries, entry_aliases) = aliased_entry_summaries(document, kind == AiKind::Actions)?;
    let all_entry_count = all_entries.len();
    let existing_tags = taxonomy_names(document, "tags_meta", "tags");
    let existing_groups = taxonomy_names(document, "groups_meta", "groups");
    let mut requested_aliases = HashMap::new();

    let (system_prompt, user_payload, max_tokens, timeout_seconds, summary) = match kind {
        AiKind::Parse => {
            if input.is_empty() {
                return Err(MobileError::new(
                    "VALIDATION_FAILED",
                    "请输入需要解析的文本",
                ));
            }
            if input.chars().count() > 6000 {
                return Err(MobileError::new(
                    "AI_INPUT_TOO_LONG",
                    "单次解析最多支持 6000 个字符",
                ));
            }
            (
                prompts::PARSE_PROMPT,
                Value::String(input.to_string()),
                3500,
                150,
                AiSendSummary {
                    title: "发送文本解析请求".to_string(),
                    entry_count: 0,
                    input_chars: count_u32(input.chars().count()),
                    includes_field_values: true,
                    categories: vec!["你输入的完整原文".to_string()],
                    privacy_note: "原文可能包含账号或密码，请确认所选 AI 服务可信。".to_string(),
                },
            )
        }
        AiKind::EntryTags => {
            let entry_id = entry_id
                .filter(|value| !value.trim().is_empty())
                .ok_or_else(|| MobileError::new("VALIDATION_FAILED", "请选择一个条目"))?;
            let entry_alias = entry_aliases
                .iter()
                .find_map(|(alias, id)| (id == entry_id).then_some(alias.as_str()))
                .ok_or_else(|| MobileError::new("ENTRY_NOT_FOUND", "所选条目不存在"))?;
            let entry = all_entries
                .iter()
                .find(|item| item.get("id").and_then(Value::as_str) == Some(entry_alias))
                .cloned()
                .ok_or_else(|| MobileError::new("ENTRY_NOT_FOUND", "所选条目不存在"))?;
            requested_aliases.insert(entry_alias.to_string(), entry_id.to_string());
            (
                prompts::ORGANIZE_PROMPT,
                json!({
                    "mode": "entry_tags",
                    "user_prompt": user_prompt,
                    "existing_tags": existing_tags,
                    "entry": entry,
                    "privacy_note": "不包含任何字段值或备注。"
                }),
                1800,
                150,
                structure_summary("发送单条目标签请求", 1),
            )
        }
        AiKind::Groups => {
            ensure_entry_limit(&all_entries, "密码组整理")?;
            if all_entries.is_empty() {
                return Err(MobileError::new("VALIDATION_FAILED", "当前没有可整理条目"));
            }
            (
                prompts::ORGANIZE_PROMPT,
                json!({
                    "mode": "groups",
                    "user_prompt": user_prompt,
                    "existing_groups": existing_groups,
                    "entries": all_entries,
                    "privacy_note": "不包含任何字段值或备注。"
                }),
                4500,
                180,
                structure_summary("发送密码组整理请求", all_entry_count),
            )
        }
        AiKind::TagGovernance => {
            ensure_entry_limit(&all_entries, "标签治理")?;
            if all_entries.is_empty() {
                return Err(MobileError::new("VALIDATION_FAILED", "当前没有可分析条目"));
            }
            let tag_entities = taxonomy_entities(document, "tags_meta", "tags");
            (
                prompts::TAG_GOVERNANCE_PROMPT,
                json!({
                    "user_prompt": user_prompt,
                    "existing_tags": tag_entities,
                    "existing_groups": existing_groups,
                    "entries": all_entries,
                    "privacy_note": "不包含任何字段值或备注。"
                }),
                4500,
                180,
                structure_summary("发送标签治理请求", all_entry_count),
            )
        }
        AiKind::Actions => {
            if input.is_empty() {
                return Err(MobileError::new("VALIDATION_FAILED", "请输入操作指令"));
            }
            if input.chars().count() > 2000 {
                return Err(MobileError::new(
                    "AI_INPUT_TOO_LONG",
                    "操作指令不能超过 2000 个字符",
                ));
            }
            ensure_entry_limit(&all_entries, "操作计划")?;
            let mut summary = structure_summary("发送操作计划请求", all_entry_count);
            summary.input_chars = count_u32(input.chars().count());
            summary.categories.push("你的操作指令".to_string());
            (
                prompts::ACTIONS_PROMPT,
                json!({
                    "instruction": input,
                    "user_prompt": user_prompt,
                    "existing_tags": existing_tags,
                    "existing_groups": existing_groups,
                    "entries": all_entries,
                    "allowed_actions": ["create_group", "update_group", "create_entry", "create_entry_from_field", "update_entry"],
                    "privacy_note": "不包含任何字段值或备注；字段拆分在本机复制真实值。"
                }),
                5500,
                180,
                summary,
            )
        }
    };

    if kind != AiKind::Parse && kind != AiKind::EntryTags {
        requested_aliases = entry_aliases;
    }

    let request = build_chat_request(
        &config.base_url,
        &config.api_key,
        &config.model,
        vec![
            json!({"role": "system", "content": system_prompt}),
            json!({
                "role": "user",
                "content": if user_payload.is_string() {
                    user_payload.as_str().unwrap_or("").to_string()
                } else {
                    serde_json::to_string(&user_payload).unwrap_or_else(|_| "{}".to_string())
                }
            }),
        ],
        max_tokens,
        timeout_seconds,
    )?;
    let token = Uuid::new_v4().to_string();
    let pending = PendingAiRequest {
        token: token.clone(),
        kind,
        source_revision: revision,
        input_chars: count_u32(input.chars().count()),
        input_lines: count_u32(input.lines().count()),
        entry_aliases: requested_aliases,
    };
    Ok((
        AiRequestPlan {
            token,
            request,
            summary,
        },
        pending,
    ))
}

pub fn preview_from_response(
    document: &Value,
    pending: &PendingAiRequest,
    content: &str,
) -> Result<PendingAiPreview, MobileError> {
    validate_response_size(content)?;
    normalize_response(document, pending, content)
}

pub fn public_preview(pending: &PendingAiPreview) -> AiPreview {
    pending.preview.clone()
}

fn validate_saved_config(config: &AiConfig) -> Result<(), MobileError> {
    normalize_base_url(&config.base_url)?;
    if config.api_key.trim().is_empty() || config.model.trim().is_empty() {
        return Err(MobileError::new(
            "AI_SETTINGS_INVALID",
            "本机 AI 设置不完整",
        ));
    }
    Ok(())
}

fn resolve_credentials(
    saved: Option<&AiConfig>,
    base_url: &str,
    api_key: &str,
) -> Result<(String, String), MobileError> {
    let base_url = normalize_base_url(base_url)?;
    let api_key = if api_key.trim().is_empty() {
        saved
            .filter(|config| config.base_url == base_url)
            .map(|config| config.api_key.trim())
            .unwrap_or("")
    } else {
        api_key.trim()
    };
    if api_key.is_empty() {
        return Err(MobileError::new("VALIDATION_FAILED", "API Key 不能为空"));
    }
    Ok((base_url, api_key.to_string()))
}

fn normalize_base_url(value: &str) -> Result<String, MobileError> {
    let mut value = value.trim().trim_end_matches('/').to_string();
    for suffix in ["/chat/completions", "/models"] {
        if value.ends_with(suffix) {
            value.truncate(value.len() - suffix.len());
            value = value.trim_end_matches('/').to_string();
        }
    }
    let parsed = Url::parse(&value)
        .map_err(|_| MobileError::new("VALIDATION_FAILED", "Base URL 格式无效"))?;
    if parsed.scheme() != "https" {
        return Err(MobileError::new(
            "AI_HTTPS_REQUIRED",
            "移动端 AI 只允许使用 HTTPS 地址",
        ));
    }
    if parsed.host_str().is_none()
        || !parsed.username().is_empty()
        || parsed.password().is_some()
        || parsed.query().is_some()
        || parsed.fragment().is_some()
    {
        return Err(MobileError::new("VALIDATION_FAILED", "Base URL 格式无效"));
    }
    Ok(value)
}

fn endpoint(base_url: &str, suffix: &str) -> Result<String, MobileError> {
    let url = format!("{}/{suffix}", base_url.trim_end_matches('/'));
    let parsed =
        Url::parse(&url).map_err(|_| MobileError::new("VALIDATION_FAILED", "AI 服务地址无效"))?;
    if parsed.scheme() != "https" {
        return Err(MobileError::new(
            "AI_HTTPS_REQUIRED",
            "移动端 AI 只允许使用 HTTPS 地址",
        ));
    }
    Ok(url)
}

fn auth_headers(api_key: &str, json_content: bool) -> Vec<AiHttpHeader> {
    let mut headers = vec![AiHttpHeader {
        name: "Authorization".to_string(),
        value: format!("Bearer {api_key}"),
    }];
    if json_content {
        headers.push(AiHttpHeader {
            name: "Content-Type".to_string(),
            value: "application/json".to_string(),
        });
    }
    headers
}

fn build_chat_request(
    base_url: &str,
    api_key: &str,
    model: &str,
    messages: Vec<Value>,
    max_tokens: u32,
    timeout_seconds: u32,
) -> Result<AiHttpRequest, MobileError> {
    let mut payload = json!({
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens
    });
    if supports_response_format(base_url) {
        payload
            .as_object_mut()
            .expect("chat payload is always an object")
            .insert(
                "response_format".to_string(),
                json!({"type": "json_object"}),
            );
    }
    let body = serde_json::to_string(&payload)
        .map_err(|_| MobileError::new("AI_REQUEST_INVALID", "无法构造 AI 请求"))?;
    Ok(AiHttpRequest {
        method: "POST".to_string(),
        url: endpoint(base_url, "chat/completions")?,
        headers: auth_headers(api_key, true),
        body,
        timeout_seconds,
    })
}

fn supports_response_format(base_url: &str) -> bool {
    Url::parse(base_url)
        .ok()
        .and_then(|url| url.host_str().map(str::to_ascii_lowercase))
        .is_some_and(|host| {
            matches!(
                host.as_str(),
                "api.openai.com" | "api.deepseek.com" | "generativelanguage.googleapis.com"
            )
        })
}

fn structure_summary(title: &str, entry_count: usize) -> AiSendSummary {
    AiSendSummary {
        title: title.to_string(),
        entry_count: count_u32(entry_count),
        input_chars: 0,
        includes_field_values: false,
        categories: vec![
            "条目名称与网址 hostname".to_string(),
            "字段名称与隐藏/复制属性".to_string(),
            "已有标签与密码组".to_string(),
        ],
        privacy_note: "不会发送字段值、主密码或备注。".to_string(),
    }
}

fn aliased_entry_summaries(
    document: &Value,
    include_field_indices: bool,
) -> Result<(Vec<Value>, HashMap<String, String>), MobileError> {
    let entries = document
        .get("entries")
        .and_then(Value::as_array)
        .ok_or_else(|| MobileError::new("INVALID_PAYLOAD", "Vault 条目数据无效"))?;
    let mut result = Vec::new();
    let mut aliases = HashMap::new();
    for entry in entries {
        let Some(item) = entry.as_object() else {
            continue;
        };
        let Some(id) = item.get("id").and_then(Value::as_str) else {
            continue;
        };
        let Some(title) = item.get("title").and_then(Value::as_str) else {
            continue;
        };
        let fields = item
            .get("fields")
            .and_then(Value::as_array)
            .map(|fields| {
                fields
                    .iter()
                    .enumerate()
                    .filter_map(|(index, field)| {
                        let field = field.as_object()?;
                        let name = field.get("name")?.as_str()?;
                        let copyable = field
                            .get("copyable")
                            .and_then(Value::as_bool)
                            .unwrap_or(false);
                        let hidden = field
                            .get("hidden")
                            .and_then(Value::as_bool)
                            .unwrap_or(copyable);
                        Some(if include_field_indices {
                            json!({
                                "index": index,
                                "name": name,
                                "copyable": copyable,
                                "hidden": hidden
                            })
                        } else {
                            json!({
                                "name": name,
                                "copyable": copyable,
                                "hidden": hidden
                            })
                        })
                    })
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default();
        let hostname = item
            .get("url")
            .and_then(Value::as_str)
            .and_then(|value| Url::parse(value).ok())
            .and_then(|value| value.host_str().map(str::to_string))
            .unwrap_or_default();
        let alias = format!("E{:03}", result.len() + 1);
        aliases.insert(alias.clone(), id.to_string());
        result.push(json!({
            "id": alias,
            "title": title,
            "hostname": hostname,
            "tags": string_values(item.get("tags")),
            "groups": string_values(item.get("groups")),
            "fields": fields,
            "starred": item.get("starred").and_then(Value::as_bool).unwrap_or(false)
        }));
    }
    Ok((result, aliases))
}

fn taxonomy_names(document: &Value, meta_key: &str, field_key: &str) -> Vec<String> {
    let mut names = BTreeSet::new();
    if let Some(meta) = document.get(meta_key).and_then(Value::as_object) {
        names.extend(meta.keys().cloned());
    }
    if let Some(entries) = document.get("entries").and_then(Value::as_array) {
        for entry in entries {
            names.extend(string_values(entry.get(field_key)));
        }
    }
    names.into_iter().collect()
}

fn taxonomy_entities(document: &Value, meta_key: &str, field_key: &str) -> Vec<Value> {
    let names = taxonomy_names(document, meta_key, field_key);
    let meta = document.get(meta_key).and_then(Value::as_object);
    names
        .into_iter()
        .map(|name| {
            let item = meta.and_then(|items| items.get(&name)).and_then(Value::as_object);
            json!({
                "name": name,
                "description": item.and_then(|value| value.get("description")).and_then(Value::as_str).unwrap_or(""),
                "color": item.and_then(|value| value.get("color")).and_then(Value::as_str).unwrap_or("")
            })
        })
        .collect()
}

fn string_values(value: Option<&Value>) -> Vec<String> {
    value
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(str::to_string)
                .collect()
        })
        .unwrap_or_default()
}

fn ensure_entry_limit(entries: &[Value], label: &str) -> Result<(), MobileError> {
    if entries.len() > MAX_AI_ENTRIES {
        return Err(MobileError::new(
            "AI_SCOPE_TOO_LARGE",
            format!("{label}单次最多支持 {MAX_AI_ENTRIES} 个条目"),
        ));
    }
    Ok(())
}

fn bounded_text<'a>(value: &'a str, maximum: usize, message: &str) -> Result<&'a str, MobileError> {
    let value = value.trim();
    if value.chars().count() > maximum {
        return Err(MobileError::new("AI_INPUT_TOO_LONG", message));
    }
    Ok(value)
}

fn count_u32(value: usize) -> u32 {
    u32::try_from(value).unwrap_or(u32::MAX)
}

fn mask_api_key(value: &str) -> String {
    let value = value.trim();
    if value.is_empty() {
        String::new()
    } else if value.chars().count() <= 8 {
        "****".to_string()
    } else {
        let prefix: String = value.chars().take(3).collect();
        let suffix: String = value
            .chars()
            .rev()
            .take(4)
            .collect::<String>()
            .chars()
            .rev()
            .collect();
        format!("{prefix}...{suffix}")
    }
}

fn validate_response_size(content: &str) -> Result<(), MobileError> {
    if content.len() > MAX_RESPONSE_BYTES {
        return Err(MobileError::new(
            "AI_RESPONSE_TOO_LARGE",
            "AI 返回内容过大，请缩小处理范围",
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use secretbase_vault_core::{VaultDocument, VaultSession};

    use super::*;
    use crate::mobile::{
        document,
        models::{EntryDraft, FieldRecord},
    };

    const NOW: &str = "2026-07-12T00:00:00.000000Z";

    fn sample_document() -> Value {
        let mut value = document::new_document(NOW);
        document::save_entry(
            &mut value,
            None,
            &EntryDraft {
                title: "示例云服务器".to_string(),
                url: "https://console.example.test".to_string(),
                starred: false,
                tags: vec!["开发".to_string()],
                groups: Vec::new(),
                fields: vec![
                    FieldRecord {
                        name: "服务器 IP".to_string(),
                        value: "192.0.2.10".to_string(),
                        copyable: true,
                        hidden: false,
                    },
                    FieldRecord {
                        name: "密码".to_string(),
                        value: "secret".to_string(),
                        copyable: true,
                        hidden: true,
                    },
                ],
                remarks: "本机私有备注".to_string(),
            },
            NOW,
        )
        .unwrap();
        value
    }

    fn pending(kind: AiKind, document: &Value) -> PendingAiRequest {
        let entry_aliases = document["entries"]
            .as_array()
            .unwrap()
            .iter()
            .enumerate()
            .filter_map(|(index, entry)| {
                entry["id"]
                    .as_str()
                    .map(|id| (format!("E{:03}", index + 1), id.to_string()))
            })
            .collect();
        PendingAiRequest {
            token: "request-token".to_string(),
            kind,
            source_revision: 8,
            input_chars: 100,
            input_lines: 4,
            entry_aliases,
        }
    }

    fn provider_response(payload: Value) -> String {
        serde_json::json!({
            "choices": [{"message": {"content": payload.to_string()}}]
        })
        .to_string()
    }

    #[test]
    fn group_organize_uses_local_fallback_when_model_returns_no_suggestions() {
        let document = sample_document();
        let preview = normalize_response(
            &document,
            &pending(AiKind::Groups, &document),
            &provider_response(serde_json::json!({"suggestions": []})),
        )
        .unwrap();

        assert_eq!(preview.preview.items.len(), 1);
        assert_eq!(preview.preview.items[0].title, "示例云服务器");
        assert!(preview.preview.items[0]
            .details
            .iter()
            .any(|detail| detail.label == "加入密码组" && detail.value.contains("开发资源")));
    }

    #[test]
    fn incomplete_field_rename_is_dropped_without_blocking_other_action_changes() {
        let mut document = sample_document();
        let response = provider_response(serde_json::json!({
            "actions": [{
                "type": "update_entry",
                "entry_id": "E001",
                "url": "https://attacker.example.test",
                "remarks": "不应覆盖",
                "field_name_new": "新字段名",
                "add_groups": ["服务器"],
                "reason": "整理服务器条目"
            }]
        }));
        let preview =
            normalize_response(&document, &pending(AiKind::Actions, &document), &response).unwrap();

        assert!(preview
            .preview
            .warnings
            .iter()
            .any(|warning| warning.contains("不完整的字段重命名")));
        let selected = vec![preview.preview.items[0].id.clone()];
        let message = apply_preview(&mut document, &preview, &selected, NOW).unwrap();
        assert_eq!(message, "已应用 1 项 AI 操作计划");
        assert_eq!(
            document["entries"][0]["groups"],
            serde_json::json!(["服务器"])
        );
        assert_eq!(document["entries"][0]["fields"][0]["name"], "服务器 IP");
        assert_eq!(
            document["entries"][0]["url"],
            "https://console.example.test"
        );
        assert_eq!(document["entries"][0]["remarks"], "本机私有备注");
    }

    #[test]
    fn parse_preview_keeps_sensitive_values_maskable_and_applies_selected_only() {
        let mut document = document::new_document(NOW);
        let response = provider_response(serde_json::json!({
            "entries": [
                {
                    "title": "邮箱",
                    "url": "",
                    "fields": [{"name": "密码", "value": "mail-secret", "copyable": true, "hidden": true}],
                    "tags": ["邮箱"],
                    "remarks": ""
                },
                {
                    "title": "服务器",
                    "url": "",
                    "fields": [{"name": "IP", "value": "192.0.2.1", "copyable": true, "hidden": false}],
                    "tags": ["服务器"],
                    "remarks": ""
                }
            ]
        }));
        let preview =
            normalize_response(&document, &pending(AiKind::Parse, &document), &response).unwrap();
        assert!(preview.preview.items[0]
            .details
            .iter()
            .any(|detail| detail.value == "mail-secret" && detail.sensitive));

        let selected = vec![preview.preview.items[1].id.clone()];
        apply_preview(&mut document, &preview, &selected, NOW).unwrap();
        assert_eq!(document["entries"].as_array().unwrap().len(), 1);
        assert_eq!(document["entries"][0]["title"], "服务器");
    }

    #[test]
    fn ai_settings_are_encrypted_and_bound_to_the_vault_session() {
        let directory = tempfile::tempdir().unwrap();
        let document = VaultDocument::from_value(document::new_document(NOW)).unwrap();
        let session = VaultSession::create("test-password", document).unwrap();
        let status = save_config(
            directory.path(),
            &session,
            "https://api.example.test/v1",
            "sk-test-secret-value",
            "test-model",
        )
        .unwrap();
        assert!(status.configured);
        assert_eq!(status.api_key_mask, "sk-...alue");
        let encrypted = storage::read_secure_settings(directory.path())
            .unwrap()
            .unwrap();
        assert!(!String::from_utf8_lossy(&encrypted).contains("sk-test-secret-value"));
        let loaded = load_config(directory.path(), &session).unwrap().unwrap();
        assert_eq!(loaded.model, "test-model");
        assert_eq!(loaded.api_key, "sk-test-secret-value");
    }

    #[test]
    fn cleartext_ai_urls_are_rejected() {
        let error = prepare_models_request(None, "http://example.test/v1", "test-key")
            .err()
            .unwrap();
        assert!(matches!(
            error,
            MobileError::Failure { ref code, .. } if code == "AI_HTTPS_REQUIRED"
        ));
    }

    #[test]
    fn provider_requests_only_use_supported_response_format() {
        let openai = build_chat_request(
            "https://api.openai.com/v1",
            "test-key",
            "test-model",
            vec![json!({"role": "user", "content": "test"})],
            100,
            30,
        )
        .unwrap();
        let openrouter = build_chat_request(
            "https://openrouter.ai/api/v1",
            "test-key",
            "test-model",
            vec![json!({"role": "user", "content": "test"})],
            100,
            30,
        )
        .unwrap();

        assert!(openai.body.contains("response_format"));
        assert!(!openrouter.body.contains("response_format"));
    }

    #[test]
    fn professional_tools_reject_secrets_outside_text_parse_mode() {
        let document = sample_document();
        let config = AiConfig {
            base_url: "https://api.example.test/v1".to_string(),
            api_key: "test-key".to_string(),
            model: "test-model".to_string(),
            saved_at: NOW.to_string(),
        };
        let error = prepare_request(
            &document,
            1,
            &config,
            "actions",
            "password: must-not-send",
            None,
            "",
        )
        .err()
        .unwrap();
        assert!(matches!(
            error,
            MobileError::Failure { ref code, .. } if code == "AI_SENSITIVE_INPUT"
        ));
    }
}
