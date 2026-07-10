"""导入导出与备份路由共享的校验、文件和响应辅助函数。"""

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, UploadFile

from models import VaultData
from storage import (
    get_vault_data,
    is_unlocked,
    read_encrypted_vault_with_current_key,
    read_encrypted_vault_with_password,
    resolve_backup_file,
)


MAX_IMPORT_BYTES = 10 * 1024 * 1024


def check_unlocked() -> None:
    """统一保护导入导出接口。"""
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


def content_disposition(path: Path, backup_type: str, suffix: str) -> str:
    readable = readable_backup_name(path, backup_type, suffix)
    return (
        f'attachment; filename="{path.stem}.{suffix}"; '
        f"filename*=UTF-8''{quote(readable)}"
    )


async def read_import_json(file: UploadFile) -> dict:
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=422, detail="导入文件为空")
        if len(content) > MAX_IMPORT_BYTES:
            raise HTTPException(status_code=413, detail="导入文件不能超过 10MB")
        return json.loads(content.decode("utf-8"))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="JSON 文件格式无效")


def resolve_backup_path(filename: str) -> tuple[Path, str]:
    """将底层文件错误转换为稳定的 API 错误码。"""
    try:
        return resolve_backup_file(filename)
    except ValueError:
        raise HTTPException(status_code=422, detail="备份文件名无效")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="备份文件不存在")


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
    data = read_encrypted_vault_with_password(content, password) if password else read_encrypted_vault_with_current_key(content)
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


def backup_password_required_error() -> None:
    raise HTTPException(
        status_code=422,
        detail={
            "error": "BACKUP_PASSWORD_REQUIRED",
            "message": "备份无法用当前会话密钥读取，可能是旧备份或主密码不匹配。请输入该备份对应的主密码后重试。",
            "data": {"needs_password": True},
        },
    )
