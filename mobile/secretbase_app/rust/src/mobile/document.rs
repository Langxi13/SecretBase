use std::collections::{HashMap, HashSet};

use serde_json::{json, Map, Value};
use uuid::Uuid;

use super::{
    error::MobileError,
    models::{EntryDraft, EntryPage, EntryRecord, FieldRecord, TaxonomyRecord},
};

pub fn new_document(now: &str) -> Value {
    json!({
        "version": "1.0",
        "created_at": now,
        "app_name": "SecretBase",
        "vault_id": Uuid::new_v4().to_string(),
        "entries": [],
        "deleted_entries": [],
        "tags_meta": {},
        "groups_meta": {}
    })
}

pub fn prepare_for_mobile(value: &mut Value, now: &str) -> Result<bool, MobileError> {
    let root = root_mut(value)?;
    let mut changed = false;
    let mut used_ids = HashSet::new();
    for key in ["entries", "deleted_entries"] {
        let deleted = key == "deleted_entries";
        for entry in array_mut(root, key)? {
            let Some(item) = entry.as_object_mut() else {
                continue;
            };
            let current_id = item
                .get("id")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|id| !id.is_empty());
            let id = current_id
                .filter(|id| !used_ids.contains(*id))
                .map(str::to_string)
                .unwrap_or_else(|| {
                    changed = true;
                    Uuid::new_v4().to_string()
                });
            used_ids.insert(id.clone());
            if item.get("id").and_then(Value::as_str) != Some(id.as_str()) {
                item.insert("id".to_string(), Value::String(id));
                changed = true;
            }
            changed |= insert_default(item, "url", Value::String(String::new()));
            changed |= insert_default(item, "starred", Value::Bool(false));
            changed |= insert_default(item, "tags", Value::Array(Vec::new()));
            changed |= insert_default(item, "groups", Value::Array(Vec::new()));
            changed |= insert_default(item, "fields", Value::Array(Vec::new()));
            changed |= insert_default(item, "remarks", Value::String(String::new()));
            changed |= insert_default(item, "created_at", Value::String(now.to_string()));
            let created_at = item
                .get("created_at")
                .and_then(Value::as_str)
                .unwrap_or(now)
                .to_string();
            changed |= insert_default(item, "updated_at", Value::String(created_at));
            if item.get("deleted").and_then(Value::as_bool) != Some(deleted) {
                item.insert("deleted".to_string(), Value::Bool(deleted));
                changed = true;
            }
            changed |= insert_default(item, "deleted_at", Value::Null);
            if let Some(fields) = item.get_mut("fields").and_then(Value::as_array_mut) {
                for field in fields {
                    let Some(field) = field.as_object_mut() else {
                        continue;
                    };
                    changed |= insert_default(field, "value", Value::String(String::new()));
                    changed |= insert_default(field, "copyable", Value::Bool(false));
                    changed |= insert_default(field, "hidden", Value::Null);
                }
            }
        }
    }
    Ok(changed)
}

fn insert_default(target: &mut Map<String, Value>, key: &str, value: Value) -> bool {
    if target.contains_key(key) {
        return false;
    }
    target.insert(key.to_string(), value);
    true
}

fn root(value: &Value) -> Result<&Map<String, Value>, MobileError> {
    value
        .as_object()
        .ok_or_else(|| MobileError::new("INVALID_PAYLOAD", "Vault 根数据无效"))
}

fn root_mut(value: &mut Value) -> Result<&mut Map<String, Value>, MobileError> {
    value
        .as_object_mut()
        .ok_or_else(|| MobileError::new("INVALID_PAYLOAD", "Vault 根数据无效"))
}

fn array<'a>(root: &'a Map<String, Value>, key: &str) -> Result<&'a Vec<Value>, MobileError> {
    root.get(key)
        .and_then(Value::as_array)
        .ok_or_else(|| MobileError::new("INVALID_PAYLOAD", format!("Vault {key} 无效")))
}

fn array_mut<'a>(
    root: &'a mut Map<String, Value>,
    key: &str,
) -> Result<&'a mut Vec<Value>, MobileError> {
    root.get_mut(key)
        .and_then(Value::as_array_mut)
        .ok_or_else(|| MobileError::new("INVALID_PAYLOAD", format!("Vault {key} 无效")))
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

