"""Metadata-only catalog and scope resolution for the AI assistant."""

from __future__ import annotations

from ai_services.organize import _filter_entries_for_organize
from ai_services.privacy import url_hostname


def normalize_assistant_view_filters(raw_filters: dict | None) -> dict:
    filters = dict(raw_filters) if isinstance(raw_filters, dict) else {}
    # The main list uses false to mean that the favorite-only toggle is inactive.
    if filters.get("starred") is False:
        filters.pop("starred", None)
    return filters


def entries_for_assistant_scope(vault, filters: dict | None, scope: str) -> list:
    if scope == "all":
        return [entry for entry in vault.entries if not entry.deleted]
    if scope == "selection":
        source = filters if isinstance(filters, dict) else {}
        entry_ids = source.get("entryIds") or source.get("entry_ids") or []
        if not entry_ids:
            return []
        return _filter_entries_for_organize(vault, {"entryIds": entry_ids})
    return _filter_entries_for_organize(vault, normalize_assistant_view_filters(filters))


def assistant_scope_catalog(
    vault,
    *,
    current_filters: dict | None,
    search: str = "",
    tag: str = "",
    group: str = "",
    starred: bool | None = None,
    selected_ids: list[str] | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    all_entries = [entry for entry in vault.entries if not entry.deleted]
    current_entries = entries_for_assistant_scope(vault, current_filters, "current_view")
    entries = list(all_entries)

    query = str(search or "").strip().casefold()
    if query:
        entries = [
            entry for entry in entries
            if query in (entry.title or "").casefold()
            or query in url_hostname(entry.url).casefold()
        ]
    tag = str(tag or "").strip()
    if tag:
        entries = [entry for entry in entries if tag in (entry.tags or [])]
    group = str(group or "").strip()
    if group:
        entries = [entry for entry in entries if group in (entry.groups or [])]
    if starred is not None:
        entries = [entry for entry in entries if bool(entry.starred) is starred]

    entries.sort(key=lambda entry: (entry.title or "").casefold())
    total = len(entries)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(max(1, page), total_pages)
    start = (page - 1) * page_size
    page_entries = entries[start:start + page_size]

    available_ids = {entry.id for entry in all_entries}
    valid_selected_ids = [
        entry_id for entry_id in (selected_ids or [])
        if entry_id in available_ids
    ]
    tag_names = sorted(
        {tag for entry in all_entries for tag in (entry.tags or [])},
        key=str.casefold,
    )
    group_names = sorted(
        {group for entry in all_entries for group in (entry.groups or [])},
        key=str.casefold,
    )

    return {
        "counts": {"all": len(all_entries), "current_view": len(current_entries)},
        "items": [
            {
                "id": entry.id,
                "title": entry.title,
                "hostname": url_hostname(entry.url),
                "starred": bool(entry.starred),
                "tags": list(entry.tags or []),
                "groups": list(entry.groups or []),
                "extra_taxonomy_count": (
                    max(0, len(entry.tags or []) - 2)
                    + max(0, len(entry.groups or []) - 1)
                ),
            }
            for entry in page_entries
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
        "tags": tag_names,
        "groups": group_names,
        "valid_selected_ids": valid_selected_ids,
    }
