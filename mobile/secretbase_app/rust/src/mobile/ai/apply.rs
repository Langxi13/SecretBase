use std::collections::HashSet;

use serde_json::{Map, Value};

use crate::mobile::{
    document,
    error::MobileError,
    models::{EntryDraft, EntryRecord, FieldRecord},
};

use super::assistant::ordered_selected_actions;
use super::types::{
    ActionPlan, AssistantAction, OrganizeSuggestion, PendingAiPreview, PreviewData,
    TagGovernanceSuggestion,
};

pub fn apply_preview(
    value: &mut Value,
    pending: &PendingAiPreview,
    selected_ids: &[String],
    now: &str,
) -> Result<String, MobileError> {
    let selected = selected_ids.iter().cloned().collect::<HashSet<_>>();
    if selected.is_empty() {
        return Err(MobileError::new("VALIDATION_FAILED", "请至少选择一条建议"));
    }
    let known = pending
        .preview
        .items
        .iter()
        .map(|item| item.id.as_str())
        .collect::<HashSet<_>>();
    if selected.iter().any(|id| !known.contains(id.as_str())) {
        return Err(MobileError::new("AI_PREVIEW_INVALID", "AI 建议选择项无效"));
    }

    match &pending.data {
        PreviewData::Parsed(entries) => {
            let mut count = 0;
            for entry in entries.iter().filter(|entry| selected.contains(&entry.id)) {
                let draft = EntryDraft {
                    title: entry.title.clone(),
                    url: entry.url.clone(),
                    starred: false,
                    tags: entry.tags.clone(),
                    groups: entry.groups.clone(),
                    fields: entry
                        .fields
                        .iter()
                        .map(|field| FieldRecord {
                            name: field.name.clone(),
                            value: field.value.clone(),
                            copyable: field.copyable,
                            hidden: field.hidden,
                        })
                        .collect(),
                    remarks: entry.remarks.clone(),
                };
                document::save_entry(value, None, &draft, now)?;
                count += 1;
            }
            Ok(format!("已创建 {count} 个 AI 解析条目"))
        }
        PreviewData::Organize(suggestions) => apply_organize(value, suggestions, &selected, now),
        PreviewData::Governance(suggestions) => {
            apply_governance(value, suggestions, &selected, now)
        }
        PreviewData::Actions(actions) => apply_actions(value, actions, &selected, now),
        PreviewData::Assistant(actions) => apply_assistant(value, actions, &selected, now),
    }
}

