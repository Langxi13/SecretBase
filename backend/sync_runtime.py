"""Shared runtime state and helpers for encrypted WebDAV synchronization."""

from __future__ import annotations

import base64
import copy
import io
import logging
import platform
import socket
import threading
import uuid
from urllib.parse import urlsplit

import qrcode
from qrcode.exceptions import DataOverflowError
from qrcode.image.svg import SvgPathImage

from crypto import verify_password
from models import VaultData
from storage import (
    get_vault_content,
    get_vault_data,
    replace_vault_data_if_revision,
    save_vault_data,
    vault_session_id,
)
from sync_crypto import decode_key, encode_recovery_code, pairing_uri
from sync_remote import HISTORY_LIMIT, RemoteHead, SyncRepository, utc_now
from sync_state import load_sync_base, load_sync_config, save_sync_base
from sync_webdav import WebDavClient, normalize_webdav_url


logger = logging.getLogger(__name__)
operation_lock = threading.Lock()
_pending_plan: dict | None = None
_runtime_status = {
    "phase": "idle",
    "message": "",
    "last_error": "",
    "pending_conflicts": 0,
}


class SyncServiceError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400, data=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data


def set_runtime(phase: str, message: str = "", *, error: str = "", conflicts: int = 0) -> None:
    _runtime_status.update({
        "phase": phase,
        "message": message,
        "last_error": error,
        "pending_conflicts": conflicts,
    })


def set_pending_plan(plan: dict) -> None:
    global _pending_plan
    _pending_plan = plan


def clear_pending_plan() -> None:
    global _pending_plan
    _pending_plan = None


def active_pending_plan() -> dict | None:
    global _pending_plan
    if not _pending_plan:
        return None
    if _pending_plan.get("vault_session_id") != vault_session_id():
        _pending_plan = None
        set_runtime("idle", "同步冲突已失效，请重新同步")
        return None
    return _pending_plan


def device_name(value: str | None = None) -> str:
    value = str(value or "").strip()
    if value:
        return value[:100]
    host = socket.gethostname().strip() or "本机"
    return f"{platform.system() or 'SecretBase'} · {host}"[:100]


def document() -> dict:
    return get_vault_data().model_dump(mode="json")


def validated_document(value: dict) -> dict:
    seen_entry_ids = set()
    for collection in ("entries", "deleted_entries"):
        items = value.get(collection) if isinstance(value, dict) else None
        if not isinstance(items, list):
            raise SyncServiceError("SYNC_DOCUMENT_INVALID", "同步后的密码库格式无效", status_code=422)
        for item in items:
            entry_id = item.get("id") if isinstance(item, dict) else None
            if not isinstance(entry_id, str) or not entry_id.strip() or entry_id in seen_entry_ids:
                raise SyncServiceError("SYNC_DOCUMENT_INVALID", "同步文档包含无效或重复条目 ID", status_code=422)
            seen_entry_ids.add(entry_id)
    try:
        return VaultData.model_validate(value).model_dump(mode="json")
    except Exception as error:
        raise SyncServiceError("SYNC_DOCUMENT_INVALID", "同步后的密码库格式无效", status_code=422) from error


def vault_has_content(value: dict) -> bool:
    return bool(
        value.get("entries")
        or value.get("deleted_entries")
        or value.get("tags_meta")
        or value.get("groups_meta")
    )


def ensure_vault_id() -> str:
    vault = get_vault_data()
    if vault.vault_id:
        return vault.vault_id
    vault.vault_id = str(uuid.uuid4())
    save_vault_data(vault)
    return vault.vault_id


def client(config: dict) -> WebDavClient:
    return WebDavClient(
        config["base_url"],
        config["username"],
        config["password"],
    )


def repository(config: dict, webdav: WebDavClient) -> SyncRepository:
    return SyncRepository(
        webdav,
        vault_id=config["vault_id"],
        sync_key=decode_key(config["sync_key"]),
    )


def save_base(head: RemoteHead, snapshot: dict, value: dict) -> None:
    save_sync_base({
        "snapshot_id": head.snapshot_id,
        "head_etag": head.etag,
        "generation": head.generation,
        "synced_at": utc_now(),
        "document": copy.deepcopy(value),
        "history": copy.deepcopy(head.payload.get("history") or []),
        "device_id": snapshot.get("device_id", ""),
    })


def ensure_remote_progress(head: RemoteHead, base: dict, config: dict | None = None) -> None:
    try:
        base_generation = int(base["generation"])
        base_snapshot_id = str(uuid.UUID(str(base["snapshot_id"])))
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise SyncServiceError("SYNC_BASE_INVALID", "同步基线格式无效，请重新加入同步空间", status_code=409) from error
    if head.generation < base_generation:
        raise SyncServiceError("SYNC_REMOTE_ROLLBACK", "检测到远端版本回退，已停止同步", status_code=409)
    if head.generation == base_generation and head.snapshot_id != base_snapshot_id:
        raise SyncServiceError("SYNC_REMOTE_ROLLBACK", "检测到远端版本分叉，已停止同步", status_code=409)
    distance = head.generation - base_generation
    if 0 < distance < HISTORY_LIMIT:
        history_ids = {str(item.get("snapshot_id") or "") for item in head.payload.get("history") or []}
        if base_snapshot_id not in history_ids:
            config = config or {}
            try:
                floor_generation = int(config.get("history_floor_generation") or 0)
                floor_snapshot_id = str(uuid.UUID(str(config.get("history_floor_snapshot_id"))))
            except (TypeError, ValueError, AttributeError):
                floor_generation = 0
                floor_snapshot_id = ""
            if (
                base_generation < floor_generation <= head.generation
                and floor_snapshot_id in history_ids
            ):
                return
            raise SyncServiceError("SYNC_REMOTE_ROLLBACK", "远端历史链不包含本机基线，已停止同步", status_code=409)


