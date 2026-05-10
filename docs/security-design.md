# SecretBase 安全设计文档

## 0. 文档状态与安全阶段

本文档定义 SecretBase 的安全目标。安全能力分为两个阶段：

| 阶段 | 安全目标 | 必须满足 |
|------|----------|----------|
| V1 安全基线 | 单用户可安全使用 | PBKDF2-HMAC-SHA256、AES-256-GCM、随机盐和 nonce、加密文件存储、内存锁定、解锁限速、日志不记录明文密码 |
| V2 安全加固 | 降低长期运行和多端并发风险 | 随机 session token、SecureKey 内存清零、文件锁、乐观锁、结构化日志脱敏已落地，安全审计清单自动化后续继续完善 |

V1 阶段不要求实现所有示例类。示例类用于指导 V2 加固实现，不得误解为当前必须全部落地。

## 1. 概述

本文档详细描述 SecretBase 的安全设计，包括加密算法、密钥管理、数据保护等安全机制。

## 2. 加密架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      用户主密码                              │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PBKDF2 密钥派生                           │
│  - 算法: PBKDF2-HMAC-SHA256                                 │
│  - 迭代次数: 600,000 (OWASP 2023 推荐)                      │
│  - 盐值: 随机 32 字节                                        │
│  - 输出: 256 位密钥                                          │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    AES-256-GCM 加密                          │
│  - 密钥: 256 位 (来自 PBKDF2)                                │
│  - IV/Nonce: 随机 12 字节 (每次加密唯一)                      │
│  - 认证标签: 128 位                                          │
│  - AAD: V1 不使用；V2 如启用必须把 AAD 元数据写入文件头       │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    加密数据文件                               │
│  secretbase.enc                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 文件格式

加密文件采用自定义二进制格式：

```
┌─────────────────────────────────────────────────────────────┐
│  Magic Bytes (4 bytes)      "SB01"                          │
├─────────────────────────────────────────────────────────────┤
│  Version (1 byte)           0x01                            │
├─────────────────────────────────────────────────────────────┤
│  Salt (32 bytes)            PBKDF2 盐值                      │
├─────────────────────────────────────────────────────────────┤
│  Nonce (12 bytes)           AES-GCM nonce                   │
├─────────────────────────────────────────────────────────────┤
│  Auth Tag (16 bytes)        AES-GCM 认证标签                 │
├─────────────────────────────────────────────────────────────┤
│  Encrypted Data (variable)  加密后的 JSON 数据                │
└─────────────────────────────────────────────────────────────┘
```

**文件头结构：**

| 偏移 | 长度 | 说明 |
|------|------|------|
| 0 | 4 | Magic bytes: "SB01" |
| 4 | 1 | 版本号: 0x01 |
| 5 | 32 | PBKDF2 盐值 |
| 37 | 12 | AES-GCM nonce |
| 49 | 16 | AES-GCM 认证标签 |
| 65 | ... | 加密数据 |

## 3. 密钥派生

### 3.1 PBKDF2 参数

```python
import hashlib
import os

def derive_key(password: str, salt: bytes) -> bytes:
    """
    从主密码派生加密密钥
    
    Args:
        password: 用户主密码
        salt: 32 字节随机盐值
    
    Returns:
        32 字节 AES-256 密钥
    """
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        iterations=600000,  # OWASP 2023 推荐值
        dklen=32
    )
```

### 3.2 安全考虑

| 参数 | 值 | 说明 |
|------|-----|------|
| 算法 | PBKDF2-HMAC-SHA256 | 广泛支持，安全可靠 |
| 迭代次数 | 600,000 | OWASP 2023 推荐，平衡安全和性能 |
| 盐值长度 | 32 字节 | 防止彩虹表攻击 |
| 输出长度 | 32 字节 | AES-256 密钥 |

### 3.3 盐值生成

```python
def generate_salt() -> bytes:
    """生成密码学安全的随机盐值"""
    return os.urandom(32)
```

## 4. 数据加密

### 4.1 AES-256-GCM 加密

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

def encrypt_data(key: bytes, plaintext: bytes, aad: bytes | None = None) -> tuple[bytes, bytes, bytes]:
    """
    使用 AES-256-GCM 加密数据
    
    Args:
        key: 32 字节密钥
        plaintext: 明文数据
        aad: 附加认证数据。V1 传 None；V2 可传文件头元数据
    
    Returns:
        (nonce, ciphertext, auth_tag)
    """
    nonce = os.urandom(12)  # 96 位 nonce
    aesgcm = AESGCM(key)
    
    # AESGCM.encrypt 返回 ciphertext + auth_tag
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, aad)
    
    # 分离 ciphertext 和 auth_tag
    ciphertext = ciphertext_with_tag[:-16]
    auth_tag = ciphertext_with_tag[-16:]
    
    return nonce, ciphertext, auth_tag
