"""Shared state and document helpers for V2 snapshot synchronization."""

from __future__ import annotations

import copy
import logging
import os
import secrets
import uuid

from storage import vault_session_id
from sync_merge import merge_documents, public_conflicts
from sync_runtime import (
    SyncServiceError,
    device_name,
    set_pending_plan,
    set_runtime,
    status,
    validated_document,
)
from sync_state import save_sync_base
from sync_v2_crypto import encode_key
from sync_v2_remote import SyncV2Repository, V2Graph, utc_now
from sync_webdav import normalize_webdav_url


logger = logging.getLogger(__name__)

PROTOCOL_VERSION = 2
MAX_FRONTIER = 32


def new_key() -> bytes:
    return os.urandom(32)


def documents_equal(left: dict, right: dict) -> bool:
    """比较同步文档语义；条目列表顺序不是密码库数据的一部分。"""
    def canonical(value: dict) -> dict:
        result = copy.deepcopy(value)
        for collection in ("entries", "deleted_entries"):
            items = result.get(collection)
            if isinstance(items, list):
                result[collection] = sorted(
                    items,
                    key=lambda item: str(item.get("id", "")) if isinstance(item, dict) else "",
                )
        return result

    return canonical(left) == canonical(right)


def build_config(payload: dict, *, vault_id: str, space_id: str, sync_key: bytes) -> dict:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "base_url": normalize_webdav_url(payload.get("base_url", "")),
        "username": str(payload.get("username") or "").strip(),
        "password": str(payload.get("password") or ""),
        "vault_id": str(uuid.UUID(vault_id)),
        "space_id": str(uuid.UUID(space_id)),
        "sync_key": encode_key(sync_key),
        "device_id": str(uuid.uuid4()),
        "device_name": device_name(payload.get("device_name")),
        "auto_sync": payload.get("auto_sync", True) is not False,
    }


def repository(config: dict, webdav) -> SyncV2Repository:
    return SyncV2Repository(
        webdav,
        vault_id=config["vault_id"],
        space_id=config["space_id"],
        sync_key=config["sync_key"],
    )


def seed(value: dict) -> dict:
    result = copy.deepcopy(value)
    result["entries"] = []
    result["deleted_entries"] = []
    result["tags_meta"] = {}
    result["groups_meta"] = {}
    return result


def join_local(remote: dict, local: dict) -> dict:
    result = copy.deepcopy(remote)
    for key in ("entries", "deleted_entries", "tags_meta", "groups_meta"):
        result[key] = copy.deepcopy(local.get(key) or ([] if key in {"entries", "deleted_entries"} else {}))
    return result


def minimal_parents(graph: V2Graph, parents: list[str] | tuple[str, ...]) -> list[str]:
    normalized = sorted({str(uuid.UUID(str(item))) for item in parents})
    result = []
    for candidate in normalized:
        if any(candidate != other and candidate in graph.ancestors(other) for other in normalized):
            continue
        result.append(candidate)
    return result


def fold_remote_documents(
    graph: V2Graph,
    *,
    ancestor: dict,
    merged: dict,
    frontier: list[str] | tuple[str, ...],
) -> tuple[dict, dict | None, dict | None]:
    """按顺序折叠远端分支，冲突时保留尚未处理的分支上下文。"""
    frontier = list(frontier)
    merged = copy.deepcopy(merged)
    for index, snapshot_id in enumerate(frontier):
        branch = validated_document(graph.get(snapshot_id).payload["document"])
        plan = merge_documents(ancestor, merged, branch)
        if plan["conflicts"]:
            return plan["document"], plan, {
                "ancestor": copy.deepcopy(ancestor),
                "remaining_frontier": frontier[index + 1 :],
            }
        merged = plan["document"]
    return validated_document(merged), None, None


def remote_document(graph: V2Graph) -> tuple[dict, dict | None, dict | None]:
    """合并远端当前分支，并为分阶段冲突保留继续处理信息。"""
    if not graph.frontier:
        raise SyncServiceError("SYNC_REMOTE_MISSING", "远端同步空间没有可用快照", status_code=404)
    if len(graph.frontier) == 1:
        return validated_document(graph.get(graph.frontier[0]).payload["document"]), None, None
    common = graph.common_ancestor(graph.frontier)
    ancestor = (
        validated_document(common.payload["document"])
        if common is not None
        else seed(validated_document(graph.get(graph.frontier[0]).payload["document"]))
    )
    return fold_remote_documents(
        graph,
        ancestor=ancestor,
        merged=ancestor,
        frontier=graph.frontier,
    )


def save_base(config: dict, frontier: list[str] | tuple[str, ...], value: dict, graph: V2Graph) -> None:
    normalized_frontier = [str(uuid.UUID(str(item))) for item in frontier]
    if not normalized_frontier or len(normalized_frontier) > MAX_FRONTIER:
        raise SyncServiceError("SYNC_BASE_INVALID", "同步基线分支数量无效", status_code=409)
    snapshots = [graph.get(item) for item in normalized_frontier]
    generation = max(item.generation for item in snapshots)
    history = [
        {
            "snapshot_id": item.snapshot_id,
            "generation": item.generation,
            "created_at": item.payload.get("created_at", ""),
            "device_id": item.payload.get("device_id", ""),
            "device_name": item.payload.get("device_name", "设备"),
            "is_frontier": item.snapshot_id in normalized_frontier,
        }
        for item in sorted(graph.snapshots.values(), key=lambda item: item.generation, reverse=True)[:50]
    ]
    save_sync_base({
        "protocol_version": PROTOCOL_VERSION,
        "space_id": config["space_id"],
        "frontier": normalized_frontier,
        "snapshot_id": normalized_frontier[0],
        "generation": generation,
        "head_etag": "",
        "synced_at": utc_now(),
        "document": copy.deepcopy(value),
        "history": history,
    })


def pending(
    plan: dict,
    *,
    config: dict,
    frontier: tuple[str, ...],
    expected_revision: int,
    local: dict,
    mode: str = "sync",
    remote_merge: dict | None = None,
    continuation: dict | None = None,
) -> dict:
    token = secrets.token_urlsafe(32)
    value = {
        "token": token,
        "mode": mode,
        "protocol_version": PROTOCOL_VERSION,
        "vault_session_id": vault_session_id(),
        "expected_revision": expected_revision,
        "remote_frontier": list(frontier),
        "plan": plan,
        "config": copy.deepcopy(config),
        "local_document": copy.deepcopy(local),
    }
    if remote_merge is not None:
        value["remote_merge"] = copy.deepcopy(remote_merge)
    if continuation is not None:
        value["continuation"] = copy.deepcopy(continuation)
    set_pending_plan(value)
    conflicts = public_conflicts(plan)
    set_runtime("conflict", "发现多端修改冲突", conflicts=len(conflicts))
    return {"status": status(), "conflict_token": token, "conflicts": conflicts}


def clear_state_best_effort() -> None:
    from sync_state import clear_sync_state

    try:
        clear_sync_state()
    except Exception:
        logger.exception("清理 V2 同步状态失败")
