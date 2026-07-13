use std::collections::HashMap;

use serde_json::{Map, Value};

use super::{
    super::types::{AssistantAction, FieldAlias, PendingAssistantRequest},
    sanitize::{
        clean_color, clean_names, clean_string_list, clean_text, normalize_empty_fields,
        optional_name, optional_text, require_name,
    },
};
use crate::mobile::error::MobileError;

pub(super) fn parse_action(
    index: usize,
    action_type: &str,
    object: &Map<String, Value>,
    pending: &PendingAssistantRequest,
) -> Result<AssistantAction, MobileError> {
    let mut action = AssistantAction {
        id: format!("assistant-{}", index + 1),
        action_type: action_type.to_string(),
        entry_ids: Vec::new(),
        entry_id: None,
        source_entry_id: None,
        field_index: None,
        field_name: None,
        name: None,
        new_name: None,
        title: None,
        description: clean_text(object.get("description"), 300),
        color: clean_color(object.get("color")),
        source_tags: clean_names(object.get("source_tags")),
        target_tag: optional_name(object.get("target_tag")),
        add: clean_names(object.get("add")),
        remove: clean_names(object.get("remove")),
        tags: clean_names(object.get("tags")),
        groups: clean_names(object.get("groups")),
        fields: normalize_empty_fields(object.get("fields")),
        copyable: object.get("copyable").and_then(Value::as_bool),
        hidden: object.get("hidden").and_then(Value::as_bool),
        reason: clean_text(object.get("reason"), 500),
    };
    match action_type {
        "create_group" | "create_tag" => {
            action.name = optional_name(object.get("name"));
            require_name(action.name.as_deref(), "AI 新建分类建议缺少名称")?;
        }
        "update_group" => {
            action.name = optional_name(object.get("group"));
            action.new_name = optional_name(object.get("new_name"));
            require_name(action.name.as_deref(), "AI 更新密码组建议缺少原名称")?;
            if action.new_name.is_none() && action.description.is_empty() {
                return Err(MobileError::new(
                    "AI_RESPONSE_INVALID",
                    "AI 更新密码组建议不完整",
                ));
            }
        }
        "assign_groups" | "assign_tags" => {
            action.entry_ids = resolve_entries(object.get("entry_refs"), &pending.entry_aliases)?;
            if action.entry_ids.is_empty() || (action.add.is_empty() && action.remove.is_empty()) {
                return Err(MobileError::new(
                    "AI_RESPONSE_INVALID",
                    "AI 分类分配建议不完整",
                ));
            }
        }
        "update_tag" | "delete_tag" => {
            action.name = optional_name(object.get("tag"));
            action.new_name = optional_name(object.get("new_name"));
            require_name(action.name.as_deref(), "AI 标签建议缺少现有标签")?;
            if action_type == "update_tag"
                && action.new_name.is_none()
                && action.description.is_empty()
                && action.color.is_none()
            {
                return Err(MobileError::new(
                    "AI_RESPONSE_INVALID",
                    "AI 标签更新建议不完整",
                ));
            }
        }
        "merge_tags" => {
            require_name(action.target_tag.as_deref(), "AI 标签合并建议缺少目标标签")?;
            if action.source_tags.is_empty() {
                return Err(MobileError::new(
                    "AI_RESPONSE_INVALID",
                    "AI 标签合并建议缺少源标签",
                ));
            }
        }
        "rename_entry" | "add_empty_field" => {
            action.entry_id = Some(resolve_entry(
                object.get("entry_ref"),
                &pending.entry_aliases,
            )?);
            if action_type == "rename_entry" {
                action.new_name = optional_name(object.get("new_title"));
                require_name(action.new_name.as_deref(), "AI 条目重命名建议缺少新标题")?;
            } else {
                action.name = optional_name(object.get("name"));
                require_name(action.name.as_deref(), "AI 添加字段建议缺少字段名")?;
            }
        }
        "rename_field" | "set_field_flags" | "create_entry_from_field" => {
            let field = resolve_field(object.get("field_ref"), &pending.field_aliases)?;
            action.entry_id = Some(field.entry_id.clone());
            action.source_entry_id = Some(field.entry_id);
            action.field_index = Some(field.index);
            action.field_name = Some(field.name);
            if action_type == "rename_field" {
                action.new_name = optional_name(object.get("new_name"));
                require_name(action.new_name.as_deref(), "AI 字段重命名建议缺少新名称")?;
            } else if action_type == "set_field_flags" {
                if action.copyable.is_none() && action.hidden.is_none() {
                    return Err(MobileError::new(
                        "AI_RESPONSE_INVALID",
                        "AI 字段状态建议不完整",
                    ));
                }
            } else {
                action.title = optional_text(object.get("title"), 200);
                if action.title.is_none() {
                    return Err(MobileError::new(
                        "AI_RESPONSE_INVALID",
                        "AI 字段拆分建议缺少标题",
                    ));
                }
            }
        }
        "create_entry_template" => {
            action.title = optional_text(object.get("title"), 200);
            if action.title.is_none() {
                return Err(MobileError::new(
                    "AI_RESPONSE_INVALID",
                    "AI 新建条目模板缺少标题",
                ));
            }
        }
        "open_entry" => {
            action.entry_id = Some(resolve_entry(
                object.get("entry_ref"),
                &pending.entry_aliases,
            )?);
            if let Some(field_ref) = object.get("field_ref").filter(|value| !value.is_null()) {
                let field = resolve_field(Some(field_ref), &pending.field_aliases)?;
                if action.entry_id.as_deref() != Some(field.entry_id.as_str()) {
                    return Err(MobileError::new(
                        "AI_RESPONSE_INVALID",
                        "AI 定位字段与条目不匹配",
                    ));
                }
            }
        }
        _ => unreachable!(),
    }
    Ok(action)
}

pub(super) fn action_domain(action: &str) -> Option<&'static str> {
    match action {
        "create_group" | "update_group" | "assign_groups" => Some("groups"),
        "create_tag" | "update_tag" | "delete_tag" | "merge_tags" | "assign_tags" => Some("tags"),
        "rename_entry" | "rename_field" | "add_empty_field" | "set_field_flags" => {
            Some("entry_structure")
        }
        "create_entry_template" | "create_entry_from_field" => Some("entry_creation"),
        "open_entry" => Some("navigation"),
        _ => None,
    }
}

fn resolve_entry(
    value: Option<&Value>,
    aliases: &HashMap<String, String>,
) -> Result<String, MobileError> {
    let entry_ref = clean_text(value, 20);
    aliases
        .get(&entry_ref)
        .cloned()
        .ok_or_else(|| MobileError::new("AI_REFERENCE_INVALID", "AI 返回了未知条目引用"))
}

fn resolve_entries(
    value: Option<&Value>,
    aliases: &HashMap<String, String>,
) -> Result<Vec<String>, MobileError> {
    let refs = clean_string_list(value, 20);
    let mut result = Vec::new();
    for entry_ref in refs {
        let id = aliases
            .get(&entry_ref)
            .ok_or_else(|| MobileError::new("AI_REFERENCE_INVALID", "AI 返回了未知条目引用"))?;
        if !result.contains(id) {
            result.push(id.clone());
        }
    }
    Ok(result)
}

fn resolve_field(
    value: Option<&Value>,
    aliases: &HashMap<String, FieldAlias>,
) -> Result<FieldAlias, MobileError> {
    let field_ref = clean_text(value, 30);
    aliases
        .get(&field_ref)
        .cloned()
        .ok_or_else(|| MobileError::new("AI_REFERENCE_INVALID", "AI 返回了未知字段引用"))
}
