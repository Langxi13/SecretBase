"""Canonical metadata-only DTOs used for every non-sensitive AI request."""

from __future__ import annotations

import math
import re
from urllib.parse import urlsplit


SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:password|passwd|token|secret|api[_ -]?key)\s*[:=]\s*\S+", re.IGNORECASE),
)


def url_hostname(value: str | None) -> str:
    try:
        parsed = urlsplit(str(value or ""))
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"}:
        return ""
    return (parsed.hostname or "").lower()


def _looks_high_entropy(value: str) -> bool:
    compact = re.sub(r"\s+", "", value)
    if len(compact) < 28 or not re.fullmatch(r"[A-Za-z0-9_+/=-]+", compact):
        return False
    counts = {char: compact.count(char) for char in set(compact)}
    entropy = -sum((count / len(compact)) * math.log2(count / len(compact)) for count in counts.values())
    return entropy >= 4.0


def detect_sensitive_metadata(strings: list[tuple[str, str]]) -> list[dict]:
    warnings = []
    for location, raw_value in strings:
        value = str(raw_value or "").strip()
        if not value:
            continue
        if any(pattern.search(value) for pattern in SECRET_PATTERNS) or _looks_high_entropy(value):
            warnings.append({"location": location, "preview": value[:24]})
    return warnings


def field_metadata(field, entry_ref: str, index: int) -> dict:
    hidden = getattr(field, "hidden", None)
    if hidden is None:
        hidden = bool(getattr(field, "copyable", False))
    return {
        "ref": f"{entry_ref}.F{index + 1:02d}",
        "name": field.name,
        "copyable": bool(getattr(field, "copyable", False)),
        "hidden": bool(hidden),
    }


def entry_metadata(entry, entry_ref: str) -> dict:
    return {
        "ref": entry_ref,
        "title": entry.title,
        "hostname": url_hostname(getattr(entry, "url", "")),
        "tags": list(getattr(entry, "tags", []) or []),
        "groups": list(getattr(entry, "groups", []) or []),
        "fields": [
            field_metadata(field, entry_ref, index)
            for index, field in enumerate(getattr(entry, "fields", []) or [])
        ],
    }


def taxonomy_metadata(vault) -> dict:
    tags = []
    for name, raw_meta in sorted((vault.tags_meta or {}).items()):
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        tags.append({
            "name": name,
            "description": str(meta.get("description") or ""),
            "color": str(meta.get("color") or ""),
        })
    groups = []
    for name, raw_meta in sorted((vault.groups_meta or {}).items()):
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        groups.append({
            "name": name,
            "description": str(meta.get("description") or ""),
        })
    return {"tags": tags, "groups": groups}


def metadata_warning_scan(entries: list[dict], taxonomy: dict) -> list[dict]:
    strings: list[tuple[str, str]] = []
    for entry in entries:
        ref = entry.get("ref", "条目")
        strings.append((f"{ref} 标题", entry.get("title", "")))
        strings.extend((f"{ref} 标签", value) for value in entry.get("tags", []))
        strings.extend((f"{ref} 密码组", value) for value in entry.get("groups", []))
        for field in entry.get("fields", []):
            strings.append((f"{field.get('ref', ref)} 字段名", field.get("name", "")))
    for tag in taxonomy.get("tags", []):
        strings.extend((("标签名", tag.get("name", "")), ("标签简介", tag.get("description", ""))))
    for group in taxonomy.get("groups", []):
        strings.extend((("密码组名", group.get("name", "")), ("密码组简介", group.get("description", ""))))
    return detect_sensitive_metadata(strings)
