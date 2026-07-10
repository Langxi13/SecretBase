"""与 vault 密钥绑定的本地加密设置辅助函数。"""

import hashlib
import os
import secrets
from pathlib import Path

from crypto import decrypt_vault_with_key, encrypt_vault_with_key, parse_vault_header


AI_SETTINGS_PURPOSE = "ai-settings"


def derive_purpose_key(vault_key: bytes, salt: bytes, purpose: str) -> bytes:
    """从 vault 密钥派生用途隔离的本地设置密钥。"""
    return hashlib.pbkdf2_hmac(
        "sha256",
        vault_key,
        b"SecretBase:" + salt + b":" + purpose.encode("utf-8"),
        iterations=100_000,
        dklen=32,
    )


def replace_file_atomically(path: Path, content: bytes | None) -> None:
    """原子替换或删除小型本地加密设置文件。"""
    if content is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        with open(temporary_path, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def prepare_rekey(
    path: Path,
    purpose: str,
    old_vault_key: bytes,
    old_salt: bytes,
    new_vault_key: bytes,
    new_salt: bytes,
) -> tuple[bytes, bytes | None] | None:
    """返回原始和重加密后的设置内容；无法读取时建议删除遗留文件。"""
    if not path.exists():
        return None

    original_content = path.read_bytes()
    try:
        header = parse_vault_header(original_content)
        if header["salt"] != old_salt:
            raise ValueError("安全设置不属于当前 vault")
        plaintext = decrypt_vault_with_key(derive_purpose_key(old_vault_key, old_salt, purpose), original_content)
        replacement = encrypt_vault_with_key(derive_purpose_key(new_vault_key, new_salt, purpose), new_salt, plaintext)
    except Exception:
        replacement = None
    return original_content, replacement
