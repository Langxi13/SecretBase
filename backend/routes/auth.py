import secrets
import time
import logging
import json
from fastapi import APIRouter, HTTPException
from config import SETTINGS_PATH
from models import AuthRequest, ChangePasswordRequest, Settings
from storage import (
    is_initialized, is_unlocked, unlock_vault, lock_vault,
    init_vault, change_vault_password, create_session_token
)

logger = logging.getLogger(__name__)
router = APIRouter()

# 速率限制
_unlock_attempts: list[float] = []
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300


def _load_auto_lock_minutes() -> int:
    try:
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            return Settings(**json.load(f)).auto_lock_minutes
    except Exception:
        return Settings().auto_lock_minutes


def _check_rate_limit():
    """检查解锁尝试速率"""
    now = time.time()
    _unlock_attempts[:] = [t for t in _unlock_attempts if now - t < WINDOW_SECONDS]
    
    if len(_unlock_attempts) >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="尝试次数过多，请 5 分钟后再试"
        )


@router.get("/status")
async def auth_status():
    """查询锁定状态"""
    initialized = is_initialized()
    locked = not is_unlocked()
    
    return {
        "success": True,
        "data": {
            "locked": locked,
            "initialized": initialized,
            "auto_lock_minutes": _load_auto_lock_minutes()
        }
    }


@router.post("/init")
async def init_password(request: AuthRequest):
    """首次设置主密码"""
    if is_initialized():
        raise HTTPException(status_code=409, detail="主密码已设置")
    
    if len(request.password) < 8:
        raise HTTPException(status_code=422, detail="密码至少 8 位")
    
    success = init_vault(request.password)
    if not success:
        raise HTTPException(status_code=500, detail="初始化失败")
    
    logger.info("主密码设置成功")
    
    return {
        "success": True,
        "data": {"token": create_session_token()},
        "message": "主密码设置成功"
    }


@router.post("/unlock")
async def unlock(request: AuthRequest):
    """输入主密码解锁"""
    _check_rate_limit()
    
    if not is_initialized():
        raise HTTPException(status_code=400, detail="请先设置主密码")
    
    _unlock_attempts.append(time.time())
    
    success = unlock_vault(request.password)
    if not success:
        raise HTTPException(status_code=401, detail="密码错误")
    
    _unlock_attempts.clear()
    
    logger.info("解锁成功")
    
    return {
        "success": True,
        "data": {"token": create_session_token()},
        "message": "解锁成功"
    }


@router.post("/lock")
async def lock():
    """手动锁定"""
    lock_vault()
    
    logger.info("已锁定")
    
    return {
        "success": True,
        "data": None,
        "message": "已锁定"
    }


@router.post("/change-password")
async def change_password(request: ChangePasswordRequest):
    """修改主密码"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")
    
    if len(request.new_password) < 8:
        raise HTTPException(status_code=422, detail="新密码至少 8 位")
    
    success = change_vault_password(request.old_password, request.new_password)
    if not success:
        raise HTTPException(status_code=401, detail="旧密码错误")
    
    logger.info("主密码已更新")
    
    return {
        "success": True,
        "data": None,
        "message": "主密码已更新"
    }
