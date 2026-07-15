use std::collections::{HashMap, HashSet};

use serde_json::Value;
use uuid::Uuid;

use crate::mobile::{
    error::MobileError,
    models::{AiPreview, AiPreviewDetail, AiPreviewItem},
};

use super::types::{
    ActionPlan, AiKind, OrganizeSuggestion, ParsedEntry, ParsedField, PendingAiPreview,
    PendingAiRequest, PreviewData, TagGovernanceSuggestion,
};

#[derive(Debug, Clone)]
struct EntryInfo {
    title: String,
    groups: Vec<String>,
    searchable: String,
}

pub fn extract_chat_payload(content: &str) -> Result<Value, MobileError> {
    let root: Value = serde_json::from_str(content)
        .map_err(|_| MobileError::new("AI_RESPONSE_INVALID", "AI 响应不是有效 JSON"))?;
    if let Some(choices) = root.get("choices").and_then(Value::as_array) {
        let content = choices
            .first()
            .and_then(|choice| choice.get("message"))
            .and_then(|message| message.get("content"))
            .ok_or_else(|| MobileError::new("AI_RESPONSE_INVALID", "AI 响应缺少内容"))?;
        let text = if let Some(text) = content.as_str() {
            text.to_string()
        } else if let Some(parts) = content.as_array() {
            parts
                .iter()
                .filter_map(|part| {
                    part.get("text")
                        .and_then(Value::as_str)
                        .or_else(|| part.as_str())
                })
                .collect::<Vec<_>>()
                .join("")
        } else {
            return Err(MobileError::new(
                "AI_RESPONSE_INVALID",
                "AI 响应内容格式无效",
            ));
        };
        return extract_first_json(&text);
    }
    if let Some(text) = root.get("output_text").and_then(Value::as_str) {
        return extract_first_json(text);
    }
    Ok(root)
}

pub fn normalize_response(
    document: &Value,
    pending: &PendingAiRequest,
    content: &str,
) -> Result<PendingAiPreview, MobileError> {
    let payload = extract_chat_payload(content)?;
    let entries = entry_info(document);
    let allowed: HashSet<&str> = pending.entry_aliases.values().map(String::as_str).collect();
    let (items, warnings, data, privacy_note) = match pending.kind {
        AiKind::Parse => normalize_parse(&payload, pending)?,
        AiKind::EntryTags | AiKind::Groups => normalize_organize(
            &payload,
            pending.kind,
            &entries,
            &allowed,
            &pending.entry_aliases,
            document,
        )?,
        AiKind::TagGovernance => normalize_governance(&payload, &entries, &pending.entry_aliases)?,
        AiKind::Actions => normalize_actions(&payload, &entries, &pending.entry_aliases)?,
    };
    let preview = AiPreview {
        token: Uuid::new_v4().to_string(),
        kind: pending.kind.as_str().to_string(),
        title: pending.kind.title().to_string(),
        source_revision: pending.source_revision,
        items,
        warnings,
        privacy_note,
    };
    Ok(PendingAiPreview {
        preview,
        data,
        conversation_id: None,
    })
}

