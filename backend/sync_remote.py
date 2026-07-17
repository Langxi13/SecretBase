"""Encrypted snapshot repository layered on strict WebDAV primitives."""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sync_crypto import KIND_HEAD, KIND_SNAPSHOT, decrypt_bundle, encrypt_bundle
from sync_webdav import SYNC_ROOT, RemoteObject, WebDavClient, WebDavError


SYNC_SCHEMA = 1
HISTORY_LIMIT = 10


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RemoteHead:
    payload: dict
    etag: str

    @property
    def snapshot_id(self) -> str:
        return str(self.payload["current_snapshot_id"])

    @property
    def generation(self) -> int:
        return int(self.payload["generation"])


class SyncRepository:
    def __init__(self, client: WebDavClient, *, vault_id: str, sync_key: bytes):
        self.client = client
        self.vault_id = str(uuid.UUID(vault_id))
        self.sync_key = sync_key

    def ensure_layout(self) -> None:
        self.client.ensure_layout(self.vault_id)

    def load_head(self, *, optional: bool = False) -> RemoteHead | None:
        remote = self.client.get(*self.client.head_path(self.vault_id), optional=optional)
        if remote is None:
            return None
        payload = decrypt_bundle(
            remote.content,
            self.sync_key,
            kind=KIND_HEAD,
            vault_id=self.vault_id,
            object_id="head",
        )
        self._validate_head(payload)
        return RemoteHead(payload=payload, etag=remote.etag)

    def load_snapshot(self, snapshot_id: str) -> dict:
        snapshot_id = str(uuid.UUID(snapshot_id))
        remote = self.client.get(*self.client.snapshot_path(self.vault_id, snapshot_id))
        if remote is None:
            raise WebDavError("SYNC_SNAPSHOT_MISSING", "远端同步快照不存在")
        payload = decrypt_bundle(
            remote.content,
            self.sync_key,
            kind=KIND_SNAPSHOT,
            vault_id=self.vault_id,
            object_id=snapshot_id,
        )
        self._validate_snapshot(payload, snapshot_id)
        return payload

    def current(self, *, optional: bool = False) -> tuple[RemoteHead, dict] | None:
        head = self.load_head(optional=optional)
        if head is None:
            return None
        return head, self.load_snapshot(head.snapshot_id)

    def publish(
        self,
        document: dict,
        *,
        current_head: RemoteHead | None,
        device_id: str,
        device_name: str,
        reset_history: bool = False,
        cleanup_history: bool = True,
    ) -> tuple[RemoteHead, dict, list[str]]:
        try:
            document_vault_id = str(uuid.UUID(str(document.get("vault_id"))))
        except (AttributeError, TypeError, ValueError) as error:
            raise WebDavError("SYNC_DOCUMENT_INVALID", "同步文档缺少有效 Vault ID", status_code=422) from error
        if document_vault_id != self.vault_id:
            raise WebDavError("SYNC_DOCUMENT_INVALID", "同步文档与远端 Vault 身份不一致", status_code=422)
        try:
            normalized_device_id = str(uuid.UUID(str(device_id)))
        except (TypeError, ValueError, AttributeError) as error:
            raise WebDavError("SYNC_DEVICE_INVALID", "同步设备 ID 无效", status_code=422) from error

        snapshot_id = str(uuid.uuid4())
        created_at = utc_now()
        parents = [] if current_head is None else [current_head.snapshot_id]
        snapshot = {
            "schema_version": SYNC_SCHEMA,
            "vault_id": self.vault_id,
            "snapshot_id": snapshot_id,
            "parents": parents,
            "created_at": created_at,
            "device_id": normalized_device_id,
            "device_name": str(device_name)[:100],
            "document": copy.deepcopy(document),
        }
        snapshot_bytes = encrypt_bundle(
            snapshot,
            self.sync_key,
            kind=KIND_SNAPSHOT,
            vault_id=self.vault_id,
            object_id=snapshot_id,
        )
        snapshot_path = self.client.snapshot_path(self.vault_id, snapshot_id)
        self.client.put(snapshot_bytes, *snapshot_path, if_none_match=True)

        previous_history = [] if current_head is None else list(current_head.payload.get("history") or [])
        history = [{
            "snapshot_id": snapshot_id,
            "created_at": created_at,
            "device_id": normalized_device_id,
            "device_name": str(device_name)[:100],
        }]
        if not reset_history:
            history.extend(previous_history[:HISTORY_LIMIT - 1])
        head_payload = {
            "schema_version": SYNC_SCHEMA,
            "vault_id": self.vault_id,
            "generation": 1 if current_head is None else current_head.generation + 1,
            "current_snapshot_id": snapshot_id,
            "history": history,
        }
        head_bytes = encrypt_bundle(
            head_payload,
            self.sync_key,
            kind=KIND_HEAD,
            vault_id=self.vault_id,
            object_id="head",
        )
        try:
            etag = self.client.put(
                head_bytes,
                *self.client.head_path(self.vault_id),
                if_match=current_head.etag if current_head else None,
                if_none_match=current_head is None,
            )
        except Exception:
            try:
                self.client.delete(*snapshot_path)
            except WebDavError:
                pass
            raise

        retained = {item["snapshot_id"] for item in history}
        dropped = [
            str(item.get("snapshot_id"))
            for item in previous_history
            if item.get("snapshot_id") and item.get("snapshot_id") not in retained
        ]
        if cleanup_history:
            for old_snapshot_id in dropped:
                try:
                    self.client.delete(*self.client.snapshot_path(self.vault_id, old_snapshot_id))
                except WebDavError:
                    pass
        return RemoteHead(head_payload, etag), snapshot, dropped

    def list_history(self, head: RemoteHead | None = None) -> list[dict]:
        head = head or self.load_head()
        return copy.deepcopy(head.payload.get("history") or [])

    def delete_remote(self) -> None:
        head = self.load_head(optional=True)
        history = [] if head is None else list(head.payload.get("history") or [])
        if head is not None:
            self.client.delete(*self.client.head_path(self.vault_id), if_match=head.etag)

        try:
            self.client.delete(SYNC_ROOT, self.vault_id, "snapshots")
        except WebDavError:
            for item in history:
                snapshot_id = item.get("snapshot_id")
                if snapshot_id:
                    self.client.delete(*self.client.snapshot_path(self.vault_id, snapshot_id))
            self.client.delete(SYNC_ROOT, self.vault_id, "snapshots")
        self.client.delete(SYNC_ROOT, self.vault_id)

    def _validate_head(self, payload: dict) -> None:
        if payload.get("schema_version") != SYNC_SCHEMA or payload.get("vault_id") != self.vault_id:
            raise WebDavError("SYNC_HEAD_INVALID", "远端同步索引格式无效")
        try:
            uuid.UUID(str(payload["current_snapshot_id"]))
            generation = int(payload["generation"])
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise WebDavError("SYNC_HEAD_INVALID", "远端同步索引缺少版本信息") from error
        history = payload.get("history")
        if generation < 1 or not isinstance(history, list) or len(history) > HISTORY_LIMIT:
            raise WebDavError("SYNC_HEAD_INVALID", "远端同步索引历史无效")
        if not history or any(not isinstance(item, dict) for item in history):
            raise WebDavError("SYNC_HEAD_INVALID", "远端同步索引历史项无效")
        try:
            snapshot_ids = [str(uuid.UUID(str(item["snapshot_id"]))) for item in history]
            device_ids = [str(uuid.UUID(str(item["device_id"]))) for item in history]
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise WebDavError("SYNC_HEAD_INVALID", "远端同步索引历史版本无效") from error
        if any(
            not isinstance(item.get("created_at"), str)
            or not isinstance(item.get("device_name"), str)
            or len(item["device_name"]) > 100
            for item in history
        ) or len(device_ids) != len(history):
            raise WebDavError("SYNC_HEAD_INVALID", "远端同步索引设备信息无效")
        if len(snapshot_ids) != len(set(snapshot_ids)):
            raise WebDavError("SYNC_HEAD_INVALID", "远端同步索引包含重复历史版本")
        if snapshot_ids[0] != str(payload["current_snapshot_id"]):
            raise WebDavError("SYNC_HEAD_INVALID", "远端同步索引当前版本不一致")

    def _validate_snapshot(self, payload: dict, snapshot_id: str) -> None:
        document = payload.get("document")
        if (
            payload.get("schema_version") != SYNC_SCHEMA
            or payload.get("vault_id") != self.vault_id
            or payload.get("snapshot_id") != snapshot_id
            or not isinstance(document, dict)
            or document.get("vault_id") != self.vault_id
            or not isinstance(payload.get("parents"), list)
        ):
            raise WebDavError("SYNC_SNAPSHOT_INVALID", "远端同步快照格式无效")
        try:
            uuid.UUID(str(payload["device_id"]))
            parents = [str(uuid.UUID(str(parent))) for parent in payload["parents"]]
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise WebDavError("SYNC_SNAPSHOT_INVALID", "远端同步快照版本关系无效") from error
        if (
            len(parents) > 2
            or len(parents) != len(set(parents))
            or not isinstance(payload.get("created_at"), str)
            or not isinstance(payload.get("device_name"), str)
            or len(payload["device_name"]) > 100
        ):
            raise WebDavError("SYNC_SNAPSHOT_INVALID", "远端同步快照设备信息无效")