fn entry_record(value: &Value) -> Option<EntryRecord> {
    let item = value.as_object()?;
    let copyable_fields = item
        .get("fields")
        .and_then(Value::as_array)
        .map(|fields| {
            fields
                .iter()
                .filter_map(|field| {
                    let field = field.as_object()?;
                    let copyable = field
                        .get("copyable")
                        .and_then(Value::as_bool)
                        .unwrap_or(false);
                    Some(FieldRecord {
                        name: field
                            .get("name")
                            .and_then(Value::as_str)
                            .unwrap_or("")
                            .to_string(),
                        value: field
                            .get("value")
                            .and_then(Value::as_str)
                            .unwrap_or("")
                            .to_string(),
                        copyable,
                        hidden: field
                            .get("hidden")
                            .and_then(Value::as_bool)
                            .unwrap_or(copyable),
                    })
                })
                .collect()
        })
        .unwrap_or_default();
    Some(EntryRecord {
        id: item.get("id")?.as_str()?.to_string(),
        title: item.get("title")?.as_str()?.to_string(),
        url: item
            .get("url")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string(),
        starred: item
            .get("starred")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        tags: string_list(item.get("tags")),
        groups: string_list(item.get("groups")),
        fields: copyable_fields,
        remarks: item
            .get("remarks")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string(),
        created_at: item
            .get("created_at")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string(),
        updated_at: item
            .get("updated_at")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string(),
        deleted: item
            .get("deleted")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        deleted_at: item
            .get("deleted_at")
            .and_then(Value::as_str)
            .map(str::to_string),
    })
}

#[cfg_attr(not(target_os = "android"), allow(dead_code))]
pub(crate) fn active_entry_records(value: &Value) -> Result<Vec<EntryRecord>, MobileError> {
    Ok(array(root(value)?, "entries")?
        .iter()
        .filter_map(entry_record)
        .collect())
}

fn normalize_names(values: &[String], label: &str) -> Result<Vec<String>, MobileError> {
    let mut result = Vec::new();
    for raw in values {
        let name = raw.trim();
        if name.is_empty() {
            return Err(MobileError::new(
                "VALIDATION_FAILED",
                format!("{label}不能为空"),
            ));
        }
        if name.chars().count() > 50 {
            return Err(MobileError::new(
                "VALIDATION_FAILED",
                format!("{label}不能超过 50 个字符"),
            ));
        }
        if !result.iter().any(|existing| existing == name) {
            result.push(name.to_string());
        }
    }
    Ok(result)
}

fn validate_draft(draft: &EntryDraft) -> Result<(Vec<String>, Vec<String>), MobileError> {
    let title = draft.title.trim();
    if title.is_empty() || title.chars().count() > 200 {
        return Err(MobileError::new(
            "VALIDATION_FAILED",
            "条目名称必须为 1 到 200 个字符",
        ));
    }
    let url = draft.url.trim();
    if !url.is_empty() && !url.starts_with("https://") && !url.starts_with("http://") {
        return Err(MobileError::new(
            "VALIDATION_FAILED",
            "网址必须以 http:// 或 https:// 开头",
        ));
    }
    if draft.remarks.chars().count() > 2000 {
        return Err(MobileError::new(
            "VALIDATION_FAILED",
            "备注不能超过 2000 个字符",
        ));
    }
    let mut field_names = HashSet::new();
    for field in &draft.fields {
        let name = field.name.trim();
        if name.is_empty() || name.chars().count() > 100 {
            return Err(MobileError::new(
                "VALIDATION_FAILED",
                "字段名称必须为 1 到 100 个字符",
            ));
        }
        if field.value.chars().count() > 10_000 {
            return Err(MobileError::new(
                "VALIDATION_FAILED",
                "字段值不能超过 10000 个字符",
            ));
        }
        if !field_names.insert(name.to_string()) {
            return Err(MobileError::new(
                "VALIDATION_FAILED",
                format!("字段名称重复：{name}"),
            ));
        }
    }
    Ok((
        normalize_names(&draft.tags, "标签")?,
        normalize_names(&draft.groups, "密码组")?,
    ))
}

