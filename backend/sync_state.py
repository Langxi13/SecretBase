"""Local encrypted WebDAV synchronization configuration and merge baseline."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from config import SYNC_BASE_FILE, SYNC_SETTINGS_FILE
from crypto import decrypt_vault_with_key, encrypt_vault_with_key, parse_vault_header
from secure_settings import (
    SYNC_BASE_PURPOSE,
    SYNC_SETTINGS_PURPOSE,
    delete_files_transactionally,
    replace_file_atomically,
)
from storage import derive_unlocked_purpose_key
from sync_crypto import decode_key


SETTINGS_SCHEMA = 1
BASE_SCHEMA = 1


class SyncStateError(ValueError):
    pass


def _load(path: Path, purpose: str) -> dict | None:
    if not path.is_file():
        return None
    key, salt = derive_unlocked_purpose_key(purpose)
    content = path.read_bytes()
    header = parse_vault_header(content)
    if header["salt"] != salt:
        raise SyncStateError("同步设置不属于当前 Vault")
    try:
        payload = json.loads(decrypt_vault_with_key(key, content).decode("utf-8"))
    except Exception as error:
        raise SyncStateError("同步设置无法读取") from error
    if not isinstance(payload, dict):
        raise SyncStateError("同步设置格式无效")
    return payload


def _save(path: Path, purpose: str, payload: dict | None) -> None:
    if payload is None:
        replace_file_atomically(path, None)
        return
    key, salt = derive_unlocked_purpose_key(purpose)
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encrypted = encrypt_vault_with_key(key, salt, plaintext)
    replace_file_atomically(path, encrypted)


def load_sync_config() -> dict | None:
    payload = _load(Path(SYNC_SETTINGS_FILE), SYNC_SETTINGS_PURPOSE)
    if payload is None:
        return None
    if payload.get("schema_version") != SETTINGS_SCHEMA:
        raise SyncStateError("同步设置版本不受支持")
    required_text = ("base_url", "username", "password", "device_name")
    if any(not isinstance(payload.get(key), str) or not payload[key] for key in required_text):
        raise SyncStateError("同步设置格式无效")
    try:
        payload["vault_id"] = str(uuid.UUID(str(payload["vault_id"])))
        payload["device_id"] = str(uuid.UUID(str(payload["device_id"])))
        decode_key(payload["sync_key"])
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise SyncStateError("同步设置身份或密钥无效") from error
    if not isinstance(payload.get("auto_sync", True), bool):
        raise SyncStateError("同步设置格式无效")
    floor_generation = payload.get("history_floor_generation")
    floor_snapshot = payload.get("history_floor_snapshot_id")
    if floor_generation is not None or floor_snapshot is not None:
        try:
            if int(floor_generation) < 1:
                raise ValueError
            payload["history_floor_snapshot_id"] = str(uuid.UUID(str(floor_snapshot)))
        except (TypeError, ValueError, AttributeError) as error:
            raise SyncStateError("同步历史起点无效") from error
    return payload


def save_sync_config(payload: dict) -> None:
    data = dict(payload)
    data["schema_version"] = SETTINGS_SCHEMA
    _save(Path(SYNC_SETTINGS_FILE), SYNC_SETTINGS_PURPOSE, data)


def load_sync_base() -> dict | None:
    payload = _load(Path(SYNC_BASE_FILE), SYNC_BASE_PURPOSE)
    if payload is None:
        return None
    if payload.get("schema_version") != BASE_SCHEMA:
        raise SyncStateError("同步基线版本不受支持")
    try:
        payload["snapshot_id"] = str(uuid.UUID(str(payload["snapshot_id"])))
        generation = int(payload["generation"])
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise SyncStateError("同步基线版本信息无效") from error
    if (
        generation < 1
        or not isinstance(payload.get("head_etag"), str)
        or not payload["head_etag"]
        or not isinstance(payload.get("document"), dict)
        or not isinstance(payload.get("history"), list)
        or len(payload["history"]) > 10
        or not isinstance(payload.get("synced_at"), str)
    ):
        raise SyncStateError("同步基线格式无效")
    return payload


def save_sync_base(payload: dict) -> None:
    data = dict(payload)
    data["schema_version"] = BASE_SCHEMA
    _save(Path(SYNC_BASE_FILE), SYNC_BASE_PURPOSE, data)


def clear_sync_state() -> None:
    delete_files_transactionally(
        [
            (Path(SYNC_SETTINGS_FILE), "同步设置"),
            (Path(SYNC_BASE_FILE), "同步基线"),
        ],
        lambda: None,
    )


def clear_sync_base() -> None:
    _save(Path(SYNC_BASE_FILE), SYNC_BASE_PURPOSE, None)
