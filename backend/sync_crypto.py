"""SecretBase Sync Bundle V1 encryption and recovery-code helpers."""

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


MAGIC = b"SBS1"
VERSION = 1
KIND_HEAD = 1
KIND_SNAPSHOT = 2
NONCE_LENGTH = 12
HEADER_LENGTH = 4 + 1 + 1 + NONCE_LENGTH
MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_PLAINTEXT_BYTES = 64 * 1024 * 1024
RECOVERY_PREFIX = "SBSYNC1"


class SyncCryptoError(ValueError):
    """Raised when a sync bundle or pairing secret is invalid."""


def generate_sync_key() -> bytes:
    return os.urandom(32)


def encode_key(key: bytes) -> str:
    if len(key) != 32:
        raise SyncCryptoError("同步密钥长度无效")
    return base64.urlsafe_b64encode(key).decode("ascii").rstrip("=")


def decode_key(value: str) -> bytes:
    try:
        encoded = str(value or "").strip()
        key = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except Exception as error:
        raise SyncCryptoError("同步密钥格式无效") from error
    if len(key) != 32:
        raise SyncCryptoError("同步密钥长度无效")
    return key


def _aad(kind: int, vault_id: str, object_id: str) -> bytes:
    try:
        normalized_vault_id = str(uuid.UUID(vault_id))
    except (ValueError, TypeError, AttributeError) as error:
        raise SyncCryptoError("同步 Vault ID 无效") from error
    object_id = str(object_id or "").strip()
    if not object_id or len(object_id) > 100:
        raise SyncCryptoError("同步对象 ID 无效")
    return b"SecretBase Sync V1\x00" + bytes([kind]) + normalized_vault_id.encode() + b"\x00" + object_id.encode()


def _gzip_decompress_limited(content: bytes) -> bytes:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(content), mode="rb") as stream:
            plaintext = stream.read(MAX_PLAINTEXT_BYTES + 1)
    except (OSError, EOFError) as error:
        raise SyncCryptoError("同步对象压缩内容无效") from error
    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        raise SyncCryptoError("同步对象解压后过大")
    return plaintext


def encrypt_bundle(payload: dict, key: bytes, *, kind: int, vault_id: str, object_id: str) -> bytes:
    if kind not in {KIND_HEAD, KIND_SNAPSHOT}:
        raise SyncCryptoError("同步对象类型无效")
    if len(key) != 32 or not isinstance(payload, dict):
        raise SyncCryptoError("同步加密参数无效")
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        raise SyncCryptoError("同步对象内容过大")
    compressed = gzip.compress(plaintext, compresslevel=6, mtime=0)
    nonce = os.urandom(NONCE_LENGTH)
    ciphertext = AESGCM(key).encrypt(nonce, compressed, _aad(kind, vault_id, object_id))
    bundle = MAGIC + bytes([VERSION, kind]) + nonce + ciphertext
    if len(bundle) > MAX_BUNDLE_BYTES:
        raise SyncCryptoError("同步对象密文过大")
    return bundle


def decrypt_bundle(content: bytes, key: bytes, *, kind: int, vault_id: str, object_id: str) -> dict:
    if len(content) > MAX_BUNDLE_BYTES or len(content) < HEADER_LENGTH + 16:
        raise SyncCryptoError("同步对象长度无效")
    if content[:4] != MAGIC or content[4] != VERSION or content[5] != kind:
        raise SyncCryptoError("同步对象格式或版本无效")
    if len(key) != 32:
        raise SyncCryptoError("同步密钥长度无效")
    nonce = content[6:HEADER_LENGTH]
    try:
        compressed = AESGCM(key).decrypt(
            nonce,
            content[HEADER_LENGTH:],
            _aad(kind, vault_id, object_id),
        )
    except Exception as error:
        raise SyncCryptoError("同步对象校验失败") from error
    plaintext = _gzip_decompress_limited(compressed)
    try:
        payload = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SyncCryptoError("同步对象内容无效") from error
    if not isinstance(payload, dict):
        raise SyncCryptoError("同步对象根节点无效")
    return payload


def encode_recovery_code(vault_id: str, key: bytes) -> str:
    try:
        payload = bytes([VERSION]) + uuid.UUID(vault_id).bytes + key
    except (ValueError, TypeError, AttributeError) as error:
        raise SyncCryptoError("恢复码参数无效") from error
    if len(key) != 32:
        raise SyncCryptoError("同步密钥长度无效")
    checksum = hashlib.sha256(RECOVERY_PREFIX.encode() + payload).digest()[:4]
    encoded = base64.b32encode(payload + checksum).decode("ascii").rstrip("=")
    groups = "-".join(encoded[index:index + 5] for index in range(0, len(encoded), 5))
    return f"{RECOVERY_PREFIX}-{groups}"


def decode_recovery_code(value: str) -> tuple[str, bytes]:
    normalized = "".join(
        character
        for character in str(value or "").upper()
        if character != "-" and not character.isspace()
    )
    if not normalized.startswith(RECOVERY_PREFIX):
        raise SyncCryptoError("同步恢复码格式无效")
    encoded = normalized[len(RECOVERY_PREFIX):]
    try:
        raw = base64.b32decode(encoded + "=" * (-len(encoded) % 8))
    except Exception as error:
        raise SyncCryptoError("同步恢复码格式无效") from error
    if len(raw) != 1 + 16 + 32 + 4 or raw[0] != VERSION:
        raise SyncCryptoError("同步恢复码版本无效")
    payload, checksum = raw[:-4], raw[-4:]
    expected = hashlib.sha256(RECOVERY_PREFIX.encode() + payload).digest()[:4]
    if not hmac.compare_digest(checksum, expected):
        raise SyncCryptoError("同步恢复码校验失败")
    return str(uuid.UUID(bytes=raw[1:17])), raw[17:49]


def pairing_uri(*, vault_id: str, key: bytes, base_url: str, username: str) -> str:
    query = urlencode({
        "v": VERSION,
        "vault_id": str(uuid.UUID(vault_id)),
        "key": encode_key(key),
        "url": str(base_url),
        "username": str(username),
    })
    return f"secretbase://sync/join?{query}"
