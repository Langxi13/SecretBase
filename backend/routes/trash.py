import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from storage import is_unlocked, get_vault_data, save_vault_data

logger = logging.getLogger(__name__)
router = APIRouter()


def check_unlocked():
    """检查是否已解锁"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")


@router.get("")
async def get_trash(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000)
):
    """获取回收站条目"""
    check_unlocked()
    
    vault = get_vault_data()
    
    # 计算过期时间
    now = datetime.now()
    items = []
    
    for entry in vault.deleted_entries:
        deleted_at = datetime.fromisoformat(entry.deleted_at) if entry.deleted_at else now
        expires_at = deleted_at + timedelta(days=30)
        remaining_days = max(0, (expires_at - now).days)
        
        items.append({
            "id": entry.id,
            "title": entry.title,
            "deleted_at": entry.deleted_at,
            "expires_at": expires_at.isoformat(),
            "remaining_days": remaining_days
        })
    
    # 分页
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    
    return {
        "success": True,
        "data": {
            "items": page_items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size
            }
        }
    }


@router.post("/{entry_id}/restore")
async def restore_entry(entry_id: str):
    """恢复条目"""
    check_unlocked()
    
    vault = get_vault_data()
    
    # 查找条目
    entry = None
    for e in vault.deleted_entries:
        if e.id == entry_id:
            entry = e
            break
    
    if not entry:
        raise HTTPException(status_code=404, detail="条目不在回收站中")
    
    # 恢复条目
    restored_at = datetime.now().isoformat()
    entry.deleted = False
    entry.deleted_at = None
    entry.updated_at = restored_at
    vault.entries.append(entry)
    vault.deleted_entries.remove(entry)
    
    save_vault_data(vault)
    
    logger.info(f"恢复条目: {entry_id}")
    
    return {
        "success": True,
        "data": {"id": entry_id, "restored_at": restored_at},
        "message": "条目已恢复"
    }


@router.delete("/{entry_id}")
async def permanently_delete(entry_id: str):
    """彻底删除"""
    check_unlocked()
    
    vault = get_vault_data()
    
    # 查找条目
    entry = None
    for e in vault.deleted_entries:
        if e.id == entry_id:
            entry = e
            break
    
    if not entry:
        raise HTTPException(status_code=404, detail="条目不在回收站中")
    
    # 彻底删除
    vault.deleted_entries.remove(entry)
    save_vault_data(vault)
    
    logger.info(f"彻底删除: {entry_id}")
    
    return {
        "success": True,
        "data": None,
        "message": "条目已彻底删除"
    }


@router.post("/empty")
async def empty_trash():
    """清空回收站"""
    check_unlocked()
    
    vault = get_vault_data()
    
    deleted_count = len(vault.deleted_entries)
    vault.deleted_entries.clear()
    
    save_vault_data(vault)
    
    logger.info(f"清空回收站: {deleted_count} 个条目")
    
    return {
        "success": True,
        "data": {"deleted_count": deleted_count},
        "message": f"回收站已清空，删除了 {deleted_count} 个条目"
    }
