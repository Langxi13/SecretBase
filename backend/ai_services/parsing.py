"""AI 文本解析结果的防御性归一化。"""

import re


def _clean_text(value, max_length: int = 10000) -> str:
    return str(value or "").strip()[:max_length]


def _to_bool(value, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "是", "可复制"}:
            return True
        if normalized in {"false", "no", "0", "否", "不可复制"}:
            return False
    return bool(value)


def _normalize_field(field):
    if isinstance(field, (str, int, float, bool)):
        field = {"name": "内容", "value": field, "copyable": False, "hidden": False}
    if not isinstance(field, dict):
        return None
    name = _clean_text(field.get("name") or field.get("label") or field.get("key") or field.get("field"), 100)
    if not name:
        return None
    raw_value = field.get("value")
    if raw_value is None:
        raw_value = field.get("text") or field.get("content") or field.get("val") or ""
    copyable = _to_bool(field.get("copyable"), True)
    return {
        "name": name,
        "value": _clean_text(raw_value, 10000),
        "copyable": copyable,
        "hidden": _to_bool(field.get("hidden"), copyable)
    }


def _normalize_fields(raw_fields):
    if isinstance(raw_fields, dict):
        raw_fields = [
            {"name": key, "value": value, "copyable": True, "hidden": True}
            for key, value in raw_fields.items()
        ]
    if not isinstance(raw_fields, list):
        raw_fields = []

    fields = []
    seen_field_names = set()
    for field in raw_fields:
        normalized = _normalize_field(field)
        if not normalized or normalized["name"] in seen_field_names:
            continue
        seen_field_names.add(normalized["name"])
        fields.append(normalized)
    return fields


def _normalize_tags(raw_tags):
    if isinstance(raw_tags, str):
        raw_tags = re.split(r"[,，;；]+", raw_tags)
    if not isinstance(raw_tags, list):
        raw_tags = []

    tags = []
    seen_tags = set()
    for tag in raw_tags:
        normalized_tag = _clean_text(tag, 50)
        if not normalized_tag or normalized_tag in seen_tags:
            continue
        seen_tags.add(normalized_tag)
        tags.append(normalized_tag)
    return tags


def _normalize_entry(entry, index: int = 0):
    if not isinstance(entry, dict):
        entry = {}

    title = _clean_text(entry.get("title") or entry.get("name") or entry.get("site") or entry.get("service"), 200) or f"AI 解析条目 {index + 1}"
    url = _clean_text(entry.get("url") or entry.get("link") or entry.get("website"), 2000)
    if url and not url.startswith(("http://", "https://")):
        url = ""

    fields = _normalize_fields(entry.get("fields") or entry.get("field_items") or entry.get("credentials"))
    tags = _normalize_tags(entry.get("tags") or entry.get("labels") or entry.get("categories"))
    groups = _normalize_tags(entry.get("groups") or entry.get("password_groups") or entry.get("folders"))

    return {
        "title": title,
        "url": url,
        "fields": fields,
        "tags": tags,
        "groups": groups,
        "remarks": _clean_text(entry.get("remarks") or entry.get("note") or entry.get("notes") or entry.get("comment"), 2000)
    }


def _normalize_ai_payload(payload):
    if isinstance(payload, list):
        raw_entries = payload
    elif isinstance(payload, dict) and isinstance(payload.get("entries"), list):
        raw_entries = payload["entries"]
    elif isinstance(payload, dict) and isinstance(payload.get("parsed_entries"), list):
        raw_entries = payload["parsed_entries"]
    elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
        raw_entries = payload["items"]
    elif isinstance(payload, dict) and isinstance(payload.get("accounts"), list):
        raw_entries = payload["accounts"]
    elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
        raw_entries = payload["records"]
    elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
        raw_entries = payload["data"]
    elif isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return _normalize_ai_payload(payload["data"])
    elif isinstance(payload, dict):
        raw_entries = [payload]
    else:
        raw_entries = [{}]

    entries = [_normalize_entry(entry, index) for index, entry in enumerate(raw_entries)]
    entries = [entry for entry in entries if entry["title"] or entry["fields"] or entry["tags"] or entry["groups"]]
    if not entries:
        entries = [_normalize_entry({}, 0)]
    return entries


def _quality_warnings(entries, source_text: str) -> list[str]:
    warnings = []
    if len(source_text) > 3000:
        warnings.append("输入内容较长，建议分批解析并逐条检查结果。")
    if len(source_text.splitlines()) > 60:
        warnings.append("输入行数较多，AI 可能误分或合并条目，请重点检查。")
    if len(entries) > 8:
        warnings.append("解析结果条目较多，请逐条确认后再创建。")
    if any(not entry.get("fields") for entry in entries):
        warnings.append("部分条目没有字段，可能需要手动补充。")
    if any(entry.get("title", "").startswith("AI 解析条目") for entry in entries):
        warnings.append("部分条目标题由系统兜底生成，建议手动改成更明确的标题。")
    return list(dict.fromkeys(warnings))
