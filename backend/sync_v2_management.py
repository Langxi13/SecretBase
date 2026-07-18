"""History, configuration, migration, and destructive operations for V2 sync."""

from __future__ import annotations

import copy
import logging
import uuid

from storage import vault_revision
from sync_runtime import (
    SyncServiceError,
    active_pending_plan,
    client,
    clear_pending_plan,
    device_name,
    document,
    operation_lock,
    replace_local,
    rollback_local,
    set_runtime,
    status,
    validated_document,
    verify_master_password,
)
from sync_state import (
    clear_sync_state,
    load_sync_base,
    load_sync_config,
    save_sync_base,
    save_sync_config,
)
from sync_v2_crypto import decode_key, encode_key, encode_recovery_code, pairing_uri
from sync_v2_remote import V2Graph
from sync_v2_shared import (
    PROTOCOL_VERSION,
    documents_equal as _documents_equal,
    new_key as _new_key,
    remote_document as _remote_document,
    repository as _repository,
    save_base as _save_base,
)
from sync_webdav import WebDavError, normalize_webdav_url


logger = logging.getLogger(__name__)


def history() -> dict:
    config = load_sync_config()
    if not config or int(config.get("protocol_version", 1)) != PROTOCOL_VERSION:
        raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 V2 快照同步", status_code=409)
    with operation_lock, client(config) as webdav:
        remote = _repository(config, webdav)
        graph = remote.discover()
        items = remote.list_history(graph)
    return {
        "items": items,
        "current_snapshot_id": graph.frontier[0] if graph.frontier else "",
        "frontier": list(graph.frontier),
        "generation": graph.max_generation,
        "protocol_version": PROTOCOL_VERSION,
    }


def restore(snapshot_id: str) -> dict:
    with operation_lock:
        config = load_sync_config()
        if not config or int(config.get("protocol_version", 1)) != PROTOCOL_VERSION:
            raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 V2 快照同步", status_code=409)
        expected_revision = vault_revision()
        local = document()
        with client(config) as webdav:
            remote = _repository(config, webdav)
            graph = remote.discover()
            selected = graph.get(snapshot_id)
            restored = validated_document(selected.payload["document"])
            new_revision = replace_local(restored, expected_revision)
            try:
                snapshot = remote.publish(
                    restored,
                    parents=list(graph.frontier),
                    generation=graph.max_generation + 1,
                    device_id=config["device_id"],
                    device_name=config["device_name"],
                )
                graph = V2Graph({**graph.snapshots, snapshot.snapshot_id: snapshot}, (snapshot.snapshot_id,))
                _save_base(config, [snapshot.snapshot_id], restored, graph)
            except Exception:
                rollback_local(local, new_revision)
                raise
        clear_pending_plan()
        set_runtime("synced", "历史版本已恢复为最新快照")
        return {"status": status(), "revision": new_revision, "protocol_version": PROTOCOL_VERSION}


def pairing_material(config: dict) -> dict:
    from sync_v2_crypto import decode_key, encode_recovery_code

    key = decode_key(config["sync_key"])
    recovery_code = encode_recovery_code(config["vault_id"], config["space_id"], key)
    uri = pairing_uri(
        vault_id=config["vault_id"],
        space_id=config["space_id"],
        key=key,
        base_url=config["base_url"],
        username=config["username"],
        recovery_code=recovery_code,
    )
    qr_data_uri = ""
    try:
        import base64
        import io
        import qrcode
        from qrcode.image.svg import SvgPathImage

        image = qrcode.make(uri, image_factory=SvgPathImage, box_size=8, border=3)
        buffer = io.BytesIO()
        image.save(buffer)
        qr_data_uri = "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        qr_data_uri = ""
    return {
        "recovery_code": recovery_code,
        "pairing_uri": uri,
        "qr_data_uri": qr_data_uri,
    }


def update_config(payload: dict) -> dict:
    with operation_lock:
        config = load_sync_config()
        if not config or int(config.get("protocol_version", 1)) != PROTOCOL_VERSION:
            raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 V2 快照同步", status_code=409)
        candidate = copy.deepcopy(config)
        connection_changed = "base_url" in payload or "username" in payload or bool(payload.get("password"))
        if "base_url" in payload:
            candidate["base_url"] = normalize_webdav_url(payload["base_url"])
        if "username" in payload:
            candidate["username"] = str(payload.get("username") or "").strip()
        if payload.get("password"):
            candidate["password"] = str(payload["password"])
        candidate["device_name"] = device_name(payload.get("device_name", config["device_name"]))
        candidate["auto_sync"] = payload.get("auto_sync", config.get("auto_sync", True)) is not False
        if connection_changed:
            with client(candidate) as webdav:
                webdav.test_basic_capabilities()
                graph = _repository(candidate, webdav).discover()
                if not graph.snapshots:
                    raise SyncServiceError("SYNC_REMOTE_MISSING", "新的 WebDAV 地址中找不到当前同步空间", status_code=404)
        save_sync_config(candidate)
        if connection_changed:
            clear_pending_plan()
            set_runtime("idle", "V2 同步连接设置已更新")
        elif active_pending_plan() is None:
            set_runtime("idle", "同步偏好已更新")
        return status()


