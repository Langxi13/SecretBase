"""Create, join, run, and resolve encrypted WebDAV synchronization."""

from __future__ import annotations

import copy
import logging
import secrets
import uuid

from storage import ConflictError, vault_revision, vault_session_id
from sync_crypto import decode_recovery_code, encode_key, generate_sync_key
from sync_merge import apply_resolutions, merge_documents, public_conflicts
from sync_runtime import (
    SyncServiceError,
    active_pending_plan,
    clear_pending_plan,
    client,
    device_name,
    document,
    ensure_vault_id,
    ensure_remote_progress,
    operation_lock,
    replace_local,
    repository,
    rollback_local,
    save_base,
    set_pending_plan,
    set_runtime,
    status,
    test_connection,
    validated_document,
    vault_has_content,
)
from sync_state import clear_sync_state, load_sync_base, load_sync_config, save_sync_config
from sync_webdav import WebDavError, normalize_webdav_url


logger = logging.getLogger(__name__)


def create(payload: dict) -> dict:
    with operation_lock:
        if load_sync_config() is not None:
            raise SyncServiceError("SYNC_ALREADY_CONFIGURED", "当前 Vault 已配置同步", status_code=409)
        connection = test_connection(payload)
        config = {
            "base_url": connection["base_url"],
            "username": str(payload.get("username") or "").strip(),
            "password": str(payload.get("password") or ""),
            "vault_id": ensure_vault_id(),
            "sync_key": encode_key(generate_sync_key()),
            "device_id": str(uuid.uuid4()),
            "device_name": device_name(payload.get("device_name")),
            "auto_sync": payload.get("auto_sync", True) is not False,
        }
        save_sync_config(config)
        try:
            with client(config) as webdav:
                remote = repository(config, webdav)
                remote.ensure_layout()
                if remote.load_head(optional=True) is not None:
                    raise SyncServiceError("SYNC_REMOTE_EXISTS", "远端已存在同名同步空间", status_code=409)
                local = document()
                head, snapshot, _ = remote.publish(
                    local,
                    current_head=None,
                    device_id=config["device_id"],
                    device_name=config["device_name"],
                )
                save_base(head, snapshot, local)
        except Exception:
            clear_sync_state()
            raise
        clear_pending_plan()
        set_runtime("synced", "已创建加密同步空间")
        return {"status": status()}


def _join_seed(remote: dict) -> dict:
    seed = copy.deepcopy(remote)
    seed["entries"] = []
    seed["deleted_entries"] = []
    seed["tags_meta"] = {}
    seed["groups_meta"] = {}
    return seed


def _join_local(remote: dict, local: dict) -> dict:
    value = copy.deepcopy(remote)
    for key in ("entries", "deleted_entries", "tags_meta", "groups_meta"):
        value[key] = copy.deepcopy(local.get(key) or ([] if key in {"entries", "deleted_entries"} else {}))
    return value


