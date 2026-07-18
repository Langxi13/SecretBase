"""Conflict continuation and resolution for V2 snapshot synchronization."""

from __future__ import annotations

import copy
import secrets

from storage import vault_revision
from sync_merge import apply_resolutions, merge_documents
from sync_runtime import (
    SyncServiceError,
    active_pending_plan,
    clear_pending_plan,
    client,
    operation_lock,
    replace_local,
    rollback_local,
    set_runtime,
    status,
    validated_document,
)
from sync_state import load_sync_config, save_sync_config
from sync_v2_remote import SyncV2Repository, V2Graph
from sync_v2_shared import (
    PROTOCOL_VERSION,
    clear_state_best_effort as clear_sync_state_best_effort,
    documents_equal as _documents_equal,
    fold_remote_documents as _fold_remote_documents,
    minimal_parents as _minimal_parents,
    pending as _pending_v2,
    repository as _repository,
    save_base as _save_base,
    seed as _seed,
    join_local as _join_local,
)


def _finish_join_after_remote_fold(
    pending: dict,
    config: dict,
    graph: V2Graph,
    remote_store: SyncV2Repository,
    remote_value: dict,
) -> dict:
    """远端多分支冲突全部处理后，继续完成加入流程。"""
    local = validated_document(pending["local_document"])
    continuation = pending.get("continuation") or {}
    if continuation.get("merge_existing"):
        seed = _seed(remote_value)
        plan = merge_documents(seed, _join_local(remote_value, local), remote_value)
        if plan["conflicts"]:
            return _pending_v2(
                plan,
                config=config,
                frontier=graph.frontier,
                expected_revision=pending["expected_revision"],
                local=local,
                mode="join",
                continuation={
                    "kind": "join-final",
                    "remote_document": remote_value,
                },
            )
        merged = validated_document(plan["document"])
    else:
        merged = remote_value
    return _commit_join_document(
        pending,
        config,
        graph,
        remote_store,
        remote_value,
        merged,
    )


def _commit_join_document(
    pending: dict,
    config: dict,
    graph: V2Graph,
    remote_store: SyncV2Repository,
    remote_value: dict,
    merged: dict,
    *,
    force_publish: bool = False,
) -> dict:
    expected_revision = pending["expected_revision"]
    local_before = pending["local_document"]
    new_revision = replace_local(merged, expected_revision)
    try:
        if force_publish or not _documents_equal(merged, remote_value) or len(graph.frontier) > 1:
            snapshot = remote_store.publish(
                merged,
                parents=list(graph.frontier),
                generation=graph.max_generation + 1,
                device_id=config["device_id"],
                device_name=config["device_name"],
            )
            graph = V2Graph({**graph.snapshots, snapshot.snapshot_id: snapshot}, (snapshot.snapshot_id,))
            frontier = [snapshot.snapshot_id]
        else:
            frontier = list(graph.frontier)
        save_sync_config(config)
        _save_base(config, frontier, merged, graph)
    except Exception:
        rollback_local(local_before, new_revision)
        clear_sync_state_best_effort()
        clear_pending_plan()
        raise
    clear_pending_plan()
    set_runtime("synced", "已加入坚果云兼容的加密快照同步空间")
    return {
        "status": status(),
        "action": "downloaded",
        "revision": new_revision,
        "conflicts": [],
        "protocol_version": PROTOCOL_VERSION,
    }


