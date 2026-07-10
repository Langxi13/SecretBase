"""AI 条目整理筛选、建议归一化与本地兜底规则。"""

import re
from datetime import datetime

from ai_services.parsing import _clean_text
from ai_services.prompts import ORGANIZE_GROUP_RULES
from tag_utils import ensure_entry_tags_meta


def _clean_name_list(raw_items) -> list[str]:
    if isinstance(raw_items, str):
        raw_items = re.split(r"[,，;；]+", raw_items)
    if not isinstance(raw_items, list):
        raw_items = []

    names = []
    seen = set()
    for item in raw_items:
        name = _clean_text(item, 50)
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _normalize_suggestion(item, valid_entry_ids: set[str]) -> dict | None:
    if not isinstance(item, dict):
        return None
    entry_id = _clean_text(item.get("entry_id") or item.get("id"), 100)
    if entry_id not in valid_entry_ids:
        return None

    descriptions = item.get("group_descriptions")
    if not isinstance(descriptions, dict):
        descriptions = {}
    cleaned_descriptions = {
        _clean_text(name, 50): _clean_text(description, 300)
        for name, description in descriptions.items()
        if _clean_text(name, 50)
    }

    return {
        "entry_id": entry_id,
        "selected": True,
        "add_tags": _clean_name_list(item.get("add_tags") or item.get("tags_to_add")),
        "remove_tags": _clean_name_list(item.get("remove_tags") or item.get("tags_to_remove")),
        "add_groups": _clean_name_list(item.get("add_groups") or item.get("groups_to_add")),
        "remove_groups": _clean_name_list(item.get("remove_groups") or item.get("groups_to_remove")),
        "group_descriptions": cleaned_descriptions,
        "reason": _clean_text(item.get("reason") or item.get("explanation"), 500),
    }


def _normalize_organize_payload(payload, valid_entry_ids: set[str]) -> tuple[list[dict], list[str]]:
    if isinstance(payload, list):
        raw_suggestions = payload
        raw_warnings = []
    elif isinstance(payload, dict):
        raw_suggestions = payload.get("suggestions") or payload.get("items") or payload.get("data") or []
        raw_warnings = payload.get("warnings") or []
    else:
        raw_suggestions = []
        raw_warnings = []

    if not isinstance(raw_suggestions, list):
        raw_suggestions = []

    suggestions = []
    seen = set()
    for item in raw_suggestions:
        suggestion = _normalize_suggestion(item, valid_entry_ids)
        if not suggestion or suggestion["entry_id"] in seen:
            continue
        seen.add(suggestion["entry_id"])
        suggestions.append(suggestion)

    warnings = [_clean_text(warning, 200) for warning in raw_warnings if _clean_text(warning, 200)] if isinstance(raw_warnings, list) else []
    return suggestions, list(dict.fromkeys(warnings))