def join(payload: dict) -> dict:
    with operation_lock:
        if load_sync_config() is not None:
            raise SyncServiceError("SYNC_ALREADY_CONFIGURED", "当前 Vault 已配置同步", status_code=409)
        vault_id, key = decode_recovery_code(payload.get("recovery_code", ""))
        config = {
            "base_url": normalize_webdav_url(payload.get("base_url", "")),
            "username": str(payload.get("username") or "").strip(),
            "password": str(payload.get("password") or ""),
            "vault_id": vault_id,
            "sync_key": encode_key(key),
            "device_id": str(uuid.uuid4()),
            "device_name": device_name(payload.get("device_name")),
            "auto_sync": payload.get("auto_sync", True) is not False,
        }
        local = document()
        original_local = copy.deepcopy(local)
        if vault_has_content(local) and payload.get("merge_existing") is not True:
            raise SyncServiceError(
                "LOCAL_VAULT_NOT_EMPTY",
                "当前密码库已有数据，请明确选择合并现有数据",
                status_code=409,
                data={"requires_merge_confirmation": True},
            )

        with client(config) as webdav:
            remote_store = repository(config, webdav)
            current = remote_store.current(optional=True)
            if current is None:
                raise SyncServiceError("SYNC_REMOTE_MISSING", "恢复码对应的远端同步空间不存在", status_code=404)
            head, snapshot = current
            remote = validated_document(snapshot["document"])
            remote["vault_id"] = vault_id
            expected_revision = vault_revision()
            if not vault_has_content(local):
                new_revision = replace_local(remote, expected_revision)
                try:
                    save_sync_config(config)
                    save_base(head, snapshot, remote)
                except Exception:
                    clear_sync_state()
                    rollback_local(original_local, new_revision)
                    raise
                clear_pending_plan()
                set_runtime("synced", "已加入同步空间")
                return {"status": status(), "revision": new_revision, "conflicts": []}

            local["vault_id"] = vault_id
            plan = merge_documents(_join_seed(remote), _join_local(remote, local), remote)
            if plan["conflicts"]:
                token = secrets.token_urlsafe(32)
                set_pending_plan({
                    "token": token,
                    "mode": "join",
                    "vault_session_id": vault_session_id(),
                    "expected_revision": expected_revision,
                    "remote_etag": head.etag,
                    "plan": plan,
                    "config": config,
                    "local_document": original_local,
                })
                conflicts = public_conflicts(plan)
                set_runtime("conflict", "加入同步空间前需要处理冲突", conflicts=len(conflicts))
                return {"status": status(), "conflict_token": token, "conflicts": conflicts}

            merged = validated_document(plan["document"])
            new_revision = replace_local(merged, expected_revision)
            try:
                head, new_snapshot, _ = remote_store.publish(
                    merged,
                    current_head=head,
                    device_id=config["device_id"],
                    device_name=config["device_name"],
                )
            except Exception:
                rollback_local(original_local, new_revision)
                raise
            try:
                save_sync_config(config)
                save_base(head, new_snapshot, merged)
            except Exception:
                clear_sync_state()
                raise
            clear_pending_plan()
            set_runtime("synced", "现有数据已合并到同步空间")
            return {"status": status(), "revision": new_revision, "conflicts": []}


def _pending_conflict(config: dict, head, plan: dict, expected_revision: int, local: dict) -> dict:
    token = secrets.token_urlsafe(32)
    set_pending_plan({
        "token": token,
        "mode": "sync",
        "vault_session_id": vault_session_id(),
        "expected_revision": expected_revision,
        "remote_etag": head.etag,
        "plan": plan,
        "config": copy.deepcopy(config),
        "local_document": copy.deepcopy(local),
    })
    conflicts = public_conflicts(plan)
    set_runtime("conflict", "发现多端修改冲突", conflicts=len(conflicts))
    return {"status": status(), "conflict_token": token, "conflicts": conflicts}