```

### 4.2 AES-256-GCM 解密

```python
def decrypt_data(key: bytes, nonce: bytes, ciphertext: bytes, 
                 auth_tag: bytes, aad: bytes | None = None) -> bytes:
    """
    使用 AES-256-GCM 解密数据
    
    Args:
        key: 32 字节密钥
        nonce: 12 字节 nonce
        ciphertext: 密文
        auth_tag: 16 字节认证标签
        aad: 附加认证数据。V1 传 None；V2 可传文件头元数据
    
    Returns:
        解密后的明文
    
    Raises:
        InvalidTag: 认证失败（数据被篡改）
    """
    aesgcm = AESGCM(key)
    
    # 组合 ciphertext 和 auth_tag
    ciphertext_with_tag = ciphertext + auth_tag
    
    return aesgcm.decrypt(nonce, ciphertext_with_tag, aad)
```

### 4.3 AAD (附加认证数据)

AAD 属于 V2 可选增强，不是 V1 文件格式要求。V1 的 AES-GCM 认证范围是 nonce、密文和认证标签，不传入 AAD。

若 V2 启用 AAD，必须满足：

- AAD 构造所需的所有字段必须存储在加密文件头中。
- 加密和解密必须使用完全相同的 AAD 字节序列。
- 文件格式版本必须升级，避免旧文件无法区分。

以下是 V2 目标示例，不适用于 V1 当前格式：

AAD 用于绑定元数据，防止数据被篡改或替换：

```python
def build_aad(version: int, timestamp: int) -> bytes:
    """
    构建 AAD
    
    Args:
        version: 文件格式版本
        timestamp: 创建时间戳
    
    Returns:
        AAD 字节序列
    """
    return f"SecretBase:{version}:{timestamp}".encode('utf-8')
```

## 5. 密钥管理

V1 当前模型：解锁后后端进程在内存中保存主密码和解密后的 vault 数据；手动锁定、前端自动锁定、后端空闲超时自动锁定或服务重启时清除缓存。该模型简单可用，但不能保证 Python 不可变字符串立即物理清零。

后端会在敏感 API 请求前检查 `auto_lock_minutes`，若距离上次成功敏感操作的空闲时间超限，则立即锁定并返回 `401`。前端计时器只作为用户体验提醒，不能作为唯一安全边界。

V2.0 当前模型：使用可清零的 `bytearray`/专用对象保存派生密钥，避免长期保存主密码字符串，并在锁定、自动锁定和密钥替换时清零派生密钥容器。

### 5.1 内存中的密钥

以下 `SecureKey` 是 V2 加固目标示例：

```python
import ctypes

class SecureKey:
    """安全的密钥存储"""
    
    def __init__(self, key: bytes):
        self._key = bytearray(key)
        self._locked = False
    
    def get(self) -> bytes:
        """获取密钥（仅在解锁状态）"""
        if self._locked:
            raise SecurityError("密钥已锁定")
        return bytes(self._key)
    
    def lock(self):
        """锁定并清零密钥"""
        if not self._locked:
            # 清零内存
            for i in range(len(self._key)):
                self._key[i] = 0
            self._locked = True
    
    def __del__(self):
        """析构时清零"""
        self.lock()
```

### 5.2 密钥生命周期

```
用户输入密码
    │
    ▼
派生密钥 (PBKDF2)
    │
    ▼
存储在内存 (SecureKey)
    │
    ├── 使用中: 解密/加密操作
    │
    ├── 自动锁定: 超时后清零
    │
    ├── 手动锁定: 用户主动锁定
    │
    └── 服务停止: 清零并销毁
```

### 5.3 密钥派生缓存

该缓存设计属于 V2 加固目标。V1 可以缓存已解锁 vault 数据以简化操作；V2 应避免以明文主密码作为长期缓存状态。

为避免重复派生，派生的密钥会缓存在内存中：

```python
class KeyCache:
    """密钥缓存（内存中）"""
    
    def __init__(self):
        self._cache = {}
    
    def get_or_derive(self, password_hash: str, salt: bytes) -> SecureKey:
        """
        获取缓存的密钥或派生新密钥
        
        Args:
            password_hash: 密码的哈希（用于缓存键）
            salt: 盐值
        """
        if password_hash not in self._cache:
            key = derive_key(password_hash, salt)
            self._cache[password_hash] = SecureKey(key)
        return self._cache[password_hash]
    
    def clear(self):
        """清空缓存"""
        for key in self._cache.values():
            key.lock()
        self._cache.clear()