fn normalize_parse(
    payload: &Value,
    pending: &PendingAiRequest,
) -> Result<(Vec<AiPreviewItem>, Vec<String>, PreviewData, String), MobileError> {
    let raw_entries = if let Some(items) = payload.as_array() {
        items.clone()
    } else if let Some(object) = payload.as_object() {
        [
            "entries",
            "parsed_entries",
            "items",
            "accounts",
            "records",
            "data",
        ]
        .iter()
        .find_map(|key| object.get(*key).and_then(Value::as_array).cloned())
        .unwrap_or_else(|| vec![payload.clone()])
    } else {
        Vec::new()
    };
    let mut entries = Vec::new();
    let mut warnings = Vec::new();
    for (index, raw) in raw_entries.into_iter().take(20).enumerate() {
        let Some(object) = raw.as_object() else {
            continue;
        };
        let title = clean_text(
            object
                .get("title")
                .or_else(|| object.get("name"))
                .or_else(|| object.get("site"))
                .or_else(|| object.get("service")),
            200,
        );
        let title = if title.is_empty() {
            warnings.push(format!("第 {} 条缺少标题，已使用临时名称", index + 1));
            format!("AI 解析条目 {}", index + 1)
        } else {
            title
        };
        let mut url = clean_text(
            object
                .get("url")
                .or_else(|| object.get("link"))
                .or_else(|| object.get("website")),
            2000,
        );
        if !url.is_empty() && !url.starts_with("https://") && !url.starts_with("http://") {
            url.clear();
        }
        let fields = normalize_fields(
            object
                .get("fields")
                .or_else(|| object.get("field_items"))
                .or_else(|| object.get("credentials")),
            true,
            &mut warnings,
        );
        if fields.is_empty() {
            warnings.push(format!("“{title}”没有识别到自定义字段"));
        }
        let tags = clean_names(
            object
                .get("tags")
                .or_else(|| object.get("labels"))
                .or_else(|| object.get("categories")),
        );
        let groups = clean_names(
            object
                .get("groups")
                .or_else(|| object.get("password_groups"))
                .or_else(|| object.get("folders")),
        );
        let remarks = clean_text(
            object
                .get("remarks")
                .or_else(|| object.get("note"))
                .or_else(|| object.get("notes"))
                .or_else(|| object.get("comment")),
            2000,
        );
        entries.push(ParsedEntry {
            id: format!("parse-{index}"),
            title,
            url,
            fields,
            tags,
            groups,
            remarks,
        });
    }
    if entries.is_empty() {
        return Err(MobileError::new("AI_RESPONSE_INVALID", "AI 未返回可用条目"));
    }
    if pending.input_chars > 3000 {
        warnings.push("输入较长，请重点检查是否存在误拆分或遗漏".to_string());
    }
    if pending.input_lines > 60 {
        warnings.push("输入行数较多，建议逐条核对解析结果".to_string());
    }
    if entries.len() > 8 {
        warnings.push("解析结果较多，请逐条确认后再应用".to_string());
    }
    let items = entries
        .iter()
        .map(|entry| {
            let mut details = Vec::new();
            if !entry.url.is_empty() {
                details.push(detail("网址", &entry.url, false, "info"));
            }
            details.extend(
                entry
                    .fields
                    .iter()
                    .map(|field| detail(&field.name, &field.value, field.hidden, "add")),
            );
            if !entry.tags.is_empty() {
                details.push(detail("标签", &entry.tags.join("、"), false, "add"));
            }
            if !entry.groups.is_empty() {
                details.push(detail("密码组", &entry.groups.join("、"), false, "add"));
            }
            if !entry.remarks.is_empty() {
                details.push(detail("备注", &entry.remarks, false, "info"));
            }
            AiPreviewItem {
                id: entry.id.clone(),
                title: entry.title.clone(),
                subtitle: format!("{} 个字段", entry.fields.len()),
                details,
            }
        })
        .collect();
    Ok((
        items,
        dedupe(warnings),
        PreviewData::Parsed(entries),
        "解析请求包含用户输入的原文；应用前请检查所有字段值。".to_string(),
    ))
}

