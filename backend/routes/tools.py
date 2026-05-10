from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException

from config import BACKUP_DIR, CORS_ORIGINS, HOST, LOG_DIR_PATH, VAULT_PATH
from storage import get_vault_data, is_unlocked


router = APIRouter()


def check_unlocked():
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")


def is_password_field(field) -> bool:
    name = field.name.lower()
    return field.copyable and any(token in name for token in ["password", "passwd", "pwd", "密码", "口令", "密钥", "key", "token"])


def is_weak_secret(value: str) -> bool:
    if len(value) < 10:
        return True
    checks = [
        any(ch.islower() for ch in value),
        any(ch.isupper() for ch in value),
        any(ch.isdigit() for ch in value),
        any(not ch.isalnum() for ch in value),
    ]
    return sum(checks) < 3


def sample_entry(entry):
    return {
        "id": entry.id,
        "title": entry.title,
        "updated_at": entry.updated_at,
        "tags": entry.tags,
    }


def path_status(path: str | Path) -> dict:
    target = Path(path)
    return {
        "path": str(target),
        "exists": target.exists(),
        "is_dir": target.is_dir(),
        "is_file": target.is_file(),
    }


def security_check(name: str, status: str, message: str) -> dict:
    return {"name": name, "status": status, "message": message}


@router.get("/health-report")
async def health_report():
    """检查弱密码、重复密码和长期未更新条目。"""
    check_unlocked()
    vault = get_vault_data()
    active_entries = [entry for entry in vault.entries if not entry.deleted]
    weak_items = []
    secret_to_entries = defaultdict(list)
    stale_items = []
    stale_before = datetime.now() - timedelta(days=180)

    for entry in active_entries:
        try:
            updated_at = datetime.fromisoformat(entry.updated_at)
            if updated_at < stale_before:
                stale_items.append(sample_entry(entry))
        except Exception:
            stale_items.append(sample_entry(entry))

        for field in entry.fields:
            if not is_password_field(field) or not field.value:
                continue
            secret_to_entries[field.value].append(sample_entry(entry))
            if is_weak_secret(field.value):
                weak_items.append({
                    **sample_entry(entry),
                    "field_name": field.name
                })

    duplicate_groups = [entries for entries in secret_to_entries.values() if len(entries) > 1]

    return {
        "success": True,
        "data": {
            "total_entries": len(active_entries),
            "weak_count": len(weak_items),
            "duplicate_count": sum(len(group) for group in duplicate_groups),
            "stale_count": len(stale_items),
            "weak_items": weak_items[:20],
            "duplicate_groups": duplicate_groups[:20],
            "stale_items": stale_items[:20],
        }
    }


@router.get("/maintenance-report")
async def maintenance_report():
    """检查重复标题、无标签条目、空字段和示例数据。"""
    check_unlocked()
    vault = get_vault_data()
    active_entries = [entry for entry in vault.entries if not entry.deleted]

    title_map = defaultdict(list)
    untagged_items = []
    empty_field_items = []
    sample_items = []

    for entry in active_entries:
        title_map[entry.title.strip().lower()].append(sample_entry(entry))
        if not entry.tags:
            untagged_items.append(sample_entry(entry))
        if any(not field.value for field in entry.fields):
            empty_field_items.append(sample_entry(entry))
        if "示例" in entry.tags or entry.title.startswith("示例："):
            sample_items.append(sample_entry(entry))

    duplicate_title_groups = [items for title, items in title_map.items() if title and len(items) > 1]

    return {
        "success": True,
        "data": {
            "total_entries": len(active_entries),
            "duplicate_title_count": sum(len(group) for group in duplicate_title_groups),
            "untagged_count": len(untagged_items),
            "empty_field_count": len(empty_field_items),
            "sample_count": len(sample_items),
            "duplicate_title_groups": duplicate_title_groups[:20],
            "untagged_items": untagged_items[:20],
            "empty_field_items": empty_field_items[:20],
            "sample_items": sample_items[:50],
        }
    }


@router.get("/security-report")
async def security_report():
    """检查运行配置安全状态，不返回敏感环境变量值。"""
    check_unlocked()
    checks = []

    host_safe = HOST in {"127.0.0.1", "localhost"}
    checks.append(security_check(
        "HOST",
        "ok" if host_safe else "warning",
        "后端仅监听本机地址" if host_safe else "后端不是仅监听 127.0.0.1，公网部署前需确认防火墙和反向代理配置"
    ))

    cors_safe = CORS_ORIGINS != "*"
    checks.append(security_check(
        "CORS",
        "ok" if cors_safe else "warning",
        "CORS 已限制来源" if cors_safe else "CORS_ORIGINS=* 仅适合本地开发，公网生产应限制为实际 HTTPS 域名"
    ))

    vault_parent = Path(VAULT_PATH).parent
    backup_dir = Path(BACKUP_DIR)
    log_dir = Path(LOG_DIR_PATH)
    checks.append(security_check(
        "Vault 路径",
        "ok" if vault_parent.exists() else "error",
        "vault 目录存在" if vault_parent.exists() else "vault 目录不存在"
    ))
    checks.append(security_check(
        "备份目录",
        "ok" if backup_dir.exists() else "error",
        "备份目录存在" if backup_dir.exists() else "备份目录不存在"
    ))
    checks.append(security_check(
        "日志目录",
        "ok" if log_dir.exists() else "error",
        "日志目录存在" if log_dir.exists() else "日志目录不存在"
    ))

    summary = {
        "ok": sum(1 for item in checks if item["status"] == "ok"),
        "warning": sum(1 for item in checks if item["status"] == "warning"),
        "error": sum(1 for item in checks if item["status"] == "error"),
    }

    return {
        "success": True,
        "data": {
            "checks": checks,
            "summary": summary,
            "config": {
                "host": HOST,
                "cors_restricted": cors_safe,
                "vault_path": path_status(VAULT_PATH),
                "backup_dir": path_status(BACKUP_DIR),
                "log_dir": path_status(LOG_DIR_PATH),
            }
        }
    }
