import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from models import TagRequest, TagRenameRequest, TagMergeRequest, TagBatchDeleteRequest
from storage import is_unlocked, get_vault_data, save_vault_data
from tag_utils import (
    ensure_tag_meta,
    ensure_tags_meta,
    list_tag_entities,
    normalize_tag_name,
    remove_tag_from_entries,
    rename_tag_everywhere,
    tag_exists,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def check_unlocked():
    """检查是否已解锁"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")


@router.get("")
async def get_tags():
    """获取所有标签"""
    check_unlocked()
    vault = get_vault_data()
    return {
        "success": True,
        "data": {"tags": list_tag_entities(vault)}
    }


@router.post("")
async def create_tag(request: TagRequest):
    """创建空标签实体"""
    check_unlocked()
    name = normalize_tag_name(request.name or request.new_name or "")
    if not name:
        raise HTTPException(status_code=422, detail="标签名称不能为空")

    vault = get_vault_data()
    if tag_exists(vault, name):
        raise HTTPException(status_code=409, detail="标签已存在")

    ensure_tag_meta(vault, name, request.description, request.color)
    save_vault_data(vault)
    logger.info("创建标签成功")
    return {
        "success": True,
        "data": {"name": name},
        "message": "标签已创建"
    }


@router.put("/{tag_name}")
async def rename_tag(tag_name: str, request: TagRenameRequest):
    """重命名标签或更新标签元数据"""
    check_unlocked()
    old_name = normalize_tag_name(tag_name)
    new_name = normalize_tag_name(request.name or request.new_name or old_name)
    if not old_name or not new_name:
        raise HTTPException(status_code=422, detail="标签名称不能为空")

    vault = get_vault_data()
    if not tag_exists(vault, old_name):
        raise HTTPException(status_code=404, detail="标签不存在")

    if new_name != old_name and tag_exists(vault, new_name):
        raise HTTPException(status_code=409, detail="新标签名已存在")

    tags_meta = ensure_tags_meta(vault)
    meta = tags_meta.pop(old_name, {}) if new_name != old_name else tags_meta.get(old_name, {})
    if not isinstance(meta, dict):
        meta = {}
    meta["description"] = request.description.strip()
    meta["color"] = request.color or meta.get("color")
    meta["updated_at"] = datetime.now().isoformat()
    meta.setdefault("created_at", datetime.now().isoformat())

    affected_count = rename_tag_everywhere(vault, old_name, new_name) if new_name != old_name else 0
    ensure_tag_meta(vault, new_name, meta.get("description", ""), meta.get("color"))
    save_vault_data(vault)

    logger.info("更新标签成功")
    return {
        "success": True,
        "data": {
            "old_name": old_name,
            "new_name": new_name,
            "affected_count": affected_count
        },
        "message": "标签已更新"
    }


@router.post("/batch-delete")
async def batch_delete_tags(request: TagBatchDeleteRequest):
    """批量删除标签"""
    check_unlocked()
    names = [normalize_tag_name(name) for name in request.names if normalize_tag_name(name)]
    if not names:
        raise HTTPException(status_code=422, detail="标签名称不能为空")

    vault = get_vault_data()
    tags_meta = ensure_tags_meta(vault)
    deleted_tags = []
    missing_tags = []
    affected_entry_ids = set()

    for name in names:
        before_entry_ids = {
            entry.id
            for entry in vault.entries
            if not entry.deleted and name in (entry.tags or [])
        }
        entry_affected = remove_tag_from_entries(vault, name)
        meta_removed = name in tags_meta
        if meta_removed:
            tags_meta.pop(name, None)

        if entry_affected == 0 and not meta_removed:
            missing_tags.append(name)
            continue

        deleted_tags.append(name)
        affected_entry_ids.update(before_entry_ids)

    if not deleted_tags:
        raise HTTPException(status_code=404, detail="标签不存在")

    save_vault_data(vault)
    affected_count = len(affected_entry_ids)

    logger.info("批量删除标签: %s 个", len(deleted_tags))
    return {
        "success": True,
        "data": {
            "deleted_tags": deleted_tags,
            "missing_tags": missing_tags,
            "affected_count": affected_count
        },
        "message": f"已删除 {len(deleted_tags)} 个标签，影响 {affected_count} 个条目"
    }


@router.delete("/{tag_name}")
async def delete_tag(tag_name: str):
    """删除标签"""
    check_unlocked()
    name = normalize_tag_name(tag_name)
    if not name:
        raise HTTPException(status_code=422, detail="标签名称不能为空")

    vault = get_vault_data()
    affected_count = remove_tag_from_entries(vault, name)
    meta_removed = False
    if name in ensure_tags_meta(vault):
        vault.tags_meta.pop(name, None)
        meta_removed = True

    if affected_count == 0 and not meta_removed:
        raise HTTPException(status_code=404, detail="标签不存在")

    save_vault_data(vault)
    logger.info("删除标签成功")
    return {
        "success": True,
        "data": {"affected_count": affected_count},
        "message": f"标签已从 {affected_count} 个条目中移除"
    }


@router.post("/merge")
async def merge_tags(request: TagMergeRequest):
    """合并标签"""
    check_unlocked()
    vault = get_vault_data()
    source_tags = [normalize_tag_name(tag) for tag in request.source_tags if normalize_tag_name(tag)]
    target_tag = normalize_tag_name(request.target_tag)
    if not source_tags or not target_tag:
        raise HTTPException(status_code=422, detail="标签名称不能为空")

    for tag in source_tags:
        if not tag_exists(vault, tag):
            raise HTTPException(status_code=404, detail=f"标签不存在: {tag}")

    affected_entries = 0
    for entry in vault.entries:
        if not entry.deleted:
            has_source = any(tag in entry.tags for tag in source_tags)
            if has_source:
                entry.tags = [tag for tag in entry.tags if tag not in source_tags]
                if target_tag not in entry.tags:
                    entry.tags.append(target_tag)
                affected_entries += 1

    tags_meta = ensure_tags_meta(vault)
    for tag in source_tags:
        tags_meta.pop(tag, None)
    ensure_tag_meta(vault, target_tag, request.description, request.color)
    save_vault_data(vault)

    logger.info("合并标签: %s 个源标签", len(source_tags))
    return {
        "success": True,
        "data": {
            "merged_count": len(source_tags),
            "affected_entries": affected_entries
        },
        "message": f"已将 {len(source_tags)} 个标签合并，影响 {affected_entries} 个条目"
    }