fn update_field_values(existing: Option<&Value>, draft: &FieldRecord) -> Value {
    let mut field = existing
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_default();
    field.insert(
        "name".to_string(),
        Value::String(draft.name.trim().to_string()),
    );
    field.insert("value".to_string(), Value::String(draft.value.clone()));
    field.insert("copyable".to_string(), Value::Bool(draft.copyable));
    field.insert("hidden".to_string(), Value::Bool(draft.hidden));
    Value::Object(field)
}

fn build_entry(
    existing: Option<&Value>,
    id: &str,
    draft: &EntryDraft,
    tags: Vec<String>,
    groups: Vec<String>,
    now: &str,
) -> Value {
    let mut entry = existing
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_default();
    let old_fields = existing
        .and_then(Value::as_object)
        .and_then(|item| item.get("fields"))
        .and_then(Value::as_array);
    let fields = draft
        .fields
        .iter()
        .enumerate()
        .map(|(index, field)| {
            update_field_values(old_fields.and_then(|items| items.get(index)), field)
        })
        .collect();
    entry.insert("id".to_string(), Value::String(id.to_string()));
    entry.insert(
        "title".to_string(),
        Value::String(draft.title.trim().to_string()),
    );
    entry.insert(
        "url".to_string(),
        Value::String(draft.url.trim().to_string()),
    );
    entry.insert("starred".to_string(), Value::Bool(draft.starred));
    entry.insert("tags".to_string(), json!(tags));
    entry.insert("groups".to_string(), json!(groups));
    entry.insert("fields".to_string(), Value::Array(fields));
    entry.insert("remarks".to_string(), Value::String(draft.remarks.clone()));
    entry
        .entry("created_at".to_string())
        .or_insert_with(|| Value::String(now.to_string()));
    entry.insert("updated_at".to_string(), Value::String(now.to_string()));
    entry.insert("deleted".to_string(), Value::Bool(false));
    entry.insert("deleted_at".to_string(), Value::Null);
    Value::Object(entry)
}

fn ensure_meta(root: &mut Map<String, Value>, key: &str, names: &[String], now: &str) {
    let Some(meta) = root.get_mut(key).and_then(Value::as_object_mut) else {
        return;
    };
    for name in names {
        let item = meta
            .entry(name.clone())
            .or_insert_with(|| Value::Object(Map::new()));
        if let Some(item) = item.as_object_mut() {
            item.entry("description".to_string())
                .or_insert_with(|| Value::String(String::new()));
            item.entry("created_at".to_string())
                .or_insert_with(|| Value::String(now.to_string()));
            item.insert("updated_at".to_string(), Value::String(now.to_string()));
            if key == "tags_meta" {
                item.entry("color".to_string())
                    .or_insert_with(|| Value::String(entity_color(name)));
            }
        }
    }
}

pub fn save_entry(
    value: &mut Value,
    entry_id: Option<&str>,
    draft: &EntryDraft,
    now: &str,
) -> Result<String, MobileError> {
    let (tags, groups) = validate_draft(draft)?;
    let root = root_mut(value)?;
    let entries = array_mut(root, "entries")?;
    let id = entry_id
        .map(str::to_string)
        .unwrap_or_else(|| Uuid::new_v4().to_string());
    if let Some(index) = entries.iter().position(|entry| {
        entry
            .get("id")
            .and_then(Value::as_str)
            .is_some_and(|candidate| candidate == id)
    }) {
        let updated = build_entry(
            Some(&entries[index]),
            &id,
            draft,
            tags.clone(),
            groups.clone(),
            now,
        );
        entries[index] = updated;
    } else if entry_id.is_some() {
        return Err(MobileError::new("ENTRY_NOT_FOUND", "条目不存在"));
    } else {
        entries.push(build_entry(
            None,
            &id,
            draft,
            tags.clone(),
            groups.clone(),
            now,
        ));
    }
    ensure_meta(root, "tags_meta", &tags, now);
    ensure_meta(root, "groups_meta", &groups, now);
    Ok(id)
}