def _filter_entries_for_organize(vault, filters: dict) -> list:
    filters = filters if isinstance(filters, dict) else {}
    entries = [entry for entry in vault.entries if not entry.deleted]

    entry_ids = filters.get("entryIds") or filters.get("entry_ids") or []
    if isinstance(entry_ids, str):
        entry_ids = [item.strip() for item in entry_ids.split(",") if item.strip()]
    if isinstance(entry_ids, list) and entry_ids:
        allowed_ids = set(str(item) for item in entry_ids)
        entries = [entry for entry in entries if entry.id in allowed_ids]

    search = str(filters.get("search") or "").strip().lower()
    search_scopes = filters.get("searchScopes") or filters.get("search_scopes") or []
    if isinstance(search_scopes, str):
        search_scopes = [item.strip() for item in search_scopes.split(",") if item.strip()]
    if search:
        if not search_scopes:
            entries = []
        else:
            scoped_entries = []
            for entry in entries:
                matched = False
                if "title" in search_scopes and search in entry.title.lower():
                    matched = True
                if "url" in search_scopes and search in (entry.url or "").lower():
                    matched = True
                if "tags" in search_scopes and any(search in tag.lower() for tag in entry.tags):
                    matched = True
                if "field_names" in search_scopes and any(search in field.name.lower() for field in entry.fields):
                    matched = True
                if "field_values" in search_scopes and any(search in field.value.lower() for field in entry.fields if not _field_is_hidden_for_organize(field)):
                    matched = True
                if "remarks" in search_scopes and search in (entry.remarks or "").lower():
                    matched = True
                if matched:
                    scoped_entries.append(entry)
            entries = scoped_entries

    tag = str(filters.get("tag") or "").strip()
    if tag:
        entries = [entry for entry in entries if tag in entry.tags]

    group = str(filters.get("group") or "").strip()
    if group:
        entries = [entry for entry in entries if group in (getattr(entry, "groups", []) or [])]

    required_tags = filters.get("tags") or []
    if isinstance(required_tags, str):
        required_tags = [item.strip() for item in required_tags.split(",") if item.strip()]
    if isinstance(required_tags, list) and required_tags:
        entries = [entry for entry in entries if all(tag in entry.tags for tag in required_tags)]

    if filters.get("untagged"):
        entries = [entry for entry in entries if not entry.tags]

    starred = filters.get("starred")
    if starred in ("true", True):
        entries = [entry for entry in entries if entry.starred]
    elif starred in ("false", False):
        entries = [entry for entry in entries if not entry.starred]

    created_from = str(filters.get("createdFrom") or filters.get("created_from") or "").strip()
    created_to = str(filters.get("createdTo") or filters.get("created_to") or "").strip()
    if created_from:
        entries = [entry for entry in entries if entry.created_at >= created_from]
    if created_to:
        entries = [entry for entry in entries if entry.created_at <= created_to]

    has_url = filters.get("hasUrl") if "hasUrl" in filters else filters.get("has_url")
    if has_url in ("yes", True, "true"):
        entries = [entry for entry in entries if bool(entry.url)]
    elif has_url in ("no", False, "false"):
        entries = [entry for entry in entries if not entry.url]

    has_remarks = filters.get("hasRemarks") if "hasRemarks" in filters else filters.get("has_remarks")
    if has_remarks in ("yes", True, "true"):
        entries = [entry for entry in entries if bool(entry.remarks)]
    elif has_remarks in ("no", False, "false"):
        entries = [entry for entry in entries if not entry.remarks]

    sort_by = str(filters.get("sortBy") or filters.get("sort_by") or "updated_at")
    sort_order = str(filters.get("sortOrder") or filters.get("sort_order") or "desc")
    if sort_by not in {"updated_at", "created_at", "title"}:
        sort_by = "updated_at"
    reverse = sort_order != "asc"
    entries.sort(key=lambda entry: getattr(entry, sort_by, "") or "", reverse=reverse)
    return entries


def _field_is_hidden_for_organize(field) -> bool:
    hidden = getattr(field, "hidden", None)
    if hidden is None:
        return bool(getattr(field, "copyable", False))
    return bool(hidden)


def _entry_for_ai_organize(entry) -> dict:
    return {
        "id": entry.id,
        "title": entry.title,
        "url": entry.url or "",
        "tags": entry.tags,
        "groups": getattr(entry, "groups", []) or [],
        "field_names": [field.name for field in entry.fields],
        "remarks": entry.remarks or "",
        "starred": entry.starred,
    }


def _append_unique(items: list[str], name: str) -> bool:
    if name and name not in items:
        items.append(name)
        return True
    return False


def _infer_organize_groups(entry, suggestion: dict, existing_groups: list[str]) -> list[str]:
    source_parts = [
        entry.title,
        entry.url or "",
        entry.remarks or "",
        " ".join(entry.tags),
        " ".join(getattr(entry, "groups", []) or []),
        " ".join(field.name for field in entry.fields),
        " ".join(suggestion.get("add_tags", [])),
    ]
    source_text = " ".join(part for part in source_parts if part).lower()
    current_groups = set(getattr(entry, "groups", []) or [])
    inferred = []

    for group in existing_groups:
        if group not in current_groups and group.lower() in source_text:
            _append_unique(inferred, group)

    for group, _description, keywords in ORGANIZE_GROUP_RULES:
        if group in current_groups:
            continue
        if any(keyword.lower() in source_text for keyword in keywords):
            _append_unique(inferred, group)

    return inferred[:2]


