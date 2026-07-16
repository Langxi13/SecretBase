import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException

from models import BatchRequest, GroupOrderRequest, GroupRequest
from storage import is_unlocked, get_vault_data, save_vault_data
from utils import get_tag_color

logger = logging.getLogger(__name__)
router = APIRouter()


def check_unlocked():
    """检查是否已解锁"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")


def normalize_group_name(name: str) -> str:
    return str(name or "").strip()


def group_meta(vault, name: str) -> dict:
    raw = vault.groups_meta.get(name, {}) if isinstance(vault.groups_meta, dict) else {}
    return raw if isinstance(raw, dict) else {}


def group_order_index(meta: dict) -> int | None:
    try:
        return int(meta.get("order_index")) if meta.get("order_index") is not None else None
    except (TypeError, ValueError):
        return None


def group_order_enabled(vault) -> bool:
    return any(
        group_order_index(meta) is not None
        for meta in (vault.groups_meta or {}).values()
        if isinstance(meta, dict)
    )


def next_group_order_index(vault) -> int:
    indexes = [
        group_order_index(meta)
        for meta in (vault.groups_meta or {}).values()
        if isinstance(meta, dict)
    ]
    indexes = [index for index in indexes if index is not None]
    return max(indexes, default=-1) + 1


def sorted_group_items(stats: dict[str, dict]) -> list[dict]:
    groups = list(stats.values())
    has_custom_order = any(item.get("order_index") is not None for item in groups)
    if has_custom_order:
        return sorted(
            groups,
            key=lambda item: (
                item["order_index"] is None,
                item["order_index"] if item["order_index"] is not None else 0,
                -item["count"],
                item["name"],
            ),
        )
    return sorted(groups, key=lambda item: (-item["count"], item["name"]))


def collect_group_stats(vault) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for name, meta in (vault.groups_meta or {}).items():
        normalized = normalize_group_name(name)
        if normalized:
            meta = meta if isinstance(meta, dict) else {}
            stats[normalized] = {
                "name": normalized,
                "description": str(meta.get("description", "")),
                "count": 0,
                "updated_at": "",
                "color": get_tag_color(normalized),
                "order_index": group_order_index(meta),
            }

    for entry in vault.entries:
        if entry.deleted:
            continue
        for group_name in getattr(entry, "groups", []) or []:
            normalized = normalize_group_name(group_name)
            if not normalized:
                continue
            if normalized not in stats:
                stats[normalized] = {
                    "name": normalized,
                    "description": "",
                    "count": 0,
                    "updated_at": "",
                    "color": get_tag_color(normalized),
                    "order_index": None,
                }
            stats[normalized]["count"] += 1
            if entry.updated_at and entry.updated_at > stats[normalized]["updated_at"]:
                stats[normalized]["updated_at"] = entry.updated_at
    return stats


@router.get("")
async def get_groups():
    """获取所有密码组"""
    check_unlocked()
    vault = get_vault_data()

    groups = sorted_group_items(collect_group_stats(vault))
    return {"success": True, "data": {"groups": groups}}


@router.post("")
async def create_group(request: GroupRequest):
    """创建密码组元数据"""
    check_unlocked()
    name = normalize_group_name(request.name or "")
    if not name:
        raise HTTPException(status_code=422, detail="密码组名称不能为空")

    vault = get_vault_data()
    if not isinstance(vault.groups_meta, dict):
        vault.groups_meta = {}
    if name in vault.groups_meta:
        raise HTTPException(status_code=409, detail="密码组已存在")

    vault.groups_meta[name] = {
        "description": request.description.strip(),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    if group_order_enabled(vault):
        vault.groups_meta[name]["order_index"] = next_group_order_index(vault)
    save_vault_data(vault)
    logger.info("创建密码组成功")
    return {"success": True, "data": {"name": name}, "message": "密码组已创建"}


@router.post("/{group_name}/entries")
async def assign_entries_to_group(group_name: str, request: BatchRequest):
    """批量将现有条目加入指定密码组。"""
    check_unlocked()
    name = normalize_group_name(group_name)
    if not name:
        raise HTTPException(status_code=422, detail="密码组名称不能为空")

    vault = get_vault_data()
    exists = name in (vault.groups_meta or {}) or any(
        name in (getattr(entry, "groups", []) or [])
        for entry in vault.entries
        if not entry.deleted
    )
    if not exists:
        raise HTTPException(status_code=404, detail="密码组不存在")

    requested_ids = set(request.ids)
    updated_count = 0
    skipped_count = 0
    missing_count = 0
    now = datetime.now().isoformat()

    entries_by_id = {
        entry.id: entry
        for entry in vault.entries
        if not entry.deleted
    }
    for entry_id in requested_ids:
        entry = entries_by_id.get(entry_id)
        if not entry:
            missing_count += 1
            continue
        groups = list(getattr(entry, "groups", []) or [])
        if name in groups:
            skipped_count += 1
            continue
        groups.append(name)
        entry.groups = groups
        entry.updated_at = now
        updated_count += 1

    if not isinstance(vault.groups_meta, dict):
        vault.groups_meta = {}
    meta_changed = False
    if name not in vault.groups_meta:
        vault.groups_meta[name] = {
            "description": "",
            "created_at": now,
            "updated_at": now,
        }
        if group_order_enabled(vault):
            vault.groups_meta[name]["order_index"] = next_group_order_index(vault)
        meta_changed = True
    elif updated_count > 0:
        vault.groups_meta[name]["updated_at"] = now
        meta_changed = True

    if updated_count > 0 or meta_changed:
        save_vault_data(vault)

    logger.info(
        "批量加入密码组: updated=%s, skipped=%s, missing=%s",
        updated_count,
        skipped_count,
        missing_count,
    )
    return {
        "success": True,
        "data": {
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "missing_count": missing_count,
        },
        "message": f"已将 {updated_count} 个条目加入「{name}」"
    }


@router.post("/order")
async def update_group_order(request: GroupOrderRequest):
    """保存或清空密码组自定义排序。"""
    check_unlocked()
    vault = get_vault_data()
    if not isinstance(vault.groups_meta, dict):
        vault.groups_meta = {}

    stats = collect_group_stats(vault)
    if not request.names:
        for meta in vault.groups_meta.values():
            if isinstance(meta, dict):
                meta.pop("order_index", None)
        save_vault_data(vault)
        return {"success": True, "data": {"groups": sorted_group_items(collect_group_stats(vault))}, "message": "已恢复默认排序"}

    names = []
    seen = set()
    for raw_name in request.names:
        name = normalize_group_name(raw_name)
        if not name or name in seen:
            continue
        if name not in stats:
            raise HTTPException(status_code=422, detail=f"密码组不存在：{name}")
        names.append(name)
        seen.add(name)

    for group in sorted_group_items(stats):
        if group["name"] not in seen:
            names.append(group["name"])
            seen.add(group["name"])

    now = datetime.now().isoformat()
    for index, name in enumerate(names):
        meta = group_meta(vault, name)
        meta.setdefault("description", stats.get(name, {}).get("description", ""))
        meta.setdefault("created_at", now)
        meta["updated_at"] = now
        meta["order_index"] = index
        vault.groups_meta[name] = meta

    save_vault_data(vault)
    return {"success": True, "data": {"groups": sorted_group_items(collect_group_stats(vault))}, "message": "密码组排序已更新"}


@router.put("/{group_name}")
async def update_group(group_name: str, request: GroupRequest):
    """重命名或更新密码组简介"""
    check_unlocked()
    old_name = normalize_group_name(group_name)
    new_name = normalize_group_name(request.name or old_name)
    if not old_name or not new_name:
        raise HTTPException(status_code=422, detail="密码组名称不能为空")

    vault = get_vault_data()
    exists = old_name in (vault.groups_meta or {}) or any(
        old_name in (getattr(entry, "groups", []) or [])
        for entry in vault.entries
        if not entry.deleted
    )
    if not exists:
        raise HTTPException(status_code=404, detail="密码组不存在")
    if new_name != old_name:
        new_exists = new_name in (vault.groups_meta or {}) or any(
            new_name in (getattr(entry, "groups", []) or [])
            for entry in vault.entries
            if not entry.deleted
        )
        if new_exists:
            raise HTTPException(status_code=409, detail="新密码组名称已存在")

    if not isinstance(vault.groups_meta, dict):
        vault.groups_meta = {}
    now = datetime.now().isoformat()
    meta = group_meta(vault, old_name)
    meta["description"] = request.description.strip()
    meta["updated_at"] = now
    if "created_at" not in meta:
        meta["created_at"] = now

    if new_name != old_name:
        vault.groups_meta.pop(old_name, None)
        for entry in vault.entries:
            if not entry.deleted and old_name in (getattr(entry, "groups", []) or []):
                entry.groups = [new_name if item == old_name else item for item in entry.groups]
                entry.updated_at = now
        logger.info("重命名密码组成功")
    else:
        logger.info("更新密码组成功")

    vault.groups_meta[new_name] = meta
    save_vault_data(vault)
    return {"success": True, "data": {"old_name": old_name, "new_name": new_name}, "message": "密码组已更新"}


@router.delete("/{group_name}")
async def delete_group(group_name: str):
    """删除密码组元数据，并从条目中移除该组"""
    check_unlocked()
    name = normalize_group_name(group_name)
    if not name:
        raise HTTPException(status_code=422, detail="密码组名称不能为空")

    vault = get_vault_data()
    affected_count = 0
    now = datetime.now().isoformat()
    for entry in vault.entries:
        if not entry.deleted and name in (getattr(entry, "groups", []) or []):
            entry.groups = [item for item in entry.groups if item != name]
            entry.updated_at = now
            affected_count += 1

    meta_removed = False
    if isinstance(vault.groups_meta, dict) and name in vault.groups_meta:
        vault.groups_meta.pop(name, None)
        meta_removed = True

    if affected_count == 0 and not meta_removed:
        raise HTTPException(status_code=404, detail="密码组不存在")

    save_vault_data(vault)
    logger.info("删除密码组成功")
    return {
        "success": True,
        "data": {"affected_count": affected_count},
        "message": f"密码组已移除，影响 {affected_count} 个条目",
    }


@router.delete("/{group_name}/empty")
async def delete_empty_group(group_name: str):
    """Delete group metadata only when no active entry belongs to it."""
    check_unlocked()
    name = normalize_group_name(group_name)
    if not name:
        raise HTTPException(status_code=422, detail="密码组名称不能为空")
    vault = get_vault_data()
    if any(name in (getattr(entry, "groups", []) or []) for entry in vault.entries if not entry.deleted):
        raise HTTPException(status_code=409, detail="密码组仍包含条目，不能删除")
    if not isinstance(vault.groups_meta, dict) or name not in vault.groups_meta:
        raise HTTPException(status_code=404, detail="密码组不存在")
    vault.groups_meta.pop(name, None)
    save_vault_data(vault)
    logger.info("删除空密码组成功")
    return {"success": True, "data": {"name": name}, "message": "空密码组已删除"}