pub fn get_entry(value: &Value, id: &str) -> Result<EntryRecord, MobileError> {
    for key in ["entries", "deleted_entries"] {
        if let Some(entry) = array(root(value)?, key)?
            .iter()
            .find(|item| item.get("id").and_then(Value::as_str) == Some(id))
            .and_then(entry_record)
        {
            return Ok(entry);
        }
    }
    Err(MobileError::new("ENTRY_NOT_FOUND", "条目不存在"))
}

fn matches_search(entry: &EntryRecord, search: &str) -> bool {
    if search.is_empty() {
        return true;
    }
    let search = search.to_lowercase();
    entry.title.to_lowercase().contains(&search)
        || entry.url.to_lowercase().contains(&search)
        || entry.remarks.to_lowercase().contains(&search)
        || entry
            .tags
            .iter()
            .any(|value| value.to_lowercase().contains(&search))
        || entry
            .groups
            .iter()
            .any(|value| value.to_lowercase().contains(&search))
        || entry.fields.iter().any(|field| {
            field.name.to_lowercase().contains(&search)
                || field.value.to_lowercase().contains(&search)
        })
}

fn mask_hidden_fields(mut entry: EntryRecord) -> EntryRecord {
    for field in &mut entry.fields {
        if field.hidden {
            field.value = "••••••".to_string();
        }
    }
    entry
}

#[allow(clippy::too_many_arguments)]
pub fn list_entries(
    value: &Value,
    page: u32,
    page_size: u32,
    search: &str,
    tag: Option<&str>,
    group: Option<&str>,
    starred: Option<bool>,
    deleted: bool,
    revision: u64,
) -> Result<EntryPage, MobileError> {
    let key = if deleted {
        "deleted_entries"
    } else {
        "entries"
    };
    let mut entries: Vec<EntryRecord> = array(root(value)?, key)?
        .iter()
        .filter_map(entry_record)
        .filter(|entry| matches_search(entry, search.trim()))
        .filter(|entry| tag.is_none_or(|name| entry.tags.iter().any(|item| item == name)))
        .filter(|entry| group.is_none_or(|name| entry.groups.iter().any(|item| item == name)))
        .filter(|entry| starred.is_none_or(|value| entry.starred == value))
        .collect();
    entries.sort_by(|left, right| {
        right
            .updated_at
            .cmp(&left.updated_at)
            .then_with(|| left.title.cmp(&right.title))
    });
    let total = u32::try_from(entries.len()).unwrap_or(u32::MAX);
    let page_size = page_size.clamp(1, 200);
    let total_pages = total.div_ceil(page_size).max(1);
    let page = page.clamp(1, total_pages);
    let start = usize::try_from((page - 1).saturating_mul(page_size)).unwrap_or(usize::MAX);
    let items = entries
        .into_iter()
        .skip(start)
        .take(page_size as usize)
        .map(mask_hidden_fields)
        .collect();
    Ok(EntryPage {
        items,
        page,
        page_size,
        total,
        total_pages,
        revision,
    })
}

fn move_entry(
    value: &mut Value,
    id: &str,
    source: &str,
    target: Option<&str>,
    now: &str,
) -> Result<(), MobileError> {
    let root = root_mut(value)?;
    let source_entries = array_mut(root, source)?;
    let Some(index) = source_entries
        .iter()
        .position(|item| item.get("id").and_then(Value::as_str) == Some(id))
    else {
        return Err(MobileError::new("ENTRY_NOT_FOUND", "条目不存在"));
    };
    let mut entry = source_entries.remove(index);
    if let Some(entry) = entry.as_object_mut() {
        entry.insert("updated_at".to_string(), Value::String(now.to_string()));
        entry.insert(
            "deleted".to_string(),
            Value::Bool(target == Some("deleted_entries")),
        );
        entry.insert(
            "deleted_at".to_string(),
            target.map_or(Value::Null, |_| Value::String(now.to_string())),
        );
    }
    if let Some(target) = target {
        let target_entries = array_mut(root, target)?;
        if target_entries
            .iter()
            .any(|item| item.get("id").and_then(Value::as_str) == Some(id))
        {
            return Err(MobileError::new("ENTRY_CONFLICT", "目标位置已存在同一条目"));
        }
        target_entries.push(entry);
    }
    Ok(())
}