fn apply_assistant(
    value: &mut Value,
    actions: &[AssistantAction],
    selected: &HashSet<String>,
    now: &str,
) -> Result<String, MobileError> {
    let mut applied = 0;
    for action in ordered_selected_actions(actions, selected)? {
        match action.action_type.as_str() {
            "create_group" => {
                let name = required_name(action.name.as_deref(), "创建密码组操作缺少名称")?;
                ensure_taxonomy(value, "groups", name, &action.description, None, now)?;
            }
            "update_group" => {
                apply_assistant_taxonomy_update(value, "groups", action, now)?;
            }
            "assign_groups" => {
                apply_assistant_assignment(value, action, true, now)?;
            }
            "create_tag" => {
                let name = required_name(action.name.as_deref(), "创建标签操作缺少名称")?;
                ensure_taxonomy(
                    value,
                    "tags",
                    name,
                    &action.description,
                    action.color.as_deref(),
                    now,
                )?;
            }
            "update_tag" => {
                apply_assistant_taxonomy_update(value, "tags", action, now)?;
            }
            "delete_tag" => {
                let name = required_name(action.name.as_deref(), "删除标签操作缺少名称")?;
                document::delete_taxonomy(value, "tags", name, now)?;
            }
            "merge_tags" => {
                let suggestion = TagGovernanceSuggestion {
                    id: action.id.clone(),
                    action: "merge_tags".to_string(),
                    tag: None,
                    new_tag: None,
                    source_tags: action.source_tags.clone(),
                    target_tag: action.target_tag.clone(),
                    entry_ids: Vec::new(),
                    description: action.description.clone(),
                    color: action.color.clone(),
                    reason: action.reason.clone(),
                };
                apply_merge_tags(value, &suggestion, now)?;
            }
            "assign_tags" => {
                apply_assistant_assignment(value, action, false, now)?;
            }
            "rename_entry" => {
                let id = required_name(action.entry_id.as_deref(), "条目重命名操作缺少条目")?;
                let entry = document::get_entry(value, id)?;
                let mut draft = draft_from_entry(&entry);
                draft.title =
                    required_name(action.new_name.as_deref(), "条目重命名操作缺少新标题")?
                        .to_string();
                document::save_entry(value, Some(id), &draft, now)?;
            }
            "rename_field" => {
                apply_assistant_field_change(value, action, "rename", now)?;
            }
            "add_empty_field" => {
                let id = required_name(action.entry_id.as_deref(), "添加字段操作缺少条目")?;
                let entry = document::get_entry(value, id)?;
                let mut draft = draft_from_entry(&entry);
                let name = required_name(action.name.as_deref(), "添加字段操作缺少字段名")?;
                if draft.fields.iter().any(|field| field.name == name) {
                    return Err(MobileError::new("VALIDATION_FAILED", "新增字段名称已存在"));
                }
                draft.fields.push(FieldRecord {
                    name: name.to_string(),
                    value: String::new(),
                    copyable: action.copyable.unwrap_or(false),
                    hidden: action.hidden.unwrap_or(false),
                });
                document::save_entry(value, Some(id), &draft, now)?;
            }
            "set_field_flags" => {
                apply_assistant_field_change(value, action, "flags", now)?;
            }
            "create_entry_template" => {
                let title = required_name(action.title.as_deref(), "新建条目模板缺少标题")?;
                let draft = EntryDraft {
                    title: title.to_string(),
                    url: String::new(),
                    starred: false,
                    tags: action.tags.clone(),
                    groups: action.groups.clone(),
                    fields: action
                        .fields
                        .iter()
                        .map(|field| FieldRecord {
                            name: field.name.clone(),
                            value: String::new(),
                            copyable: field.copyable,
                            hidden: field.hidden,
                        })
                        .collect(),
                    remarks: String::new(),
                };
                document::save_entry(value, None, &draft, now)?;
            }
            "create_entry_from_field" => {
                apply_assistant_split_field(value, action, now)?;
            }
            _ => {
                return Err(MobileError::new(
                    "AI_ACTION_INVALID",
                    "不支持的 AI 管家操作",
                ))
            }
        }
        applied += 1;
    }
    Ok(format!("已应用 {applied} 项 AI 管家操作"))
}

fn apply_assistant_taxonomy_update(
    value: &mut Value,
    kind: &str,
    action: &AssistantAction,
    now: &str,
) -> Result<(), MobileError> {
    let current = required_name(action.name.as_deref(), "更新分类操作缺少原名称")?;
    if !taxonomy_exists(value, kind, current)? {
        return Err(MobileError::new(
            "TAXONOMY_NOT_FOUND",
            "AI 更新的分类不存在",
        ));
    }
    let destination = action.new_name.as_deref().unwrap_or(current);
    let (current_description, current_color) = taxonomy_meta(value, kind, current);
    let description = if action.description.is_empty() {
        current_description.as_str()
    } else {
        action.description.as_str()
    };
    let color = action.color.as_deref().or(current_color.as_deref());
    document::save_taxonomy(
        value,
        kind,
        Some(current),
        destination,
        description,
        color,
        now,
    )
}

fn apply_assistant_assignment(
    value: &mut Value,
    action: &AssistantAction,
    groups: bool,
    now: &str,
) -> Result<(), MobileError> {
    let kind = if groups { "groups" } else { "tags" };
    for name in &action.add {
        ensure_taxonomy(value, kind, name, "", None, now)?;
    }
    for id in &action.entry_ids {
        let entry = document::get_entry(value, id)?;
        if entry.deleted {
            return Err(MobileError::new(
                "ENTRY_NOT_FOUND",
                "AI 建议引用的条目已删除",
            ));
        }
        let mut draft = draft_from_entry(&entry);
        let names = if groups {
            &mut draft.groups
        } else {
            &mut draft.tags
        };
        names.retain(|name| !action.remove.contains(name));
        append_unique(names, &action.add);
        document::save_entry(value, Some(id), &draft, now)?;
    }
    Ok(())
}