fn normalize_organize(
    payload: &Value,
    kind: AiKind,
    entries: &HashMap<String, EntryInfo>,
    allowed: &HashSet<&str>,
    aliases: &HashMap<String, String>,
    document: &Value,
) -> Result<(Vec<AiPreviewItem>, Vec<String>, PreviewData, String), MobileError> {
    let raw = payload_items(payload, "suggestions");
    let mut suggestions = Vec::new();
    let mut seen = HashSet::new();
    for item in raw {
        let Some(object) = item.as_object() else {
            continue;
        };
        let entry_ref = clean_text(object.get("entry_id").or_else(|| object.get("id")), 20);
        let Some(entry_id) = aliases.get(&entry_ref).cloned() else {
            continue;
        };
        if !seen.insert(entry_id.clone()) {
            continue;
        }
        let descriptions = object
            .get("group_descriptions")
            .and_then(Value::as_object)
            .map(|items| {
                items
                    .iter()
                    .filter_map(|(name, description)| {
                        let name = clean_name(name);
                        if name.is_empty() {
                            None
                        } else {
                            Some((name, clean_text(Some(description), 300)))
                        }
                    })
                    .collect()
            })
            .unwrap_or_default();
        let mut suggestion = OrganizeSuggestion {
            id: format!("organize-{}", suggestions.len()),
            entry_id,
            add_tags: clean_names(object.get("add_tags").or_else(|| object.get("tags_to_add"))),
            remove_tags: clean_names(
                object
                    .get("remove_tags")
                    .or_else(|| object.get("tags_to_remove")),
            ),
            add_groups: clean_names(
                object
                    .get("add_groups")
                    .or_else(|| object.get("groups_to_add")),
            ),
            remove_groups: clean_names(
                object
                    .get("remove_groups")
                    .or_else(|| object.get("groups_to_remove")),
            ),
            group_descriptions: descriptions,
            reason: clean_text(
                object.get("reason").or_else(|| object.get("explanation")),
                500,
            ),
        };
        if kind == AiKind::EntryTags {
            suggestion.add_groups.clear();
            suggestion.remove_groups.clear();
            suggestion.group_descriptions.clear();
        } else {
            suggestion.add_tags.clear();
            suggestion.remove_tags.clear();
        }
        suggestions.push(suggestion);
    }

    if kind == AiKind::Groups {
        enrich_group_suggestions(&mut suggestions, entries, allowed, document);
    }
    suggestions.retain(|suggestion| {
        !suggestion.add_tags.is_empty()
            || !suggestion.remove_tags.is_empty()
            || !suggestion.add_groups.is_empty()
            || !suggestion.remove_groups.is_empty()
    });
    let mut warnings = payload_warnings(payload);
    if suggestions.is_empty() {
        warnings.push(if kind == AiKind::Groups {
            "没有发现需要调整的密码组".to_string()
        } else {
            "没有发现需要调整的标签".to_string()
        });
    }
    let items = suggestions
        .iter()
        .filter_map(|suggestion| {
            let entry = entries.get(&suggestion.entry_id)?;
            let mut details = Vec::new();
            push_names(&mut details, "新增标签", &suggestion.add_tags, "add");
            push_names(&mut details, "移除标签", &suggestion.remove_tags, "remove");
            push_names(&mut details, "加入密码组", &suggestion.add_groups, "add");
            push_names(
                &mut details,
                "移出密码组",
                &suggestion.remove_groups,
                "remove",
            );
            if !suggestion.reason.is_empty() {
                details.push(detail("原因", &suggestion.reason, false, "info"));
            }
            Some(AiPreviewItem {
                id: suggestion.id.clone(),
                title: entry.title.clone(),
                subtitle: if kind == AiKind::Groups {
                    "密码组调整".to_string()
                } else {
                    "标签调整".to_string()
                },
                details,
            })
        })
        .collect();
    Ok((
        items,
        dedupe(warnings),
        PreviewData::Organize(suggestions),
        "本次请求未发送字段值、主密码或备注。".to_string(),
    ))
}

fn normalize_governance(
    payload: &Value,
    entries: &HashMap<String, EntryInfo>,
    aliases: &HashMap<String, String>,
) -> Result<(Vec<AiPreviewItem>, Vec<String>, PreviewData, String), MobileError> {
    let allowed_actions = [
        "create_tag",
        "update_tag",
        "delete_tag",
        "merge_tags",
        "replace_tag",
        "assign_tag",
    ];
    let mut suggestions = Vec::new();
    for item in payload_items(payload, "suggestions") {
        let Some(object) = item.as_object() else {
            continue;
        };
        let action = clean_text(object.get("action"), 30);
        if !allowed_actions.contains(&action.as_str()) {
            continue;
        }
        let entry_ids = clean_names_unbounded(
            object.get("entry_ids").or_else(|| object.get("entries")),
            100,
        )
        .into_iter()
        .filter_map(|entry_ref| aliases.get(&entry_ref).cloned())
        .collect();
        let color = clean_text(object.get("color"), 20);
        suggestions.push(TagGovernanceSuggestion {
            id: format!("tag-action-{}", suggestions.len()),
            action,
            tag: optional_name(
                object
                    .get("tag")
                    .or_else(|| object.get("old_tag"))
                    .or_else(|| object.get("old_name")),
            ),
            new_tag: optional_name(object.get("new_tag").or_else(|| object.get("new_name"))),
            source_tags: clean_names(object.get("source_tags").or_else(|| object.get("sources"))),
            target_tag: optional_name(object.get("target_tag").or_else(|| object.get("target"))),
            entry_ids,
            description: clean_text(object.get("description"), 300),
            color: if valid_color(&color) {
                Some(color.to_lowercase())
            } else {
                None
            },
            reason: clean_text(
                object.get("reason").or_else(|| object.get("explanation")),
                500,
            ),
        });
    }
    let items = suggestions
        .iter()
        .map(|suggestion| {
            let mut details = governance_details(suggestion, entries);
            if !suggestion.reason.is_empty() {
                details.push(detail("原因", &suggestion.reason, false, "info"));
            }
            AiPreviewItem {
                id: suggestion.id.clone(),
                title: governance_title(suggestion),
                subtitle: action_label(&suggestion.action).to_string(),
                details,
            }
        })
        .collect();
    let mut warnings = payload_warnings(payload);
    if suggestions.is_empty() {
        warnings.push("没有发现需要治理的标签".to_string());
    }
    Ok((
        items,
        dedupe(warnings),
        PreviewData::Governance(suggestions),
        "本次请求未发送字段值、主密码或备注。".to_string(),
    ))
}

