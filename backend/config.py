from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# 基础配置
BASE_DIR = Path(__file__).resolve().parent
APP_MODE = os.getenv("SECRETBASE_MODE", "server").strip().lower() or "server"

# 服务器模式加载固定位置的 .env 文件，避免启动目录不同导致配置不一致。
# 桌面模式由启动器显式设置关键路径和端口，不读取仓库内 .env。
if APP_MODE != "desktop":
    load_dotenv(BASE_DIR / ".env", override=False)


def resolve_backend_path(value: str | os.PathLike) -> Path:
    """Resolve relative paths from backend/ for Windows dev and Ubuntu service."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


@dataclass(frozen=True)
class RuntimeConfig:
    mode: str
    base_dir: Path
    data_dir: Path
    backup_dir: Path
    log_dir: Path
    host: str
    port: int
    vault_path: Path
    settings_path: Path
    ai_model: str
    ai_api_key: str
    ai_api_url: str
    cors_origins: str
    log_level: str


def is_desktop_mode() -> bool:
    return APP_MODE == "desktop"


def load_runtime_config() -> RuntimeConfig:
    data_dir = resolve_backend_path(os.getenv("DATA_DIR", "data"))
    backup_dir = resolve_backend_path(os.getenv("BACKUP_DIR", data_dir / "backups"))
    log_dir = resolve_backend_path(os.getenv("LOG_DIR", "logs"))
    vault_path = resolve_backend_path(os.getenv("VAULT_PATH", data_dir / "secretbase.enc"))
    settings_path = resolve_backend_path(os.getenv("SETTINGS_PATH", "settings.json"))

    return RuntimeConfig(
        mode=APP_MODE,
        base_dir=BASE_DIR,
        data_dir=data_dir,
        backup_dir=backup_dir,
        log_dir=log_dir,
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", 10004)),
        vault_path=vault_path,
        settings_path=settings_path,
        ai_model=os.getenv("AI_MODEL", "deepseek-v4-flash"),
        ai_api_key=os.getenv("DEEPSEEK_API_KEY") or os.getenv("AI_API_KEY", ""),
        ai_api_url=os.getenv("AI_API_URL", "https://api.deepseek.com/chat/completions"),
        cors_origins=os.getenv("CORS_ORIGINS", "*"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


RUNTIME_CONFIG = load_runtime_config()

DATA_DIR = RUNTIME_CONFIG.data_dir
BACKUP_DIR = RUNTIME_CONFIG.backup_dir
LOG_DIR = RUNTIME_CONFIG.log_dir

# 服务配置
PORT = RUNTIME_CONFIG.port
HOST = RUNTIME_CONFIG.host

# 数据文件路径
VAULT_PATH = str(RUNTIME_CONFIG.vault_path)
SETTINGS_PATH = str(RUNTIME_CONFIG.settings_path)

# AI 配置
AI_MODEL = RUNTIME_CONFIG.ai_model
AI_API_KEY = RUNTIME_CONFIG.ai_api_key
AI_API_URL = RUNTIME_CONFIG.ai_api_url

# CORS 配置
CORS_ORIGINS = RUNTIME_CONFIG.cors_origins

# 日志配置
LOG_LEVEL = RUNTIME_CONFIG.log_level
LOG_DIR_PATH = str(LOG_DIR)

# 安全配置
PBKDF2_ITERATIONS = 600000
SALT_LENGTH = 32
NONCE_LENGTH = 12
AUTH_TAG_LENGTH = 16

# 自动备份配置
MAX_BACKUPS = 30

# 速率限制配置
MAX_UNLOCK_ATTEMPTS = 5
UNLOCK_WINDOW_SECONDS = 300


def ensure_runtime_dirs() -> None:
    """Create runtime directories explicitly during application startup."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    Path(VAULT_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(SETTINGS_PATH).parent.mkdir(parents=True, exist_ok=True)


def get_cors_origins() -> list:
    """获取 CORS 允许的来源列表"""
    if CORS_ORIGINS == "*":
        return ["*"]
    return [origin.strip() for origin in CORS_ORIGINS.split(",")]
