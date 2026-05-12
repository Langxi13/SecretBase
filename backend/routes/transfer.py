import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from models import VaultData
from storage import (
    create_backup,
    export_plain_vault,
    get_vault_content,
    get_vault_data,
    import_encrypted_vault,
    import_encrypted_vault_with_password,
    import_plain_vault,
    is_initialized,
    is_unlocked,
    list_backup_files,
    read_encrypted_vault_with_current_key,
    read_encrypted_vault_with_password,
    resolve_backup_file,
    VaultLockTimeoutError,
)

router = APIRouter()
MAX_IMPORT_BYTES = 10 * 1024 * 1024


def check_unlocked():
    """检查是否已解锁"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")


def backup_filename(suffix: str) -> str:
    date = datetime.now().strftime("%Y%m%d")
    return f"secretbase-backup-{date}.{suffix}"


def backup_type_label(backup_type: str) -> str:
    if backup_type == "manual":
        return "手动备份"
    if backup_type == "auto":
        return "自动备份"
    return "旧版备份"


def backup_timestamp(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime)


def readable_backup_name(path: Path, backup_type: str, suffix: str = "bak") -> str:
    timestamp = backup_timestamp(path).strftime("%Y年%m月%d日%H时%M分%S秒")
    return f"{backup_type_label(backup_type)}-{timestamp}.{suffix}"


def ascii_download_name(path: Path, suffix: str) -> str:
    return f"{path.stem}.{suffix}"


def content_disposition(path: Path, backup_type: str, suffix: str) -> str:
    readable = readable_backup_name(path, backup_type, suffix)
    return (
        f'attachment; filename="{ascii_download_name(path, suffix)}"; '
        f"filename*=UTF-8''{quote(readable)}"
    )


async def read_import_json(file: UploadFile) -> dict:
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=422, detail="导入文件为空")
        if len(content) > MAX_IMPORT_BYTES:
            raise HTTPException(status_code=413, detail="导入文件不能超过 10MB")
        return json.loads(content.decode('utf-8'))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="JSON 文件格式无效")


def get_backup_path(filename: str) -> Path:
    try:
        path, _backup_type = resolve_backup_file(filename)
    except ValueError:
        raise HTTPException(status_code=422, detail="备份文件名无效")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="备份文件不存在")
    return path


def parse_selected_entry_ids(raw: str | None) -> list[str] | None:
    if raw is None or raw == "":
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = [item.strip() for item in raw.split(",") if item.strip()]
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise HTTPException(status_code=422, detail="导入条目选择无效")
    return [item for item in parsed if item]


def parse_conflict_resolutions(raw: str | None) -> dict[str, str] | None:
    if raw is None or raw == "":
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=422, detail="导入冲突处理选择无效")
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail="导入冲突处理选择无效")
    normalized = {}
    for entry_id, strategy in parsed.items():
        if not isinstance(entry_id, str) or strategy not in {"skip", "overwrite", "ask"}:
            raise HTTPException(status_code=422, detail="导入冲突处理选择无效")
        normalized[entry_id] = strategy
    return normalized


def backup_summary_from_data(data: VaultData) -> dict:
    return {
        "entry_count": len(data.entries),
        "deleted_count": len(data.deleted_entries),
        "created_at": data.created_at,
        "version": data.version,
    }


def current_vault_counts() -> dict:
    data = get_vault_data()
    return {
        "current_entry_count": len(data.entries),
        "current_deleted_count": len(data.deleted_entries),
    }


def backup_summary_from_content(content: bytes, password: str | None = None) -> dict:
    if password:
        data = read_encrypted_vault_with_password(content, password)
    else:
        data = read_encrypted_vault_with_current_key(content)
    return backup_summary_from_data(data)


def backup_summary_for_list(path: Path) -> dict:
    try:
        return {
            **backup_summary_from_content(path.read_bytes()),
            "summary_available": True,
            "needs_password": False,
        }
    except Exception:
        return {
            "entry_count": None,
            "deleted_count": None,
            "created_at": None,
            "version": None,
            "summary_available": False,
            "needs_password": True,
        }


def backup_response_item(path: Path, backup_type: str, include_summary: bool = True) -> dict:
    stat = path.stat()
    item = {
        "filename": path.name,
        "type": backup_type,
        "display_name": readable_backup_name(path, backup_type),
        "download_name_encrypted": readable_backup_name(path, backup_type, "bak"),
        "download_name_plain": readable_backup_name(path, backup_type, "json"),
        "size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }
    if include_summary:
        item.update(backup_summary_for_list(path))
    return item


def backup_password_required_error():
    raise HTTPException(
        status_code=422,
        detail={
            "error": "BACKUP_PASSWORD_REQUIRED",
            "message": "备份无法用当前会话密钥读取，可能是旧备份或主密码不匹配。请输入该备份对应的主密码后重试。",
            "data": {"needs_password": True}
        }
    )


@router.post("/export/encrypted")
async def export_encrypted():
    """导出加密备份文件。"""
    check_unlocked()
    if not is_initialized():
        raise HTTPException(status_code=404, detail="数据文件不存在")

    content = get_vault_content()
    if content is None:
        raise HTTPException(status_code=404, detail="数据文件不存在")

    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{backup_filename("enc")}"'}
    )


@router.post("/export/plain")
async def export_plain(payload: dict = Body(default_factory=dict)):
    """导出明文 JSON 文件，必须显式确认。"""
    check_unlocked()
    if payload.get("confirm") is not True:
        raise HTTPException(status_code=422, detail="导出明文前必须确认")

    content = export_plain_vault()
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{backup_filename("json")}"'}
    )


@router.post("/import/encrypted")
async def import_encrypted(file: UploadFile = File(...), password: str | None = Form(default=None)):
    """导入加密备份文件。"""
    check_unlocked()
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="导入文件为空")
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="导入文件不能超过 10MB")

    try:
        imported_count = import_encrypted_vault_with_password(content, password) if password else import_encrypted_vault(content)
    except Exception:
        if password:
            raise HTTPException(status_code=422, detail="加密备份无效或主密码不匹配")
        backup_password_required_error()

    return {
        "success": True,
        "data": {
            "imported_count": imported_count,
            "skipped_count": 0,
            "conflicts": []
        },
        "message": f"成功导入 {imported_count} 个条目"
    }


@router.post("/import/plain")
async def import_plain(
    file: UploadFile = File(...),
    conflict_strategy: str = Form(default="skip"),
    selected_entry_ids: str | None = Form(default=None),
    conflict_resolutions: str | None = Form(default=None)
):
    """导入明文 JSON 文件。"""
    check_unlocked()
    if conflict_strategy not in {"skip", "overwrite", "ask"}:
        raise HTTPException(status_code=422, detail="冲突处理策略无效")

    data = await read_import_json(file)
    selected_ids = parse_selected_entry_ids(selected_entry_ids)
    resolutions = parse_conflict_resolutions(conflict_resolutions)

    try:
        result = import_plain_vault(data, conflict_strategy, selected_ids, resolutions)
    except VaultLockTimeoutError:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"导入数据无效: {exc}")

    if result.get("needs_resolution"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "CONFLICT",
                "message": "发现冲突，请选择处理方式",
                "data": {"conflicts": result["conflicts"]}
            }
        )

    return {
        "success": True,
        "data": {
            "imported_count": result["imported_count"],
            "created_count": result.get("created_count", result["imported_count"]),
            "overwritten_count": result.get("overwritten_count", 0),
            "skipped_count": result["skipped_count"],
            "conflicts": result["conflicts"]
        },
        "message": f"成功导入 {result['imported_count']} 个条目"
    }


@router.post("/import/plain/preview")
async def preview_import_plain(file: UploadFile = File(...)):
    """预览明文 JSON 导入，不写入数据。"""
    check_unlocked()
    data = await read_import_json(file)

    try:
        incoming = VaultData(**data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"导入数据无效: {exc}")

    vault = get_vault_data()
    existing_by_id = {entry.id: entry for entry in vault.entries}
    conflicts = []
    entries = []
    for entry in incoming.entries:
        existing = existing_by_id.get(entry.id)
        entry_preview = {
            "id": entry.id,
            "title": entry.title,
            "is_conflict": bool(existing),
            "field_count": len(entry.fields),
            "tag_count": len(entry.tags),
            "tags": entry.tags[:5]
        }
        entries.append(entry_preview)
        if existing:
            conflicts.append({
                "id": entry.id,
                "existing_title": existing.title,
                "import_title": entry.title
            })

    return {
        "success": True,
        "data": {
            "total_count": len(incoming.entries),
            "new_count": len(incoming.entries) - len(conflicts),
            "conflict_count": len(conflicts),
            "entries": entries,
            "conflicts": conflicts[:20]
        }
    }


@router.get("/backups")
async def list_backups():
    """列出自动备份文件。"""
    check_unlocked()
    backups = []
    for item in list_backup_files():
        backups.append(backup_response_item(item["path"], item["type"]))

    return {
        "success": True,
        "data": {
            "items": backups,
            "total": len(backups)
        }
    }


@router.post("/backups")
async def create_manual_backup():
    """手动创建当前加密 vault 的备份。"""
    check_unlocked()
    try:
        path = create_backup()
    except VaultLockTimeoutError:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="创建备份失败")

    backup_type = resolve_backup_file(path.name)[1]
    return {
        "success": True,
        "data": backup_response_item(path, backup_type),
        "message": "已创建手动备份"
    }


@router.get("/backups/{filename}/download/encrypted")
async def download_backup_encrypted(filename: str):
    """下载指定服务器备份的加密文件。"""
    check_unlocked()
    path, backup_type = resolve_backup_file(filename)
    return Response(
        content=path.read_bytes(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": content_disposition(path, backup_type, "bak")}
    )


@router.post("/backups/{filename}/download/plain")
async def download_backup_plain(filename: str, payload: dict = Body(default_factory=dict)):
    """下载指定服务器备份的明文 JSON，必须显式确认。"""
    check_unlocked()
    if payload.get("confirm") is not True:
        raise HTTPException(status_code=422, detail="下载明文备份前必须确认")

    path, backup_type = resolve_backup_file(filename)
    password = payload.get("password")
    try:
        data = read_encrypted_vault_with_password(path.read_bytes(), password) if password else read_encrypted_vault_with_current_key(path.read_bytes())
    except Exception:
        if password:
            raise HTTPException(status_code=422, detail="备份无效或主密码不匹配")
        backup_password_required_error()

    return Response(
        content=data.model_dump_json(),
        media_type="application/json",
        headers={"Content-Disposition": content_disposition(path, backup_type, "json")}
    )


@router.get("/backups/{filename}/summary")
async def get_backup_summary(filename: str):
    """读取备份概况，必须能用当前主密码解密。"""
    check_unlocked()
    path = get_backup_path(filename)
    try:
        summary = backup_summary_from_content(path.read_bytes())
    except Exception:
        backup_password_required_error()

    stat = path.stat()
    return {
        "success": True,
        "data": {
            **summary,
            **current_vault_counts(),
            "filename": path.name,
            "type": resolve_backup_file(filename)[1],
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        }
    }


@router.post("/backups/{filename}/summary")
async def post_backup_summary(filename: str, payload: dict = Body(default_factory=dict)):
    """使用用户输入的主密码读取旧备份概况。"""
    check_unlocked()
    password = payload.get("password")
    if not password:
        backup_password_required_error()
    path = get_backup_path(filename)
    try:
        summary = backup_summary_from_content(path.read_bytes(), password)
    except Exception:
        raise HTTPException(status_code=422, detail="备份无效或主密码不匹配")

    stat = path.stat()
    return {
        "success": True,
        "data": {
            **summary,
            **current_vault_counts(),
            "filename": path.name,
            "type": resolve_backup_file(filename)[1],
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "used_password": True,
        }
    }


@router.post("/backups/{filename}/restore")
async def restore_backup(filename: str, payload: dict = Body(default_factory=dict)):
    """恢复加密备份。备份必须能用当前主密码解密。"""
    check_unlocked()
    path = get_backup_path(filename)
    try:
        content = path.read_bytes()
        password = payload.get("password")
        imported_count = import_encrypted_vault_with_password(content, password) if password else import_encrypted_vault(content)
    except VaultLockTimeoutError:
        raise
    except Exception:
        if payload.get("password"):
            raise HTTPException(status_code=422, detail="备份无效或主密码不匹配")
        backup_password_required_error()

    return {
        "success": True,
        "data": {"imported_count": imported_count},
        "message": f"已恢复备份，包含 {imported_count} 个条目"
    }
