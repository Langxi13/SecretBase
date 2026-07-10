"""数据导入与导入预览路由。"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from import_service import import_plain_vault, preview_plain_import
from models import VaultData
from storage import (
    ConflictError,
    VaultLockTimeoutError,
    import_encrypted_vault,
    import_encrypted_vault_with_password,
)
from routes.transfer_common import (
    MAX_IMPORT_BYTES,
    backup_password_required_error,
    check_unlocked,
    parse_conflict_resolutions,
    parse_selected_entry_ids,
    read_import_json,
)


router = APIRouter()


async def read_encrypted_import(file: UploadFile) -> bytes:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="导入文件为空")
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="导入文件不能超过 10MB")
    return content


@router.post("/import/encrypted")
async def import_encrypted(file: UploadFile = File(...), password: str | None = Form(default=None)):
    """导入加密备份文件。"""
    check_unlocked()
    content = await read_encrypted_import(file)
    try:
        imported_count = import_encrypted_vault_with_password(content, password) if password else import_encrypted_vault(content)
    except (ConflictError, VaultLockTimeoutError):
        raise
    except Exception:
        if password:
            raise HTTPException(status_code=422, detail="加密备份无效或主密码不匹配")
        backup_password_required_error()
    return {
        "success": True,
        "data": {"imported_count": imported_count, "skipped_count": 0, "conflicts": []},
        "message": f"成功导入 {imported_count} 个条目",
    }


@router.post("/import/plain")
async def import_plain(
    file: UploadFile = File(...),
    conflict_strategy: str = Form(default="skip"),
    selected_entry_ids: str | None = Form(default=None),
    conflict_resolutions: str | None = Form(default=None),
):
    """导入明文 JSON 文件。"""
    check_unlocked()
    if conflict_strategy not in {"skip", "overwrite", "ask"}:
        raise HTTPException(status_code=422, detail="冲突处理策略无效")
    data = await read_import_json(file)
    try:
        result = import_plain_vault(
            data,
            conflict_strategy,
            parse_selected_entry_ids(selected_entry_ids),
            parse_conflict_resolutions(conflict_resolutions),
        )
    except (ConflictError, VaultLockTimeoutError):
        raise
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"导入数据无效: {error}")

    if result.get("needs_resolution"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "CONFLICT",
                "message": "发现冲突，请选择处理方式",
                "data": {"conflicts": result["conflicts"]},
            },
        )
    return {
        "success": True,
        "data": {
            "imported_count": result["imported_count"],
            "created_count": result.get("created_count", result["imported_count"]),
            "overwritten_count": result.get("overwritten_count", 0),
            "skipped_count": result["skipped_count"],
            "conflicts": result["conflicts"],
        },
        "message": f"成功导入 {result['imported_count']} 个条目",
    }


@router.post("/import/plain/preview")
async def preview_import_plain(file: UploadFile = File(...)):
    """预览明文 JSON 导入，不写入数据。"""
    check_unlocked()
    data = await read_import_json(file)
    try:
        incoming = VaultData(**data)
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"导入数据无效: {error}")

    return {"success": True, "data": preview_plain_import(incoming)}