fn normalize_actions(
    payload: &Value,
    entries: &HashMap<String, EntryInfo>,
    aliases: &HashMap<String, String>,
) -> Result<(Vec<AiPreviewItem>, Vec<String>, PreviewData, String), MobileError> {
    let allowed_types = [
        "create_group",
        "update_group",
        "create_entry",
        "create_entry_from_field",
        "update_entry",
    ];
    let mut plans = Vec::new();
    let mut warnings = payload_warnings(payload);
    for item in payload_items(payload, "actions") {
        let Some(object) = item.as_object() else {
            continue;
        };
        let action_type = clean_text(object.get("type").or_else(|| object.get("action")), 50);
        if !allowed_types.contains(&action_type.as_str()) {
            warnings.push(format!("已忽略不支持的操作：{action_type}"));
            continue;
        }
        let entry_ref = optional_text(object.get("entry_id").or_else(|| object.get("id")), 20);
        let source_entry_ref = optional_text(
            object
                .get("source_entry_id")
                .or_else(|| object.get("source_id")),
            20,
        );
        let entry_id = entry_ref
            .as_deref()
            .and_then(|entry_ref| aliases.get(entry_ref))
            .cloned();
        let source_entry_id = source_entry_ref
            .as_deref()
            .and_then(|entry_ref| aliases.get(entry_ref))
            .cloned();
        if action_type == "update_entry" && entry_id.is_none() {
            warnings.push("已忽略引用未知条目的更新操作".to_string());
            continue;
        }
        if action_type == "create_entry_from_field" && source_entry_id.is_none() {
            warnings.push("已忽略引用未知来源条目的字段拆分操作".to_string());
            continue;
        }
        let field_index = object
            .get("field_index")
            .and_then(|value| {
                value
                    .as_u64()
                    .or_else(|| value.as_str().and_then(|text| text.parse().ok()))
            })
            .and_then(|value| usize::try_from(value).ok());
        let mut field_name = optional_text(object.get("field_name"), 100);
        let mut field_name_new = optional_text(
            object
                .get("field_name_new")
                .or_else(|| object.get("new_field_name")),
            100,
        );
        let has_field_context =
            field_index.is_some() || field_name.is_some() || field_name_new.is_some();
        let complete_rename =
            field_index.is_some() && field_name.is_some() && field_name_new.is_some();
        let field_index = if has_field_context && !complete_rename {
            warnings.push("已忽略不完整的字段重命名信息".to_string());
            field_name = None;
            field_name_new = None;
            None
        } else {
            field_index
        };
        let mut field_warnings = Vec::new();
        let fields = normalize_fields(object.get("fields"), false, &mut field_warnings);
        warnings.extend(field_warnings);
        let updates_existing_entry = action_type == "update_entry";
        let mut url = if updates_existing_entry {
            None
        } else {
            optional_text(object.get("url"), 2000)
        };
        if url
            .as_deref()
            .is_some_and(|value| !value.starts_with("https://") && !value.starts_with("http://"))
        {
            url = None;
        }
        plans.push(ActionPlan {
            id: format!("action-{}", plans.len()),
            action_type,
            group: optional_name(object.get("group").or_else(|| object.get("name"))),
            group_new: optional_name(
                object
                    .get("group_new")
                    .or_else(|| object.get("new_group"))
                    .or_else(|| object.get("group_name_new")),
            ),
            description: clean_text(object.get("description"), 300),
            title: optional_text(object.get("title"), 200),
            url,
            tags: clean_names(object.get("tags")),
            groups: clean_names(object.get("groups")),
            remarks: if updates_existing_entry {
                String::new()
            } else {
                clean_text(object.get("remarks").or_else(|| object.get("note")), 2000)
            },
            fields,
            entry_id,
            source_entry_id,
            field_index,
            field_name,
            field_name_new,
            add_tags: clean_names(object.get("add_tags").or_else(|| object.get("tags_to_add"))),
            remove_tags: clean_names(
                object
                    .get("remove_tags")
                    .or_else(|| object.get("tags_to_remove")),
            ),
            add_groups: clean_names(
                object
                    .get("add_groups")
                    .or_else(|| object.get("groups_to_add")),
            ),
            remove_groups: clean_names(
                object
                    .get("remove_groups")
                    .or_else(|| object.get("groups_to_remove")),
            ),
            reason: clean_text(
                object.get("reason").or_else(|| object.get("explanation")),
                500,
            ),
        });
    }
    let items = plans
        .iter()
        .map(|plan| action_preview_item(plan, entries))
        .collect();
    if plans.is_empty() {
        warnings.push("AI 未生成可执行的操作计划".to_string());
    }
    Ok((
        items,
        dedupe(warnings),
        PreviewData::Actions(plans),
        "本次请求未发送字段值、主密码或备注；字段拆分仅在本机复制真实值。".to_string(),
    ))
}

