"""明文 vault 导入、冲突处理和实体元数据合并。"""

from datetime import datetime

from models import VaultData
from storage import get_vault_data, save_vault_data
from tag_utils import ensure_tag_meta, ensure_tags_meta


def _existing_entries(vault) -> tuple[dict, dict]:
    active = {entry.id: entry for entry in vault.entries}
    deleted = {entry.id: entry for entry in vault.deleted_entries}
    return active, deleted


def _import_conflicts(incoming: VaultData, active_entries: dict, deleted_entries: dict) -> list[dict]:
    conflicts = []
    for entry in incoming.entries:
        existing = active_entries.get(entry.id) or deleted_entries.get(entry.id)
        if existing:
            conflicts.append({
                "id": entry.id,
                "existing_title": existing.title,
                "import_title": entry.title,
                "existing_deleted": entry.id in deleted_entries,
            })
    return conflicts


def _referenced_names(entries, attribute: str) -> set[str]:
    return {
        name
        for entry in entries
        for name in (getattr(entry, attribute, []) or [])
        if name
    }


def _source_meta(source_meta, name: str) -> dict:
    value = source_meta.get(name, {}) if isinstance(source_meta, dict) else {}
    return value if isinstance(value, dict) else {}


def _clean_description(value) -> str:
    return str(value or "").strip()[:300]


def _merge_imported_tag_meta(vault, incoming: VaultData, imported_entries: list) -> bool:
    changed = False
    tags_meta = ensure_tags_meta(vault)
    for tag in _referenced_names(imported_entries, "tags"):
        source = _source_meta(incoming.tags_meta, tag)
        target = tags_meta.get(tag)
        if not isinstance(target, dict):
            ensure_tag_meta(vault, tag, _clean_description(source.get("description")), source.get("color"))
            changed = True
            continue

        description = _clean_description(source.get("description"))
        if description and not str(target.get("description", "")).strip():
            target["description"] = description
            target["updated_at"] = datetime.now().isoformat()
            changed = True
        if source.get("color") and not target.get("color"):
            ensure_tag_meta(vault, tag, None, source["color"])
            changed = True
    return changed


def _merge_imported_group_meta(vault, incoming: VaultData, imported_entries: list) -> bool:
    if not isinstance(vault.groups_meta, dict):
        vault.groups_meta = {}
    changed = False
    now = datetime.now().isoformat()
    for group in _referenced_names(imported_entries, "groups"):
        source = _source_meta(incoming.groups_meta, group)
        target = vault.groups_meta.get(group)
        if not isinstance(target, dict):
            vault.groups_meta[group] = {
                "description": _clean_description(source.get("description")),
                "created_at": now,
                "updated_at": now,
            }
            changed = True
            continue

        description = _clean_description(source.get("description"))
        if description and not str(target.get("description", "")).strip():
            target["description"] = description
            target["updated_at"] = now
            changed = True
    return changed


def preview_plain_import(incoming: VaultData) -> dict:
    """构建导入前预览，回收站中同 ID 的条目同样视为冲突。"""
    active_entries, deleted_entries = _existing_entries(get_vault_data())
    conflicts = _import_conflicts(incoming, active_entries, deleted_entries)
    conflict_ids = {item["id"] for item in conflicts}
    entries = [
        {
            "id": entry.id,
            "title": entry.title,
            "is_conflict": entry.id in conflict_ids,
            "field_count": len(entry.fields),
            "tag_count": len(entry.tags),
            "tags": entry.tags[:5],
        }
        for entry in incoming.entries
    ]
    return {
        "total_count": len(incoming.entries),
        "new_count": len(incoming.entries) - len(conflicts),
        "conflict_count": len(conflicts),
        "entries": entries,
        "conflicts": conflicts[:20],
    }


def import_plain_vault(
    data: dict,
    conflict_strategy: str = "skip",
    selected_entry_ids: list[str] | None = None,
    conflict_resolutions: dict[str, str] | None = None,
) -> dict:
    """合并明文导入条目，保留本地优先的标签与密码组元数据。"""
    incoming = VaultData(**data)
    if selected_entry_ids is not None:
        selected_ids = set(selected_entry_ids)
        incoming.entries = [entry for entry in incoming.entries if entry.id in selected_ids]

    conflict_resolutions = conflict_resolutions or {}
    vault = get_vault_data()
    active_entries, deleted_entries = _existing_entries(vault)
    conflicts = _import_conflicts(incoming, active_entries, deleted_entries)
    unresolved = [
        conflict
        for conflict in conflicts
        if conflict_resolutions.get(conflict["id"], conflict_strategy) == "ask"
    ]
    if unresolved:
        return {
            "imported_count": 0,
            "skipped_count": 0,
            "conflicts": unresolved,
            "needs_resolution": True,
        }

    imported_entries = []
    created_count = 0
    overwritten_count = 0
    skipped_count = 0

    for entry in incoming.entries:
        active_entry = active_entries.get(entry.id)
        deleted_entry = deleted_entries.get(entry.id)
        existing = active_entry or deleted_entry
        if existing and conflict_resolutions.get(entry.id, conflict_strategy) != "overwrite":
            skipped_count += 1
            continue

        entry.deleted = False
        entry.deleted_at = None
        if active_entry:
            vault.entries[vault.entries.index(active_entry)] = entry
            overwritten_count += 1
        elif deleted_entry:
            vault.deleted_entries.remove(deleted_entry)
            vault.entries.append(entry)
            overwritten_count += 1
        else:
            vault.entries.append(entry)
            created_count += 1
        active_entries[entry.id] = entry
        deleted_entries.pop(entry.id, None)
        imported_entries.append(entry)

    metadata_changed = _merge_imported_tag_meta(vault, incoming, imported_entries)
    metadata_changed = _merge_imported_group_meta(vault, incoming, imported_entries) or metadata_changed
    imported_count = len(imported_entries)
    if imported_count or metadata_changed:
        save_vault_data(vault)

    return {
        "imported_count": imported_count,
        "created_count": created_count,
        "overwritten_count": overwritten_count,
        "skipped_count": skipped_count,
        "conflicts": conflicts,
        "needs_resolution": False,
    }