```

## 6. 密码安全

### 6.1 主密码要求

| 要求 | 说明 |
|------|------|
| 最小长度 | 8 字符 |
| 最大长度 | 128 字符 |
| 复杂度 | 无强制要求（用户自主选择） |
| 存储 | 仅存储派生后的密钥，不存储密码本身 |

### 6.2 密码验证

不存储密码明文或哈希，验证方式：

```python
def verify_password(password: str, salt: bytes, expected_key: bytes) -> bool:
    """
    验证密码是否正确
    
    通过尝试解密文件头来验证
    """
    try:
        derived_key = derive_key(password, salt)
        # 尝试解密文件头
        decrypt_header(derived_key)
        return True
    except InvalidTag:
        return False
```

### 6.3 暴力破解防护

```python
class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_attempts: int = 5, window: int = 300):
        self.max_attempts = max_attempts
        self.window = window  # 秒
        self.attempts = []
    
    def check(self) -> bool:
        """检查是否允许尝试"""
        now = time.time()
        # 清除过期记录
        self.attempts = [t for t in self.attempts if now - t < self.window]
        
        if len(self.attempts) >= self.max_attempts:
            return False
        
        self.attempts.append(now)
        return True
    
    def remaining(self) -> int:
        """剩余尝试次数"""
        now = time.time()
        self.attempts = [t for t in self.attempts if now - t < self.window]
        return max(0, self.max_attempts - len(self.attempts))
```

## 7. 数据保护

### 7.1 内存保护

```python
import gc

class SecureMemory:
    """安全内存管理"""
    
    @staticmethod
    def clear_sensitive_data(data):
        """清零敏感数据"""
        if isinstance(data, bytearray):
            for i in range(len(data)):
                data[i] = 0
        elif isinstance(data, str):
            # Python 字符串不可变，只能等待 GC
            del data
            gc.collect()
    
    @staticmethod
    def secure_copy(data: bytes) -> bytearray:
        """安全复制（可清零）"""
        return bytearray(data)
```

### 7.2 敏感数据处理

| 数据类型 | 存储位置 | 生命周期 |
|----------|----------|----------|
| 主密码 | 不存储 | 用户输入后立即派生密钥 |
| 派生密钥 | 内存 | 锁定时清零 |
| 明文数据 | 内存 | 操作完成后立即清零 |
| 加密数据 | 磁盘 | 永久存储 |

### 7.3 日志安全

```python
class SecureLogger:
    """安全日志记录器"""
    
    # 敏感字段列表
    SENSITIVE_FIELDS = ['password', 'token', 'key', 'secret']
    
    @classmethod
    def sanitize(cls, data: dict) -> dict:
        """清理敏感数据"""
        sanitized = data.copy()
        for key in sanitized:
            if any(s in key.lower() for s in cls.SENSITIVE_FIELDS):
                sanitized[key] = '***REDACTED***'
        return sanitized
    
    @classmethod
    def log_request(cls, method: str, path: str, data: dict = None):
        """记录 API 请求（清理敏感数据）"""
        sanitized_data = cls.sanitize(data) if data else None
        logger.info(f"{method} {path}", extra={'data': sanitized_data})
```

## 8. 并发控制

并发控制属于 V2 工程增强目标。V2.1 已加入跨平台独占锁和乐观锁；生产环境仍建议使用单进程、单 worker 运行，文件锁用于降低误覆盖风险，不等同于完整多进程协同模型。

### 8.1 文件锁实现

以下 `FileLock` 是 V2 目标实现示例：

```python
import fcntl
import os

