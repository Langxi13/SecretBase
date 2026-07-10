"""AI 操作计划的归一化、校验和本地应用。"""

from datetime import datetime

from fastapi import HTTPException

from models import Entry, FieldItem
from tag_utils import ensure_entry_tags_meta
from ai_services.organize import _append_unique, _clean_name_list, _field_is_hidden_for_organize
from ai_services.parsing import _clean_text, _normalize_fields, _to_bool


def _entry_for_ai_actions(entry) -> dict:
    return {
        "id": entry.id,
        "title": entry.title,
        "url": entry.url or "",
        "tags": entry.tags,
        "groups": getattr(entry, "groups", []) or [],
        "fields": [
            {
                "index": index,
                "name": field.name,
                "copyable": bool(getattr(field, "copyable", False)),
                "hidden": _field_is_hidden_for_organize(field),
            }
            for index, field in enumerate(entry.fields)
        ],
        "remarks": entry.remarks or "",
        "starred": entry.starred,
    }


def _clean_ai_action_fields(raw_fields) -> list[dict]:
    fields = _normalize_fields(raw_fields)
    cleaned = []
    seen_names = set()
    for field in fields:
        name = _clean_text(field.get("name"), 100)
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        cleaned.append({
            "name": name,
            "value": "",
            "copyable": bool(field.get("copyable")),
            "hidden": _to_bool(field.get("hidden"), bool(field.get("copyable"))),
        })
    return cleaned


def _normalize_ai_action(item, valid_entry_ids: set[str]) -> tuple[dict | None, str | None]:
    if not isinstance(item, dict):
        return None, "已忽略无效操作计划项"

    action_type = _clean_text(item.get("type") or item.get("action"), 50)
    allowed_types = {"create_group", "update_group", "create_entry", "create_entry_from_field", "update_entry"}
    if action_type not in allowed_types:
        return None, f"已忽略不支持的操作：{action_type or '未知操作'}"

    entry_id = _clean_text(item.get("entry_id") or item.get("id"), 100) or None
    source_entry_id = _clean_text(item.get("source_entry_id") or item.get("source_id"), 100) or None
    if action_type == "update_entry" and entry_id not in valid_entry_ids:
        return None, "已忽略引用未知条目的更新操作"
    if action_type == "create_entry_from_field" and source_entry_id not in valid_entry_ids:
        return None, "已忽略引用未知来源条目的字段拆分操作"

    raw_field_index = item.get("field_index")
    try:
        field_index = int(raw_field_index) if raw_field_index is not None else None
    except (TypeError, ValueError):
        field_index = None

    action = {
        "type": action_type,
        "selected": True,
        "group": _clean_text(item.get("group") or item.get("name"), 50) or None,
        "group_new": _clean_text(item.get("group_new") or item.get("new_group") or item.get("group_name_new"), 50) or None,
        "description": _clean_text(item.get("description"), 300),
        "title": _clean_text(item.get("title"), 200) or None,
        "url": _clean_text(item.get("url"), 2000) or None,
        "tags": _clean_name_list(item.get("tags")),
        "groups": _clean_name_list(item.get("groups")),
        "remarks": _clean_text(item.get("remarks") or item.get("note"), 2000),
        "fields": _clean_ai_action_fields(item.get("fields")),
        "entry_id": entry_id,
        "source_entry_id": source_entry_id,
        "field_index": field_index,
        "field_name": _clean_text(item.get("field_name"), 100) or None,
        "field_name_new": _clean_text(item.get("field_name_new") or item.get("new_field_name"), 100) or None,
        "add_tags": _clean_name_list(item.get("add_tags") or item.get("tags_to_add")),
        "remove_tags": _clean_name_list(item.get("remove_tags") or item.get("tags_to_remove")),
        "add_groups": _clean_name_list(item.get("add_groups") or item.get("groups_to_add")),
        "remove_groups": _clean_name_list(item.get("remove_groups") or item.get("groups_to_remove")),
        "reason": _clean_text(item.get("reason") or item.get("explanation"), 500),
    }
    if action["url"] and not action["url"].startswith(("http://", "https://")):
        action["url"] = None
    warning = None
    if action_type == "update_entry":
        has_field_context = action["field_index"] is not None or bool(action["field_name"]) or bool(action["field_name_new"])
        has_complete_rename = action["field_index"] is not None and bool(action["field_name"]) and bool(action["field_name_new"])
        if has_field_context and not has_complete_rename:
            action["field_index"] = None
            action["field_name"] = None
            action["field_name_new"] = None
            warning = "已忽略不完整的字段重命名信息"
    return action, warning


def _normalize_ai_actions_payload(payload, valid_entry_ids: set[str]) -> tuple[list[dict], list[str]]:
    if isinstance(payload, list):
        raw_actions = payload
        raw_warnings = []
    elif isinstance(payload, dict):
        raw_actions = payload.get("actions") or payload.get("suggestions") or payload.get("items") or payload.get("data") or []
        raw_warnings = payload.get("warnings") or []
    else:
        raw_actions = []
        raw_warnings = []

    actions = []
    warnings = [_clean_text(warning, 200) for warning in raw_warnings if _clean_text(warning, 200)] if isinstance(raw_warnings, list) else []
    if isinstance(raw_actions, list):
        for item in raw_actions:
            action, warning = _normalize_ai_action(item, valid_entry_ids)
            if action:
                actions.append(action)
            if warning:
                warnings.append(warning)
    return actions, list(dict.fromkeys(warnings))