fn apply_assistant_field_change(
    value: &mut Value,
    action: &AssistantAction,
    change: &str,
    now: &str,
) -> Result<(), MobileError> {
    let id = required_name(action.entry_id.as_deref(), "字段操作缺少条目")?;
    let entry = document::get_entry(value, id)?;
    let mut draft = draft_from_entry(&entry);
    let index = action
        .field_index
        .ok_or_else(|| MobileError::new("VALIDATION_FAILED", "字段操作缺少字段索引"))?;
    let field = draft
        .fields
        .get(index)
        .ok_or_else(|| MobileError::new("VALIDATION_FAILED", "字段操作引用的字段索引无效"))?;
    if action.field_name.as_deref() != Some(field.name.as_str()) {
        return Err(MobileError::retryable(
            "REVISION_CONFLICT",
            "字段名称已变化，请重新生成 AI 计划",
        ));
    }
    if change == "rename" {
        let new_name = required_name(action.new_name.as_deref(), "字段重命名缺少新名称")?;
        if draft
            .fields
            .iter()
            .enumerate()
            .any(|(other_index, field)| other_index != index && field.name == new_name)
        {
            return Err(MobileError::new(
                "VALIDATION_FAILED",
                "字段重命名后的名称已存在",
            ));
        }
        draft.fields[index].name = new_name.to_string();
    } else {
        if let Some(copyable) = action.copyable {
            draft.fields[index].copyable = copyable;
        }
        if let Some(hidden) = action.hidden {
            draft.fields[index].hidden = hidden;
        }
    }
    document::save_entry(value, Some(id), &draft, now)?;
    Ok(())
}

fn apply_assistant_split_field(
    value: &mut Value,
    action: &AssistantAction,
    now: &str,
) -> Result<(), MobileError> {
    let source_id = required_name(
        action.source_entry_id.as_deref(),
        "字段拆分操作缺少来源条目",
    )?;
    let source = document::get_entry(value, source_id)?;
    let index = action
        .field_index
        .ok_or_else(|| MobileError::new("VALIDATION_FAILED", "字段拆分操作缺少字段索引"))?;
    let field = source
        .fields
        .get(index)
        .ok_or_else(|| MobileError::new("VALIDATION_FAILED", "字段拆分引用的字段索引无效"))?;
    if action.field_name.as_deref() != Some(field.name.as_str()) {
        return Err(MobileError::retryable(
            "REVISION_CONFLICT",
            "字段名称已变化，请重新生成 AI 计划",
        ));
    }
    let title = required_name(action.title.as_deref(), "字段拆分操作缺少新条目标题")?;
    let draft = EntryDraft {
        title: title.to_string(),
        url: String::new(),
        starred: false,
        tags: action.tags.clone(),
        groups: action.groups.clone(),
        fields: vec![field.clone()],
        remarks: String::new(),
    };
    document::save_entry(value, None, &draft, now)?;
    Ok(())
}

fn taxonomy_meta(value: &Value, kind: &str, name: &str) -> (String, Option<String>) {
    let key = if kind == "groups" {
        "groups_meta"
    } else {
        "tags_meta"
    };
    let record = value
        .get(key)
        .and_then(Value::as_object)
        .and_then(|meta| meta.get(name))
        .and_then(Value::as_object);
    let description = record
        .and_then(|record| record.get("description"))
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let color = record
        .and_then(|record| record.get("color"))
        .and_then(Value::as_str)
        .map(str::to_string);
    (description, color)
}

fn apply_organize(
    value: &mut Value,
    suggestions: &[OrganizeSuggestion],
    selected: &HashSet<String>,
    now: &str,
) -> Result<String, MobileError> {
    let mut updated = 0;
    for suggestion in suggestions
        .iter()
        .filter(|item| selected.contains(&item.id))
    {
        let entry = document::get_entry(value, &suggestion.entry_id)?;
        if entry.deleted {
            return Err(MobileError::new(
                "ENTRY_NOT_FOUND",
                "AI 建议引用的条目已删除",
            ));
        }
        let mut draft = draft_from_entry(&entry);
        let original_tags = draft.tags.clone();
        let original_groups = draft.groups.clone();
        draft
            .tags
            .retain(|tag| !suggestion.remove_tags.contains(tag));
        append_unique(&mut draft.tags, &suggestion.add_tags);
        draft
            .groups
            .retain(|group| !suggestion.remove_groups.contains(group));
        append_unique(&mut draft.groups, &suggestion.add_groups);
        if draft.tags != original_tags || draft.groups != original_groups {
            document::save_entry(value, Some(&entry.id), &draft, now)?;
            updated += 1;
        }
        for (group, description) in &suggestion.group_descriptions {
            if suggestion.add_groups.contains(group) && !description.is_empty() {
                ensure_taxonomy(value, "groups", group, description, None, now)?;
            }
        }
    }
    Ok(format!("已整理 {updated} 个条目"))
}

