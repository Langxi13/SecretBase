"""与 vault 密钥绑定的本地加密设置辅助函数。"""

import hashlib
import logging
import os
import secrets
from collections.abc import Callable, Iterable
from pathlib import Path

from crypto import decrypt_vault_with_key, encrypt_vault_with_key, parse_vault_header


AI_SETTINGS_PURPOSE = "ai-settings"
AI_HISTORY_PURPOSE = "ai-conversation-history-v1"
SYNC_SETTINGS_PURPOSE = "webdav-sync-settings-v1"
SYNC_BASE_PURPOSE = "webdav-sync-base-v1"

logger = logging.getLogger(__name__)


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


def replace_files_transactionally(
    replacements: Iterable[tuple[Path, bytes | None, bytes | None, str]],
    commit: Callable[[], None],
) -> None:
    """原子替换一组小文件，并在提交失败时按逆序恢复。"""
    applied_states: list[tuple[Path, str, bytes | None]] = []
    try:
        for path, expected_content, replacement, label in replacements:
            current_content = path.read_bytes() if path.exists() else None
            if current_content != expected_content:
                raise RuntimeError(f"{label}在事务期间发生变化")
            applied_states.append((path, label, expected_content))
            replace_file_atomically(path, replacement)
        commit()
    except Exception:
        for path, label, original_content in reversed(applied_states):
            try:
                replace_file_atomically(path, original_content)
            except Exception as rollback_error:
                logger.critical("安全文件事务回滚%s失败: %s", label, rollback_error)
        raise


def delete_files_transactionally(
    files: Iterable[tuple[Path, str]],
    commit: Callable[[], None],
) -> None:
    """删除一组小文件，并与调用方提交动作组成同一事务。"""
    replacements = []
    for path, label in files:
        original_content = path.read_bytes() if path.exists() else None
        if original_content is not None:
            replacements.append((path, original_content, None, label))
    replace_files_transactionally(replacements, commit)


def rekey_secure_files_transactionally(
    secure_files: Iterable[tuple[Path, str, str]],
    old_vault_key: bytes,
    old_salt: bytes,
    new_vault_key: bytes,
    new_salt: bytes,
    commit: Callable[[], None],
) -> None:
    """轮换安全文件并提交 vault；任一步失败都恢复已触碰的文件。"""
    replacements = []
    for path, purpose, label in secure_files:
        state = prepare_rekey(
            path,
            purpose,
            old_vault_key,
            old_salt,
            new_vault_key,
            new_salt,
        )
        if state is None:
            continue

        original_content, replacement = state
        if replacement is None:
            logger.warning("%s无法随主密码迁移，将清除遗留文件", label)
        replacements.append((path, original_content, replacement, label))

    replace_files_transactionally(replacements, commit)