def migrate_from_v1(password: str) -> dict:
    """将当前 V1 空间复制为 V2，不删除旧空间，便于用户验收后再清理。"""
    with operation_lock:
        verify_master_password(password)
        old_config = load_sync_config()
        if not old_config or int(old_config.get("protocol_version", 1)) != 1:
            raise SyncServiceError("SYNC_NOT_V1", "当前不是可迁移的严格 ETag 同步空间", status_code=409)
        old_base = load_sync_base()
        with client(old_config) as webdav:
            old_remote = v1_repository(old_config, webdav)
            current = old_remote.current()
            if current is None:
                raise SyncServiceError("SYNC_REMOTE_MISSING", "旧同步空间没有可迁移的快照", status_code=404)
            _old_head, old_snapshot = current
            value = validated_document(old_snapshot["document"])
            new_config = copy.deepcopy(old_config)
            new_config.update({
                "protocol_version": PROTOCOL_VERSION,
                "space_id": str(uuid.uuid4()),
                "sync_key": encode_key(_new_key()),
            })
            new_remote = _repository(new_config, webdav)
            new_remote.ensure_layout(new_config["device_id"])
            snapshot = new_remote.publish(
                value,
                parents=[],
                generation=1,
                device_id=new_config["device_id"],
                device_name=new_config["device_name"],
            )
            graph = V2Graph({snapshot.snapshot_id: snapshot}, (snapshot.snapshot_id,))
            try:
                save_sync_config(new_config)
                _save_base(new_config, [snapshot.snapshot_id], value, graph)
            except Exception:
                try:
                    save_sync_config(old_config)
                    if old_base is not None:
                        save_sync_base(old_base)
                except Exception:
                    logger.critical("V1 到 V2 迁移失败后无法恢复旧同步状态")
                raise
        clear_pending_plan()
        set_runtime("synced", "已迁移到坚果云兼容的 V2 快照模式；旧 V1 空间仍保留")
        material = pairing_material(new_config)
        material.update({
            "status": status(),
            "protocol_version": PROTOCOL_VERSION,
            "legacy_space_retained": True,
        })
        return material


def v1_repository(config: dict, webdav):
    from sync_runtime import repository as repository_v1

    return repository_v1(config, webdav)


def rotate_key(password: str) -> dict:
    with operation_lock:
        verify_master_password(password)
        config = load_sync_config()
        old_base = load_sync_base()
        if not config or int(config.get("protocol_version", 1)) != PROTOCOL_VERSION:
            raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 V2 快照同步", status_code=409)
        if not old_base or int(old_base.get("protocol_version", 1)) != PROTOCOL_VERSION:
            raise SyncServiceError("SYNC_BASE_MISSING", "V2 同步基线缺失，请重新加入同步空间", status_code=409)
        old_config = copy.deepcopy(config)
        with client(config) as webdav:
            old_remote = _repository(config, webdav)
            old_graph = old_remote.discover()
            current, conflict, _remote_merge = _remote_document(old_graph)
            if conflict:
                raise SyncServiceError("SYNC_CONFLICT_PENDING", "请先处理现有同步冲突，再轮换同步密钥", status_code=409)
            new_config = copy.deepcopy(config)
            new_config["space_id"] = str(uuid.uuid4())
            new_config["sync_key"] = encode_key(_new_key())
            new_remote = _repository(new_config, webdav)
            new_remote.ensure_layout(new_config["device_id"])
            snapshot = new_remote.publish(
                current,
                parents=[],
                generation=1,
                device_id=new_config["device_id"],
                device_name=new_config["device_name"],
            )
            new_graph = V2Graph({snapshot.snapshot_id: snapshot}, (snapshot.snapshot_id,))
            try:
                save_sync_config(new_config)
                _save_base(new_config, [snapshot.snapshot_id], current, new_graph)
            except Exception:
                try:
                    save_sync_config(old_config)
                    save_sync_base(old_base)
                except Exception:
                    logger.critical("V2 密钥轮换失败后无法恢复旧本机同步状态")
                raise
            old_remote_deleted = True
            try:
                old_remote.delete_remote()
            except Exception:
                old_remote_deleted = False
                logger.warning("V2 旧同步空间清理失败，已保留为加密历史")
        clear_pending_plan()
        set_runtime(
            "synced",
            "同步密钥已轮换，旧设备需要使用新恢复码重新加入"
            + ("；旧同步空间待手动清理" if not old_remote_deleted else ""),
        )
        material = pairing_material(new_config)
        material.update({
            "status": status(),
            "previous_key_invalidated": old_config["sync_key"] != new_config["sync_key"],
            "old_space_deleted": old_remote_deleted,
        })
        return material


