import logging
from fastapi import APIRouter, HTTPException
from models import TagRenameRequest, TagMergeRequest
from storage import is_unlocked, get_vault_data, save_vault_data
from utils import get_tag_color

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
    
    # 统计标签
    tags_count: dict[str, int] = {}
    for entry in vault.entries:
        if not entry.deleted:
            for tag in entry.tags:
                tags_count[tag] = tags_count.get(tag, 0) + 1
    
    # 构建响应
    tags = []
    for name, count in tags_count.items():
        tags.append({
            "name": name,
            "color": get_tag_color(name),
            "count": count
        })
    
    # 默认优先展示覆盖条目最多的标签，数量相同再按名称稳定排序。
    tags.sort(key=lambda t: (-t["count"], t["name"]))
    
    return {
        "success": True,
        "data": {"tags": tags}
    }


@router.put("/{tag_name}")
async def rename_tag(tag_name: str, request: TagRenameRequest):
    """重命名标签"""
    check_unlocked()
    
    vault = get_vault_data()
    
    # 检查标签是否存在
    exists = any(
        tag_name in entry.tags
        for entry in vault.entries
        if not entry.deleted
    )
    if not exists:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    # 检查新标签名是否已存在
    new_name_exists = any(
        request.new_name in entry.tags
        for entry in vault.entries
        if not entry.deleted
    )
    if new_name_exists:
        raise HTTPException(status_code=409, detail="新标签名已存在")
    
    # 重命名
    affected_count = 0
    for entry in vault.entries:
        if not entry.deleted and tag_name in entry.tags:
            entry.tags = [request.new_name if t == tag_name else t for t in entry.tags]
            affected_count += 1
    
    save_vault_data(vault)
    
    logger.info(f"重命名标签: {tag_name} -> {request.new_name}")
    
    return {
        "success": True,
        "data": {
            "old_name": tag_name,
            "new_name": request.new_name,
            "affected_count": affected_count
        },
        "message": "标签已重命名"
    }


@router.delete("/{tag_name}")
async def delete_tag(tag_name: str):
    """删除标签"""
    check_unlocked()
    
    vault = get_vault_data()
    
    # 从所有条目中移除
    affected_count = 0
    for entry in vault.entries:
        if not entry.deleted and tag_name in entry.tags:
            entry.tags.remove(tag_name)
            affected_count += 1
    
    if affected_count == 0:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    save_vault_data(vault)
    
    logger.info(f"删除标签: {tag_name}")
    
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
    
    # 检查源标签是否存在
    existing_tags = set()
    for entry in vault.entries:
        if not entry.deleted:
            existing_tags.update(entry.tags)
    
    for tag in request.source_tags:
        if tag not in existing_tags:
            raise HTTPException(status_code=404, detail=f"标签不存在: {tag}")
    
    # 合并
    affected_entries = 0
    for entry in vault.entries:
        if not entry.deleted:
            has_source = any(tag in entry.tags for tag in request.source_tags)
            if has_source:
                entry.tags = [t for t in entry.tags if t not in request.source_tags]
                if request.target_tag not in entry.tags:
                    entry.tags.append(request.target_tag)
                affected_entries += 1
    
    save_vault_data(vault)
    
    logger.info(f"合并标签: {request.source_tags} -> {request.target_tag}")
    
    return {
        "success": True,
        "data": {
            "merged_count": len(request.source_tags),
            "affected_entries": affected_entries
        },
        "message": f"已将 {len(request.source_tags)} 个标签合并，影响 {affected_entries} 个条目"
    }
