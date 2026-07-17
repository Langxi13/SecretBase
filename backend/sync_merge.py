"""Three-way merge for SecretBase Vault documents."""

from __future__ import annotations

import copy
import uuid
from typing import Any


ENTRY_KEYS = {"entries", "deleted_entries"}
META_KEYS = {"tags_meta", "groups_meta"}


def _entry_states(document: dict) -> dict[str, dict]:
    states: dict[str, dict] = {}
    for location in ("entries", "deleted_entries"):
        for raw in document.get(location, []) or []:
            if isinstance(raw, dict) and raw.get("id"):
                states[str(raw["id"])] = {
                    "location": location,
                    "entry": copy.deepcopy(raw),
                }
    return states


def _changed_sections(left: dict | None, right: dict | None) -> list[str]:
    if left is None or right is None:
        return ["状态"]
    labels = {
        "title": "标题",
        "url": "网址",
        "starred": "收藏",
        "tags": "标签",
        "groups": "密码组",
        "fields": "自定义字段",
        "remarks": "备注",
        "deleted": "删除状态",
    }
    changed = [label for key, label in labels.items() if left.get(key) != right.get(key)]
    return changed or ["条目元数据"]


def _state_summary(state: dict | None) -> dict:
    if state is None:
        return {"state": "absent", "title": "已彻底删除", "updated_at": "", "field_count": 0}
    entry = state["entry"]
    return {
        "state": "deleted" if state["location"] == "deleted_entries" else "active",
        "title": str(entry.get("title") or "未命名条目"),
        "updated_at": str(entry.get("updated_at") or ""),
        "field_count": len(entry.get("fields") or []),
    }


def _choice(base: Any, local: Any, remote: Any) -> tuple[bool, Any]:
    if local == remote:
        return True, copy.deepcopy(local)
    if local == base:
        return True, copy.deepcopy(remote)
    if remote == base:
        return True, copy.deepcopy(local)
    return False, copy.deepcopy(remote)


def _merge_entries(base: dict, local: dict, remote: dict, merged: dict, conflicts: list[dict]) -> None:
    base_states = _entry_states(base)
    local_states = _entry_states(local)
    remote_states = _entry_states(remote)
    merged["entries"] = []
    merged["deleted_entries"] = []
    for entry_id in sorted(set(base_states) | set(local_states) | set(remote_states)):
        base_state = base_states.get(entry_id)
        local_state = local_states.get(entry_id)
        remote_state = remote_states.get(entry_id)
        resolved, selected = _choice(base_state, local_state, remote_state)
        if not resolved:
            conflicts.append({
                "conflict_id": f"entry:{entry_id}",
                "kind": "entry",
                "entry_id": entry_id,
                "base": copy.deepcopy(base_state),
                "local": copy.deepcopy(local_state),
                "remote": copy.deepcopy(remote_state),
                "public": {
                    "conflict_id": f"entry:{entry_id}",
                    "kind": "entry",
                    "label": _state_summary(local_state)["title"],
                    "local": _state_summary(local_state),
                    "remote": _state_summary(remote_state),
                    "changed_sections": _changed_sections(
                        local_state and local_state["entry"],
                        remote_state and remote_state["entry"],
                    ),
                    "allow_both": local_state is not None and remote_state is not None,
                },
            })
        if selected is not None:
            merged[selected["location"]].append(selected["entry"])


def _merge_meta(kind: str, base: dict, local: dict, remote: dict, merged: dict, conflicts: list[dict]) -> None:
    base_meta = base.get(kind) if isinstance(base.get(kind), dict) else {}
    local_meta = local.get(kind) if isinstance(local.get(kind), dict) else {}
    remote_meta = remote.get(kind) if isinstance(remote.get(kind), dict) else {}
    result = {}
    label_kind = "标签" if kind == "tags_meta" else "密码组"
    for name in sorted(set(base_meta) | set(local_meta) | set(remote_meta)):
        resolved, selected = _choice(base_meta.get(name), local_meta.get(name), remote_meta.get(name))
        if not resolved:
            conflict_id = f"{kind}:{name}"
            conflicts.append({
                "conflict_id": conflict_id,
                "kind": kind,
                "name": name,
                "base": copy.deepcopy(base_meta.get(name)),
                "local": copy.deepcopy(local_meta.get(name)),
                "remote": copy.deepcopy(remote_meta.get(name)),
                "public": {
                    "conflict_id": conflict_id,
                    "kind": kind,
                    "label": f"{label_kind}：{name}",
                    "local": {"state": "present" if name in local_meta else "absent"},
                    "remote": {"state": "present" if name in remote_meta else "absent"},
                    "changed_sections": ["名称、简介、颜色或排序"],
                    "allow_both": False,
                },
            })
        if selected is not None:
            result[name] = selected
    merged[kind] = result