fn action_preview_item(plan: &ActionPlan, entries: &HashMap<String, EntryInfo>) -> AiPreviewItem {
    let mut details = Vec::new();
    let (title, subtitle) = match plan.action_type.as_str() {
        "create_group" => (
            format!("新建密码组：{}", plan.group.as_deref().unwrap_or("未命名")),
            "创建密码组".to_string(),
        ),
        "update_group" => (
            format!("更新密码组：{}", plan.group.as_deref().unwrap_or("未命名")),
            "更新密码组".to_string(),
        ),
        "create_entry" => (
            format!("新建条目：{}", plan.title.as_deref().unwrap_or("未命名")),
            "创建空字段条目".to_string(),
        ),
        "create_entry_from_field" => {
            let source = plan
                .source_entry_id
                .as_ref()
                .and_then(|id| entries.get(id))
                .map(|entry| entry.title.as_str())
                .unwrap_or("未知条目");
            (
                format!("从“{source}”拆分新条目"),
                plan.title.clone().unwrap_or_else(|| "字段拆分".to_string()),
            )
        }
        "update_entry" => {
            let source = plan
                .entry_id
                .as_ref()
                .and_then(|id| entries.get(id))
                .map(|entry| entry.title.as_str())
                .unwrap_or("未知条目");
            (format!("更新条目：{source}"), "修改条目结构".to_string())
        }
        _ => ("未知操作".to_string(), String::new()),
    };
    if let Some(value) = &plan.group_new {
        details.push(detail("新密码组名称", value, false, "update"));
    }
    if !plan.description.is_empty() {
        details.push(detail("简介", &plan.description, false, "update"));
    }
    if let Some(value) = &plan.title {
        details.push(detail("条目名称", value, false, "update"));
    }
    if let Some(value) = &plan.url {
        details.push(detail("网址", value, false, "update"));
    }
    push_names(&mut details, "标签", &plan.tags, "add");
    push_names(&mut details, "密码组", &plan.groups, "add");
    push_names(&mut details, "新增标签", &plan.add_tags, "add");
    push_names(&mut details, "移除标签", &plan.remove_tags, "remove");
    push_names(&mut details, "加入密码组", &plan.add_groups, "add");
    push_names(&mut details, "移出密码组", &plan.remove_groups, "remove");
    if let (Some(old), Some(new)) = (&plan.field_name, &plan.field_name_new) {
        details.push(detail(
            "字段重命名",
            &format!("{old} → {new}"),
            false,
            "update",
        ));
    }
    if !plan.fields.is_empty() {
        details.push(detail(
            "空字段",
            &plan
                .fields
                .iter()
                .map(|field| field.name.as_str())
                .collect::<Vec<_>>()
                .join("、"),
            false,
            "add",
        ));
    }
    if !plan.remarks.is_empty() {
        details.push(detail("备注", &plan.remarks, false, "update"));
    }
    if !plan.reason.is_empty() {
        details.push(detail("原因", &plan.reason, false, "info"));
    }
    AiPreviewItem {
        id: plan.id.clone(),
        title,
        subtitle,
        details,
    }
}

