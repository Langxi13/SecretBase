"""Encryption and pairing helpers for the ETag-free Sync Bundle V2."""

from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import io
import json
import os
import uuid
from urllib.parse import urlencode

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


MAGIC = b"SBS2"
VERSION = 2
KIND_SNAPSHOT = 1
NONCE_LENGTH = 12
HEADER_LENGTH = 4 + 1 + 1 + NONCE_LENGTH
MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_PLAINTEXT_BYTES = 64 * 1024 * 1024
RECOVERY_PREFIX = "SBSYNC2"


class SyncV2CryptoError(ValueError):
    """Raised when a V2 bundle or pairing secret is invalid."""


def _uuid(value: str, label: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise SyncV2CryptoError(f"{label}无效") from error


def _key(key: bytes) -> bytes:
    if not isinstance(key, bytes) or len(key) != 32:
        raise SyncV2CryptoError("同步密钥长度无效")
    return key


def encode_key(key: bytes) -> str:
    return base64.urlsafe_b64encode(_key(key)).decode("ascii").rstrip("=")


def decode_key(value: str) -> bytes:
    try:
        encoded = str(value or "").strip()
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except Exception as error:
        raise SyncV2CryptoError("同步密钥格式无效") from error
    return _key(decoded)


def _aad(vault_id: str, space_id: str, snapshot_id: str) -> bytes:
    return (
        b"SecretBase Sync V2\x00"
        + _uuid(vault_id, "Vault ID").encode("ascii")
        + b"\x00"
        + _uuid(space_id, "同步空间 ID").encode("ascii")
        + b"\x00"
        + _uuid(snapshot_id, "快照 ID").encode("ascii")
    )


def encrypt_snapshot(payload: dict, key: bytes, *, vault_id: str, space_id: str, snapshot_id: str) -> bytes:
    if not isinstance(payload, dict):
        raise SyncV2CryptoError("同步快照内容无效")
    key = _key(key)
    vault_id = _uuid(vault_id, "Vault ID")
    space_id = _uuid(space_id, "同步空间 ID")
    snapshot_id = _uuid(snapshot_id, "快照 ID")
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        raise SyncV2CryptoError("同步快照解压后过大")
    compressed = gzip.compress(plaintext, compresslevel=6, mtime=0)
    nonce = os.urandom(NONCE_LENGTH)
    ciphertext = AESGCM(key).encrypt(nonce, compressed, _aad(vault_id, space_id, snapshot_id))
    result = MAGIC + bytes([VERSION, KIND_SNAPSHOT]) + nonce + ciphertext
    if len(result) > MAX_BUNDLE_BYTES:
        raise SyncV2CryptoError("同步快照密文过大")
    return result


def _decompress_limited(content: bytes) -> bytes:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(content), mode="rb") as stream:
            plaintext = stream.read(MAX_PLAINTEXT_BYTES + 1)
    except (OSError, EOFError) as error:
        raise SyncV2CryptoError("同步快照压缩内容无效") from error
    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        raise SyncV2CryptoError("同步快照解压后过大")
    return plaintext


def decrypt_snapshot(content: bytes, key: bytes, *, vault_id: str, space_id: str, snapshot_id: str) -> dict:
    if not isinstance(content, bytes) or len(content) < HEADER_LENGTH + 16 or len(content) > MAX_BUNDLE_BYTES:
        raise SyncV2CryptoError("同步快照长度无效")
    if content[:4] != MAGIC or content[4] != VERSION or content[5] != KIND_SNAPSHOT:
        raise SyncV2CryptoError("同步快照格式或版本无效")
    try:
        compressed = AESGCM(_key(key)).decrypt(
            content[6:HEADER_LENGTH],
            content[HEADER_LENGTH:],
            _aad(vault_id, space_id, snapshot_id),
        )
    except Exception as error:
        raise SyncV2CryptoError("同步快照校验失败") from error
    try:
        payload = json.loads(_decompress_limited(compressed).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SyncV2CryptoError("同步快照内容无效") from error
    if not isinstance(payload, dict):
        raise SyncV2CryptoError("同步快照根节点无效")
    return payload


def encode_recovery_code(vault_id: str, space_id: str, key: bytes) -> str:
    try:
        payload = bytes([VERSION]) + uuid.UUID(vault_id).bytes + uuid.UUID(space_id).bytes + _key(key)
    except (TypeError, ValueError, AttributeError) as error:
        raise SyncV2CryptoError("恢复码参数无效") from error
    checksum = hashlib.sha256(RECOVERY_PREFIX.encode("ascii") + payload).digest()[:4]
    encoded = base64.b32encode(payload + checksum).decode("ascii").rstrip("=")
    grouped = "-".join(encoded[index:index + 5] for index in range(0, len(encoded), 5))
    return f"{RECOVERY_PREFIX}-{grouped}"


def decode_recovery_code(value: str) -> tuple[str, str, bytes]:
    normalized = "".join(
        character for character in str(value or "").upper()
        if character != "-" and not character.isspace()
    )
    prefix = RECOVERY_PREFIX
    if not normalized.startswith(prefix):
        raise SyncV2CryptoError("同步恢复码格式无效")
    try:
        raw = base64.b32decode(normalized[len(prefix):] + "=" * (-len(normalized[len(prefix):]) % 8))
    except Exception as error:
        raise SyncV2CryptoError("同步恢复码格式无效") from error
    expected_length = 1 + 16 + 16 + 32 + 4
    if len(raw) != expected_length or raw[0] != VERSION:
        raise SyncV2CryptoError("同步恢复码版本无效")
    body, checksum = raw[:-4], raw[-4:]
    expected = hashlib.sha256(prefix.encode("ascii") + body).digest()[:4]
    if not hmac.compare_digest(checksum, expected):
        raise SyncV2CryptoError("同步恢复码校验失败")
    return str(uuid.UUID(bytes=raw[1:17])), str(uuid.UUID(bytes=raw[17:33])), raw[33:65]


def pairing_uri(
    *,
    vault_id: str,
    space_id: str,
    key: bytes,
    base_url: str,
    username: str,
    recovery_code: str | None = None,
) -> str:
    """Build a V2 pairing URI without including the WebDAV password.

    The recovery code already contains the space identity and sync key.  New
    links therefore expose that single importable secret instead of duplicating
    the raw key in a second query parameter.  ``key`` remains an argument so
    older callers retain validation of the current configuration.
    """
    if recovery_code:
        decoded_vault, decoded_space, decoded_key = decode_recovery_code(recovery_code)
        if (
            decoded_vault != _uuid(vault_id, "Vault ID")
            or decoded_space != _uuid(space_id, "同步空间 ID")
            or not hmac.compare_digest(decoded_key, key)
        ):
            raise SyncV2CryptoError("恢复码与当前同步空间不匹配")
    else:
        recovery_code = encode_recovery_code(vault_id, space_id, key)
    query = urlencode({
        "v": VERSION,
        "vault_id": _uuid(vault_id, "Vault ID"),
        "space_id": _uuid(space_id, "同步空间 ID"),
        "recovery_code": recovery_code,
        "url": str(base_url),
        "username": str(username),
    })
    return f"secretbase://sync/join?{query}"


def bundle_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