pub fn trash_entry(value: &mut Value, id: &str, now: &str) -> Result<(), MobileError> {
    move_entry(value, id, "entries", Some("deleted_entries"), now)
}

pub fn restore_entry(value: &mut Value, id: &str, now: &str) -> Result<(), MobileError> {
    move_entry(value, id, "deleted_entries", Some("entries"), now)
}

pub fn purge_entry(value: &mut Value, id: &str, now: &str) -> Result<(), MobileError> {
    move_entry(value, id, "deleted_entries", None, now)
}

fn entity_color(name: &str) -> String {
    const COLORS: [&str; 12] = [
        "#2563eb", "#0891b2", "#0f766e", "#15803d", "#65a30d", "#ca8a04", "#ea580c", "#dc2626",
        "#db2777", "#9333ea", "#4f46e5", "#475569",
    ];
    let hash = name.bytes().fold(2_166_136_261_u32, |value, byte| {
        (value ^ u32::from(byte)).wrapping_mul(16_777_619)
    });
    COLORS[hash as usize % COLORS.len()].to_string()
}

fn taxonomy_counts(value: &Value, field: &str) -> Result<HashMap<String, u32>, MobileError> {
    let mut counts = HashMap::new();
    for entry in array(root(value)?, "entries")? {
        if let Some(entry) = entry.as_object() {
            for name in string_list(entry.get(field)) {
                *counts.entry(name).or_insert(0) += 1;
            }
        }
    }
    Ok(counts)
}

pub fn list_taxonomy(value: &Value, kind: &str) -> Result<Vec<TaxonomyRecord>, MobileError> {
    let (meta_key, entry_field) = match kind {
        "tags" => ("tags_meta", "tags"),
        "groups" => ("groups_meta", "groups"),
        _ => return Err(MobileError::new("INVALID_TAXONOMY", "分类类型无效")),
    };
    let counts = taxonomy_counts(value, entry_field)?;
    let root = root(value)?;
    let meta = root
        .get(meta_key)
        .and_then(Value::as_object)
        .ok_or_else(|| MobileError::new("INVALID_PAYLOAD", "分类元数据无效"))?;
    let mut names: HashSet<String> = counts.keys().cloned().collect();
    names.extend(meta.keys().cloned());
    let mut items = Vec::new();
    for name in names {
        let raw = meta.get(&name).and_then(Value::as_object);
        items.push(TaxonomyRecord {
            name: name.clone(),
            description: raw
                .and_then(|item| item.get("description"))
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string(),
            color: raw
                .and_then(|item| item.get("color"))
                .and_then(Value::as_str)
                .map(str::to_string)
                .unwrap_or_else(|| entity_color(&name)),
            count: counts.get(&name).copied().unwrap_or(0),
            order_index: raw
                .and_then(|item| item.get("order_index"))
                .and_then(Value::as_i64),
        });
    }
    if kind == "groups" && items.iter().any(|item| item.order_index.is_some()) {
        items.sort_by(|left, right| {
            left.order_index
                .unwrap_or(i64::MAX)
                .cmp(&right.order_index.unwrap_or(i64::MAX))
                .then_with(|| right.count.cmp(&left.count))
                .then_with(|| left.name.cmp(&right.name))
        });
    } else {
        items.sort_by(|left, right| {
            right
                .count
                .cmp(&left.count)
                .then_with(|| left.name.cmp(&right.name))
        });
    }
    Ok(items)
}