def replace_local(value: dict, expected_revision: int) -> int:
    return replace_vault_data_if_revision(
        VaultData.model_validate(validated_document(value)),
        expected_revision,
    )


def rollback_local(value: dict, expected_revision: int) -> None:
    try:
        replace_local(value, expected_revision)
    except Exception as error:
        logger.critical("同步失败后无法回滚本机 Vault: %s", error)


def pairing_material(config: dict) -> dict:
    if int(config.get("protocol_version", 1)) == 2:
        from sync_v2_service import pairing_material as pairing_material_v2

        return pairing_material_v2(config)
    key = decode_key(config["sync_key"])
    recovery_code = encode_recovery_code(config["vault_id"], key)
    uri = pairing_uri(
        vault_id=config["vault_id"],
        key=key,
        base_url=config["base_url"],
        username=config["username"],
    )
    try:
        image = qrcode.make(uri, image_factory=SvgPathImage, box_size=8, border=3)
        buffer = io.BytesIO()
        image.save(buffer)
        qr_data_uri = "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except DataOverflowError:
        qr_data_uri = ""
    return {"recovery_code": recovery_code, "pairing_uri": uri, "qr_data_uri": qr_data_uri}


def _public_username(username: str) -> str:
    username = str(username or "")
    if len(username) <= 2:
        return "*" * len(username)
    return f"{username[0]}***{username[-1]}"


def _public_status(config: dict | None, base: dict | None) -> dict:
    if not config:
        return {
            "configured": False,
            "pending_join": False,
            "protocol_version": 2,
            "sync_mode": "坚果云兼容快照模式",
            "phase": "disabled",
            "message": "尚未配置 WebDAV 同步",
            "pending_conflicts": 0,
            "auto_sync": True,
            "space_id": "",
            "frontier": [],
        }
    parsed = urlsplit(config["base_url"])
    return {
        "configured": True,
        "pending_join": False,
        "protocol_version": int(config.get("protocol_version", 1)),
        "sync_mode": "坚果云兼容快照模式" if int(config.get("protocol_version", 1)) == 2 else "严格 ETag 模式",
        "phase": _runtime_status["phase"],
        "message": _runtime_status["message"],
        "last_error": _runtime_status["last_error"],
        "pending_conflicts": _runtime_status["pending_conflicts"],
        "auto_sync": config.get("auto_sync", True),
        "host": parsed.hostname or "",
        "base_url": config["base_url"],
        "username_mask": _public_username(config["username"]),
        "device_name": config["device_name"],
        "vault_id": config["vault_id"],
        "space_id": config.get("space_id", ""),
        "last_synced_at": (base or {}).get("synced_at", ""),
        "generation": int((base or {}).get("generation") or 0),
        "frontier": list((base or {}).get("frontier") or []),
    }


def status() -> dict:
    try:
        config = load_sync_config()
        pending = active_pending_plan()
        if config is None and pending and pending.get("mode") == "join":
            result = _public_status(pending["config"], None)
            result["configured"] = False
            result["pending_join"] = True
            return result
        return _public_status(config, load_sync_base())
    except Exception as error:
        logger.warning("读取同步状态失败: %s", error)
        return {
            "configured": False,
            "pending_join": False,
            "protocol_version": 2,
            "sync_mode": "坚果云兼容快照模式",
            "phase": "error",
            "message": "同步设置无法读取",
            "last_error": "请重新配置 WebDAV 同步",
            "pending_conflicts": 0,
            "auto_sync": True,
            "space_id": "",
            "frontier": [],
        }


def test_connection(payload: dict) -> dict:
    base_url = normalize_webdav_url(payload.get("base_url", ""))
    with WebDavClient(
        base_url,
        payload.get("username", ""),
        payload.get("password", ""),
    ) as webdav:
        capabilities = webdav.test_capabilities()
    return {"base_url": base_url, "host": urlsplit(base_url).hostname or "", "capabilities": capabilities}


def test_connection_v2(payload: dict) -> dict:
    base_url = normalize_webdav_url(payload.get("base_url", ""))
    with WebDavClient(
        base_url,
        payload.get("username", ""),
        payload.get("password", ""),
    ) as webdav:
        capabilities = webdav.test_basic_capabilities()
    return {"base_url": base_url, "host": urlsplit(base_url).hostname or "", "capabilities": capabilities}


def verify_master_password(password: str) -> None:
    content = get_vault_content()
    if content is None or not verify_password(str(password or ""), content):
        raise SyncServiceError("MASTER_PASSWORD_INVALID", "主密码错误", status_code=422)