def _group_description(group: str) -> str:
    for group_name, description, _keywords in ORGANIZE_GROUP_RULES:
        if group == group_name:
            return description
    return f"{group}相关账号和密码条目"


def _fallback_group_suggestions(entries, existing_groups: list[str]) -> list[dict]:
    suggestions = []
    for entry in entries:
        suggestion = {
            "entry_id": entry.id,
            "selected": True,
            "add_tags": [],
            "remove_tags": [],
            "add_groups": [],
            "remove_groups": [],
            "group_descriptions": {},
            "reason": "根据标题、字段名、标签和备注推断适合加入这些密码组",
        }
        for group in _infer_organize_groups(entry, suggestion, existing_groups):
            if _append_unique(suggestion["add_groups"], group):
                suggestion["group_descriptions"][group] = _group_description(group)
        if suggestion["add_groups"]:
            suggestions.append(suggestion)
    return suggestions


def _organize_summary(suggestions: list[dict], existing_groups: list[str] | None = None) -> dict:
    selected = [item for item in suggestions if item.get("selected", True)]
    existing_group_set = set(existing_groups or [])
    unique_add_groups = {
        group
        for item in selected
        for group in item.get("add_groups", [])
    }
    unique_new_groups = unique_add_groups - existing_group_set
    return {
        "affected_entries": len(selected),
        "add_tags": sum(len(item.get("add_tags", [])) for item in selected),
        "remove_tags": sum(len(item.get("remove_tags", [])) for item in selected),
        "add_groups": len(unique_new_groups),
        "add_group_assignments": sum(len(item.get("add_groups", [])) for item in selected),
        "assigned_groups": len(unique_add_groups),
        "remove_groups": sum(len(item.get("remove_groups", [])) for item in selected),
    }


def existing_groups(vault) -> list[str]:
    return sorted({
        group
        for entry in vault.entries
        if not entry.deleted
        for group in (getattr(entry, "groups", []) or [])
    } | set((vault.groups_meta or {}).keys()))


def apply_organize_suggestions(vault, suggestions) -> dict:
    """应用用户确认后的条目整理建议。"""
    entries_by_id = {entry.id: entry for entry in vault.entries if not entry.deleted}
    if not isinstance(vault.groups_meta, dict):
        vault.groups_meta = {}

    updated_count = 0
    created_groups = []
    updated_groups = []
    now = datetime.now().isoformat()

    for suggestion in suggestions:
        if not suggestion.selected:
            continue
        entry = entries_by_id.get(suggestion.entry_id)
        if not entry:
            continue

        changed = False
        original_tags = list(entry.tags)
        original_groups = list(getattr(entry, "groups", []) or [])

        tags = [tag for tag in original_tags if tag not in suggestion.remove_tags]
        for tag in suggestion.add_tags:
            _append_unique(tags, tag)
        ensure_entry_tags_meta(vault, tags)

        groups = [group for group in original_groups if group not in suggestion.remove_groups]
        for group in suggestion.add_groups:
            if group not in groups:
                groups.append(group)
            if group not in vault.groups_meta:
                vault.groups_meta[group] = {
                    "description": str(suggestion.group_descriptions.get(group, "")).strip(),
                    "created_at": now,
                    "updated_at": now,
                }
                created_groups.append(group)
            elif suggestion.group_descriptions.get(group):
                meta = vault.groups_meta[group]
                if not isinstance(meta, dict):
                    meta = {"description": "", "created_at": now, "updated_at": now}
                    vault.groups_meta[group] = meta
                if not str(meta.get("description", "")).strip():
                    meta["description"] = str(suggestion.group_descriptions[group]).strip()
                    meta["updated_at"] = now
                    updated_groups.append(group)

        if tags != original_tags:
            entry.tags = tags
            changed = True
        if groups != original_groups:
            entry.groups = groups
            changed = True
        if changed:
            entry.updated_at = now
            updated_count += 1

    return {
        "updated_count": updated_count,
        "created_groups": sorted(set(created_groups)),
        "updated_groups": sorted(set(updated_groups)),
    }
