"""服务器备份管理路由。"""

from datetime import datetime

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response

from storage import (
    ConflictError,
    VaultLockTimeoutError,
    create_backup,
    import_encrypted_vault,
    import_encrypted_vault_with_password,
    list_backup_files,
    read_encrypted_vault_with_current_key,
    read_encrypted_vault_with_password,
)
from routes.transfer_common import (
    backup_password_required_error,
    backup_response_item,
    backup_summary_from_content,
    check_unlocked,
    content_disposition,
    current_vault_counts,
    resolve_backup_path,
)


router = APIRouter()


@router.get("/backups")
async def list_backups():
    """列出自动和手动备份文件。"""
    check_unlocked()
    backups = [backup_response_item(item["path"], item["type"]) for item in list_backup_files()]
    return {"success": True, "data": {"items": backups, "total": len(backups)}}


@router.post("/backups")
async def create_manual_backup():
    """手动创建当前加密 vault 的备份。"""
    check_unlocked()
    try:
        path = create_backup()
    except (ConflictError, VaultLockTimeoutError):
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="创建备份失败")
    _, backup_type = resolve_backup_path(path.name)
    return {
        "success": True,
        "data": backup_response_item(path, backup_type),
        "message": "已创建手动备份",
    }


@router.get("/backups/{filename}/download/encrypted")
async def download_backup_encrypted(filename: str):
    """下载指定服务器备份的加密文件。"""
    check_unlocked()
    path, backup_type = resolve_backup_path(filename)
    return Response(
        content=path.read_bytes(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": content_disposition(path, backup_type, "bak")},
    )


@router.post("/backups/{filename}/download/plain")
async def download_backup_plain(filename: str, payload: dict = Body(default_factory=dict)):
    """下载指定服务器备份的明文 JSON，必须显式确认。"""
    check_unlocked()
    if payload.get("confirm") is not True:
        raise HTTPException(status_code=422, detail="下载明文备份前必须确认")
    path, backup_type = resolve_backup_path(filename)
    password = payload.get("password")
    try:
        content = path.read_bytes()
        data = read_encrypted_vault_with_password(content, password) if password else read_encrypted_vault_with_current_key(content)
    except Exception:
        if password:
            raise HTTPException(status_code=422, detail="备份无效或主密码不匹配")
        backup_password_required_error()
    return Response(
        content=data.model_dump_json(),
        media_type="application/json",
        headers={"Content-Disposition": content_disposition(path, backup_type, "json")},
    )


def backup_summary_response(path, backup_type: str, summary: dict, *, used_password: bool = False) -> dict:
    stat = path.stat()
    data = {
        **summary,
        **current_vault_counts(),
        "filename": path.name,
        "type": backup_type,
        "size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }
    if used_password:
        data["used_password"] = True
    return {"success": True, "data": data}


@router.get("/backups/{filename}/summary")
async def get_backup_summary(filename: str):
    """读取备份概况，必须能用当前主密码解密。"""
    check_unlocked()
    path, backup_type = resolve_backup_path(filename)
    try:
        summary = backup_summary_from_content(path.read_bytes())
    except Exception:
        backup_password_required_error()
    return backup_summary_response(path, backup_type, summary)


@router.post("/backups/{filename}/summary")
async def post_backup_summary(filename: str, payload: dict = Body(default_factory=dict)):
    """使用用户输入的主密码读取旧备份概况。"""
    check_unlocked()
    password = payload.get("password")
    if not password:
        backup_password_required_error()
    path, backup_type = resolve_backup_path(filename)
    try:
        summary = backup_summary_from_content(path.read_bytes(), password)
    except Exception:
        raise HTTPException(status_code=422, detail="备份无效或主密码不匹配")
    return backup_summary_response(path, backup_type, summary, used_password=True)


@router.post("/backups/{filename}/restore")
async def restore_backup(filename: str, payload: dict = Body(default_factory=dict)):
    """恢复加密备份。备份必须能用当前主密码解密。"""
    check_unlocked()
    path, _backup_type = resolve_backup_path(filename)
    password = payload.get("password")
    try:
        content = path.read_bytes()
        imported_count = import_encrypted_vault_with_password(content, password) if password else import_encrypted_vault(content)
    except (ConflictError, VaultLockTimeoutError):
        raise
    except Exception:
        if password:
            raise HTTPException(status_code=422, detail="备份无效或主密码不匹配")
        backup_password_required_error()
    return {
        "success": True,
        "data": {"imported_count": imported_count},
        "message": f"已恢复备份，包含 {imported_count} 个条目",
    }
