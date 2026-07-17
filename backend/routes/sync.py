"""WebDAV encrypted synchronization API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from models import (
    SyncConfigUpdateRequest,
    SyncConflictResolutionRequest,
    SyncConnectionRequest,
    SyncJoinRequest,
    SyncPasswordRequest,
    SyncResetRequest,
)
from storage import ConflictError, VaultLockTimeoutError
from sync_crypto import SyncCryptoError
from sync_runtime import SyncServiceError, status, test_connection
import sync_service
import sync_management
from sync_state import SyncStateError
from sync_webdav import WebDavError


router = APIRouter()


def _raise_sync_error(error: Exception):
    if isinstance(error, SyncServiceError):
        raise HTTPException(
            status_code=error.status_code,
            detail={"error": error.code, "message": error.message, "data": error.data},
        ) from error
    if isinstance(error, WebDavError):
        status = 502 if error.status_code == 401 else error.status_code
        raise HTTPException(
            status_code=status,
            detail={"error": error.code, "message": error.message},
        ) from error
    if isinstance(error, (SyncCryptoError, SyncStateError, ValueError)):
        raise HTTPException(status_code=422, detail=str(error)) from error
    raise error


async def _call(function, *args):
    try:
        return await run_in_threadpool(function, *args)
    except (ConflictError, VaultLockTimeoutError):
        raise
    except Exception as error:
        _raise_sync_error(error)


@router.get("/status")
async def get_status():
    return {"success": True, "data": status()}


@router.post("/config/test")
async def test_config(request: SyncConnectionRequest):
    data = await _call(test_connection, request.model_dump())
    return {"success": True, "data": data, "message": "WebDAV 连接与条件写入测试通过"}


@router.post("/create")
async def create_sync(request: SyncConnectionRequest):
    data = await _call(sync_service.create, request.model_dump())
    return {"success": True, "data": data, "message": "已创建端到端加密同步空间"}


@router.post("/join")
async def join_sync(request: SyncJoinRequest):
    data = await _call(sync_service.join, request.model_dump())
    return {"success": True, "data": data, "message": "已加入端到端加密同步空间"}


@router.put("/config")
async def update_config(request: SyncConfigUpdateRequest):
    updates = request.model_dump(exclude_none=True)
    data = await _call(sync_management.update_config, updates)
    return {"success": True, "data": data, "message": "同步设置已保存"}


@router.delete("/config")
async def disconnect():
    data = await _call(sync_management.disconnect)
    return {"success": True, "data": data, "message": "已断开本机同步"}


@router.post("/run")
async def run_sync():
    data = await _call(sync_service.run)
    return {"success": True, "data": data, "message": data["status"].get("message", "同步完成")}


@router.get("/conflicts")
async def get_conflicts():
    return {"success": True, "data": sync_service.conflicts()}


@router.post("/conflicts/resolve")
async def resolve_conflicts(request: SyncConflictResolutionRequest):
    data = await _call(
        sync_service.resolve_conflicts,
        request.conflict_token,
        request.resolutions,
    )
    return {"success": True, "data": data, "message": "同步冲突已处理"}


@router.get("/history")
async def get_history():
    data = await _call(sync_management.history)
    return {"success": True, "data": data}


@router.post("/history/{snapshot_id}/restore")
async def restore_history(snapshot_id: str):
    data = await _call(sync_management.restore, snapshot_id)
    return {"success": True, "data": data, "message": "同步历史已恢复为最新版本"}


@router.post("/recovery-code")
async def reveal_recovery_code(request: SyncPasswordRequest):
    data = await _call(sync_management.recovery_material, request.password)
    return {"success": True, "data": data}


@router.post("/rotate-key")
async def rotate_key(request: SyncPasswordRequest):
    data = await _call(sync_management.rotate_key, request.password)
    return {"success": True, "data": data, "message": "同步密钥已轮换"}


@router.post("/reset")
async def reset_remote(request: SyncResetRequest):
    data = await _call(sync_management.reset_remote, request.password, request.confirmation)
    return {"success": True, "data": data, "message": "远端同步数据已删除"}