def compact_history(password: str, confirmation: str) -> dict:
    """在确认所有设备已同步后，以新空间根快照替换旧历史。"""
    if confirmation != "COMPACT":
        raise SyncServiceError(
            "CONFIRMATION_REQUIRED",
            "请输入 COMPACT 确认压缩并清理同步历史",
            status_code=422,
        )
    with operation_lock:
        verify_master_password(password)
        config = load_sync_config()
        base = load_sync_base()
        if not config or int(config.get("protocol_version", 1)) != PROTOCOL_VERSION:
            raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 V2 快照同步", status_code=409)
        if not base or int(base.get("protocol_version", 1)) != PROTOCOL_VERSION:
            raise SyncServiceError("SYNC_BASE_MISSING", "V2 同步基线缺失，请先同步", status_code=409)
        expected_revision = vault_revision()
        local = validated_document(document())
        baseline = validated_document(base["document"])
        if not _documents_equal(local, baseline):
            raise SyncServiceError(
                "SYNC_LOCAL_CHANGES",
                "本机还有未同步修改，请先完成同步再压缩历史",
                status_code=409,
            )

        old_config = copy.deepcopy(config)
        old_base = copy.deepcopy(base)
        old_space = config["space_id"]
        new_config = copy.deepcopy(config)
        new_config["space_id"] = str(uuid.uuid4())
        with client(config) as webdav:
            old_remote = _repository(config, webdav)
            graph = old_remote.discover()
            remote_value, remote_conflict, _remote_merge = _remote_document(graph)
            if remote_conflict:
                raise SyncServiceError(
                    "SYNC_CONFLICT_PENDING",
                    "远端仍有未处理分支冲突，请先处理冲突再压缩历史",
                    status_code=409,
                )
            frontier_match = tuple(sorted(graph.frontier)) == tuple(sorted(base["frontier"]))
            document_match = _documents_equal(remote_value, baseline)
            if not frontier_match or not document_match:
                raise SyncServiceError(
                    "SYNC_DEVICES_NOT_SYNCED",
                    "检测到仍有设备未同步，请在所有设备完成同步后重试",
                    status_code=409,
                )
            if vault_revision() != expected_revision:
                raise SyncServiceError(
                    "REVISION_CONFLICT",
                    "密码库在检查期间发生变化，请重新同步后重试",
                    status_code=409,
                )
            new_remote = _repository(new_config, webdav)
            new_remote.ensure_layout(new_config["device_id"])
            snapshot = new_remote.publish(
                baseline,
                parents=[],
                generation=1,
                device_id=new_config["device_id"],
                device_name=new_config["device_name"],
            )
            new_remote_graph = V2Graph({snapshot.snapshot_id: snapshot}, (snapshot.snapshot_id,))
            try:
                if vault_revision() != expected_revision:
                    raise SyncServiceError(
                        "REVISION_CONFLICT",
                        "密码库在压缩期间发生变化，请重新同步后重试",
                        status_code=409,
                    )
                save_sync_config(new_config)
                _save_base(new_config, [snapshot.snapshot_id], baseline, new_remote_graph)
            except Exception:
                try:
                    save_sync_config(old_config)
                    save_sync_base(old_base)
                except Exception:
                    logger.critical("V2 历史压缩失败后无法恢复旧本机同步状态")
                try:
                    new_remote.delete_remote()
                except Exception:
                    logger.warning("V2 历史压缩回滚时无法删除新同步空间", exc_info=True)
                raise

            old_space_deleted = True
            try:
                old_remote.delete_remote()
            except Exception:
                old_space_deleted = False
                logger.warning("V2 历史压缩后旧同步空间清理失败", exc_info=True)

        clear_pending_plan()
        set_runtime(
            "synced",
            "同步历史已压缩；其他设备需要使用新的恢复码重新加入"
            + ("；旧历史待手动清理" if not old_space_deleted else ""),
        )
        material = pairing_material(new_config)
        material.update({
            "status": status(),
            "protocol_version": PROTOCOL_VERSION,
            "old_space_id": old_space,
            "new_space_id": new_config["space_id"],
            "old_space_deleted": old_space_deleted,
            "snapshot_count": 1,
        })
        return material


def reset_remote(password: str, confirmation: str) -> dict:
    if confirmation != "DELETE":
        raise SyncServiceError("CONFIRMATION_REQUIRED", "请输入 DELETE 确认删除远端同步数据", status_code=422)
    with operation_lock:
        verify_master_password(password)
        config = load_sync_config()
        if not config or int(config.get("protocol_version", 1)) != PROTOCOL_VERSION:
            raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 V2 快照同步", status_code=409)
        with client(config) as webdav:
            _repository(config, webdav).delete_remote()
        clear_sync_state()
        clear_pending_plan()
        set_runtime("disabled", "远端同步数据已删除")
        return status()
