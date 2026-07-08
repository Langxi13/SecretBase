from datetime import datetime
import re

from utils import get_tag_color

TAG_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_tag_name(name: str) -> str:
    return str(name or "").strip()


def normalize_tag_color(color: str | None, fallback_name: str) -> str:
    color = str(color or "").strip()
    if TAG_COLOR_PATTERN.match(color):
        return color.lower()
    return get_tag_color(fallback_name)


def ensure_tags_meta(vault) -> dict:
    if not isinstance(getattr(vault, "tags_meta", None), dict):
        vault.tags_meta = {}
    return vault.tags_meta


def tag_exists(vault, name: str) -> bool:
    normalized = normalize_tag_name(name)
    if not normalized:
        return False
    if normalized in ensure_tags_meta(vault):
        return True
    return any(normalized in (entry.tags or []) for entry in vault.entries if not entry.deleted)


def ensure_tag_meta(vault, name: str, description: str | None = None, color: str | None = None) -> dict | None:
    normalized = normalize_tag_name(name)
    if not normalized:
        return None

    now = datetime.now().isoformat()
    tags_meta = ensure_tags_meta(vault)
    raw = tags_meta.get(normalized)
    meta = raw if isinstance(raw, dict) else {}
    meta.setdefault("description", "")
    meta.setdefault("created_at", now)
    if description is not None:
        meta["description"] = str(description or "").strip()
    meta["color"] = normalize_tag_color(color or meta.get("color"), normalized)
    meta["updated_at"] = now
    tags_meta[normalized] = meta
    return meta


def ensure_entry_tags_meta(vault, tags: list[str] | None) -> None:
    for tag in tags or []:
        ensure_tag_meta(vault, tag)


def tag_counts(vault) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in vault.entries:
        if entry.deleted:
            continue
        for tag in entry.tags or []:
            normalized = normalize_tag_name(tag)
            if normalized:
                counts[normalized] = counts.get(normalized, 0) + 1
    return counts


def list_tag_entities(vault) -> list[dict]:
    counts = tag_counts(vault)
    tags_meta = ensure_tags_meta(vault)
    names = set(counts) | {normalize_tag_name(name) for name in tags_meta.keys()}
    tags = []
    for name in names:
        if not name:
            continue
        meta = tags_meta.get(name, {})
        if not isinstance(meta, dict):
            meta = {}
        tags.append({
            "name": name,
            "description": str(meta.get("description", "")),
            "color": normalize_tag_color(meta.get("color"), name),
            "count": counts.get(name, 0),
            "created_at": str(meta.get("created_at", "")),
            "updated_at": str(meta.get("updated_at", "")),
        })
    tags.sort(key=lambda item: (-item["count"], item["name"]))
    return tags


def remove_tag_from_entries(vault, name: str) -> int:
    affected_count = 0
    for entry in vault.entries:
        if not entry.deleted and name in (entry.tags or []):
            entry.tags = [tag for tag in entry.tags if tag != name]
            affected_count += 1
    return affected_count


def rename_tag_everywhere(vault, old_name: str, new_name: str) -> int:
    affected_count = 0
    for entry in vault.entries:
        if entry.deleted or old_name not in (entry.tags or []):
            continue
        renamed = [new_name if tag == old_name else tag for tag in entry.tags]
        deduped = []
        for tag in renamed:
            if tag not in deduped:
                deduped.append(tag)
        entry.tags = deduped
        affected_count += 1
    return affected_count