class FileLock:
    """文件级锁"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.lockpath = filepath + '.lock'
        self.fd = None
    
    def acquire(self, timeout: int = 10):
        """获取锁"""
        start = time.time()
        while True:
            try:
                self.fd = open(self.lockpath, 'w')
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except IOError:
                if time.time() - start > timeout:
                    raise TimeoutError("获取锁超时")
                time.sleep(0.1)
    
    def release(self):
        """释放锁"""
        if self.fd:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            self.fd.close()
            self.fd = None
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, *args):
        self.release()
```

### 8.2 乐观并发控制

以下 `OptimisticLock` 是 V2 目标实现示例：

```python
class OptimisticLock:
    """乐观锁"""
    
    def __init__(self, vault_path: str):
        self.vault_path = vault_path
        self.read_timestamp = None
        self.read_hash = None
    
    def load(self) -> dict:
        """加载数据并记录状态"""
        stat = os.stat(self.vault_path)
        self.read_timestamp = stat.st_mtime
        
        with open(self.vault_path, 'rb') as f:
            self.read_hash = hashlib.sha256(f.read()).hexdigest()
        
        return decrypt_file(self.vault_path)
    
    def save(self, data: dict):
        """保存数据，检查冲突"""
        current_stat = os.stat(self.vault_path)
        
        if current_stat.st_mtime != self.read_timestamp:
            raise ConflictError("数据已被修改")
        
        with open(self.vault_path, 'rb') as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()
        
        if current_hash != self.read_hash:
            raise ConflictError("数据已被修改")
        
        encrypt_file(self.vault_path, data)
        
        # 更新状态
        self.read_timestamp = os.stat(self.vault_path).st_mtime
        with open(self.vault_path, 'rb') as f:
            self.read_hash = hashlib.sha256(f.read()).hexdigest()
```

## 9. CORS 安全

### 9.1 CORS 配置

```python
from fastapi.middleware.cors import CORSMiddleware

def setup_cors(app, origins: str):
    """
    配置 CORS
    
    Args:
        origins: 允许的来源，逗号分隔或 * 表示所有
    """
    if origins == "*":
        allow_origins = ["*"]
    else:
        allow_origins = [o.strip() for o in origins.split(",")]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

### 9.2 安全建议

| 场景 | 配置 |
|------|------|
| 本地使用 | `CORS_ORIGINS=*` |
| 局域网访问 | `CORS_ORIGINS=http://192.168.1.*` |
| 公网访问 | `CORS_ORIGINS=https://yourdomain.com` |

Windows 本地开发允许 `CORS_ORIGINS=*`，因为前端静态服务会直连 `http://127.0.0.1:10004`。Ubuntu 公网生产环境不得使用 `*`，必须配置实际 HTTPS 域名，并确保后端只监听 `127.0.0.1`，由 nginx 暴露统一入口。

## 10. 输入验证

### 10.1 请求验证

```python
from pydantic import BaseModel, validator, constr

class EntryCreate(BaseModel):
    title: constr(min_length=1, max_length=200)
    url: Optional[str] = None
    starred: bool = False
    tags: List[str] = []
    fields: List[FieldItem] = []
    remarks: Optional[constr(max_length=2000)] = None
    
    @validator('url')
    def validate_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('URL 必须以 http:// 或 https:// 开头')
        return v
    
    @validator('tags')
    def validate_tags(cls, v):
        for tag in v:
            if not tag.strip():
                raise ValueError('标签不能为空')
        return v
    
    @validator('fields')
    def validate_fields(cls, v):
        names = set()
        for field in v:
            if not field.name.strip():
                raise ValueError('字段名不能为空')
            if field.name in names:
                raise ValueError(f'字段名重复: {field.name}')
            names.add(field.name)
        return v
```

### 10.2 SQL 注入防护

由于使用文件存储而非数据库，不存在 SQL 注入风险。但仍需防范：

- 路径遍历攻击
- 文件名注入

```python
def sanitize_path(path: str) -> str:
    """清理路径，防止路径遍历"""
    # 移除路径遍历字符
    cleaned = path.replace('..', '').replace('/', '').replace('\\', '')
    # 只允许字母、数字、下划线、点
    cleaned = re.sub(r'[^a-zA-Z0-9_.]', '', cleaned)
    return cleaned
```

## 11. 安全配置建议

### 11.1 生产环境配置

```env
# 服务配置
HOST=127.0.0.1  # 仅本地访问
PORT=10004

# CORS（严格限制）
CORS_ORIGINS=https://yourdomain.com

# 日志级别（避免记录敏感信息）
LOG_LEVEL=WARNING
```

### 11.2 系统级安全

```bash
# 限制文件权限
chmod 600 backend/.env
chmod 600 backend/data/secretbase.enc
chmod 700 backend/data/backups/

# 使用专用用户运行
useradd -r -s /bin/false vault
chown -R vault:vault /opt/secretbase
```

### 11.3 nginx 安全配置

```nginx
server {
    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # 限制请求大小
    client_max_body_size 10m;
    
    # 代理后端
    location /api/ {
        proxy_pass http://127.0.0.1:10004/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 12. 安全审计清单

### 12.1 部署前检查

- [ ] 主密码强度要求已配置
- [ ] CORS 限制已配置
- [ ] 文件权限已设置
- [ ] 日志不包含敏感信息
- [ ] HTTPS 已启用（生产环境）
- [ ] 防火墙已配置
- [ ] 后端以单 worker 运行（V1）
- [ ] 若使用公网 IP 访问，已评估无 HTTPS 的风险并限制来源

### 12.2 运行时检查

- [ ] 自动锁定功能正常
- [ ] 速率限制生效
- [ ] 备份加密正常
- [ ] 错误信息不泄露敏感信息
- [ ] 锁定后内存缓存被清除

## 13. 已知限制

| 限制 | 说明 | 缓解措施 |
|------|------|----------|
| 单用户设计 | 不支持多用户 | 使用系统用户隔离 |
| 文件存储 | 不适合海量数据 | 限制条目数量 |
| 内存中明文 | 运行时存在内存中 | 及时锁定，限制访问 |
| 无双因素认证 | 仅密码认证 | 可扩展支持 |

## 14. 安全更新策略

- 定期更新依赖库
- 监控 CVE 漏洞
- 及时应用安全补丁
- 定期审查加密参数
