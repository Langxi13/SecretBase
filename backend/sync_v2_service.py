"""V5.3 ETag-free snapshot-DAG synchronization service."""

from __future__ import annotations

import copy
import logging
import uuid

from storage import ConflictError, vault_revision
from sync_merge import merge_documents
from sync_runtime import (
    SyncServiceError,
    clear_pending_plan,
    client,
    document,
    ensure_vault_id,
    operation_lock,
    replace_local,
    rollback_local,
    set_runtime,
    status,
    test_connection_v2,
    validated_document,
    vault_has_content,
)
from sync_state import load_sync_base, load_sync_config, save_sync_config
from sync_v2_crypto import decode_recovery_code
from sync_v2_remote import V2Graph
from sync_webdav import WebDavError
from sync_v2_shared import (
    MAX_FRONTIER,
    PROTOCOL_VERSION,
    build_config as _config,
    clear_state_best_effort as clear_sync_state_best_effort,
    documents_equal as _documents_equal,
    fold_remote_documents as _fold_remote_documents,
    join_local as _join_local,
    minimal_parents as _minimal_parents,
    new_key as _new_key,
    pending as _pending_v2,
    remote_document as _remote_document,
    repository as _repository,
    save_base as _save_base,
    seed as _seed,
)
from sync_v2_conflicts import resolve_conflicts
from sync_v2_management import (
    compact_history,
    history,
    migrate_from_v1,
    pairing_material,
    reset_remote,
    restore,
    rotate_key,
    update_config,
)


logger = logging.getLogger(__name__)


def create(payload: dict) -> dict:
    with operation_lock:
        if load_sync_config() is not None:
            raise SyncServiceError("SYNC_ALREADY_CONFIGURED", "当前 Vault 已配置同步", status_code=409)
        vault_id = ensure_vault_id()
        space_id = str(uuid.uuid4())
        test_connection_v2(payload)
        config = _config(payload, vault_id=vault_id, space_id=space_id, sync_key=_new_key())
        local = validated_document(document())
        with client(config) as webdav:
            remote = _repository(config, webdav)
            remote.ensure_layout(config["device_id"])
            graph = remote.discover()
            if graph.snapshots:
                raise SyncServiceError("SYNC_REMOTE_EXISTS", "远端已存在同步快照，请改用加入或清理空间", status_code=409)
            snapshot = remote.publish(
                local,
                parents=[],
                generation=1,
                device_id=config["device_id"],
                device_name=config["device_name"],
            )
            graph = V2Graph({snapshot.snapshot_id: snapshot}, (snapshot.snapshot_id,))
            try:
                save_sync_config(config)
                _save_base(config, [snapshot.snapshot_id], local, graph)
            except Exception:
                clear_sync_state_best_effort()
                raise
        clear_pending_plan()
        set_runtime("synced", "已创建坚果云兼容的加密快照同步空间")
        return {"status": status(), "protocol_version": PROTOCOL_VERSION}