fn apply_governance(
    value: &mut Value,
    suggestions: &[TagGovernanceSuggestion],
    selected: &HashSet<String>,
    now: &str,
) -> Result<String, MobileError> {
    let mut applied = 0;
    for suggestion in suggestions
        .iter()
        .filter(|item| selected.contains(&item.id))
    {
        let changed = match suggestion.action.as_str() {
            "create_tag" => apply_create_tag(value, suggestion, now)?,
            "update_tag" => apply_update_tag(value, suggestion, now)?,
            "delete_tag" => apply_delete_tag(value, suggestion, now)?,
            "merge_tags" => apply_merge_tags(value, suggestion, now)?,
            "replace_tag" => apply_replace_tag(value, suggestion, now)?,
            "assign_tag" => apply_assign_tag(value, suggestion, now)?,
            _ => false,
        };
        if changed {
            applied += 1;
        }
    }
    Ok(format!("已应用 {applied} 条标签治理建议"))
}

fn apply_create_tag(
    value: &mut Value,
    suggestion: &TagGovernanceSuggestion,
    now: &str,
) -> Result<bool, MobileError> {
    let tag = required_name(suggestion.tag.as_deref(), "新建标签操作缺少名称")?;
    ensure_taxonomy(
        value,
        "tags",
        tag,
        &suggestion.description,
        suggestion.color.as_deref(),
        now,
    )?;
    let mut changed = true;
    for entry_id in &suggestion.entry_ids {
        changed |= assign_tag_to_entry(value, entry_id, tag, now)?;
    }
    Ok(changed)
}

fn apply_update_tag(
    value: &mut Value,
    suggestion: &TagGovernanceSuggestion,
    now: &str,
) -> Result<bool, MobileError> {
    let tag = required_name(suggestion.tag.as_deref(), "更新标签操作缺少原名称")?;
    if !taxonomy_exists(value, "tags", tag)? {
        return Err(MobileError::new(
            "TAG_NOT_FOUND",
            "更新标签引用的标签不存在",
        ));
    }
    let destination = suggestion.new_tag.as_deref().unwrap_or(tag);
    document::save_taxonomy(
        value,
        "tags",
        Some(tag),
        destination,
        &suggestion.description,
        suggestion.color.as_deref(),
        now,
    )?;
    Ok(true)
}

fn apply_delete_tag(
    value: &mut Value,
    suggestion: &TagGovernanceSuggestion,
    now: &str,
) -> Result<bool, MobileError> {
    let tag = required_name(suggestion.tag.as_deref(), "删除标签操作缺少名称")?;
    if !taxonomy_exists(value, "tags", tag)? {
        return Ok(false);
    }
    document::delete_taxonomy(value, "tags", tag, now)?;
    Ok(true)
}

