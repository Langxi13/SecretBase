import os
import hashlib
import struct
import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

# 文件格式常量
MAGIC_BYTES = b"SB01"
VERSION = 0x01
HEADER_LENGTH = 65


class EncryptionError(Exception):
    """加密相关错误"""
    pass


class DecryptionError(Exception):
    """解密相关错误"""
    pass


class SecureKey:
    """可清零的派生密钥容器。"""

    def __init__(self, key: bytes, salt: bytes):
        self._key = bytearray(key)
        self._salt = bytes(salt)
        self._locked = False

    @property
    def salt(self) -> bytes:
        return self._salt

    def get(self) -> bytes:
        if self._locked:
            raise EncryptionError("密钥已锁定")
        return bytes(self._key)

    def lock(self):
        if not self._locked:
            for index in range(len(self._key)):
                self._key[index] = 0
            self._locked = True

    def __del__(self):
        self.lock()


def derive_key(password: str, salt: bytes, iterations: int = 600000) -> bytes:
    """
    从主密码派生 AES-256 密钥
    
    Args:
        password: 用户主密码
        salt: 32 字节随机盐值
        iterations: PBKDF2 迭代次数
    
    Returns:
        32 字节 AES-256 密钥
    """
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        iterations=iterations,
        dklen=32
    )


def generate_salt() -> bytes:
    """生成密码学安全的随机盐值"""
    return os.urandom(32)


def parse_vault_header(file_content: bytes) -> dict:
    """解析 vault 文件头。"""
    if len(file_content) < HEADER_LENGTH:
        raise DecryptionError("文件格式无效")

    magic = file_content[:4]
    if magic != MAGIC_BYTES:
        raise DecryptionError("文件格式无效: magic bytes 不匹配")

    version = file_content[4]
    if version != VERSION:
        raise DecryptionError(f"不支持的文件版本: {version}")

    return {
        "version": version,
        "salt": file_content[5:37],
        "nonce": file_content[37:49],
        "auth_tag": file_content[49:65],
        "ciphertext": file_content[65:],
    }


def generate_nonce() -> bytes:
    """生成 AES-GCM nonce"""
    return os.urandom(12)


def build_aad(version: int, timestamp: int) -> bytes:
    """
    构建附加认证数据 (AAD)
    
    Args:
        version: 文件格式版本
        timestamp: 创建时间戳
    
    Returns:
        AAD 字节序列
    """
    return f"SecretBase:{version}:{timestamp}".encode('utf-8')


def encrypt_data(key: bytes, plaintext: bytes) -> tuple[bytes, bytes, bytes]:
    """
    使用 AES-256-GCM 加密数据
    
    Args:
        key: 32 字节密钥
        plaintext: 明文数据
    
    Returns:
        (nonce, ciphertext, auth_tag)
    """
    try:
        nonce = generate_nonce()
        
        aesgcm = AESGCM(key)
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)
        
        ciphertext = ciphertext_with_tag[:-16]
        auth_tag = ciphertext_with_tag[-16:]
        
        return nonce, ciphertext, auth_tag
    except Exception as e:
        raise EncryptionError(f"加密失败: {e}")


def decrypt_data(key: bytes, nonce: bytes, ciphertext: bytes, 
                 auth_tag: bytes) -> bytes:
    """
    使用 AES-256-GCM 解密数据
    
    Args:
        key: 32 字节密钥
        nonce: 12 字节 nonce
        ciphertext: 密文
        auth_tag: 16 字节认证标签
    
    Returns:
        解密后的明文
    """
    try:
        aesgcm = AESGCM(key)
        ciphertext_with_tag = ciphertext + auth_tag
        
        # 使用空的 AAD 进行解密（简化实现）
        return aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    except InvalidTag:
        raise DecryptionError("解密失败: 数据已损坏或密码错误")
    except Exception as e:
        raise DecryptionError(f"解密失败: {e}")


def encrypt_vault(password: str, data: bytes) -> bytes:
    """
    加密整个 vault 文件
    
    Args:
        password: 用户密码
        data: 明文 JSON 数据
    
    Returns:
        完整的加密文件内容
    """
    salt = generate_salt()
    key = derive_key(password, salt)
    nonce, ciphertext, auth_tag = encrypt_data(key, data)
    
    # 构建文件头
    header = bytearray()
    header.extend(MAGIC_BYTES)          # 4 bytes: magic
    header.append(VERSION)               # 1 byte: version
    header.extend(salt)                  # 32 bytes: salt
    header.extend(nonce)                 # 12 bytes: nonce
    header.extend(auth_tag)              # 16 bytes: auth tag
    
    return bytes(header) + ciphertext


def encrypt_vault_with_key(key: bytes, salt: bytes, data: bytes) -> bytes:
    """使用已派生密钥加密 vault，避免保存主密码字符串。"""
    if len(salt) != 32:
        raise EncryptionError("salt 长度无效")
    nonce, ciphertext, auth_tag = encrypt_data(key, data)

    header = bytearray()
    header.extend(MAGIC_BYTES)
    header.append(VERSION)
    header.extend(salt)
    header.extend(nonce)
    header.extend(auth_tag)

    return bytes(header) + ciphertext


def decrypt_vault_with_key(key: bytes, file_content: bytes) -> bytes:
    """使用已派生密钥解密 vault。调用方必须确保 key 与文件 salt 匹配。"""
    header = parse_vault_header(file_content)
    return decrypt_data(key, header["nonce"], header["ciphertext"], header["auth_tag"])


def decrypt_vault(password: str, file_content: bytes) -> bytes:
    """
    解密 vault 文件
    
    Args:
        password: 用户主密码
        file_content: 加密文件内容
    
    Returns:
        解密后的明文 JSON 数据
    """
    header = parse_vault_header(file_content)
    salt = header["salt"]
    
    # 派生密钥
    key = derive_key(password, salt)
    
    # 解密数据
    return decrypt_data(key, header["nonce"], header["ciphertext"], header["auth_tag"])


def verify_password(password: str, file_content: bytes) -> bool:
    """
    验证密码是否正确
    
    Args:
        password: 用户主密码
        file_content: 加密文件内容
    
    Returns:
        密码是否正确
    """
    try:
        decrypt_vault(password, file_content)
        return True
    except (DecryptionError, Exception):
        return False


def change_password(old_password: str, new_password: str, 
                    file_content: bytes) -> bytes:
    """
    修改主密码
    
    Args:
        old_password: 旧密码
        new_password: 新密码
        file_content: 当前加密文件内容
    
    Returns:
        使用新密码加密的文件内容
    """
    # 用旧密码解密
    plaintext = decrypt_vault(old_password, file_content)
    
    # 用新密码加密
    return encrypt_vault(new_password, plaintext)