pub fn save_taxonomy(
    value: &mut Value,
    kind: &str,
    old_name: Option<&str>,
    new_name: &str,
    description: &str,
    color: Option<&str>,
    now: &str,
) -> Result<(), MobileError> {
    let new_name = new_name.trim();
    if new_name.is_empty() || new_name.chars().count() > 50 {
        return Err(MobileError::new(
            "VALIDATION_FAILED",
            "名称必须为 1 到 50 个字符",
        ));
    }
    let (meta_key, entry_field) = match kind {
        "tags" => ("tags_meta", "tags"),
        "groups" => ("groups_meta", "groups"),
        _ => return Err(MobileError::new("INVALID_TAXONOMY", "分类类型无效")),
    };
    let root = root_mut(value)?;
    let old_name = old_name.map(str::trim).filter(|name| !name.is_empty());
    if let Some(old_name) = old_name {
        if old_name != new_name {
            for key in ["entries", "deleted_entries"] {
                for entry in array_mut(root, key)? {
                    let Some(entry) = entry.as_object_mut() else {
                        continue;
                    };
                    let names = string_list(entry.get(entry_field));
                    if names.iter().any(|name| name == old_name) {
                        let mut renamed = Vec::new();
                        for name in names {
                            let name = if name == old_name {
                                new_name.to_string()
                            } else {
                                name
                            };
                            if !renamed.contains(&name) {
                                renamed.push(name);
                            }
                        }
                        entry.insert(entry_field.to_string(), json!(renamed));
                        entry.insert("updated_at".to_string(), Value::String(now.to_string()));
                    }
                }
            }
        }
    }
    let meta = root
        .get_mut(meta_key)
        .and_then(Value::as_object_mut)
        .ok_or_else(|| MobileError::new("INVALID_PAYLOAD", "分类元数据无效"))?;
    if old_name != Some(new_name) && meta.contains_key(new_name) {
        return Err(MobileError::new("TAXONOMY_EXISTS", "该名称已存在"));
    }
    let mut record = old_name
        .and_then(|name| meta.remove(name))
        .and_then(|value| value.as_object().cloned())
        .unwrap_or_default();
    record.insert(
        "description".to_string(),
        Value::String(description.trim().to_string()),
    );
    record
        .entry("created_at".to_string())
        .or_insert_with(|| Value::String(now.to_string()));
    record.insert("updated_at".to_string(), Value::String(now.to_string()));
    if kind == "tags" {
        let color = color
            .filter(|value| value.len() == 7 && value.starts_with('#'))
            .map(str::to_lowercase)
            .unwrap_or_else(|| entity_color(new_name));
        record.insert("color".to_string(), Value::String(color));
    }
    meta.insert(new_name.to_string(), Value::Object(record));
    Ok(())
}

pub fn delete_taxonomy(
    value: &mut Value,
    kind: &str,
    name: &str,
    now: &str,
) -> Result<(), MobileError> {
    let (meta_key, entry_field) = match kind {
        "tags" => ("tags_meta", "tags"),
        "groups" => ("groups_meta", "groups"),
        _ => return Err(MobileError::new("INVALID_TAXONOMY", "分类类型无效")),
    };
    let root = root_mut(value)?;
    for key in ["entries", "deleted_entries"] {
        for entry in array_mut(root, key)? {
            let Some(entry) = entry.as_object_mut() else {
                continue;
            };
            let names = string_list(entry.get(entry_field));
            if names.iter().any(|item| item == name) {
                entry.insert(
                    entry_field.to_string(),
                    json!(names
                        .into_iter()
                        .filter(|item| item != name)
                        .collect::<Vec<_>>()),
                );
                entry.insert("updated_at".to_string(), Value::String(now.to_string()));
            }
        }
    }
    if let Some(meta) = root.get_mut(meta_key).and_then(Value::as_object_mut) {
        meta.remove(name);
    }
    Ok(())
}

pub fn delete_taxonomies(
    value: &mut Value,
    kind: &str,
    names: &[String],
    now: &str,
) -> Result<usize, MobileError> {
    let names = normalize_names(
        names,
        if kind == "tags" {
            "标签"
        } else {
            "密码组"
        },
    )?;
    for name in &names {
        delete_taxonomy(value, kind, name, now)?;
    }
    Ok(names.len())
}

pub fn save_group_order(value: &mut Value, names: &[String], now: &str) -> Result<(), MobileError> {
    let existing = list_taxonomy(value, "groups")?;
    let known: HashSet<String> = existing.iter().map(|item| item.name.clone()).collect();
    let mut ordered = normalize_names(names, "密码组")?;
    if ordered.iter().any(|name| !known.contains(name)) {
        return Err(MobileError::new(
            "GROUP_NOT_FOUND",
            "排序中包含不存在的密码组",
        ));
    }
    for item in existing {
        if !ordered.contains(&item.name) {
            ordered.push(item.name);
        }
    }
    let root = root_mut(value)?;
    let meta = root
        .get_mut("groups_meta")
        .and_then(Value::as_object_mut)
        .ok_or_else(|| MobileError::new("INVALID_PAYLOAD", "密码组元数据无效"))?;
    if names.is_empty() {
        for value in meta.values_mut() {
            if let Some(item) = value.as_object_mut() {
                item.remove("order_index");
            }
        }
        return Ok(());
    }
    for (index, name) in ordered.iter().enumerate() {
        let item = meta.entry(name.clone()).or_insert_with(|| json!({}));
        if let Some(item) = item.as_object_mut() {
            item.insert("order_index".to_string(), json!(index));
            item.insert("updated_at".to_string(), Value::String(now.to_string()));
        }
    }
    Ok(())
}

