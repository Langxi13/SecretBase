"""Composite AI plan domains, deterministic ordering, and conflict detection."""

from __future__ import annotations

from collections import defaultdict


DOMAIN_ACTIONS = {
    "groups": {"create_group", "update_group", "assign_groups"},
    "tags": {"create_tag", "update_tag", "delete_tag", "merge_tags", "assign_tags"},
    "entry_structure": {"rename_entry", "rename_field", "add_empty_field", "set_field_flags"},
    "entry_creation": {"create_entry_template", "create_entry_from_field"},
    "navigation": {"open_entry"},
}
ALLOWED_ACTIONS = set().union(*DOMAIN_ACTIONS.values())

_EXECUTION_PRIORITY = {
    "create_group": 10,
    "create_tag": 10,
    "assign_groups": 20,
    "assign_tags": 20,
    "create_entry_template": 30,
    "create_entry_from_field": 30,
    "set_field_flags": 40,
    "add_empty_field": 45,
    "rename_field": 50,
    "rename_entry": 50,
    "update_group": 60,
    "update_tag": 60,
    "merge_tags": 70,
    "delete_tag": 80,
}


def action_domain(action_type: str) -> str:
    return next(name for name, action_types in DOMAIN_ACTIONS.items() if action_type in action_types)


def ordered_actions(actions: list[dict]) -> list[dict]:
    indexed = enumerate(actions)
    return [
        action for _index, action in sorted(
            indexed,
            key=lambda pair: (_EXECUTION_PRIORITY.get(pair[1].get("type"), 100), pair[0]),
        )
    ]


def _field_key(action: dict) -> tuple[str, int, str] | None:
    field = action.get("field") or {}
    entry_id = str(field.get("entry_id") or "")
    if not entry_id:
        return None
    try:
        index = int(field.get("index", -1))
    except (TypeError, ValueError):
        index = -1
    return entry_id, index, str(field.get("name") or "")


def detect_conflicts(actions: list[dict]) -> list[dict]:
    conflicts: list[dict] = []
    signatures = set()

    def add(items: list[dict], message: str, kind: str) -> None:
        action_ids = list(dict.fromkeys(str(item.get("id") or "") for item in items if item.get("id")))
        if len(action_ids) < 2:
            return
        signature = (tuple(sorted(action_ids)), kind)
        if signature in signatures:
            return
        signatures.add(signature)
        conflicts.append({
            "id": f"conflict-{len(conflicts) + 1}",
            "kind": kind,
            "action_ids": action_ids,
            "message": message,
        })

    def duplicate_by(action_type: str, key_builder, label: str, include_key: bool = True) -> None:
        grouped = defaultdict(list)
        for action in actions:
            if action.get("type") == action_type:
                key = key_builder(action)
                if key:
                    grouped[key].append(action)
        for key, items in grouped.items():
            if len(items) > 1:
                subject = f"{label}「{key}」" if include_key else label
                for index, item in enumerate(items):
                    for other in items[index + 1:]:
                        add([item, other], f"{subject}存在重复操作，请只保留一项。", "duplicate")

    duplicate_by("create_group", lambda item: item.get("name"), "密码组")
    duplicate_by("create_tag", lambda item: item.get("name"), "标签")
    duplicate_by("rename_entry", lambda item: item.get("entry_id"), "同一条目", False)
    duplicate_by("add_empty_field", lambda item: (item.get("entry_id"), item.get("name")), "同一空字段", False)
    duplicate_by("rename_field", _field_key, "同一字段重命名", False)
    duplicate_by("set_field_flags", _field_key, "同一字段属性调整", False)

    group_updates = [item for item in actions if item.get("type") == "update_group"]
    group_creates = [item for item in actions if item.get("type") == "create_group"]
    group_assignments = [item for item in actions if item.get("type") == "assign_groups"]
    for index, update in enumerate(group_updates):
        names = {update.get("group"), update.get("new_name")} - {None, ""}
        for other in group_updates[index + 1:]:
            other_names = {other.get("group"), other.get("new_name")} - {None, ""}
            if names.intersection(other_names):
                add([update, other], "多个密码组更新引用了相同名称，执行顺序存在歧义。", "group-update")
        destination = update.get("new_name")
        if destination:
            for create in group_creates:
                if create.get("name") == destination:
                    add([update, create], f"密码组改名目标「{destination}」同时被新建。", "group-destination")
            for assignment in group_assignments:
                if destination in set(assignment.get("add", []) + assignment.get("remove", [])):
                    add([update, assignment], f"密码组改名目标「{destination}」同时参与分配。", "group-assignment")

    tag_governance = [
        item for item in actions
        if item.get("type") in {"update_tag", "delete_tag", "merge_tags"}
    ]

    def governance_names(action: dict) -> set[str]:
        if action["type"] == "update_tag":
            return {action.get("tag"), action.get("new_name")} - {None, ""}
        if action["type"] == "delete_tag":
            return {action.get("tag")} - {None, ""}
        return set(action.get("source_tags", [])) | ({action.get("target_tag")} - {None, ""})

    for index, governance in enumerate(tag_governance):
        names = governance_names(governance)
        for other in tag_governance[index + 1:]:
            if names.intersection(governance_names(other)):
                add([governance, other], "多个标签治理操作引用了相同标签，执行结果存在歧义。", "tag-governance")
        if governance["type"] == "update_tag" and governance.get("new_name"):
            destination = governance["new_name"]
            for create in actions:
                if create.get("type") == "create_tag" and create.get("name") == destination:
                    add([governance, create], f"标签改名目标「{destination}」同时被新建。", "tag-destination")
            for assignment in actions:
                if assignment.get("type") == "assign_tags" and destination in set(
                    assignment.get("add", []) + assignment.get("remove", [])
                ):
                    add([governance, assignment], f"标签改名目标「{destination}」同时参与分配。", "tag-assignment")
        if governance["type"] == "delete_tag":
            deleted = governance.get("tag")
            for assignment in actions:
                if assignment.get("type") == "assign_tags" and deleted in set(
                    assignment.get("add", []) + assignment.get("remove", [])
                ):
                    add([governance, assignment], f"标签「{deleted}」同时被删除和分配。", "tag-delete")

    field_actions = defaultdict(list)
    for action in actions:
        key = _field_key(action)
        if key:
            field_actions[key].append(action)
    for items in field_actions.values():
        creations = [item for item in items if item["type"] == "create_entry_from_field"]
        mutations = [item for item in items if item["type"] in {"rename_field", "set_field_flags"}]
        for creation in creations:
            for mutation in mutations:
                add([creation, mutation], "同一字段同时用于创建条目并修改结构，复制结果存在歧义。", "field-source")

    renames = [item for item in actions if item.get("type") == "rename_field"]
    additions = [item for item in actions if item.get("type") == "add_empty_field"]
    for index, rename in enumerate(renames):
        field = rename.get("field") or {}
        entry_id = field.get("entry_id")
        destination = rename.get("new_name")
        for addition in additions:
            if addition.get("entry_id") == entry_id and addition.get("name") == destination:
                add([rename, addition], f"字段目标名称「{destination}」同时被新增。", "field-destination")
        for other in renames[index + 1:]:
            other_field = other.get("field") or {}
            if other_field.get("entry_id") != entry_id:
                continue
            if destination == other.get("new_name") or destination == other_field.get("name") or other.get("new_name") == field.get("name"):
                add([rename, other], "同一条目中的字段重命名目标互相占用。", "field-rename")

    return conflicts
