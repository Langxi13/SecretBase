"""数据导出路由。"""

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response

from storage import export_plain_vault, get_vault_content, is_initialized
from routes.transfer_common import backup_filename, check_unlocked


router = APIRouter()


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
        headers={"Content-Disposition": f'attachment; filename="{backup_filename("enc")}"'},
    )


@router.post("/export/plain")
async def export_plain(payload: dict = Body(default_factory=dict)):
    """导出明文 JSON 文件，必须显式确认。"""
    check_unlocked()
    if payload.get("confirm") is not True:
        raise HTTPException(status_code=422, detail="导出明文前必须确认")
    return Response(
        content=export_plain_vault(),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{backup_filename("json")}"'},
    )