fn apply_merge_tags(
    value: &mut Value,
    suggestion: &TagGovernanceSuggestion,
    now: &str,
) -> Result<bool, MobileError> {
    let target = required_name(suggestion.target_tag.as_deref(), "合并标签操作缺少目标标签")?;
    let sources = suggestion
        .source_tags
        .iter()
        .filter(|source| source.as_str() != target)
        .cloned()
        .collect::<Vec<_>>();
    if sources.is_empty() {
        return Err(MobileError::new(
            "VALIDATION_FAILED",
            "合并标签操作缺少源标签",
        ));
    }
    ensure_taxonomy(
        value,
        "tags",
        target,
        &suggestion.description,
        suggestion.color.as_deref(),
        now,
    )?;
    let mut changed = false;
    for key in ["entries", "deleted_entries"] {
        let entries = root_mut(value)?
            .get_mut(key)
            .and_then(Value::as_array_mut)
            .ok_or_else(|| MobileError::new("INVALID_PAYLOAD", "Vault 条目数据无效"))?;
        for entry in entries {
            let Some(entry) = entry.as_object_mut() else {
                continue;
            };
            let current = string_list(entry.get("tags"));
            if current.iter().any(|tag| sources.contains(tag)) {
                let mut tags = current
                    .into_iter()
                    .filter(|tag| !sources.contains(tag))
                    .collect::<Vec<_>>();
                if !tags.iter().any(|tag| tag == target) {
                    tags.push(target.to_string());
                }
                entry.insert("tags".to_string(), serde_json::json!(tags));
                entry.insert("updated_at".to_string(), Value::String(now.to_string()));
                changed = true;
            }
        }
    }
    for source in sources {
        if taxonomy_exists(value, "tags", &source)? {
            remove_meta_only(value, "tags_meta", &source)?;
            changed = true;
        }
    }
    Ok(changed)
}

fn apply_replace_tag(
    value: &mut Value,
    suggestion: &TagGovernanceSuggestion,
    now: &str,
) -> Result<bool, MobileError> {
    let old = required_name(suggestion.tag.as_deref(), "替换标签操作缺少原标签")?;
    let new = required_name(suggestion.new_tag.as_deref(), "替换标签操作缺少新标签")?;
    ensure_taxonomy(
        value,
        "tags",
        new,
        &suggestion.description,
        suggestion.color.as_deref(),
        now,
    )?;
    let ids = if suggestion.entry_ids.is_empty() {
        active_entry_ids(value)?
    } else {
        suggestion.entry_ids.clone()
    };
    let mut changed = false;
    for id in ids {
        let entry = document::get_entry(value, &id)?;
        if entry.deleted || !entry.tags.iter().any(|tag| tag == old) {
            continue;
        }
        let mut draft = draft_from_entry(&entry);
        draft.tags = draft
            .tags
            .into_iter()
            .map(|tag| if tag == old { new.to_string() } else { tag })
            .fold(Vec::new(), |mut tags, tag| {
                if !tags.contains(&tag) {
                    tags.push(tag);
                }
                tags
            });
        document::save_entry(value, Some(&id), &draft, now)?;
        changed = true;
    }
    Ok(changed)
}

fn apply_assign_tag(
    value: &mut Value,
    suggestion: &TagGovernanceSuggestion,
    now: &str,
) -> Result<bool, MobileError> {
    let tag = required_name(suggestion.tag.as_deref(), "分配标签操作缺少标签名称")?;
    if suggestion.entry_ids.is_empty() {
        return Err(MobileError::new(
            "VALIDATION_FAILED",
            "分配标签操作缺少条目",
        ));
    }
    ensure_taxonomy(
        value,
        "tags",
        tag,
        &suggestion.description,
        suggestion.color.as_deref(),
        now,
    )?;
    let mut changed = false;
    for id in &suggestion.entry_ids {
        changed |= assign_tag_to_entry(value, id, tag, now)?;
    }
    Ok(changed)
}

fn apply_actions(
    value: &mut Value,
    actions: &[ActionPlan],
    selected: &HashSet<String>,
    now: &str,
) -> Result<String, MobileError> {
    let mut applied = 0;
    for action in actions.iter().filter(|item| selected.contains(&item.id)) {
        match action.action_type.as_str() {
            "create_group" => {
                let group = required_name(action.group.as_deref(), "创建密码组操作缺少名称")?;
                ensure_taxonomy(value, "groups", group, &action.description, None, now)?;
            }
            "update_group" => apply_group_update(value, action, now)?,
            "create_entry" => apply_create_entry(value, action, now)?,
            "create_entry_from_field" => apply_split_field(value, action, now)?,
            "update_entry" => apply_update_entry(value, action, now)?,
            _ => return Err(MobileError::new("AI_ACTION_INVALID", "不支持的 AI 操作")),
        }
        applied += 1;
    }
    Ok(format!("已应用 {applied} 项 AI 操作计划"))
}

