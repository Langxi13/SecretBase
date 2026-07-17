"""Configuration, history, recovery, and destructive sync operations."""

from __future__ import annotations

import copy
import logging

from storage import vault_revision
from sync_crypto import encode_key, generate_sync_key
from sync_runtime import (
    SyncServiceError,
    active_pending_plan,
    clear_pending_plan,
    client,
    device_name,
    document,
    operation_lock,
    pairing_material,
    replace_local,
    repository,
    rollback_local,
    save_base,
    set_runtime,
    status,
    validated_document,
    verify_master_password,
)
from sync_remote import RemoteHead
from sync_state import clear_sync_state, load_sync_config, save_sync_config
from sync_webdav import WebDavError, normalize_webdav_url


logger = logging.getLogger(__name__)


def history() -> dict:
    config = load_sync_config()
    if not config:
        raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 WebDAV 同步", status_code=409)
    with operation_lock, client(config) as webdav:
        remote = repository(config, webdav)
        head = remote.load_head()
        items = remote.list_history(head)
    return {"items": items, "current_snapshot_id": head.snapshot_id, "generation": head.generation}


def restore(snapshot_id: str) -> dict:
    with operation_lock:
        config = load_sync_config()
        if not config:
            raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 WebDAV 同步", status_code=409)
        expected_revision = vault_revision()
        local = document()
        with client(config) as webdav:
            remote = repository(config, webdav)
            head = remote.load_head()
            allowed = {item.get("snapshot_id") for item in remote.list_history(head)}
            if snapshot_id not in allowed:
                raise SyncServiceError("SYNC_HISTORY_NOT_FOUND", "同步历史版本不存在", status_code=404)
            selected = remote.load_snapshot(snapshot_id)
            restored = validated_document(selected["document"])
            new_revision = replace_local(restored, expected_revision)
            try:
                head, snapshot, _ = remote.publish(
                    restored,
                    current_head=head,
                    device_id=config["device_id"],
                    device_name=config["device_name"],
                )
            except Exception:
                rollback_local(local, new_revision)
                raise
            save_base(head, snapshot, restored)
        clear_pending_plan()
        set_runtime("synced", "历史版本已恢复为最新版本")
        return {"status": status(), "revision": new_revision}


def update_config(payload: dict) -> dict:
    with operation_lock:
        config = load_sync_config()
        if not config:
            raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 WebDAV 同步", status_code=409)
        candidate = copy.deepcopy(config)
        connection_changed = "base_url" in payload or "username" in payload or bool(payload.get("password"))
        if "base_url" in payload:
            candidate["base_url"] = normalize_webdav_url(payload["base_url"])
        if "username" in payload:
            candidate["username"] = str(payload["username"] or "").strip()
        if payload.get("password"):
            candidate["password"] = str(payload["password"])
        candidate["device_name"] = device_name(payload.get("device_name", config["device_name"]))
        candidate["auto_sync"] = payload.get("auto_sync", config.get("auto_sync", True)) is not False
        if connection_changed:
            with client(candidate) as webdav:
                webdav.test_capabilities()
                if repository(candidate, webdav).load_head(optional=True) is None:
                    raise SyncServiceError("SYNC_REMOTE_MISSING", "新的 WebDAV 地址中找不到当前同步空间", status_code=404)
        save_sync_config(candidate)
        if connection_changed:
            clear_pending_plan()
            set_runtime("idle", "同步连接设置已更新")
        elif active_pending_plan() is None:
            set_runtime("idle", "同步偏好已更新")
        return status()


def disconnect() -> dict:
    with operation_lock:
        clear_sync_state()
        clear_pending_plan()
        set_runtime("disabled", "已断开本机同步")
        return status()


def recovery_material(password: str) -> dict:
    with operation_lock:
        verify_master_password(password)
        config = load_sync_config()
        if not config:
            raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 WebDAV 同步", status_code=409)
        return pairing_material(config)


def _rollback_rotated_remote(webdav, old_config: dict, old_head, new_head, value: dict) -> None:
    try:
        old_remote = repository(old_config, webdav)
        rollback_anchor = RemoteHead(payload=copy.deepcopy(old_head.payload), etag=new_head.etag)
        rollback_head, rollback_snapshot, _ = old_remote.publish(
            value,
            current_head=rollback_anchor,
            device_id=old_config["device_id"],
            device_name=old_config["device_name"],
        )
        save_sync_config(old_config)
        save_base(rollback_head, rollback_snapshot, value)
        try:
            webdav.delete(*webdav.snapshot_path(old_config["vault_id"], new_head.snapshot_id))
        except WebDavError:
            pass
    except Exception as error:
        logger.critical("同步密钥轮换失败后无法恢复旧密钥: %s", error)


def rotate_key(password: str) -> dict:
    with operation_lock:
        verify_master_password(password)
        config = load_sync_config()
        if not config:
            raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 WebDAV 同步", status_code=409)
        old_config = copy.deepcopy(config)
        with client(config) as webdav:
            old_remote = repository(old_config, webdav)
            head = old_remote.load_head()
            current = old_remote.load_snapshot(head.snapshot_id)
            config["sync_key"] = encode_key(generate_sync_key())
            new_remote = repository(config, webdav)
            new_head, snapshot, _ = new_remote.publish(
                current["document"],
                current_head=head,
                device_id=config["device_id"],
                device_name=config["device_name"],
                reset_history=True,
                cleanup_history=False,
            )
            config["history_floor_generation"] = new_head.generation
            config["history_floor_snapshot_id"] = new_head.snapshot_id
            try:
                save_sync_config(config)
            except Exception:
                _rollback_rotated_remote(webdav, old_config, head, new_head, current["document"])
                raise
            try:
                save_base(new_head, snapshot, current["document"])
            finally:
                for item in head.payload.get("history") or []:
                    old_snapshot_id = item.get("snapshot_id")
                    if old_snapshot_id and old_snapshot_id != new_head.snapshot_id:
                        try:
                            webdav.delete(*webdav.snapshot_path(config["vault_id"], old_snapshot_id))
                        except WebDavError:
                            pass
        clear_pending_plan()
        set_runtime("synced", "同步密钥已轮换，旧设备需要重新加入")
        material = pairing_material(config)
        material["previous_key_invalidated"] = old_config["sync_key"] != config["sync_key"]
        return {"status": status(), **material}


def reset_remote(password: str, confirmation: str) -> dict:
    if confirmation != "DELETE":
        raise SyncServiceError("CONFIRMATION_REQUIRED", "请输入 DELETE 确认删除远端同步数据", status_code=422)
    with operation_lock:
        verify_master_password(password)
        config = load_sync_config()
        if not config:
            raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 WebDAV 同步", status_code=409)
        with client(config) as webdav:
            repository(config, webdav).delete_remote()
        clear_sync_state()
        clear_pending_plan()
        set_runtime("disabled", "远端同步数据已删除")
        return status()