def _attach_ai_action_entry_titles(actions: list[dict], entries_by_id: dict[str, object]) -> list[dict]:
    for action in actions:
        entry = entries_by_id.get(action.get("entry_id") or "")
        if entry:
            action["entry_title"] = entry.title
        source_entry = entries_by_id.get(action.get("source_entry_id") or "")
        if source_entry:
            action["source_entry_title"] = source_entry.title
    return actions


def _ai_actions_summary(actions: list[dict]) -> dict:
    selected = [item for item in actions if item.get("selected", True)]
    summary = {
        "total_actions": len(selected),
        "create_group": 0,
        "update_group": 0,
        "create_entry": 0,
        "create_entry_from_field": 0,
        "update_entry": 0,
    }
    for action in selected:
        action_type = action.get("type")
        if action_type in summary:
            summary[action_type] += 1
    return summary


def _ensure_group_meta(vault, group: str, description: str = "") -> bool:
    group = _clean_text(group, 50)
    if not group:
        return False
    if not isinstance(vault.groups_meta, dict):
        vault.groups_meta = {}
    now = datetime.now().isoformat()
    if group not in vault.groups_meta:
        vault.groups_meta[group] = {
            "description": _clean_text(description, 300),
            "created_at": now,
            "updated_at": now,
        }
        return True
    if description and not str(vault.groups_meta[group].get("description", "")).strip():
        vault.groups_meta[group]["description"] = _clean_text(description, 300)
        vault.groups_meta[group]["updated_at"] = now
    return False


def _append_group(groups: list[str], group: str) -> bool:
    group = _clean_text(group, 50)
    if group and group not in groups:
        groups.append(group)
        return True
    return False


def _group_exists(vault, group: str) -> bool:
    group = _clean_text(group, 50)
    if not group:
        return False
    return group in (vault.groups_meta or {}) or any(
        group in (getattr(entry, "groups", []) or [])
        for entry in vault.entries
        if not entry.deleted
    )


def _apply_group_update(vault, group: str, group_new: str | None = None, description: str = "") -> bool:
    old_name = _clean_text(group, 50)
    new_name = _clean_text(group_new, 50) or old_name
    description = _clean_text(description, 300)
    if not old_name or not new_name:
        return False
    if not isinstance(vault.groups_meta, dict):
        vault.groups_meta = {}

    now = datetime.now().isoformat()
    old_meta = vault.groups_meta.get(old_name, {})
    meta = dict(old_meta) if isinstance(old_meta, dict) else {}
    if not meta:
        meta = {"description": "", "created_at": now, "updated_at": now}

    changed = False
    if description and description != str(meta.get("description", "")):
        meta["description"] = description
        changed = True

    if new_name != old_name:
        vault.groups_meta.pop(old_name, None)
        for entry in vault.entries:
            if not entry.deleted and old_name in (getattr(entry, "groups", []) or []):
                entry.groups = [new_name if item == old_name else item for item in entry.groups]
                entry.updated_at = now
        changed = True

    if changed:
        meta["updated_at"] = now
    meta.setdefault("created_at", now)
    vault.groups_meta[new_name] = meta
    return changed