def _finish_sync_after_remote_fold(
    pending: dict,
    config: dict,
    graph: V2Graph,
    remote_store: SyncV2Repository,
    remote_value: dict,
) -> dict:
    """远端分支已折叠后，继续执行本机与远端的最终三方合并。"""
    continuation = pending.get("continuation") or {}
    base = validated_document(continuation["base_document"])
    local = validated_document(pending["local_document"])
    expected_revision = pending["expected_revision"]
    if _documents_equal(local, base):
        new_revision = replace_local(remote_value, expected_revision)
        try:
            snapshot = remote_store.publish(
                remote_value,
                parents=list(graph.frontier),
                generation=graph.max_generation + 1,
                device_id=config["device_id"],
                device_name=config["device_name"],
            )
            graph = V2Graph({**graph.snapshots, snapshot.snapshot_id: snapshot}, (snapshot.snapshot_id,))
            _save_base(config, [snapshot.snapshot_id], remote_value, graph)
        except Exception:
            rollback_local(local, new_revision)
            raise
        clear_pending_plan()
        set_runtime("synced", "远端修改已应用")
        return {
            "status": status(),
            "action": "downloaded",
            "revision": new_revision,
            "protocol_version": PROTOCOL_VERSION,
        }

    plan = merge_documents(base, local, remote_value)
    if plan["conflicts"]:
        return _pending_v2(
            plan,
            config=config,
            frontier=graph.frontier,
            expected_revision=expected_revision,
            local=local,
            continuation={
                "kind": "sync-final",
                "base_frontier": list(continuation["base_frontier"]),
            },
        )
    merged = validated_document(plan["document"])
    new_revision = replace_local(merged, expected_revision)
    try:
        parents = _minimal_parents(
            graph,
            [*continuation["base_frontier"], *graph.frontier],
        ) or list(graph.frontier)
        snapshot = remote_store.publish(
            merged,
            parents=parents,
            generation=max(int(continuation["base_generation"]), graph.max_generation) + 1,
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
    return {
        "status": status(),
        "action": "merged",
        "revision": new_revision,
        "protocol_version": PROTOCOL_VERSION,
    }


def _commit_resolved_document(
    pending: dict,
    config: dict,
    graph: V2Graph,
    remote_store: SyncV2Repository,
    merged: dict,
) -> dict:
    expected_revision = pending["expected_revision"]
    local_before = pending["local_document"]
    new_revision = replace_local(merged, expected_revision)
    try:
        parents = _minimal_parents(graph, pending["remote_frontier"]) or list(graph.frontier)
        snapshot = remote_store.publish(
            merged,
            parents=parents,
            generation=graph.max_generation + 1,
            device_id=config["device_id"],
            device_name=config["device_name"],
        )
        if pending["mode"] == "join":
            save_sync_config(config)
        graph = V2Graph({**graph.snapshots, snapshot.snapshot_id: snapshot}, (snapshot.snapshot_id,))
        _save_base(config, [snapshot.snapshot_id], merged, graph)
    except Exception:
        rollback_local(local_before, new_revision)
        if pending["mode"] == "join":
            clear_sync_state_best_effort()
        clear_pending_plan()
        raise
    clear_pending_plan()
    set_runtime("synced", "同步冲突已处理")
    return {
        "status": status(),
        "action": "merged",
        "revision": new_revision,
        "protocol_version": PROTOCOL_VERSION,
    }


def resolve_conflicts(token: str, resolutions: dict[str, str]) -> dict:
    with operation_lock:
        pending = active_pending_plan()
        if not pending or pending.get("protocol_version") != PROTOCOL_VERSION or not secrets.compare_digest(str(token or ""), pending["token"]):
            raise SyncServiceError("SYNC_CONFLICT_EXPIRED", "同步冲突处理已失效，请重新同步", status_code=409)
        if vault_revision() != pending["expected_revision"]:
            clear_pending_plan()
            raise SyncServiceError("SYNC_CONFLICT_EXPIRED", "密码库已发生变化，请重新同步", status_code=409)
        config = load_sync_config() if pending["mode"] != "join" else pending["config"]
        if pending["mode"] != "join" and (not config or config.get("space_id") != pending["config"].get("space_id")):
            clear_pending_plan()
            raise SyncServiceError("SYNC_CONFIG_CHANGED", "同步配置已变化，请重新同步", status_code=409)
        expected_revision = pending["expected_revision"]
        with client(config) as webdav:
            remote_store = _repository(config, webdav)
            graph = remote_store.discover()
            if tuple(sorted(graph.frontier)) != tuple(sorted(pending["remote_frontier"])):
                clear_pending_plan()
                raise SyncServiceError("SYNC_REMOTE_CHANGED", "远端分支已变化，请重新同步", status_code=409)
            merged = validated_document(apply_resolutions(pending["plan"], resolutions))
            remote_merge = pending.get("remote_merge")
            if remote_merge:
                remote_value, next_plan, next_merge = _fold_remote_documents(
                    graph,
                    ancestor=validated_document(remote_merge["ancestor"]),
                    merged=merged,
                    frontier=remote_merge.get("remaining_frontier") or [],
                )
                if next_plan:
                    return _pending_v2(
                        next_plan,
                        config=config,
                        frontier=graph.frontier,
                        expected_revision=expected_revision,
                        local=pending["local_document"],
                        mode=pending["mode"],
                        remote_merge=next_merge,
                        continuation=pending.get("continuation"),
                    )
                kind = (pending.get("continuation") or {}).get("kind")
                if kind == "join":
                    return _finish_join_after_remote_fold(
                        pending,
                        config,
                        graph,
                        remote_store,
                        remote_value,
                    )
                if kind == "sync":
                    return _finish_sync_after_remote_fold(
                        pending,
                        config,
                        graph,
                        remote_store,
                        remote_value,
                    )
                raise SyncServiceError(
                    "SYNC_CONFLICT_INVALID",
                    "同步冲突上下文无效，请重新同步",
                    status_code=409,
                )

            continuation = pending.get("continuation") or {}
            if continuation.get("kind") == "join-final":
                return _commit_join_document(
                    pending,
                    config,
                    graph,
                    remote_store,
                    validated_document(continuation["remote_document"]),
                    merged,
                    force_publish=True,
                )
            return _commit_resolved_document(
                pending,
                config,
                graph,
                remote_store,
                merged,
            )