pub fn summary(value: &Value) -> Result<(u32, u32, u32, u32), MobileError> {
    let root = root(value)?;
    let entries = u32::try_from(array(root, "entries")?.len()).unwrap_or(u32::MAX);
    let deleted = u32::try_from(array(root, "deleted_entries")?.len()).unwrap_or(u32::MAX);
    let tags = u32::try_from(list_taxonomy(value, "tags")?.len()).unwrap_or(u32::MAX);
    let groups = u32::try_from(list_taxonomy(value, "groups")?.len()).unwrap_or(u32::MAX);
    Ok((entries, deleted, tags, groups))
}

#[cfg(test)]
mod tests {
    use super::*;

    const NOW: &str = "2026-07-12T00:00:00.000000Z";

    fn draft(title: &str) -> EntryDraft {
        EntryDraft {
            title: title.to_string(),
            url: "https://example.test".to_string(),
            starred: false,
            tags: vec!["测试".to_string()],
            groups: vec!["默认组".to_string()],
            fields: vec![FieldRecord {
                name: "账号".to_string(),
                value: "demo".to_string(),
                copyable: true,
                hidden: false,
            }],
            remarks: String::new(),
        }
    }

    #[test]
    fn editing_preserves_unknown_root_entry_and_field_values() {
        let mut value = new_document(NOW);
        value["future_root"] = json!({"retain": true});
        value["entries"] = json!([{
            "id": "entry-1",
            "title": "旧名称",
            "url": "",
            "starred": false,
            "tags": [],
            "groups": [],
            "fields": [{
                "name": "账号",
                "value": "old",
                "copyable": true,
                "hidden": false,
                "future_field": {"retain": "字段"}
            }],
            "remarks": "",
            "created_at": NOW,
            "updated_at": NOW,
            "deleted": false,
            "deleted_at": null,
            "future_entry": {"retain": "条目"}
        }]);

        save_entry(&mut value, Some("entry-1"), &draft("新名称"), NOW).unwrap();

        assert_eq!(value["future_root"]["retain"], true);
        assert_eq!(value["entries"][0]["future_entry"]["retain"], "条目");
        assert_eq!(
            value["entries"][0]["fields"][0]["future_field"]["retain"],
            "字段"
        );
        assert_eq!(value["entries"][0]["title"], "新名称");
    }

    #[test]
    fn mobile_preparation_assigns_stable_ids_and_defaults_without_dropping_extensions() {
        let mut value = json!({
            "version": "1.0",
            "created_at": NOW,
            "app_name": "SecretBase",
            "entries": [{
                "title": "旧条目",
                "fields": [{"name": "账号", "future": true}],
                "future_entry": {"retain": true}
            }],
            "deleted_entries": [],
            "tags_meta": {},
            "groups_meta": {},
            "future_root": {"retain": true}
        });
        assert!(prepare_for_mobile(&mut value, NOW).unwrap());
        let id = value["entries"][0]["id"].as_str().unwrap().to_string();
        assert!(!id.is_empty());
        assert_eq!(value["entries"][0]["fields"][0]["hidden"], Value::Null);
        assert_eq!(value["entries"][0]["future_entry"]["retain"], true);
        assert_eq!(value["future_root"]["retain"], true);
        assert!(!prepare_for_mobile(&mut value, NOW).unwrap());
        assert_eq!(value["entries"][0]["id"], id);
    }