def join(payload: dict) -> dict:
    with operation_lock:
        if load_sync_config() is not None:
            raise SyncServiceError("SYNC_ALREADY_CONFIGURED", "当前 Vault 已配置同步", status_code=409)
        try:
            vault_id, space_id, key = decode_recovery_code(payload.get("recovery_code", ""))
        except Exception as error:
            raise SyncServiceError("SYNC_RECOVERY_INVALID", "V2 同步恢复码无效", status_code=422) from error
        config = _config(payload, vault_id=vault_id, space_id=space_id, sync_key=key)
        local = validated_document(document())
        original_local = copy.deepcopy(local)
        if vault_has_content(local) and payload.get("merge_existing") is not True:
            raise SyncServiceError(
                "LOCAL_VAULT_NOT_EMPTY",
                "当前密码库已有数据，请明确选择合并现有数据",
                status_code=409,
                data={"requires_merge_confirmation": True},
            )
        with client(config) as webdav:
            remote = _repository(config, webdav)
            try:
                graph = remote.discover()
            except WebDavError as error:
                if error.code in {"WEBDAV_LIST_FAILED", "WEBDAV_READ_FAILED"} and error.status_code == 404:
                    raise SyncServiceError("SYNC_REMOTE_MISSING", "恢复码对应的远端同步空间不存在", status_code=404) from error
                raise
            if not graph.snapshots:
                raise SyncServiceError("SYNC_REMOTE_MISSING", "恢复码对应的远端同步空间为空", status_code=404)
            remote_value, remote_conflict, remote_merge = _remote_document(graph)
            expected_revision = vault_revision()
            if remote_conflict:
                return _pending_v2(
                    remote_conflict,
                    config=config,
                    frontier=graph.frontier,
                    expected_revision=expected_revision,
                    local=original_local,
                    mode="join",
                    remote_merge=remote_merge,
                    continuation={
                        "kind": "join",
                        "merge_existing": vault_has_content(local),
                    },
                )
            if vault_has_content(local):
                seed = _seed(remote_value)
                plan = merge_documents(seed, _join_local(remote_value, local), remote_value)
                if plan["conflicts"]:
                    return _pending_v2(
                        plan,
                        config=config,
                        frontier=graph.frontier,
                        expected_revision=expected_revision,
                        local=original_local,
                        mode="join",
                    )
                merged = validated_document(plan["document"])
            else:
                merged = remote_value
            new_revision = replace_local(merged, expected_revision)
            try:
                if not _documents_equal(merged, remote_value) or len(graph.frontier) > 1:
                    parents = list(graph.frontier)
                    snapshot = remote.publish(
                        merged,
                        parents=parents,
                        generation=graph.max_generation + 1,
                        device_id=config["device_id"],
                        device_name=config["device_name"],
                    )
                    graph = V2Graph(
                        {**graph.snapshots, snapshot.snapshot_id: snapshot},
                        (snapshot.snapshot_id,),
                    )
                    frontier = [snapshot.snapshot_id]
                else:
                    frontier = list(graph.frontier)
                save_sync_config(config)
                _save_base(config, frontier, merged, graph)
            except Exception:
                clear_sync_state_best_effort()
                rollback_local(original_local, new_revision)
                raise
        clear_pending_plan()
        set_runtime("synced", "已加入坚果云兼容的加密快照同步空间")
        return {"status": status(), "revision": new_revision, "conflicts": [], "protocol_version": PROTOCOL_VERSION}


def _remote_progress(graph: V2Graph, base: dict) -> bool:
    try:
        base_frontier = [str(uuid.UUID(str(item))) for item in base["frontier"]]
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise SyncServiceError("SYNC_BASE_INVALID", "V2 同步基线格式无效，请重新加入同步空间", status_code=409) from error
    if set(base_frontier) == set(graph.frontier):
        return False
    for item in base_frontier:
        if item not in graph.snapshots:
            raise SyncServiceError("SYNC_REMOTE_ROLLBACK", "远端历史缺少本机基线，已停止同步", status_code=409)
        if not any(item in graph.ancestors(frontier) for frontier in graph.frontier):
            raise SyncServiceError("SYNC_REMOTE_ROLLBACK", "远端历史分叉或回退，已停止同步", status_code=409)
    return True


