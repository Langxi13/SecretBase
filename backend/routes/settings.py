import json
import logging
from fastapi import APIRouter, HTTPException
from models import Settings
from config import SETTINGS_PATH
from storage import is_unlocked

logger = logging.getLogger(__name__)
router = APIRouter()

# 默认设置
DEFAULT_SETTINGS = Settings()


def check_unlocked():
    """检查是否已解锁"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")


def load_settings() -> Settings:
    """加载设置"""
    try:
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return Settings(**data)
    except FileNotFoundError:
        return DEFAULT_SETTINGS
    except Exception as e:
        logger.error(f"加载设置失败: {e}")
        return DEFAULT_SETTINGS


def save_settings(settings: Settings):
    """保存设置"""
    try:
        with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(settings.dict(), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存设置失败: {e}")
        raise HTTPException(status_code=500, detail="保存设置失败")


@router.get("")
async def get_settings():
    """获取设置"""
    check_unlocked()
    settings = load_settings()
    
    return {
        "success": True,
        "data": settings.dict()
    }


@router.put("")
async def update_settings(updates: dict):
    """更新设置"""
    check_unlocked()
    settings = load_settings()
    
    # 字段名映射（前端驼峰 -> 后端下划线）
    field_mapping = {
        'pageSize': 'page_size',
        'autoLockMinutes': 'auto_lock_minutes',
        'autoBackupRetention': 'auto_backup_retention',
        'theme': 'theme',
        'language': 'language'
    }
    
    # 更新设置
    for key, value in updates.items():
        backend_key = field_mapping.get(key, key)
        if hasattr(settings, backend_key):
            setattr(settings, backend_key, value)
    
    # 验证设置
    try:
        settings = Settings(**settings.dict())
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"设置值无效: {e}")
    
    save_settings(settings)
    
    logger.info(f"设置已更新: {updates}")
    
    return {
        "success": True,
        "data": settings.dict(),
        "message": "设置已更新"
    }
