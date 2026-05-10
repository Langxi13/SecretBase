import os
import json
import logging
import shutil
import time
import hashlib
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import VAULT_PATH, BACKUP_DIR, MAX_BACKUPS
from crypto import (
    SecureKey,
    decrypt_vault,
    decrypt_vault_with_key,
    derive_key,
    encrypt_vault_with_key,
    generate_salt,
    parse_vault_header,
)
from models import VaultData, Entry, EntryCreate, EntryUpdate

logger = logging.getLogger(__name__)

# 内存中缓存解锁状态。V2 不再长期保存主密码字符串。
_vault_key: Optional[SecureKey] = None
_vault_data: Optional[VaultData] = None
_last_activity_at: Optional[float] = None
_session_token: Optional[str] = None
_vault_fingerprint: Optional[str] = None


class ConflictError(Exception):
    """Vault 文件已被外部修改。"""
    pass


class VaultLockTimeoutError(Exception):
    """获取 vault 文件锁超时。"""
    pass


class VaultFileLock:
    """跨平台的简单独占文件锁。"""

    def __init__(self, filepath: str, timeout: float = 10.0):
        self.lock_path = f"{filepath}.lock"
        self.timeout = timeout
        self.fd: int | None = None

    def acquire(self):
        start = time.time()
        while True:
            try:
                self.fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, f"pid={os.getpid()} created_at={time.time()}\n".encode("utf-8"))
                return
            except FileExistsError:
                if time.time() - start >= self.timeout:
                    raise VaultLockTimeoutError("获取 vault 文件锁超时")
                time.sleep(0.1)

    def release(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
            try:
                os.unlink(self.lock_path)
            except FileNotFoundError:
                pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


def _fingerprint_content(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _fingerprint_vault_file() -> str | None:
    if not is_initialized():
        return None
    with open(VAULT_PATH, "rb") as f:
        return _fingerprint_content(f.read())


def _set_vault_fingerprint_from_content(content: bytes):
    global _vault_fingerprint
    _vault_fingerprint = _fingerprint_content(content)


def _ensure_current_vault_unchanged():
    if _vault_fingerprint is None or not is_initialized():
        return
    current = _fingerprint_vault_file()
    if current != _vault_fingerprint:
        raise ConflictError("Vault 文件已被外部修改，请重新解锁后再操作")


def _encrypt_with_current_key(plaintext: bytes) -> bytes:
    if _vault_key is None:
        raise ValueError("Vault 未解锁")
    return encrypt_vault_with_key(_vault_key.get(), _vault_key.salt, plaintext)


def _decrypt_with_current_key(content: bytes) -> bytes:
    if _vault_key is None:
        raise ValueError("Vault 未解锁")
    header = parse_vault_header(content)
    if header["salt"] != _vault_key.salt:
        raise ValueError("备份文件不是当前解锁会话可验证的 vault")
    return decrypt_vault_with_key(_vault_key.get(), content)


def create_session_token() -> str:
    """创建新的单用户 session token，旧 token 立即失效。"""
    global _session_token
    _session_token = secrets.token_urlsafe(32)
    return _session_token


def validate_session_token(token: str | None) -> bool:
    return bool(_session_token and token and secrets.compare_digest(_session_token, token))


def is_initialized() -> bool:
    """检查 vault 是否已初始化"""
    return os.path.exists(VAULT_PATH)


def get_vault_content() -> bytes:
    """获取 vault 文件内容"""
    if not is_initialized():
        return None
    with open(VAULT_PATH, 'rb') as f:
        return f.read()


def save_vault(content: bytes):
    """保存 vault 文件"""
    global _vault_fingerprint
    with VaultFileLock(VAULT_PATH):
        _ensure_current_vault_unchanged()
        if is_initialized():
            _create_backup_unlocked()

        tmp_path = f"{VAULT_PATH}.tmp"
        with open(tmp_path, 'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, VAULT_PATH)
        _set_vault_fingerprint_from_content(content)


def import_encrypted_vault(content: bytes) -> int:
    """导入加密 vault 文件，必须能用当前主密码解密。"""
    global _vault_data

    if not is_unlocked():
        raise ValueError("Vault 未解锁")

    plaintext = _decrypt_with_current_key(content)
    data = VaultData(**json.loads(plaintext.decode('utf-8')))
    save_vault(content)
    _vault_data = data
    logger.info("导入加密 vault 成功")
    return len(data.entries)


def import_encrypted_vault_with_password(content: bytes, password: str) -> int:
    """用备份主密码解密旧备份，再用当前会话密钥写回。"""
    global _vault_data

    if not is_unlocked():
        raise ValueError("Vault 未解锁")

    plaintext = decrypt_vault(password, content)
    data = VaultData(**json.loads(plaintext.decode('utf-8')))
    save_vault(_encrypt_with_current_key(plaintext))
    _vault_data = data
    logger.info("导入旧加密 vault 成功")
    return len(data.entries)


def read_encrypted_vault_with_current_key(content: bytes) -> VaultData:
    """读取使用当前解锁密钥可验证的加密 vault 内容。"""
    plaintext = _decrypt_with_current_key(content)
    return VaultData(**json.loads(plaintext.decode('utf-8')))


def read_encrypted_vault_with_password(content: bytes, password: str) -> VaultData:
    """用指定主密码读取加密 vault 内容。"""
    plaintext = decrypt_vault(password, content)
    return VaultData(**json.loads(plaintext.decode('utf-8')))


def touch_activity():
    """记录最近一次解锁态活动时间。"""
    global _last_activity_at
    if is_unlocked():
        _last_activity_at = time.time()


def enforce_auto_lock(auto_lock_minutes: int) -> bool:
    """超过空闲时间后锁定 vault，返回是否发生自动锁定。"""
    global _last_activity_at
    if not is_unlocked() or auto_lock_minutes <= 0:
        return False

    now = time.time()
    if _last_activity_at is None:
        _last_activity_at = now
        return False

    if now - _last_activity_at >= auto_lock_minutes * 60:
        lock_vault()
        return True

    return False


def export_plain_vault() -> str:
    """导出当前明文 vault JSON。"""
    return get_vault_data().model_dump_json()


def import_plain_vault(
    data: dict,
    conflict_strategy: str = "skip",
    selected_entry_ids: list[str] | None = None,
    conflict_resolutions: dict[str, str] | None = None,
) -> dict:
    """导入明文 vault JSON，按 id 处理冲突。"""
    incoming = VaultData(**data)
    if selected_entry_ids is not None:
        selected_ids = set(selected_entry_ids)
        incoming.entries = [entry for entry in incoming.entries if entry.id in selected_ids]
    conflict_resolutions = conflict_resolutions or {}
    vault = get_vault_data()
    existing_by_id = {entry.id: entry for entry in vault.entries}
    conflicts = []

    for entry in incoming.entries:
        if entry.id in existing_by_id:
            conflicts.append({
                "id": entry.id,
                "existing_title": existing_by_id[entry.id].title,
                "import_title": entry.title
            })

    unresolved_conflicts = [conflict for conflict in conflicts if conflict_resolutions.get(conflict["id"], conflict_strategy) == "ask"]
    if unresolved_conflicts:
        return {
            "imported_count": 0,
            "skipped_count": 0,
            "conflicts": unresolved_conflicts,
            "needs_resolution": True
        }

    imported_count = 0
    created_count = 0
    overwritten_count = 0
    skipped_count = 0

    for entry in incoming.entries:
        existing = existing_by_id.get(entry.id)
        if existing:
            entry_strategy = conflict_resolutions.get(entry.id, conflict_strategy)
            if entry_strategy == "overwrite":
                index = vault.entries.index(existing)
                vault.entries[index] = entry
                existing_by_id[entry.id] = entry
                imported_count += 1
                overwritten_count += 1
            else:
                skipped_count += 1
        else:
            vault.entries.append(entry)
            existing_by_id[entry.id] = entry
            imported_count += 1
            created_count += 1

    save_vault_data(vault)
    logger.info(f"导入明文 vault 成功: imported={imported_count}, skipped={skipped_count}")
    return {
        "imported_count": imported_count,
        "created_count": created_count,
        "overwritten_count": overwritten_count,
        "skipped_count": skipped_count,
        "conflicts": conflicts,
        "needs_resolution": False
    }


def _create_backup_unlocked(strict: bool = False):
    """创建自动备份"""
    try:
        if not is_initialized():
            raise ValueError("数据文件不存在")
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = os.path.join(BACKUP_DIR, f"secretbase.enc.{timestamp}.bak")
        shutil.copy2(VAULT_PATH, backup_path)
        _cleanup_backups()
        logger.info(f"创建备份: {backup_path}")
        return Path(backup_path)
    except Exception as e:
        logger.error(f"创建备份失败: {e}")
        if strict:
            raise
        return None


def create_backup() -> Path:
    """手动创建当前 vault 的加密备份。"""
    with VaultFileLock(VAULT_PATH):
        _ensure_current_vault_unchanged()
        return _create_backup_unlocked(strict=True)


def _cleanup_backups():
    """清理旧备份"""
    try:
        backups = sorted(Path(BACKUP_DIR).glob("secretbase.enc.*.bak"))
        while len(backups) > MAX_BACKUPS:
            oldest = backups.pop(0)
            oldest.unlink()
            logger.info(f"删除旧备份: {oldest}")
    except Exception as e:
        logger.error(f"清理备份失败: {e}")


def unlock_vault(password: str) -> bool:
    """解锁 vault，缓存派生密钥和数据。"""
    global _vault_key, _vault_data
    
    content = get_vault_content()
    if content is None:
        return False
    
    try:
        header = parse_vault_header(content)
        key = derive_key(password, header["salt"])
        plaintext = decrypt_vault_with_key(key, content)
        data = json.loads(plaintext.decode('utf-8'))
        _vault_data = VaultData(**data)
        if _vault_key is not None:
            _vault_key.lock()
        _vault_key = SecureKey(key, header["salt"])
        _set_vault_fingerprint_from_content(content)
        touch_activity()
        logger.info("Vault 解锁成功")
        return True
    except Exception as e:
        logger.error(f"解锁失败: {e}")
        return False


def lock_vault():
    """锁定 vault，清除缓存"""
    global _vault_key, _vault_data, _last_activity_at, _session_token, _vault_fingerprint
    if _vault_key is not None:
        _vault_key.lock()
    _vault_key = None
    _vault_data = None
    _last_activity_at = None
    _session_token = None
    _vault_fingerprint = None
    logger.info("Vault 已锁定")


def is_unlocked() -> bool:
    """检查 vault 是否已解锁"""
    return _vault_key is not None


def get_vault_data() -> VaultData:
    """获取 vault 数据（必须已解锁）"""
    if not is_unlocked():
        raise ValueError("Vault 未解锁")
    return _vault_data


def save_vault_data(vault: VaultData):
    """保存 vault 数据（必须已解锁）"""
    global _vault_data
    
    if not is_unlocked():
        raise ValueError("Vault 未解锁")
    
    try:
        plaintext = vault.model_dump_json().encode('utf-8')
        encrypted = _encrypt_with_current_key(plaintext)
        save_vault(encrypted)
        _vault_data = vault
        logger.info("Vault 数据已保存")
    except Exception as e:
        logger.error(f"保存 vault 失败: {e}")
        raise


def init_vault(password: str) -> bool:
    """初始化新的 vault"""
    global _vault_key, _vault_data
    
    if is_initialized():
        return False
    
    try:
        vault = VaultData()
        plaintext = vault.model_dump_json().encode('utf-8')
        salt = generate_salt()
        key = derive_key(password, salt)
        encrypted = encrypt_vault_with_key(key, salt, plaintext)
        save_vault(encrypted)

        if _vault_key is not None:
            _vault_key.lock()
        _vault_key = SecureKey(key, salt)
        _vault_data = vault
        touch_activity()
        logger.info("Vault 初始化成功")
        return True
    except Exception as e:
        logger.error(f"初始化 vault 失败: {e}")
        return False


def change_vault_password(old_password: str, new_password: str) -> bool:
    """修改 vault 密码"""
    global _vault_key
    
    if not is_unlocked():
        return False
    
    content = get_vault_content()
    if content is None:
        return False
    
    try:
        from crypto import verify_password
        if not verify_password(old_password, content):
            return False
        
        plaintext = decrypt_vault(old_password, content)
        new_salt = generate_salt()
        new_key = derive_key(new_password, new_salt)
        encrypted = encrypt_vault_with_key(new_key, new_salt, plaintext)
        save_vault(encrypted)

        if _vault_key is not None:
            _vault_key.lock()
        _vault_key = SecureKey(new_key, new_salt)
        logger.info("密码修改成功")
        return True
    except Exception as e:
        logger.error(f"修改密码失败: {e}")
        return False


def get_entry(entry_id: str) -> Optional[Entry]:
    """获取单个条目"""
    vault = get_vault_data()
    for entry in vault.entries:
        if entry.id == entry_id and not entry.deleted:
            return entry
    return None


def add_entry(entry_data: EntryCreate) -> Entry:
    """添加条目"""
    vault = get_vault_data()
    
    entry = Entry(
        title=entry_data.title,
        url=entry_data.url or "",
        starred=entry_data.starred,
        tags=entry_data.tags,
        fields=entry_data.fields,
        remarks=entry_data.remarks or ""
    )
    
    vault.entries.append(entry)
    save_vault_data(vault)
    
    return entry


def update_entry(entry_id: str, entry_data: EntryUpdate) -> Optional[Entry]:
    """更新条目"""
    vault = get_vault_data()
    
    for entry in vault.entries:
        if entry.id == entry_id and not entry.deleted:
            if entry_data.title is not None:
                entry.title = entry_data.title
            if entry_data.url is not None:
                entry.url = entry_data.url
            if entry_data.starred is not None:
                entry.starred = entry_data.starred
            if entry_data.tags is not None:
                entry.tags = entry_data.tags
            if entry_data.fields is not None:
                entry.fields = entry_data.fields
            if entry_data.remarks is not None:
                entry.remarks = entry_data.remarks
            
            entry.updated_at = datetime.now().isoformat()
            save_vault_data(vault)
            return entry
    
    return None


def delete_entry(entry_id: str) -> bool:
    """删除条目（移到回收站）"""
    vault = get_vault_data()
    
    for entry in vault.entries:
        if entry.id == entry_id and not entry.deleted:
            entry.deleted = True
            entry.deleted_at = datetime.now().isoformat()
            vault.entries.remove(entry)
            vault.deleted_entries.append(entry)
            save_vault_data(vault)
            return True
    
    return False