def run() -> dict:
    if not operation_lock.acquire(blocking=False):
        raise SyncServiceError("SYNC_BUSY", "同步正在进行，请稍后重试", status_code=409)
    try:
        config = load_sync_config()
        base = load_sync_base()
        if not config:
            raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 WebDAV 同步", status_code=409)
        if not base:
            raise SyncServiceError("SYNC_BASE_MISSING", "同步基线缺失，请重新加入同步空间", status_code=409)
        set_runtime("syncing", "正在检查远端版本")
        expected_revision = vault_revision()
        local = document()
        with client(config) as webdav:
            remote_store = repository(config, webdav)
            current = remote_store.current(optional=True)
            if current is None:
                raise SyncServiceError("SYNC_REMOTE_MISSING", "远端同步空间已被删除", status_code=404)
            head, snapshot = current
            ensure_remote_progress(head, base, config)
            remote = validated_document(snapshot["document"])
            ancestor = validated_document(base["document"])
            local_changed = local != ancestor
            remote_changed = head.snapshot_id != base.get("snapshot_id") or remote != ancestor

            if not local_changed and not remote_changed:
                save_base(head, snapshot, remote)
                action, message = "none", "密码库已是最新版本"
            elif local_changed and not remote_changed:
                head, snapshot, _ = remote_store.publish(
                    local,
                    current_head=head,
                    device_id=config["device_id"],
                    device_name=config["device_name"],
                )
                save_base(head, snapshot, local)
                action, message = "uploaded", "本地修改已上传"
            elif remote_changed and not local_changed:
                latest_head = remote_store.load_head()
                if latest_head.etag != head.etag:
                    raise SyncServiceError("SYNC_REMOTE_CHANGED", "远端版本在下载期间发生变化，请重新同步", status_code=409)
                new_revision = replace_local(remote, expected_revision)
                try:
                    save_base(head, snapshot, remote)
                except Exception:
                    rollback_local(local, new_revision)
                    raise
                clear_pending_plan()
                set_runtime("synced", "远端修改已应用")
                return {"status": status(), "action": "downloaded", "revision": new_revision}
            else:
                plan = merge_documents(ancestor, local, remote)
                if plan["conflicts"]:
                    return _pending_conflict(config, head, plan, expected_revision, local)
                merged = validated_document(plan["document"])
                new_revision = replace_local(merged, expected_revision)
                try:
                    head, snapshot, _ = remote_store.publish(
                        merged,
                        current_head=head,
                        device_id=config["device_id"],
                        device_name=config["device_name"],
                    )
                except Exception:
                    rollback_local(local, new_revision)
                    raise
                save_base(head, snapshot, merged)
                clear_pending_plan()
                set_runtime("synced", "多端修改已自动合并")
                return {"status": status(), "action": "merged", "revision": new_revision}

            clear_pending_plan()
            set_runtime("synced", message)
            return {"status": status(), "action": action}
    except (WebDavError, SyncServiceError, ConflictError) as error:
        set_runtime("error", "同步未完成", error=getattr(error, "message", str(error)))
        raise
    except Exception as error:
        logger.exception("同步执行发生未处理错误")
        set_runtime("error", "同步未完成", error="本机同步状态保存失败，请检查数据目录权限后重试")
        raise
    finally:
        operation_lock.release()


def conflicts() -> dict:
    pending = active_pending_plan()
    if not pending:
        return {"conflict_token": "", "conflicts": []}
    return {
        "conflict_token": pending["token"],
        "conflicts": public_conflicts(pending["plan"]),
    }


def resolve_conflicts(token: str, resolutions: dict[str, str]) -> dict:
    with operation_lock:
        pending = active_pending_plan()
        if not pending or not secrets.compare_digest(str(token or ""), pending["token"]):
            raise SyncServiceError("SYNC_CONFLICT_EXPIRED", "同步冲突处理已失效，请重新同步", status_code=409)
        if vault_revision() != pending["expected_revision"]:
            clear_pending_plan()
            raise SyncServiceError("SYNC_CONFLICT_EXPIRED", "密码库已发生变化，请重新同步", status_code=409)
        persisted_config = load_sync_config()
        if pending["mode"] == "join":
            config = pending["config"]
            config_changed = persisted_config is not None
        else:
            config = persisted_config
            config_changed = not config or config["vault_id"] != pending["config"]["vault_id"]
        if config_changed:
            clear_pending_plan()
            raise SyncServiceError("SYNC_CONFIG_CHANGED", "同步配置已变化，请重新同步", status_code=409)

        with client(config) as webdav:
            remote_store = repository(config, webdav)
            head = remote_store.load_head()
            if head.etag != pending["remote_etag"]:
                clear_pending_plan()
                raise SyncServiceError("SYNC_REMOTE_CHANGED", "远端版本已变化，请重新同步", status_code=409)
            merged = validated_document(apply_resolutions(pending["plan"], resolutions))
            new_revision = replace_local(merged, pending["expected_revision"])
            try:
                head, snapshot, _ = remote_store.publish(
                    merged,
                    current_head=head,
                    device_id=config["device_id"],
                    device_name=config["device_name"],
                )
            except Exception:
                rollback_local(pending["local_document"], new_revision)
                clear_pending_plan()
                raise
            try:
                if pending["mode"] == "join":
                    save_sync_config(config)
                save_base(head, snapshot, merged)
            except Exception:
                if pending["mode"] == "join":
                    clear_sync_state()
                clear_pending_plan()
                raise
        clear_pending_plan()
        set_runtime("synced", "同步冲突已处理")
        return {"status": status(), "revision": new_revision}