fn apply_group_update(
    value: &mut Value,
    action: &ActionPlan,
    now: &str,
) -> Result<(), MobileError> {
    let group = required_name(action.group.as_deref(), "更新密码组操作缺少原名称")?;
    if action.group_new.is_none() && action.description.is_empty() {
        return Err(MobileError::new(
            "VALIDATION_FAILED",
            "更新密码组操作缺少新名称或简介",
        ));
    }
    if !taxonomy_exists(value, "groups", group)? {
        return Err(MobileError::new(
            "GROUP_NOT_FOUND",
            "更新密码组操作引用的密码组不存在",
        ));
    }
    let destination = action.group_new.as_deref().unwrap_or(group);
    document::save_taxonomy(
        value,
        "groups",
        Some(group),
        destination,
        &action.description,
        None,
        now,
    )
}

fn apply_create_entry(
    value: &mut Value,
    action: &ActionPlan,
    now: &str,
) -> Result<(), MobileError> {
    let title = action
        .title
        .as_deref()
        .filter(|title| !title.trim().is_empty())
        .ok_or_else(|| MobileError::new("VALIDATION_FAILED", "创建条目操作缺少标题"))?;
    let draft = EntryDraft {
        title: title.to_string(),
        url: action.url.clone().unwrap_or_default(),
        starred: false,
        tags: action.tags.clone(),
        groups: action.groups.clone(),
        fields: action
            .fields
            .iter()
            .map(|field| FieldRecord {
                name: field.name.clone(),
                value: String::new(),
                copyable: field.copyable,
                hidden: field.hidden,
            })
            .collect(),
        remarks: action.remarks.clone(),
    };
    document::save_entry(value, None, &draft, now)?;
    Ok(())
}

fn apply_split_field(value: &mut Value, action: &ActionPlan, now: &str) -> Result<(), MobileError> {
    let source_id = action
        .source_entry_id
        .as_deref()
        .ok_or_else(|| MobileError::new("VALIDATION_FAILED", "字段拆分操作缺少来源条目"))?;
    let source = document::get_entry(value, source_id)?;
    if source.deleted {
        return Err(MobileError::new(
            "ENTRY_NOT_FOUND",
            "字段拆分来源条目已删除",
        ));
    }
    let index = action
        .field_index
        .ok_or_else(|| MobileError::new("VALIDATION_FAILED", "字段拆分操作缺少字段索引"))?;
    let field = source
        .fields
        .get(index)
        .ok_or_else(|| MobileError::new("VALIDATION_FAILED", "字段拆分引用的字段索引无效"))?;
    if action.field_name.as_deref() != Some(field.name.as_str()) {
        return Err(MobileError::retryable(
            "REVISION_CONFLICT",
            "字段拆分引用的字段名已变化，请重新生成计划",
        ));
    }
    let title = action
        .title
        .as_deref()
        .filter(|title| !title.trim().is_empty())
        .ok_or_else(|| MobileError::new("VALIDATION_FAILED", "字段拆分操作缺少新条目标题"))?;
    let draft = EntryDraft {
        title: title.to_string(),
        url: action.url.clone().unwrap_or_else(|| source.url.clone()),
        starred: false,
        tags: action.tags.clone(),
        groups: action.groups.clone(),
        fields: vec![field.clone()],
        remarks: if action.remarks.is_empty() {
            format!("由“{}”的字段“{}”拆分生成", source.title, field.name)
        } else {
            action.remarks.clone()
        },
    };
    document::save_entry(value, None, &draft, now)?;
    Ok(())
}