fn normalize_fields(
    value: Option<&Value>,
    preserve_values: bool,
    warnings: &mut Vec<String>,
) -> Vec<ParsedField> {
    let raw = if let Some(object) = value.and_then(Value::as_object) {
        object
            .iter()
            .map(|(name, value)| {
                serde_json::json!({
                    "name": name,
                    "value": value,
                    "copyable": true,
                    "hidden": true
                })
            })
            .collect()
    } else {
        value.and_then(Value::as_array).cloned().unwrap_or_default()
    };
    let mut fields = Vec::new();
    let mut names = HashSet::new();
    for raw in raw {
        let Some(object) = raw.as_object() else {
            continue;
        };
        let name = clean_text(
            object
                .get("name")
                .or_else(|| object.get("label"))
                .or_else(|| object.get("key"))
                .or_else(|| object.get("field")),
            100,
        );
        if name.is_empty() || !names.insert(name.clone()) {
            continue;
        }
        let raw_value = object
            .get("value")
            .or_else(|| object.get("text"))
            .or_else(|| object.get("content"))
            .or_else(|| object.get("val"));
        let source_value = clean_text(raw_value, 10_000);
        if !preserve_values && !source_value.is_empty() {
            warnings.push("AI 返回的字段值已被安全丢弃".to_string());
        }
        let copyable = to_bool(object.get("copyable"), true);
        let hidden = to_bool(object.get("hidden"), copyable);
        fields.push(ParsedField {
            name,
            value: if preserve_values {
                source_value
            } else {
                String::new()
            },
            copyable,
            hidden,
        });
    }
    fields
}

fn enrich_group_suggestions(
    suggestions: &mut Vec<OrganizeSuggestion>,
    entries: &HashMap<String, EntryInfo>,
    allowed: &HashSet<&str>,
    document: &Value,
) {
    let existing_groups: HashSet<String> = taxonomy_names(document, "groups_meta", "groups")
        .into_iter()
        .collect();
    let mut by_entry: HashMap<String, usize> = suggestions
        .iter()
        .enumerate()
        .map(|(index, item)| (item.entry_id.clone(), index))
        .collect();
    for entry_id in allowed {
        let Some(entry) = entries.get(*entry_id) else {
            continue;
        };
        let inferred = infer_groups(entry, &existing_groups);
        if inferred.is_empty() {
            continue;
        }
        if let Some(index) = by_entry.get(*entry_id).copied() {
            let item = &mut suggestions[index];
            if item.add_groups.is_empty() && item.remove_groups.is_empty() {
                item.add_groups = inferred.clone();
                if item.reason.is_empty() {
                    item.reason = "根据条目名称、网址、字段名和现有分类推断".to_string();
                }
                for group in inferred {
                    if !existing_groups.contains(&group) {
                        item.group_descriptions
                            .push((group.clone(), group_description(&group)));
                    }
                }
            }
        } else {
            let id = format!("organize-{}", suggestions.len());
            let descriptions = inferred
                .iter()
                .filter(|group| !existing_groups.contains(*group))
                .map(|group| (group.clone(), group_description(group)))
                .collect();
            suggestions.push(OrganizeSuggestion {
                id,
                entry_id: (*entry_id).to_string(),
                add_tags: Vec::new(),
                remove_tags: Vec::new(),
                add_groups: inferred,
                remove_groups: Vec::new(),
                group_descriptions: descriptions,
                reason: "根据条目名称、网址、字段名和现有分类推断".to_string(),
            });
            by_entry.insert((*entry_id).to_string(), suggestions.len() - 1);
        }
    }
}

fn infer_groups(entry: &EntryInfo, existing_groups: &HashSet<String>) -> Vec<String> {
    const RULES: [(&str, &[&str]); 6] = [
        (
            "开发资源",
            &[
                "开发", "代码", "git", "github", "gitlab", "仓库", "api", "token", "docker", "k8s",
            ],
        ),
        (
            "工作账号",
            &[
                "工作", "公司", "企业", "办公", "内网", "oa", "邮箱", "mail", "飞书", "钉钉",
            ],
        ),
        (
            "服务器",
            &[
                "服务器",
                "ssh",
                "root",
                "主机",
                "云",
                "vps",
                "数据库",
                "mysql",
                "redis",
                "ip",
                "端口",
            ],
        ),
        ("学校账号", &["学校", "校园", "教务", "课程", "学生", "edu"]),
        (
            "家庭设备",
            &["家庭", "家里", "路由器", "nas", "wifi", "设备", "摄像头"],
        ),
        (
            "金融账号",
            &["银行", "支付", "证券", "基金", "账单", "信用卡", "银行卡"],
        ),
    ];
    let mut result = Vec::new();
    for group in existing_groups {
        if !entry.groups.contains(group) && entry.searchable.contains(&group.to_lowercase()) {
            result.push(group.clone());
        }
    }
    for (group, keywords) in RULES {
        if entry.groups.iter().any(|current| current == group)
            || result.iter().any(|item| item == group)
        {
            continue;
        }
        if keywords
            .iter()
            .any(|keyword| entry.searchable.contains(&keyword.to_lowercase()))
        {
            result.push(group.to_string());
        }
    }
    result.truncate(2);
    result
}