def run() -> dict:
    if not operation_lock.acquire(blocking=False):
        raise SyncServiceError("SYNC_BUSY", "同步正在进行，请稍后重试", status_code=409)
    try:
        config = load_sync_config()
        base = load_sync_base()
        if not config or int(config.get("protocol_version", 1)) != PROTOCOL_VERSION:
            raise SyncServiceError("SYNC_NOT_CONFIGURED", "尚未配置 V2 快照同步", status_code=409)
        if not base or int(base.get("protocol_version", 1)) != PROTOCOL_VERSION:
            raise SyncServiceError("SYNC_BASE_MISSING", "V2 同步基线缺失，请重新加入同步空间", status_code=409)
        set_runtime("syncing", "正在发现坚果云快照")
        expected_revision = vault_revision()
        local = validated_document(document())
        with client(config) as webdav:
            remote = _repository(config, webdav)
            graph = remote.discover()
            if not graph.snapshots:
                raise SyncServiceError("SYNC_REMOTE_MISSING", "远端同步空间已被删除", status_code=404)
            remote_changed = _remote_progress(graph, base)
            remote_value, remote_conflict, remote_merge = _remote_document(graph)
            ancestor = validated_document(base["document"])
            local_changed = not _documents_equal(local, ancestor)
            if remote_conflict:
                return _pending_v2(
                    remote_conflict,
                    config=config,
                    frontier=graph.frontier,
                    expected_revision=expected_revision,
                    local=local,
                    remote_merge=remote_merge,
                    continuation={
                        "kind": "sync",
                        "base_document": ancestor,
                        "base_frontier": list(base["frontier"]),
                        "base_generation": int(base["generation"]),
                    },
                )
            if not local_changed and not remote_changed:
                _save_base(config, list(graph.frontier), remote_value, graph)
                set_runtime("synced", "密码库已是最新版本")
                return {"status": status(), "action": "none", "protocol_version": PROTOCOL_VERSION}
            if not local_changed and remote_changed:
                new_revision = replace_local(remote_value, expected_revision)
                try:
                    _save_base(config, list(graph.frontier), remote_value, graph)
                except Exception:
                    rollback_local(local, new_revision)
                    raise
                clear_pending_plan()
                set_runtime("synced", "远端修改已应用")
                return {"status": status(), "action": "downloaded", "revision": new_revision, "protocol_version": PROTOCOL_VERSION}
            if local_changed and not remote_changed:
                parents = list(base["frontier"])
                snapshot = remote.publish(
                    local,
                    parents=parents,
                    generation=int(base["generation"]) + 1,
                    device_id=config["device_id"],
                    device_name=config["device_name"],
                )
                graph = V2Graph({**graph.snapshots, snapshot.snapshot_id: snapshot}, (snapshot.snapshot_id,))
                _save_base(config, [snapshot.snapshot_id], local, graph)
                clear_pending_plan()
                set_runtime("synced", "本地修改已上传")
                return {"status": status(), "action": "uploaded", "protocol_version": PROTOCOL_VERSION}

            plan = merge_documents(ancestor, local, remote_value)
            if plan["conflicts"]:
                return _pending_v2(
                    plan,
                    config=config,
                    frontier=graph.frontier,
                    expected_revision=expected_revision,
                    local=local,
                )
            merged = validated_document(plan["document"])
            parents = _minimal_parents(graph, [*base["frontier"], *graph.frontier])
            generation = max(int(base["generation"]), graph.max_generation) + 1
            new_revision = replace_local(merged, expected_revision)
            try:
                snapshot = remote.publish(
                    merged,
                    parents=parents,
                    generation=generation,
                    device_id=config["device_id"],
                    device_name=config["device_name"],
                )
                graph = V2Graph({**graph.snapshots, snapshot.snapshot_id: snapshot}, (snapshot.snapshot_id,))
                _save_base(config, [snapshot.snapshot_id], merged, graph)
            except Exception:
                rollback_local(local, new_revision)
                raise
            clear_pending_plan()
            set_runtime("synced", "多端修改已自动合并")
            return {"status": status(), "action": "merged", "revision": new_revision, "protocol_version": PROTOCOL_VERSION}
    except (WebDavError, SyncServiceError, ConflictError) as error:
        set_runtime("error", "同步未完成", error=getattr(error, "message", str(error)))
        raise
    except Exception:
        logger.exception("V2 同步执行发生未处理错误")
        set_runtime("error", "同步未完成", error="本机同步状态保存失败，请检查数据目录权限后重试")
        raise
    finally:
        operation_lock.release()
