"""AI 标签治理建议的归一化与本地应用。"""

from datetime import datetime

from ai_services.organize import _clean_name_list
from ai_services.parsing import _clean_text
from ai_services.privacy import url_hostname
from tag_utils import (
    TAG_COLOR_PATTERN,
    ensure_entry_tags_meta,
    ensure_tag_meta,
    normalize_tag_name,
    rename_tag_everywhere,
)


def _entry_for_ai_tag_governance(entry, entry_ref: str | None = None) -> dict:
    return {
        "id": entry_ref or entry.id,
        "title": entry.title,
        "hostname": url_hostname(entry.url),
        "tags": entry.tags,
        "groups": getattr(entry, "groups", []) or [],
        "field_names": [field.name for field in entry.fields],
    }


def _clean_color(value) -> str | None:
    color = _clean_text(value, 20)
    return color.lower() if TAG_COLOR_PATTERN.match(color) else None


def _normalize_tag_governance_suggestion(item, valid_entry_ids: set[str]) -> dict | None:
    if not isinstance(item, dict):
        return None
    action = _clean_text(item.get("action"), 30)
    if action not in {"create_tag", "update_tag", "delete_tag", "merge_tags", "replace_tag", "assign_tag"}:
        return None

    raw_entry_ids = item.get("entry_ids") or item.get("entries") or []
    if isinstance(raw_entry_ids, str):
        raw_entry_ids = [part.strip() for part in raw_entry_ids.split(",") if part.strip()]
    entry_ids = []
    if isinstance(raw_entry_ids, list):
        for entry_id in raw_entry_ids:
            cleaned = _clean_text(entry_id, 100)
            if cleaned in valid_entry_ids and cleaned not in entry_ids:
                entry_ids.append(cleaned)

    return {
        "action": action,
        "selected": True,
        "tag": normalize_tag_name(item.get("tag") or item.get("old_tag") or item.get("old_name")) or None,
        "new_tag": normalize_tag_name(item.get("new_tag") or item.get("new_name")) or None,
        "source_tags": _clean_name_list(item.get("source_tags") or item.get("sources")),
        "target_tag": normalize_tag_name(item.get("target_tag") or item.get("target")) or None,
        "entry_ids": entry_ids,
        "description": _clean_text(item.get("description"), 300),
        "color": _clean_color(item.get("color")),
        "reason": _clean_text(item.get("reason") or item.get("explanation"), 500),
    }


def _normalize_tag_governance_payload(payload, valid_entry_ids: set[str]) -> tuple[list[dict], list[str]]:
    if isinstance(payload, list):
        raw_suggestions = payload
        raw_warnings = []
    elif isinstance(payload, dict):
        raw_suggestions = payload.get("suggestions") or payload.get("items") or payload.get("data") or []
        raw_warnings = payload.get("warnings") or []
    else:
        raw_suggestions = []
        raw_warnings = []

    suggestions = []
    if isinstance(raw_suggestions, list):
        for item in raw_suggestions:
            suggestion = _normalize_tag_governance_suggestion(item, valid_entry_ids)
            if suggestion:
                suggestions.append(suggestion)

    warnings = [_clean_text(warning, 200) for warning in raw_warnings if _clean_text(warning, 200)] if isinstance(raw_warnings, list) else []
    return suggestions, list(dict.fromkeys(warnings))


def _tag_governance_summary(suggestions: list[dict]) -> dict:
    selected = [item for item in suggestions if item.get("selected", True)]
    affected_entries = {
        entry_id
        for item in selected
        for entry_id in (item.get("entry_ids") or [])
    }
    summary = {
        "total_actions": len(selected),
        "affected_entries": len(affected_entries),
    }
    for action in ("create_tag", "update_tag", "delete_tag", "merge_tags", "replace_tag", "assign_tag"):
        summary[action] = sum(1 for item in selected if item.get("action") == action)
    return summary


def _add_tag_to_entry(entry, tag: str) -> bool:
    if not tag or tag in (entry.tags or []):
        return False
    entry.tags.append(tag)
    return True


def _replace_tag_in_entry(entry, old_tag: str, new_tag: str) -> bool:
    if old_tag not in (entry.tags or []):
        return False
    changed = False
    tags = []
    for tag in entry.tags:
        replacement = new_tag if tag == old_tag else tag
        if replacement not in tags:
            tags.append(replacement)
        if replacement != tag:
            changed = True
    entry.tags = tags
    return changed


