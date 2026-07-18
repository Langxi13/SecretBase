"""Immutable snapshot-DAG repository for WebDAV services without ETag CAS."""

from __future__ import annotations

import copy
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sync_v2_crypto import (
    SyncV2CryptoError,
    bundle_digest,
    decode_key,
    decrypt_snapshot,
    encrypt_snapshot,
)
from sync_webdav import SYNC_ROOT_V2, RemoteChild, WebDavClient, WebDavError


SYNC_SCHEMA = 2
PROTOCOL = "snapshot-dag"
MAX_PARENTS = 32
MAX_REMOTE_SNAPSHOTS = 1_000
MAX_REMOTE_HISTORY_BYTES = 256 * 1024 * 1024
MAX_REMOTE_HISTORY_PLAINTEXT_BYTES = 256 * 1024 * 1024
MAX_DEVICE_NAME = 100
SNAPSHOT_NAME_RE = re.compile(
    r"^(?P<generation>[1-9][0-9]{0,18})-(?P<snapshot>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12})\.sbs$"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class V2Snapshot:
    payload: dict
    size: int
    digest: str
    path: tuple[str, ...]

    @property
    def snapshot_id(self) -> str:
        return str(self.payload["snapshot_id"])

    @property
    def generation(self) -> int:
        return int(self.payload["generation"])

    @property
    def parents(self) -> tuple[str, ...]:
        return tuple(self.payload.get("parents") or [])


@dataclass(frozen=True)
class V2Graph:
    snapshots: dict[str, V2Snapshot]
    frontier: tuple[str, ...]

    @property
    def max_generation(self) -> int:
        return max((item.generation for item in self.snapshots.values()), default=0)

    def get(self, snapshot_id: str) -> V2Snapshot:
        try:
            return self.snapshots[str(uuid.UUID(str(snapshot_id)))]
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise WebDavError("SYNC_SNAPSHOT_MISSING", "远端同步快照不存在", status_code=404) from error

    def ancestors(self, snapshot_id: str) -> set[str]:
        result: set[str] = set()
        pending = [str(snapshot_id)]
        while pending:
            current = pending.pop()
            if current in result:
                continue
            result.add(current)
            snapshot = self.snapshots.get(current)
            if snapshot:
                pending.extend(snapshot.parents)
        return result

    def common_ancestor(self, snapshot_ids: list[str] | tuple[str, ...]) -> V2Snapshot | None:
        if not snapshot_ids:
            return None
        common: set[str] | None = None
        for snapshot_id in snapshot_ids:
            ancestors = self.ancestors(snapshot_id)
            common = ancestors if common is None else common & ancestors
        if not common:
            return None
        return max(
            (self.snapshots[item] for item in common if item in self.snapshots),
            key=lambda item: (item.generation, item.snapshot_id),
            default=None,
        )


class SyncV2Repository:
    def __init__(self, client: WebDavClient, *, vault_id: str, space_id: str, sync_key: bytes):
        try:
            self.vault_id = str(uuid.UUID(str(vault_id)))
            self.space_id = str(uuid.UUID(str(space_id)))
        except (TypeError, ValueError, AttributeError) as error:
            raise WebDavError("SYNC_ID_INVALID", "同步空间身份无效", status_code=422) from error
        try:
            self.sync_key = decode_key(sync_key) if isinstance(sync_key, str) else sync_key
            if len(self.sync_key) != 32:
                raise ValueError
        except (TypeError, ValueError, AttributeError) as error:
            raise WebDavError("SYNC_KEY_INVALID", "同步密钥无效", status_code=422) from error
        self.client = client

    def ensure_layout(self, device_id: str | None = None) -> None:
        self.client.ensure_v2_layout(self.vault_id, self.space_id, device_id)

    def discover(self) -> V2Graph:
        root = self.client.v2_snapshots_path(self.vault_id, self.space_id)
        device_children = self.client.list_children(*root)
        snapshots: dict[str, V2Snapshot] = {}
        encrypted_bytes = 0
        plaintext_bytes = 0
        for device_child in device_children:
            if not device_child.is_collection:
                continue
            try:
                device_id = str(uuid.UUID(device_child.name))
            except (TypeError, ValueError, AttributeError):
                # WebDAV 服务可能在目录中保留隐藏文件，非 UUID 目录不属于协议对象。
                continue
            device_path = (*root, device_id)
            for child in self.client.list_children(*device_path):
                if child.is_collection:
                    continue
                match = SNAPSHOT_NAME_RE.fullmatch(child.name)
                if not match:
                    if child.name.endswith(".sbs"):
                        raise WebDavError("SYNC_SNAPSHOT_INVALID", "远端快照文件名无效")
                    continue
                snapshot_id = str(uuid.UUID(match.group("snapshot")))
                if snapshot_id in snapshots:
                    raise WebDavError("SYNC_SNAPSHOT_INVALID", "远端包含重复快照 ID")
                if len(snapshots) >= MAX_REMOTE_SNAPSHOTS:
                    raise WebDavError("SYNC_HISTORY_TOO_LARGE", "远端同步历史过大，请先执行历史压缩")
                generation = int(match.group("generation"))
                path = self.client.v2_snapshot_path(
                    self.vault_id,
                    self.space_id,
                    device_id,
                    generation,
                    snapshot_id,
                )
                remote = self.client.get(*path, require_etag=False)
                if remote is None:
                    raise WebDavError("SYNC_SNAPSHOT_MISSING", "远端快照在发现后消失，请重试")
                encrypted_bytes += len(remote.content)
                if encrypted_bytes > MAX_REMOTE_HISTORY_BYTES:
                    raise WebDavError("SYNC_HISTORY_TOO_LARGE", "远端同步历史占用过大，请先执行历史压缩")
                try:
                    payload = decrypt_snapshot(
                        remote.content,
                        self.sync_key,
                        vault_id=self.vault_id,
                        space_id=self.space_id,
                        snapshot_id=snapshot_id,
                    )
                except SyncV2CryptoError as error:
                    raise WebDavError("SYNC_SNAPSHOT_INVALID", "远端快照无法验证") from error
                plaintext_bytes += len(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                )
                if plaintext_bytes > MAX_REMOTE_HISTORY_PLAINTEXT_BYTES:
                    raise WebDavError("SYNC_HISTORY_TOO_LARGE", "远端同步历史解密后过大，请先执行历史压缩")
                if payload.get("vault_id") != self.vault_id or payload.get("space_id") != self.space_id:
                    raise WebDavError("SYNC_SNAPSHOT_INVALID", "远端快照不属于当前同步空间")
                self._validate_snapshot(payload, snapshot_id, device_id, generation)
                snapshots[snapshot_id] = V2Snapshot(
                    payload=payload,
                    size=len(remote.content),
                    digest=bundle_digest(remote.content),
                    path=path,
                )
        self._validate_graph(snapshots)
        children_ids = {
            parent
            for snapshot in snapshots.values()
            for parent in snapshot.parents
        }
        frontier = tuple(sorted(set(snapshots) - children_ids))
        if not frontier and snapshots:
            raise WebDavError("SYNC_GRAPH_INVALID", "远端同步历史没有可用的当前分支")
        if len(frontier) > MAX_PARENTS:
            raise WebDavError("SYNC_GRAPH_INVALID", "远端同步历史包含过多并发分支，请先在其他设备处理冲突")
        return V2Graph(snapshots=snapshots, frontier=frontier)

    def publish(
        self,
        document: dict,
        *,
        parents: list[str] | tuple[str, ...],
        generation: int,
        device_id: str,
        device_name: str,
    ) -> V2Snapshot:
        try:
            normalized_device = str(uuid.UUID(str(device_id)))
            normalized_parents = [str(uuid.UUID(str(item))) for item in parents]
            document_vault = str(uuid.UUID(str(document.get("vault_id"))))
        except (TypeError, ValueError, AttributeError) as error:
            raise WebDavError("SYNC_DOCUMENT_INVALID", "同步文档或提交关系无效", status_code=422) from error
        if document_vault != self.vault_id:
            raise WebDavError("SYNC_DOCUMENT_INVALID", "同步文档与远端 Vault 身份不一致", status_code=422)
        if len(normalized_parents) > MAX_PARENTS or len(set(normalized_parents)) != len(normalized_parents):
            raise WebDavError("SYNC_GRAPH_INVALID", "同步提交 parent 数量无效", status_code=422)
        if int(generation) < 1:
            raise WebDavError("SYNC_GRAPH_INVALID", "同步提交 generation 无效", status_code=422)
        if not normalized_parents and int(generation) != 1:
            raise WebDavError("SYNC_GRAPH_INVALID", "同步根快照 generation 必须为 1", status_code=422)
        snapshot_id = str(uuid.uuid4())
        payload = {
            "schema_version": SYNC_SCHEMA,
            "protocol": PROTOCOL,
            "vault_id": self.vault_id,
            "space_id": self.space_id,
            "snapshot_id": snapshot_id,
            "generation": int(generation),
            "parents": normalized_parents,
            "created_at": utc_now(),
            "device_id": normalized_device,
            "device_name": str(device_name or "设备")[:MAX_DEVICE_NAME],
            "document": copy.deepcopy(document),
        }
        content = encrypt_snapshot(
            payload,
            self.sync_key,
            vault_id=self.vault_id,
            space_id=self.space_id,
            snapshot_id=snapshot_id,
        )
        self.ensure_layout(normalized_device)
        path = self.client.v2_snapshot_path(
            self.vault_id,
            self.space_id,
            normalized_device,
            int(generation),
            snapshot_id,
        )
        self.client.put_unconditional(content, *path)
        stored = self.client.get(*path, require_etag=False)
        if stored is None or stored.content != content:
            raise WebDavError("SYNC_UPLOAD_VERIFY_FAILED", "远端快照上传后校验失败")
        return V2Snapshot(payload=payload, size=len(content), digest=bundle_digest(content), path=path)

    def list_history(self, graph: V2Graph | None = None) -> list[dict]:
        graph = graph or self.discover()
        items = []
        for snapshot in sorted(
            graph.snapshots.values(),
            key=lambda item: (item.generation, item.payload.get("created_at", ""), item.snapshot_id),
            reverse=True,
        ):
            payload = snapshot.payload
            items.append({
                "snapshot_id": snapshot.snapshot_id,
                "generation": snapshot.generation,
                "parents": list(snapshot.parents),
                "created_at": payload.get("created_at", ""),
                "device_id": payload.get("device_id", ""),
                "device_name": payload.get("device_name", "设备"),
                "is_frontier": snapshot.snapshot_id in graph.frontier,
                "size": snapshot.size,
            })
        return items

    def delete_remote(self) -> None:
        graph = self.discover()
        for snapshot in sorted(graph.snapshots.values(), key=lambda item: item.generation):
            self.client.delete(*snapshot.path, optional=False)
        # 删除空设备目录和空间目录。若有并发写入，保留对象并报告，不误报已清空。
        root = self.client.v2_snapshots_path(self.vault_id, self.space_id)
        for child in self.client.list_children(*root, optional=True):
            if not child.is_collection:
                continue
            try:
                uuid.UUID(child.name)
            except (TypeError, ValueError, AttributeError):
                continue
            if self.client.list_children(*root, child.name, optional=True):
                continue
            try:
                self.client.delete(*root, child.name, optional=False)
            except WebDavError:
                pass
        remaining = self.client.list_children(*root, optional=True)
        if remaining:
            raise WebDavError("SYNC_REMOTE_CHANGED", "删除期间远端出现新同步对象，请重新确认后重试", status_code=409)
        for path in (
            (SYNC_ROOT_V2, self.vault_id, self.space_id, "snapshots"),
            (SYNC_ROOT_V2, self.vault_id, self.space_id),
        ):
            self.client.delete(*path, optional=False)

    @staticmethod
    def _validate_snapshot(payload: dict, snapshot_id: str, device_id: str, filename_generation: int) -> None:
        if (
            payload.get("schema_version") != SYNC_SCHEMA
            or payload.get("protocol") != PROTOCOL
            or payload.get("snapshot_id") != snapshot_id
            or payload.get("device_id") != device_id
            or not isinstance(payload.get("document"), dict)
            or not isinstance(payload.get("parents"), list)
            or not isinstance(payload.get("device_name"), str)
            or len(payload["device_name"]) > MAX_DEVICE_NAME
        ):
            raise WebDavError("SYNC_SNAPSHOT_INVALID", "远端同步快照格式无效")
        try:
            generation = int(payload["generation"])
            parents = [str(uuid.UUID(str(item))) for item in payload["parents"]]
            uuid.UUID(str(payload["vault_id"]))
            uuid.UUID(str(payload["space_id"]))
            uuid.UUID(device_id)
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise WebDavError("SYNC_SNAPSHOT_INVALID", "远端同步快照身份或版本无效") from error
        if generation != filename_generation or generation < 1:
            raise WebDavError("SYNC_SNAPSHOT_INVALID", "远端同步快照文件名与内容版本不一致")
        if len(parents) > MAX_PARENTS or len(parents) != len(set(parents)) or snapshot_id in parents:
            raise WebDavError("SYNC_GRAPH_INVALID", "远端同步快照 parent 关系无效")

    @staticmethod
    def _validate_graph(snapshots: dict[str, V2Snapshot]) -> None:
        for snapshot in snapshots.values():
            for parent in snapshot.parents:
                if parent not in snapshots:
                    raise WebDavError("SYNC_GRAPH_INVALID", "远端同步快照缺少 parent")
                if snapshots[parent].generation >= snapshot.generation:
                    raise WebDavError("SYNC_GRAPH_INVALID", "远端同步快照 generation 回退")
            expected_generation = 1 if not snapshot.parents else max(snapshots[parent].generation for parent in snapshot.parents) + 1
            if snapshot.generation != expected_generation:
                raise WebDavError("SYNC_GRAPH_INVALID", "远端同步快照 generation 规则无效")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(snapshot_id: str) -> None:
            if snapshot_id in visiting:
                raise WebDavError("SYNC_GRAPH_INVALID", "远端同步历史包含循环")
            if snapshot_id in visited:
                return
            visiting.add(snapshot_id)
            for parent in snapshots[snapshot_id].parents:
                visit(parent)
            visiting.remove(snapshot_id)
            visited.add(snapshot_id)

        for snapshot_id in snapshots:
            visit(snapshot_id)