fn apply_update_entry(
    value: &mut Value,
    action: &ActionPlan,
    now: &str,
) -> Result<(), MobileError> {
    let id = action
        .entry_id
        .as_deref()
        .ok_or_else(|| MobileError::new("VALIDATION_FAILED", "更新条目操作缺少条目 ID"))?;
    let entry = document::get_entry(value, id)?;
    if entry.deleted {
        return Err(MobileError::new("ENTRY_NOT_FOUND", "更新条目已删除"));
    }
    let mut draft = draft_from_entry(&entry);
    if let Some(title) = action
        .title
        .as_ref()
        .filter(|title| !title.trim().is_empty())
    {
        draft.title = title.clone();
    }
    draft.tags.retain(|tag| !action.remove_tags.contains(tag));
    append_unique(&mut draft.tags, &action.add_tags);
    draft
        .groups
        .retain(|group| !action.remove_groups.contains(group));
    append_unique(&mut draft.groups, &action.add_groups);
    if action.field_name_new.is_some() {
        let index = action.field_index.ok_or_else(|| {
            MobileError::new(
                "VALIDATION_FAILED",
                "字段重命名必须提供字段索引、当前字段名和新字段名",
            )
        })?;
        let field = draft
            .fields
            .get_mut(index)
            .ok_or_else(|| MobileError::new("VALIDATION_FAILED", "字段重命名引用的字段索引无效"))?;
        if action.field_name.as_deref() != Some(field.name.as_str()) {
            return Err(MobileError::retryable(
                "REVISION_CONFLICT",
                "字段重命名引用的字段名已变化，请重新生成计划",
            ));
        }
        let new_name = required_name(action.field_name_new.as_deref(), "字段重命名缺少新字段名")?;
        if draft
            .fields
            .iter()
            .enumerate()
            .any(|(field_index, field)| field_index != index && field.name == new_name)
        {
            return Err(MobileError::new(
                "VALIDATION_FAILED",
                "字段重命名后的名称已存在",
            ));
        }
        draft.fields[index].name = new_name.to_string();
    }
    document::save_entry(value, Some(id), &draft, now)?;
    Ok(())
}

fn assign_tag_to_entry(
    value: &mut Value,
    id: &str,
    tag: &str,
    now: &str,
) -> Result<bool, MobileError> {
    let entry = document::get_entry(value, id)?;
    if entry.deleted || entry.tags.iter().any(|current| current == tag) {
        return Ok(false);
    }
    let mut draft = draft_from_entry(&entry);
    draft.tags.push(tag.to_string());
    document::save_entry(value, Some(id), &draft, now)?;
    Ok(true)
}

fn draft_from_entry(entry: &EntryRecord) -> EntryDraft {
    EntryDraft {
        title: entry.title.clone(),
        url: entry.url.clone(),
        starred: entry.starred,
        tags: entry.tags.clone(),
        groups: entry.groups.clone(),
        fields: entry.fields.clone(),
        remarks: entry.remarks.clone(),
    }
}

fn ensure_taxonomy(
    value: &mut Value,
    kind: &str,
    name: &str,
    description: &str,
    color: Option<&str>,
    now: &str,
) -> Result<(), MobileError> {
    let exists = taxonomy_exists(value, kind, name)?;
    if exists && description.is_empty() && color.is_none() {
        return Ok(());
    }
    document::save_taxonomy(
        value,
        kind,
        exists.then_some(name),
        name,
        description,
        color,
        now,
    )
}

fn taxonomy_exists(value: &Value, kind: &str, name: &str) -> Result<bool, MobileError> {
    Ok(document::list_taxonomy(value, kind)?
        .iter()
        .any(|item| item.name == name))
}

fn active_entry_ids(value: &Value) -> Result<Vec<String>, MobileError> {
    Ok(value
        .get("entries")
        .and_then(Value::as_array)
        .ok_or_else(|| MobileError::new("INVALID_PAYLOAD", "Vault 条目数据无效"))?
        .iter()
        .filter_map(|entry| entry.get("id").and_then(Value::as_str).map(str::to_string))
        .collect())
}

fn remove_meta_only(value: &mut Value, meta_key: &str, name: &str) -> Result<(), MobileError> {
    let meta = root_mut(value)?
        .get_mut(meta_key)
        .and_then(Value::as_object_mut)
        .ok_or_else(|| MobileError::new("INVALID_PAYLOAD", "分类元数据无效"))?;
    meta.remove(name);
    Ok(())
}

fn root_mut(value: &mut Value) -> Result<&mut Map<String, Value>, MobileError> {
    value
        .as_object_mut()
        .ok_or_else(|| MobileError::new("INVALID_PAYLOAD", "Vault 根数据无效"))
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

fn append_unique(target: &mut Vec<String>, values: &[String]) {
    for value in values {
        if !target.contains(value) {
            target.push(value.clone());
        }
    }
}

fn required_name<'a>(value: Option<&'a str>, message: &str) -> Result<&'a str, MobileError> {
    value
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| MobileError::new("VALIDATION_FAILED", message))
}