def _tag_exists(vault, tag: str) -> bool:
    return bool(tag) and (
        tag in (vault.tags_meta or {})
        or any(tag in (entry.tags or []) for entry in vault.entries if not entry.deleted)
    )


def apply_tag_governance(vault, suggestions) -> dict:
    """应用用户确认后的标签治理建议，并返回变更统计。"""
    entries_by_id = {entry.id: entry for entry in vault.entries if not entry.deleted}
    updated_entry_ids: set[str] = set()
    applied_count = 0
    now = datetime.now().isoformat()

    def mark_updated(entry):
        entry.updated_at = now
        updated_entry_ids.add(entry.id)

    for suggestion in suggestions:
        if not suggestion.selected:
            continue

        action = suggestion.action
        tag = normalize_tag_name(suggestion.tag or "")
        new_tag = normalize_tag_name(suggestion.new_tag or "")
        target_tag = normalize_tag_name(suggestion.target_tag or "")
        source_tags = [normalize_tag_name(item) for item in suggestion.source_tags if normalize_tag_name(item)]
        entry_ids = [entry_id for entry_id in suggestion.entry_ids if entry_id in entries_by_id]
        changed = False

        if action == "create_tag":
            if not tag:
                continue
            ensure_tag_meta(vault, tag, suggestion.description, suggestion.color)
            for entry_id in entry_ids:
                entry = entries_by_id[entry_id]
                if _add_tag_to_entry(entry, tag):
                    mark_updated(entry)
                    changed = True
            changed = True

        elif action == "update_tag":
            if not tag or not _tag_exists(vault, tag):
                continue
            destination = new_tag or tag
            description = suggestion.description
            if destination != tag:
                rename_tag_everywhere(vault, tag, destination)
                if isinstance(vault.tags_meta, dict):
                    old_meta = vault.tags_meta.pop(tag, {})
                    if isinstance(old_meta, dict) and not description:
                        description = str(old_meta.get("description", ""))
                for entry in vault.entries:
                    if not entry.deleted and destination in (entry.tags or []):
                        mark_updated(entry)
                changed = True
            ensure_tag_meta(vault, destination, description, suggestion.color)
            changed = True

        elif action == "delete_tag":
            if not tag or not _tag_exists(vault, tag):
                continue
            affected = 0
            for entry in vault.entries:
                if not entry.deleted and tag in (entry.tags or []):
                    entry.tags = [item for item in entry.tags if item != tag]
                    mark_updated(entry)
                    affected += 1
            if isinstance(vault.tags_meta, dict) and tag in vault.tags_meta:
                vault.tags_meta.pop(tag, None)
                changed = True
            changed = changed or affected > 0

        elif action == "merge_tags":
            existing_sources = [source for source in source_tags if _tag_exists(vault, source)]
            if not existing_sources or not target_tag:
                continue
            ensure_tag_meta(vault, target_tag, suggestion.description, suggestion.color)
            for entry in vault.entries:
                if entry.deleted:
                    continue
                if any(source in (entry.tags or []) for source in existing_sources):
                    entry.tags = [item for item in entry.tags if item not in existing_sources]
                    _add_tag_to_entry(entry, target_tag)
                    mark_updated(entry)
                    changed = True
            if isinstance(vault.tags_meta, dict):
                for source in existing_sources:
                    if source in vault.tags_meta:
                        vault.tags_meta.pop(source, None)
                        changed = True

        elif action == "replace_tag":
            if not tag or not new_tag or not _tag_exists(vault, tag):
                continue
            ensure_tag_meta(vault, new_tag, suggestion.description, suggestion.color)
            target_entries = [entries_by_id[entry_id] for entry_id in entry_ids] if entry_ids else list(entries_by_id.values())
            for entry in target_entries:
                if _replace_tag_in_entry(entry, tag, new_tag):
                    mark_updated(entry)
                    changed = True

        elif action == "assign_tag":
            if not tag or not entry_ids:
                continue
            ensure_tag_meta(vault, tag, suggestion.description, suggestion.color)
            for entry_id in entry_ids:
                entry = entries_by_id[entry_id]
                if _add_tag_to_entry(entry, tag):
                    mark_updated(entry)
                    changed = True

        if changed:
            applied_count += 1

    if applied_count > 0:
        for entry in vault.entries:
            if not entry.deleted:
                ensure_entry_tags_meta(vault, entry.tags)

    return {
        "applied_count": applied_count,
        "updated_entries": len(updated_entry_ids),
    }