fn group_description(group: &str) -> String {
    match group {
        "开发资源" => "代码仓库、开发平台、API 和 CI/CD 相关账号".to_string(),
        "工作账号" => "公司邮箱、协作工具和内部系统账号".to_string(),
        "服务器" => "服务器、云主机、数据库和运维入口".to_string(),
        "学校账号" => "学校、校园、课程和教育系统账号".to_string(),
        "家庭设备" => "家庭网络、路由器、NAS 和智能设备账号".to_string(),
        "金融账号" => "银行、支付、证券和账单相关账号".to_string(),
        _ => format!("{group}相关账号和密码条目"),
    }
}

fn entry_info(document: &Value) -> HashMap<String, EntryInfo> {
    let mut result = HashMap::new();
    let Some(entries) = document.get("entries").and_then(Value::as_array) else {
        return result;
    };
    for entry in entries {
        let Some(item) = entry.as_object() else {
            continue;
        };
        let Some(id) = item.get("id").and_then(Value::as_str) else {
            continue;
        };
        let title = item
            .get("title")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let tags = string_list(item.get("tags"));
        let groups = string_list(item.get("groups"));
        let field_names = item
            .get("fields")
            .and_then(Value::as_array)
            .map(|fields| {
                fields
                    .iter()
                    .filter_map(|field| field.get("name").and_then(Value::as_str))
                    .collect::<Vec<_>>()
                    .join(" ")
            })
            .unwrap_or_default();
        let searchable = format!(
            "{} {} {} {} {}",
            title,
            item.get("url").and_then(Value::as_str).unwrap_or(""),
            tags.join(" "),
            groups.join(" "),
            field_names
        )
        .to_lowercase();
        result.insert(
            id.to_string(),
            EntryInfo {
                title,
                groups,
                searchable,
            },
        );
    }
    result
}

fn governance_details(
    suggestion: &TagGovernanceSuggestion,
    entries: &HashMap<String, EntryInfo>,
) -> Vec<AiPreviewDetail> {
    let mut details = Vec::new();
    if let Some(tag) = &suggestion.tag {
        details.push(detail("标签", tag, false, "info"));
    }
    if let Some(tag) = &suggestion.new_tag {
        details.push(detail("新标签", tag, false, "update"));
    }
    push_names(&mut details, "源标签", &suggestion.source_tags, "remove");
    if let Some(tag) = &suggestion.target_tag {
        details.push(detail("目标标签", tag, false, "add"));
    }
    if !suggestion.entry_ids.is_empty() {
        let titles = suggestion
            .entry_ids
            .iter()
            .filter_map(|id| entries.get(id).map(|entry| entry.title.as_str()))
            .collect::<Vec<_>>()
            .join("、");
        if !titles.is_empty() {
            details.push(detail("涉及条目", &titles, false, "info"));
        }
    }
    if !suggestion.description.is_empty() {
        details.push(detail("简介", &suggestion.description, false, "update"));
    }
    if let Some(color) = &suggestion.color {
        details.push(detail("颜色", color, false, "update"));
    }
    details
}

fn governance_title(suggestion: &TagGovernanceSuggestion) -> String {
    match suggestion.action.as_str() {
        "create_tag" => format!(
            "新建标签：{}",
            suggestion.tag.as_deref().unwrap_or("未命名")
        ),
        "update_tag" => format!(
            "更新标签：{}",
            suggestion.tag.as_deref().unwrap_or("未命名")
        ),
        "delete_tag" => format!(
            "删除标签：{}",
            suggestion.tag.as_deref().unwrap_or("未命名")
        ),
        "merge_tags" => format!(
            "合并到：{}",
            suggestion.target_tag.as_deref().unwrap_or("未命名")
        ),
        "replace_tag" => format!(
            "替换标签：{}",
            suggestion.tag.as_deref().unwrap_or("未命名")
        ),
        "assign_tag" => format!(
            "分配标签：{}",
            suggestion.tag.as_deref().unwrap_or("未命名")
        ),
        _ => "标签建议".to_string(),
    }
}

fn action_label(action: &str) -> &str {
    match action {
        "create_tag" => "新建标签",
        "update_tag" => "更新标签",
        "delete_tag" => "删除标签",
        "merge_tags" => "合并标签",
        "replace_tag" => "替换标签",
        "assign_tag" => "分配标签",
        _ => "标签建议",
    }
}

