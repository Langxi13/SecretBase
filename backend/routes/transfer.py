"""导入、导出与备份路由聚合入口。"""

from fastapi import APIRouter

from routes import transfer_backups, transfer_exports, transfer_imports
from routes.transfer_backups import (
    create_manual_backup,
    download_backup_encrypted,
    download_backup_plain,
    get_backup_summary,
    list_backups,
    post_backup_summary,
    restore_backup,
)
from routes.transfer_exports import export_encrypted, export_plain
from routes.transfer_imports import import_encrypted, import_plain, preview_import_plain


router = APIRouter()
router.include_router(transfer_exports.router)
router.include_router(transfer_imports.router)
router.include_router(transfer_backups.router)
