use std::collections::HashMap;

use super::super::types::AssistantAction;
use crate::mobile::models::{AiPreviewDetail, AiPreviewItem};

pub(super) fn preview_item(
    action: &AssistantAction,
    entries: &HashMap<String, String>,
) -> AiPreviewItem {
    let entry_title = action
        .entry_id
        .as_ref()
        .or(action.source_entry_id.as_ref())
        .and_then(|id| entries.get(id))
        .map(String::as_str)
        .unwrap_or("条目");
    let mut details = Vec::new();
    let (title, subtitle) = match action.action_type.as_str() {
        "create_group" => (
            format!(
                "新建密码组「{}」",
                action.name.as_deref().unwrap_or("未命名")
            ),
            "密码组".to_string(),
        ),
        "update_group" => (
            format!(
                "更新密码组「{}」",
                action.name.as_deref().unwrap_or("未命名")
            ),
            "密码组".to_string(),
        ),
        "assign_groups" => (
            format!("调整 {} 个条目的密码组", action.entry_ids.len()),
            "密码组分配".to_string(),
        ),
        "create_tag" => (
            format!("新建标签「{}」", action.name.as_deref().unwrap_or("未命名")),
            "标签".to_string(),
        ),
        "update_tag" => (
            format!("更新标签「{}」", action.name.as_deref().unwrap_or("未命名")),
            "标签".to_string(),
        ),
        "delete_tag" => (
            format!("删除标签「{}」", action.name.as_deref().unwrap_or("未命名")),
            "标签删除".to_string(),
        ),
        "merge_tags" => (
            format!(
                "合并标签到「{}」",
                action.target_tag.as_deref().unwrap_or("未命名")
            ),
            "标签合并".to_string(),
        ),
        "assign_tags" => (
            format!("调整 {} 个条目的标签", action.entry_ids.len()),
            "标签分配".to_string(),
        ),
        "rename_entry" => (format!("重命名「{entry_title}」"), "条目结构".to_string()),
        "rename_field" => (
            format!("重命名「{entry_title}」的字段"),
            "字段结构".to_string(),
        ),
        "add_empty_field" => (
            format!("为「{entry_title}」添加空字段"),
            "字段结构".to_string(),
        ),
        "set_field_flags" => (
            format!("调整「{entry_title}」字段属性"),
            "字段属性".to_string(),
        ),
        "create_entry_template" => (
            format!(
                "新建空条目「{}」",
                action.title.as_deref().unwrap_or("未命名")
            ),
            "条目模板".to_string(),
        ),
        "create_entry_from_field" => (
            format!("从「{entry_title}」字段新建条目"),
            "本机复制字段值".to_string(),
        ),
        _ => ("AI 操作".to_string(), String::new()),
    };
    push_detail(&mut details, "新名称", action.new_name.as_deref(), "update");
    push_detail(
        &mut details,
        "简介",
        non_empty(&action.description),
        "update",
    );
    push_detail(&mut details, "字段名", action.name.as_deref(), "add");
    push_detail(
        &mut details,
        "当前字段",
        action.field_name.as_deref(),
        "info",
    );
    push_names(&mut details, "新增", &action.add, "add");
    push_names(&mut details, "移除", &action.remove, "remove");
    push_names(&mut details, "标签", &action.tags, "add");
    push_names(&mut details, "密码组", &action.groups, "add");
    push_names(&mut details, "源标签", &action.source_tags, "remove");
    push_detail(
        &mut details,
        "目标标签",
        action.target_tag.as_deref(),
        "add",
    );
    if let Some(copyable) = action.copyable {
        push_detail(
            &mut details,
            "可复制",
            Some(if copyable { "是" } else { "否" }),
            "update",
        );
    }
    if let Some(hidden) = action.hidden {
        push_detail(
            &mut details,
            "默认隐藏",
            Some(if hidden { "是" } else { "否" }),
            "update",
        );
    }
    push_detail(&mut details, "原因", non_empty(&action.reason), "info");
    AiPreviewItem {
        id: action.id.clone(),
        title,
        subtitle,
        details,
    }
}

fn push_detail(
    details: &mut Vec<AiPreviewDetail>,
    label: &str,
    value: Option<&str>,
    change_type: &str,
) {
    let Some(value) = value.filter(|value| !value.is_empty()) else {
        return;
    };
    details.push(AiPreviewDetail {
        label: label.to_string(),
        value: value.to_string(),
        sensitive: false,
        change_type: change_type.to_string(),
    });
}

fn push_names(
    details: &mut Vec<AiPreviewDetail>,
    label: &str,
    values: &[String],
    change_type: &str,
) {
    if values.is_empty() {
        return;
    }
    push_detail(details, label, Some(&values.join("、")), change_type);
}

fn non_empty(value: &str) -> Option<&str> {
    (!value.is_empty()).then_some(value)
}