fn payload_items(payload: &Value, preferred: &str) -> Vec<Value> {
    if let Some(items) = payload.as_array() {
        return items.clone();
    }
    let Some(object) = payload.as_object() else {
        return Vec::new();
    };
    [preferred, "suggestions", "actions", "items", "data"]
        .iter()
        .find_map(|key| object.get(*key).and_then(Value::as_array).cloned())
        .unwrap_or_default()
}

fn payload_warnings(payload: &Value) -> Vec<String> {
    payload
        .get("warnings")
        .and_then(Value::as_array)
        .map(|warnings| {
            warnings
                .iter()
                .map(|warning| clean_text(Some(warning), 200))
                .filter(|warning| !warning.is_empty())
                .collect()
        })
        .unwrap_or_default()
}

fn extract_first_json(content: &str) -> Result<Value, MobileError> {
    let content = content.trim();
    for (index, character) in content.char_indices() {
        if character != '{' && character != '[' {
            continue;
        }
        let mut values = serde_json::Deserializer::from_str(&content[index..]).into_iter::<Value>();
        if let Some(Ok(value)) = values.next() {
            return Ok(value);
        }
    }
    Err(MobileError::new(
        "AI_RESPONSE_INVALID",
        "AI 未返回可解析的 JSON",
    ))
}

fn clean_text(value: Option<&Value>, maximum: usize) -> String {
    let raw = match value {
        Some(Value::String(value)) => value.clone(),
        Some(Value::Null) | None => String::new(),
        Some(value) => value.to_string(),
    };
    raw.trim().chars().take(maximum).collect()
}

fn optional_text(value: Option<&Value>, maximum: usize) -> Option<String> {
    let value = clean_text(value, maximum);
    (!value.is_empty()).then_some(value)
}

fn optional_name(value: Option<&Value>) -> Option<String> {
    let value = clean_text(value, 50);
    let value = clean_name(&value);
    (!value.is_empty()).then_some(value)
}

fn clean_name(value: &str) -> String {
    value.trim().chars().take(50).collect()
}

fn clean_names(value: Option<&Value>) -> Vec<String> {
    clean_names_unbounded(value, 50)
}

fn clean_names_unbounded(value: Option<&Value>, maximum: usize) -> Vec<String> {
    let values = match value {
        Some(Value::Array(values)) => values.clone(),
        Some(Value::String(value)) => value
            .split([',', '，', ';', '；'])
            .map(|item| Value::String(item.to_string()))
            .collect(),
        _ => Vec::new(),
    };
    let mut result = Vec::new();
    for value in values {
        let name = clean_text(Some(&value), maximum);
        if !name.is_empty() && !result.contains(&name) {
            result.push(name);
        }
    }
    result
}

fn string_list(value: Option<&Value>) -> Vec<String> {
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

fn to_bool(value: Option<&Value>, default: bool) -> bool {
    match value {
        Some(Value::Bool(value)) => *value,
        Some(Value::String(value)) => match value.trim().to_lowercase().as_str() {
            "true" | "yes" | "1" | "是" | "可复制" => true,
            "false" | "no" | "0" | "否" | "不可复制" => false,
            _ => default,
        },
        Some(Value::Number(value)) => value.as_i64().is_some_and(|value| value != 0),
        _ => default,
    }
}

fn valid_color(value: &str) -> bool {
    value.len() == 7
        && value.starts_with('#')
        && value[1..]
            .chars()
            .all(|character| character.is_ascii_hexdigit())
}

fn taxonomy_names(document: &Value, meta_key: &str, field_key: &str) -> Vec<String> {
    let mut names = HashSet::new();
    if let Some(meta) = document.get(meta_key).and_then(Value::as_object) {
        names.extend(meta.keys().cloned());
    }
    if let Some(entries) = document.get("entries").and_then(Value::as_array) {
        for entry in entries {
            names.extend(string_list(entry.get(field_key)));
        }
    }
    names.into_iter().collect()
}

fn detail(label: &str, value: &str, sensitive: bool, change_type: &str) -> AiPreviewDetail {
    AiPreviewDetail {
        label: label.to_string(),
        value: value.to_string(),
        sensitive,
        change_type: change_type.to_string(),
    }
}

fn push_names(
    details: &mut Vec<AiPreviewDetail>,
    label: &str,
    values: &[String],
    change_type: &str,
) {
    if !values.is_empty() {
        details.push(detail(label, &values.join("、"), false, change_type));
    }
}

fn dedupe(values: Vec<String>) -> Vec<String> {
    let mut result = Vec::new();
    for value in values {
        if !value.is_empty() && !result.contains(&value) {
            result.push(value);
        }
    }
    result
}
