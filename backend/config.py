import os
from pathlib import Path
from dotenv import load_dotenv

# 基础配置
BASE_DIR = Path(__file__).resolve().parent

# 加载固定位置的 .env 文件，避免启动目录不同导致配置不一致。
load_dotenv(BASE_DIR / ".env")


def resolve_backend_path(value: str | os.PathLike) -> Path:
    """Resolve relative paths from backend/ for Windows dev and Ubuntu service."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


DATA_DIR = resolve_backend_path(os.getenv("DATA_DIR", "data"))
BACKUP_DIR = resolve_backend_path(os.getenv("BACKUP_DIR", DATA_DIR / "backups"))
LOG_DIR = resolve_backend_path(os.getenv("LOG_DIR", "logs"))

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 服务配置
PORT = int(os.getenv("PORT", 10004))
HOST = os.getenv("HOST", "127.0.0.1")

# 数据文件路径
VAULT_PATH = str(resolve_backend_path(os.getenv("VAULT_PATH", DATA_DIR / "secretbase.enc")))
SETTINGS_PATH = str(resolve_backend_path(os.getenv("SETTINGS_PATH", "settings.json")))
Path(VAULT_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(SETTINGS_PATH).parent.mkdir(parents=True, exist_ok=True)

# AI 配置
AI_MODEL = os.getenv("AI_MODEL", "deepseek-v4-flash")
AI_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("AI_API_KEY", "")
AI_API_URL = os.getenv("AI_API_URL", "https://api.deepseek.com/chat/completions")

# CORS 配置
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR_PATH = str(LOG_DIR)

# 安全配置
PBKDF2_ITERATIONS = 600000
SALT_LENGTH = 32
NONCE_LENGTH = 12
AUTH_TAG_LENGTH = 16

# 自动备份配置
MAX_BACKUPS = 5

# 速率限制配置
MAX_UNLOCK_ATTEMPTS = 5
UNLOCK_WINDOW_SECONDS = 300


def get_cors_origins() -> list:
    """获取 CORS 允许的来源列表"""
    if CORS_ORIGINS == "*":
        return ["*"]
    return [origin.strip() for origin in CORS_ORIGINS.split(",")]