def _merge_root(base: dict, local: dict, remote: dict, merged: dict, conflicts: list[dict]) -> None:
    keys = (set(base) | set(local) | set(remote)) - ENTRY_KEYS - META_KEYS
    for key in sorted(keys):
        resolved, selected = _choice(base.get(key), local.get(key), remote.get(key))
        if not resolved:
            conflict_id = f"root:{key}"
            conflicts.append({
                "conflict_id": conflict_id,
                "kind": "root",
                "key": key,
                "base": copy.deepcopy(base.get(key)),
                "local": copy.deepcopy(local.get(key)),
                "remote": copy.deepcopy(remote.get(key)),
                "public": {
                    "conflict_id": conflict_id,
                    "kind": "root",
                    "label": f"Vault 扩展字段：{key}",
                    "local": {"state": "changed"},
                    "remote": {"state": "changed"},
                    "changed_sections": ["兼容扩展数据"],
                    "allow_both": False,
                },
            })
        if selected is not None:
            merged[key] = selected
        else:
            merged.pop(key, None)


def merge_documents(base: dict, local: dict, remote: dict) -> dict:
    merged = copy.deepcopy(remote)
    conflicts: list[dict] = []
    _merge_root(base, local, remote, merged, conflicts)
    _merge_entries(base, local, remote, merged, conflicts)
    _merge_meta("tags_meta", base, local, remote, merged, conflicts)
    _merge_meta("groups_meta", base, local, remote, merged, conflicts)
    return {"document": merged, "conflicts": conflicts}


def _remove_entry(document: dict, entry_id: str) -> None:
    for key in ENTRY_KEYS:
        document[key] = [item for item in document.get(key, []) if item.get("id") != entry_id]


def _insert_entry_state(document: dict, state: dict | None) -> None:
    if state is not None:
        document.setdefault(state["location"], []).append(copy.deepcopy(state["entry"]))


def _duplicate_local_entry(document: dict, state: dict) -> None:
    duplicate = copy.deepcopy(state["entry"])
    duplicate["id"] = str(uuid.uuid4())
    duplicate["title"] = f"{str(duplicate.get('title') or '未命名条目')}（本机冲突副本）"[:200]
    location = state["location"]
    duplicate["deleted"] = location == "deleted_entries"
    if location == "entries":
        duplicate["deleted_at"] = None
    document.setdefault(location, []).append(duplicate)


def apply_resolutions(plan: dict, resolutions: dict[str, str]) -> dict:
    document = copy.deepcopy(plan["document"])
    for conflict in plan["conflicts"]:
        conflict_id = conflict["conflict_id"]
        choice = resolutions.get(conflict_id)
        allowed = {"local", "remote"}
        if conflict["kind"] == "entry" and conflict["local"] is not None and conflict["remote"] is not None:
            allowed.add("both")
        if choice not in allowed:
            raise ValueError(f"冲突 {conflict_id} 缺少有效处理方式")

        if conflict["kind"] == "entry":
            _remove_entry(document, conflict["entry_id"])
            if choice == "both":
                _insert_entry_state(document, conflict["remote"])
                _duplicate_local_entry(document, conflict["local"])
            else:
                _insert_entry_state(document, conflict[choice])
        elif conflict["kind"] in META_KEYS:
            meta = document.setdefault(conflict["kind"], {})
            meta.pop(conflict["name"], None)
            selected = conflict[choice]
            if selected is not None:
                meta[conflict["name"]] = copy.deepcopy(selected)
        else:
            key = conflict["key"]
            selected = conflict[choice]
            if selected is None:
                document.pop(key, None)
            else:
                document[key] = copy.deepcopy(selected)
    return document


def public_conflicts(plan: dict) -> list[dict]:
    return [copy.deepcopy(conflict["public"]) for conflict in plan["conflicts"]]
