import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from models import EntryCreate, EntryUpdate, BatchRequest, BatchTagRequest, BatchStarRequest
from storage import (
    is_unlocked, get_vault_data, save_vault_data,
    get_entry, add_entry, update_entry, delete_entry
)

logger = logging.getLogger(__name__)
router = APIRouter()

SEARCH_SCOPE_KEYS = {"title", "url", "tags", "field_names", "field_values", "remarks"}


def check_unlocked():
    """检查是否已解锁"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")


@router.get("")
async def get_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    search: Optional[str] = None,
    search_scopes: Optional[str] = None,
    ids: Optional[str] = None,
    tag: Optional[str] = None,
    tags: Optional[str] = None,
    untagged: bool = False,
    starred: Optional[bool] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    updated_from: Optional[str] = None,
    updated_to: Optional[str] = None,
    has_url: Optional[bool] = None,
    has_remarks: Optional[bool] = None,
    sort_by: str = Query("updated_at", pattern="^(updated_at|created_at|title)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$")
):
    """获取条目列表"""
    check_unlocked()
    
    vault = get_vault_data()
    entries = [e for e in vault.entries if not e.deleted]

    if ids:
        id_set = {item.strip() for item in ids.split(",") if item.strip()}
        entries = [e for e in entries if e.id in id_set]
    
    # 搜索筛选
    if search:
        search_lower = search.lower()
        scopes = {
            item.strip() for item in search_scopes.split(",") if item.strip() in SEARCH_SCOPE_KEYS
        } if search_scopes else set()

        def field_matches(field) -> bool:
            if "field_names" in scopes and search_lower in field.name.lower():
                return True
            # 不搜索可复制字段的明文值，避免密码/API Key 等隐藏内容造成看似无关的命中。
            return "field_values" in scopes and (not field.copyable) and search_lower in field.value.lower()

        entries = [
            e for e in entries
            if ("title" in scopes and search_lower in e.title.lower())
            or ("url" in scopes and e.url and search_lower in e.url.lower())
            or ("tags" in scopes and any(search_lower in t.lower() for t in e.tags))
            or any(field_matches(f) for f in e.fields)
            or ("remarks" in scopes and e.remarks and search_lower in e.remarks.lower())
        ]
    
    # 标签筛选
    if tag:
        entries = [e for e in entries if tag in e.tags]

    if tags:
        required_tags = [t.strip() for t in tags.split(",") if t.strip()]
        if required_tags:
            entries = [e for e in entries if all(t in e.tags for t in required_tags)]

    if untagged:
        entries = [e for e in entries if not e.tags]
    
    # 星标筛选
    if starred:
        entries = [e for e in entries if e.starred]

    if created_from:
        entries = [e for e in entries if e.created_at >= created_from]
    if created_to:
        entries = [e for e in entries if e.created_at <= created_to]
    if updated_from:
        entries = [e for e in entries if e.updated_at >= updated_from]
    if updated_to:
        entries = [e for e in entries if e.updated_at <= updated_to]
    if has_url is True:
        entries = [e for e in entries if bool((e.url or "").strip())]
    elif has_url is False:
        entries = [e for e in entries if not (e.url or "").strip()]
    if has_remarks is True:
        entries = [e for e in entries if bool((e.remarks or "").strip())]
    elif has_remarks is False:
        entries = [e for e in entries if not (e.remarks or "").strip()]
    
    # 排序。导入旧数据或手工编辑 JSON 时可能出现空值，排序时统一归一化避免 500。
    def sort_key(e):
        if sort_by == "title":
            return (e.title or "").lower()
        return str(getattr(e, sort_by, "") or "")
    
    entries.sort(key=sort_key, reverse=(sort_order == "desc"))
    
    # 分页
    total = len(entries)
    start = (page - 1) * page_size
    end = start + page_size
    page_entries = entries[start:end]
    
    # 转换为响应格式（隐藏敏感字段）
    items = []
    for entry in page_entries:
        fields = []
        for f in entry.fields:
            fields.append({
                "name": f.name,
                "value": "••••••" if f.copyable else f.value,
                "copyable": f.copyable,
                "masked": f.copyable
            })
        items.append({
            "id": entry.id,
            "title": entry.title,
            "url": entry.url,
            "starred": entry.starred,
            "tags": entry.tags,
            "fields": fields,
            "remarks": entry.remarks,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at
        })
    
    return {
        "success": True,
        "data": {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size
            }
        }
    }


@router.get("/{entry_id}")
async def get_entry_detail(entry_id: str):
    """获取条目详情（包含明文字段）"""
    check_unlocked()
    
    entry = get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    
    fields = [{"name": f.name, "value": f.value, "copyable": f.copyable} for f in entry.fields]
    
    return {
        "success": True,
        "data": {
            "id": entry.id,
            "title": entry.title,
            "url": entry.url,
            "starred": entry.starred,
            "tags": entry.tags,
            "fields": fields,
            "remarks": entry.remarks,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at
        }
    }


@router.post("")
async def create_entry(entry_data: EntryCreate):
    """创建条目"""
    check_unlocked()
    
    entry = add_entry(entry_data)
    
    logger.info(f"创建条目: {entry.title}")
    
    return {
        "success": True,
        "data": {
            "id": entry.id,
            "title": entry.title,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at
        },
        "message": "条目创建成功"
    }


@router.put("/{entry_id}")
async def update_entry_api(entry_id: str, entry_data: EntryUpdate):
    """更新条目"""
    check_unlocked()
    
    entry = update_entry(entry_id, entry_data)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    
    logger.info(f"更新条目: {entry_id}")
    
    return {
        "success": True,
        "data": {"id": entry.id, "updated_at": entry.updated_at},
        "message": "条目更新成功"
    }


@router.delete("/{entry_id}")
async def delete_entry_api(entry_id: str):
    """删除条目（移到回收站）"""
    check_unlocked()
    
    success = delete_entry(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="条目不存在")
    
    logger.info(f"删除条目: {entry_id}")
    
    return {
        "success": True,
        "data": None,
        "message": "条目已移至回收站"
    }


@router.post("/batch-delete")
async def batch_delete(request: BatchRequest):
    """批量删除"""
    check_unlocked()
    
    deleted_count = 0
    for entry_id in request.ids:
        if delete_entry(entry_id):
            deleted_count += 1
    
    logger.info(f"批量删除: {deleted_count} 个条目")
    
    return {
        "success": True,
        "data": {"deleted_count": deleted_count},
        "message": f"已删除 {deleted_count} 个条目"
    }


@router.post("/batch-update-tags")
async def batch_update_tags(request: BatchTagRequest):
    """批量修改标签"""
    check_unlocked()
    
    vault = get_vault_data()
    updated_count = 0
    
    for entry in vault.entries:
        if entry.id in request.ids and not entry.deleted:
            for tag in request.add_tags:
                if tag not in entry.tags:
                    entry.tags.append(tag)
            for tag in request.remove_tags:
                if tag in entry.tags:
                    entry.tags.remove(tag)
            updated_count += 1
    
    save_vault_data(vault)
    
    logger.info(f"批量更新标签: {updated_count} 个条目")
    
    return {
        "success": True,
        "data": {"updated_count": updated_count},
        "message": f"已更新 {updated_count} 个条目的标签"
    }


@router.post("/batch-star")
async def batch_star(request: BatchStarRequest):
    """批量星标"""
    check_unlocked()
    
    vault = get_vault_data()
    updated_count = 0
    
    for entry in vault.entries:
        if entry.id in request.ids and not entry.deleted:
            entry.starred = request.starred
            updated_count += 1
    
    save_vault_data(vault)
    
    logger.info(f"批量星标: {updated_count} 个条目")
    
    return {
        "success": True,
        "data": {"updated_count": updated_count},
        "message": f"已更新 {updated_count} 个条目的星标状态"
    }
