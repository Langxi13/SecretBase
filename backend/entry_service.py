"""条目领域的写入操作，集中处理 vault 持久化与实体元数据。"""

from datetime import datetime

from models import Entry, EntryCreate, EntryUpdate
from storage import get_vault_data, save_vault_data
from tag_utils import ensure_entry_tags_meta


def get_entry(entry_id: str) -> Entry | None:
    """获取单个未删除条目。"""
    for entry in get_vault_data().entries:
        if entry.id == entry_id and not entry.deleted:
            return entry
    return None


def add_entry(entry_data: EntryCreate) -> Entry:
    """添加条目，并为引用的标签补齐元数据。"""
    vault = get_vault_data()
    entry = Entry(
        title=entry_data.title,
        url=entry_data.url or "",
        starred=entry_data.starred,
        tags=entry_data.tags,
        groups=entry_data.groups,
        fields=entry_data.fields,
        remarks=entry_data.remarks or "",
    )
    vault.entries.append(entry)
    ensure_entry_tags_meta(vault, entry.tags)
    save_vault_data(vault)
    return entry


def update_entry(entry_id: str, entry_data: EntryUpdate) -> Entry | None:
    """更新条目，并同步新增的标签元数据。"""
    vault = get_vault_data()
    entry = get_entry(entry_id)
    if not entry:
        return None

    if entry_data.title is not None:
        entry.title = entry_data.title
    if entry_data.url is not None:
        entry.url = entry_data.url
    if entry_data.starred is not None:
        entry.starred = entry_data.starred
    if entry_data.tags is not None:
        entry.tags = entry_data.tags
        ensure_entry_tags_meta(vault, entry.tags)
    if entry_data.groups is not None:
        entry.groups = entry_data.groups
    if entry_data.fields is not None:
        entry.fields = entry_data.fields
    if entry_data.remarks is not None:
        entry.remarks = entry_data.remarks

    entry.updated_at = datetime.now().isoformat()
    save_vault_data(vault)
    return entry


def delete_entry(entry_id: str) -> bool:
    """将条目移入回收站。"""
    return delete_entries([entry_id]) > 0


def delete_entries(entry_ids: list[str]) -> int:
    """批量将条目移入回收站，只执行一次 vault 写入。"""
    vault = get_vault_data()
    requested_ids = set(entry_ids)
    if not requested_ids:
        return 0

    deleted_at = datetime.now().isoformat()
    retained_entries = []
    deleted_entries = []
    for entry in vault.entries:
        if not entry.deleted and entry.id in requested_ids:
            entry.deleted = True
            entry.deleted_at = deleted_at
            entry.updated_at = deleted_at
            deleted_entries.append(entry)
        else:
            retained_entries.append(entry)
    if not deleted_entries:
        return 0

    vault.entries = retained_entries
    vault.deleted_entries.extend(deleted_entries)
    save_vault_data(vault)
    return len(deleted_entries)