    #[test]
    fn pagination_filters_and_clamps_pages() {
        let mut value = new_document(NOW);
        for index in 0..12 {
            let mut item = draft(&format!("条目 {index:02}"));
            item.tags = vec![if index % 2 == 0 { "偶数" } else { "奇数" }.to_string()];
            item.starred = index == 10;
            save_entry(&mut value, None, &item, NOW).unwrap();
        }

        let first = list_entries(&value, 1, 5, "", None, None, None, false, 7).unwrap();
        assert_eq!(first.total, 12);
        assert_eq!(first.total_pages, 3);
        assert_eq!(first.items.len(), 5);
        assert_eq!(first.revision, 7);

        let filtered =
            list_entries(&value, 99, 5, "条目", Some("偶数"), None, None, false, 8).unwrap();
        assert_eq!(filtered.total, 6);
        assert_eq!(filtered.page, 2);
        assert_eq!(filtered.items.len(), 1);

        let starred = list_entries(&value, 1, 20, "", None, None, Some(true), false, 8).unwrap();
        assert_eq!(starred.total, 1);
        assert_eq!(starred.items[0].title, "条目 10");
        assert_eq!(starred.items[0].fields[0].value, "demo");

        let mut secret = draft("隐藏字段");
        secret.fields[0].hidden = true;
        secret.fields[0].value = "不能出现在列表".to_string();
        save_entry(&mut value, None, &secret, NOW).unwrap();
        let masked =
            list_entries(&value, 1, 20, "不能出现在列表", None, None, None, false, 9).unwrap();
        assert_eq!(masked.total, 1);
        assert_eq!(masked.items[0].fields[0].value, "••••••");
        assert_eq!(
            get_entry(&value, &masked.items[0].id).unwrap().fields[0].value,
            "不能出现在列表"
        );
    }

    #[test]
    fn trash_restore_and_purge_move_the_same_record() {
        let mut value = new_document(NOW);
        let id = save_entry(&mut value, None, &draft("可恢复条目"), NOW).unwrap();

        trash_entry(&mut value, &id, NOW).unwrap();
        assert_eq!(summary(&value).unwrap().0, 0);
        assert_eq!(summary(&value).unwrap().1, 1);
        assert!(get_entry(&value, &id).unwrap().deleted);

        restore_entry(&mut value, &id, NOW).unwrap();
        assert_eq!(summary(&value).unwrap().0, 1);
        assert!(!get_entry(&value, &id).unwrap().deleted);

        trash_entry(&mut value, &id, NOW).unwrap();
        purge_entry(&mut value, &id, NOW).unwrap();
        assert!(get_entry(&value, &id).is_err());
    }

    #[test]
    fn taxonomy_rename_delete_and_custom_group_order_update_memberships() {
        let mut value = new_document(NOW);
        let mut first = draft("第一条");
        first.tags = vec!["旧标签".to_string(), "保留".to_string()];
        first.groups = vec!["工作".to_string()];
        save_entry(&mut value, None, &first, NOW).unwrap();
        let mut second = draft("第二条");
        second.tags = vec!["旧标签".to_string()];
        second.groups = vec!["个人".to_string()];
        save_entry(&mut value, None, &second, NOW).unwrap();

        save_taxonomy(
            &mut value,
            "tags",
            Some("旧标签"),
            "新标签",
            "已归并",
            Some("#2563eb"),
            NOW,
        )
        .unwrap();
        assert!(
            list_entries(&value, 1, 20, "", Some("新标签"), None, None, false, 1,)
                .unwrap()
                .total
                == 2
        );

        save_group_order(&mut value, &["个人".to_string(), "工作".to_string()], NOW).unwrap();
        let groups = list_taxonomy(&value, "groups").unwrap();
        assert_eq!(groups[0].name, "个人");
        assert_eq!(groups[1].name, "工作");

        delete_taxonomy(&mut value, "tags", "新标签", NOW).unwrap();
        assert!(list_taxonomy(&value, "tags")
            .unwrap()
            .iter()
            .all(|item| item.name != "新标签"));

        let deleted = delete_taxonomies(
            &mut value,
            "groups",
            &["工作".to_string(), "个人".to_string()],
            NOW,
        )
        .unwrap();
        assert_eq!(deleted, 2);
        assert!(list_taxonomy(&value, "groups").unwrap().is_empty());
    }
}