def apply_actions(vault, selected_actions) -> dict:
    """校验并应用已由用户勾选的 AI 操作计划。"""
    entries_by_id = {entry.id: entry for entry in vault.entries if not entry.deleted}

    for action in selected_actions:
        if action.type == "create_group":
            if not action.group:
                raise HTTPException(status_code=422, detail="创建密码组操作缺少名称")

        elif action.type == "update_group":
            if not action.group:
                raise HTTPException(status_code=422, detail="更新密码组操作缺少原名称")
            if not action.group_new and not action.description:
                raise HTTPException(status_code=422, detail="更新密码组操作缺少新名称或简介")
            if not _group_exists(vault, action.group):
                raise HTTPException(status_code=422, detail="更新密码组操作引用的密码组不存在")
            target_name = action.group_new or action.group
            if target_name != action.group and _group_exists(vault, target_name):
                raise HTTPException(status_code=422, detail="更新后的密码组名称已存在")

        elif action.type == "create_entry":
            if not action.title:
                raise HTTPException(status_code=422, detail="创建条目操作缺少标题")
            if any(field.value for field in action.fields):
                raise HTTPException(status_code=422, detail="AI 操作计划不能包含字段值")

        elif action.type == "create_entry_from_field":
            source = entries_by_id.get(action.source_entry_id or "")
            if not source:
                raise HTTPException(status_code=422, detail="字段拆分操作引用的来源条目不存在")
            if action.field_index is None or action.field_index >= len(source.fields):
                raise HTTPException(status_code=422, detail="字段拆分操作引用的字段索引无效")
            source_field = source.fields[action.field_index]
            if source_field.name != action.field_name:
                raise HTTPException(status_code=422, detail="字段拆分操作引用的字段名已变化，请重新生成计划")
            if not action.title:
                raise HTTPException(status_code=422, detail="字段拆分操作缺少新条目标题")

        elif action.type == "update_entry":
            entry = entries_by_id.get(action.entry_id or "")
            if not entry:
                raise HTTPException(status_code=422, detail="更新条目操作引用的条目不存在")
            wants_field_rename = bool(action.field_name_new)
            if wants_field_rename:
                if action.field_index is None or not action.field_name or not action.field_name_new:
                    raise HTTPException(status_code=422, detail="字段重命名必须提供字段索引、当前字段名和新字段名")
                if action.field_index >= len(entry.fields):
                    raise HTTPException(status_code=422, detail="字段重命名引用的字段索引无效")
                if entry.fields[action.field_index].name != action.field_name:
                    raise HTTPException(status_code=422, detail="字段重命名引用的字段名已变化，请重新生成计划")
                duplicate_names = [
                    field.name
                    for index, field in enumerate(entry.fields)
                    if index != action.field_index
                ]
                if action.field_name_new in duplicate_names:
                    raise HTTPException(status_code=422, detail="字段重命名后的名称已存在")

        else:
            raise HTTPException(status_code=422, detail="不支持的操作计划类型")

    created_entries = 0
    created_groups = 0
    updated_groups = 0
    updated_entry_ids: set[str] = set()
    applied_count = 0
    now = datetime.now().isoformat()

    for action in selected_actions:
        if action.type == "create_group":
            if _ensure_group_meta(vault, action.group or "", action.description):
                created_groups += 1
            applied_count += 1

        elif action.type == "update_group":
            if _apply_group_update(vault, action.group or "", action.group_new, action.description):
                updated_groups += 1
                old_name = action.group or ""
                new_name = action.group_new or old_name
                if new_name != old_name:
                    for entry in vault.entries:
                        if not entry.deleted and new_name in (getattr(entry, "groups", []) or []):
                            updated_entry_ids.add(entry.id)
            applied_count += 1

        elif action.type == "create_entry":
            groups = list(action.groups)
            tags = list(action.tags)
            for group in groups:
                if _ensure_group_meta(vault, group):
                    created_groups += 1
            ensure_entry_tags_meta(vault, tags)
            vault.entries.append(Entry(
                title=action.title or "AI 新建条目",
                url=action.url or "",
                tags=tags,
                groups=groups,
                fields=[
                    FieldItem(
                        name=field.name,
                        value="",
                        copyable=field.copyable,
                        hidden=_field_is_hidden_for_organize(field),
                    )
                    for field in action.fields
                ],
                remarks=action.remarks or "",
            ))
            created_entries += 1
            applied_count += 1

        elif action.type == "create_entry_from_field":
            source = entries_by_id[action.source_entry_id or ""]
            source_field = source.fields[action.field_index]
            groups = list(action.groups)
            tags = list(action.tags)
            for group in groups:
                if _ensure_group_meta(vault, group):
                    created_groups += 1
            ensure_entry_tags_meta(vault, tags)
            vault.entries.append(Entry(
                title=action.title or source_field.name,
                url=action.url or source.url or "",
                tags=tags,
                groups=groups,
                fields=[FieldItem(
                    name=source_field.name,
                    value=source_field.value,
                    copyable=source_field.copyable,
                    hidden=_field_is_hidden_for_organize(source_field),
                )],
                remarks=action.remarks or f"由 {source.title} 的字段「{source_field.name}」拆分生成",
            ))
            created_entries += 1
            applied_count += 1

        elif action.type == "update_entry":
            entry = entries_by_id[action.entry_id or ""]
            changed = False
            if action.title and action.title != entry.title:
                entry.title = action.title
                changed = True
            if action.url is not None and action.url != (entry.url or ""):
                entry.url = action.url
                changed = True
            if action.remarks and action.remarks != (entry.remarks or ""):
                entry.remarks = action.remarks
                changed = True

            tags = [tag for tag in (entry.tags or []) if tag not in action.remove_tags]
            for tag in action.add_tags:
                if tag not in tags:
                    tags.append(tag)
            if tags != (entry.tags or []):
                entry.tags = tags
                ensure_entry_tags_meta(vault, entry.tags)
                changed = True

            groups = [group for group in (getattr(entry, "groups", []) or []) if group not in action.remove_groups]
            for group in action.add_groups:
                if _append_group(groups, group) and _ensure_group_meta(vault, group):
                    created_groups += 1
            if groups != (getattr(entry, "groups", []) or []):
                entry.groups = groups
                changed = True

            if action.field_index is not None and action.field_name_new:
                entry.fields[action.field_index].name = action.field_name_new
                changed = True

            if changed:
                entry.updated_at = now
                updated_entry_ids.add(entry.id)
            applied_count += 1

    return {
        "applied_count": applied_count,
        "created_entries": created_entries,
        "created_groups": created_groups,
        "updated_groups": updated_groups,
        "updated_entries": len(updated_entry_ids),
    }
