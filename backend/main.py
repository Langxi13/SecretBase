import uvicorn
import logging
from logging.handlers import TimedRotatingFileHandler
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
import time
import os
import json
import re

from config import (
    PORT,
    HOST,
    LOG_LEVEL,
    LOG_DIR_PATH,
    SETTINGS_PATH,
    BASE_DIR,
    ensure_runtime_dirs,
    get_cors_origins,
    is_desktop_mode,
)
from models import Settings
from storage import ConflictError, VaultLockTimeoutError, enforce_auto_lock, is_unlocked, touch_activity, validate_session_token
from routes import auth, entries, trash, tags, ai, settings, health, transfer, tools


SENSITIVE_KEYS = {"password", "token", "key", "secret", "api_key", "authorization"}
SENSITIVE_LOG_PATTERN = re.compile(r"(?i)(password|token|api[_-]?key|secret|authorization)=([^\s,]+)")


def is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    if normalized in {"password", "old_password", "new_password", "master_password", "token", "api_key", "authorization"}:
        return True
    if "secret" in normalized or "api_key" in normalized or normalized.endswith("_token"):
        return True
    return False


def redact_sensitive(value):
    """递归脱敏错误响应中的敏感字段。"""
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if is_sensitive_key(str(key)):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        return SENSITIVE_LOG_PATTERN.sub(r"\1=***REDACTED***", super().format(record))

# 配置日志
def setup_logging():
    """配置日志系统"""
    root_logger = logging.getLogger()
    if getattr(root_logger, "_secretbase_logging_configured", False):
        return

    os.makedirs(LOG_DIR_PATH, exist_ok=True)
    
    log_file = os.path.join(LOG_DIR_PATH, 'secretbase.log')
    
    handler = TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    
    formatter = RedactingFormatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    root_logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    root_logger.addHandler(handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    root_logger._secretbase_logging_configured = True

ensure_runtime_dirs()
setup_logging()
logger = logging.getLogger(__name__)

NORMAL_BODY_LIMIT_BYTES = 1 * 1024 * 1024
IMPORT_BODY_LIMIT_BYTES = 10 * 1024 * 1024
PUBLIC_PATHS = {
    "/health",
    "/api/health",
    "/auth/status",
    "/api/auth/status",
    "/auth/init",
    "/api/auth/init",
    "/auth/unlock",
    "/api/auth/unlock",
    "/secretbase-runtime-config.js",
}
API_PREFIXES = (
    "/api",
    "/auth",
    "/entries",
    "/trash",
    "/tags",
    "/ai",
    "/settings",
    "/tools",
    "/export",
    "/import",
    "/backups",
)


def session_token(request: Request) -> str | None:
    header_token = request.headers.get("x-secretbase-token", "").strip()
    if header_token:
        return header_token

    auth_header = request.headers.get("authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def is_public_request(request: Request) -> bool:
    path = request.url.path
    if path in PUBLIC_PATHS:
        return True
    if is_desktop_mode() and request.method == "GET":
        return not path.startswith(API_PREFIXES)
    return False


def get_auto_lock_minutes() -> int:
    try:
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            return Settings(**json.load(f)).auto_lock_minutes
    except Exception:
        return Settings().auto_lock_minutes


# 生命周期事件
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info("SecretBase 服务启动")
    logger.info(f"监听地址: {HOST}:{PORT}")
    yield
    logger.info("SecretBase 服务关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="SecretBase",
    description="密码/密钥/重要信息管理工具",
    version="1.0.0",
    lifespan=lifespan
)

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录 API 请求"""
    start_time = time.time()

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit():
        limit = IMPORT_BODY_LIMIT_BYTES if request.url.path.startswith("/import/") else NORMAL_BODY_LIMIT_BYTES
        if int(content_length) > limit:
            return JSONResponse(
                status_code=413,
                content={
                    "success": False,
                    "error": "REQUEST_TOO_LARGE",
                    "message": "请求体过大"
                }
            )

    if request.method != "OPTIONS" and not is_public_request(request):
        if is_unlocked() and enforce_auto_lock(get_auto_lock_minutes()):
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "error": "UNAUTHORIZED",
                    "message": "已自动锁定，请重新解锁"
                }
            )

        if not is_unlocked() or not validate_session_token(session_token(request)):
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "error": "UNAUTHORIZED",
                    "message": "请先解锁"
                }
            )
    
    response = await call_next(request)

    if request.url.path not in PUBLIC_PATHS and response.status_code < 400:
        touch_activity()
    
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} "
        f"status={response.status_code} "
        f"duration={process_time:.3f}s"
    )
    
    return response


# 配置 CORS。保持在自定义中间件之后注册，确保提前返回的 401/413 也带 CORS 响应头。
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/secretbase-runtime-config.js", include_in_schema=False)
async def runtime_config_js():
    api_base_url = "" if is_desktop_mode() else None
    config = {
        "mode": "desktop" if is_desktop_mode() else "server",
        "apiBaseUrl": api_base_url,
    }
    script = (
        f"window.SECRETBASE_RUNTIME_CONFIG = {json.dumps(config, ensure_ascii=False)};\n"
        "if (window.SECRETBASE_RUNTIME_CONFIG.apiBaseUrl !== null) {\n"
        "  window.SECRETBASE_API_BASE_URL = window.SECRETBASE_RUNTIME_CONFIG.apiBaseUrl;\n"
        "}\n"
    )
    return Response(content=script, media_type="application/javascript")


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "INTERNAL_ERROR",
            "message": "服务器内部错误"
        }
    )


@app.exception_handler(ConflictError)
async def conflict_exception_handler(request: Request, exc: ConflictError):
    """Vault 乐观锁冲突。"""
    logger.warning(f"Vault 写入冲突: {exc}")
    return JSONResponse(
        status_code=409,
        content={
            "success": False,
            "error": "CONFLICT",
            "message": "数据文件已被其他进程修改，请重新解锁后再操作"
        }
    )


@app.exception_handler(VaultLockTimeoutError)
async def vault_lock_timeout_handler(request: Request, exc: VaultLockTimeoutError):
    """Vault 文件锁超时。"""
    logger.warning(f"Vault 文件锁超时: {exc}")
    return JSONResponse(
        status_code=423,
        content={
            "success": False,
            "error": "VAULT_LOCKED",
            "message": "数据文件正在被其他进程使用。请确认没有旧的 SecretBase 进程仍在运行后重试。"
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 异常处理"""
    error_by_status = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "REQUEST_TOO_LARGE",
        423: "VAULT_LOCKED",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        502: "AI_ERROR",
    }

    if isinstance(exc.detail, dict):
        error = exc.detail.get("error", error_by_status.get(exc.status_code, "HTTP_ERROR"))
        message = exc.detail.get("message", "请求失败")
        details = exc.detail.get("details")
        data = exc.detail.get("data")
    else:
        error = error_by_status.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail
        details = None
        data = None

    content = {
        "success": False,
        "error": error,
        "message": message
    }
    if data is not None:
        content["data"] = redact_sensitive(data)
    if details is not None:
        content["details"] = redact_sensitive(details)

    return JSONResponse(
        status_code=exc.status_code,
        content=content
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理"""
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": "请求参数无效",
            "details": redact_sensitive(jsonable_encoder(exc.errors()))
        }
    )


# 注册路由
app.include_router(health.router, tags=["健康检查"])
app.include_router(auth.router, prefix="/auth", tags=["认证"])
app.include_router(entries.router, prefix="/entries", tags=["条目管理"])
app.include_router(trash.router, prefix="/trash", tags=["回收站"])
app.include_router(tags.router, prefix="/tags", tags=["标签管理"])
app.include_router(ai.router, prefix="/ai", tags=["AI 智能录入"])
app.include_router(settings.router, prefix="/settings", tags=["设置"])
app.include_router(transfer.router, tags=["导入导出"])
app.include_router(tools.router, prefix="/tools", tags=["管理工具"])

# 兼容前端以 /api 作为 API Base URL 的部署形态。生产 nginx 可继续 rewrite
# /api/* 到顶层路径；后端别名让未 rewrite 的请求也不会落到 404。
app.include_router(health.router, prefix="/api", tags=["健康检查"])
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(entries.router, prefix="/api/entries", tags=["条目管理"])
app.include_router(trash.router, prefix="/api/trash", tags=["回收站"])
app.include_router(tags.router, prefix="/api/tags", tags=["标签管理"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI 智能录入"])
app.include_router(settings.router, prefix="/api/settings", tags=["设置"])
app.include_router(transfer.router, prefix="/api", tags=["导入导出"])
app.include_router(tools.router, prefix="/api/tools", tags=["管理工具"])

if is_desktop_mode():
    frontend_dir = BASE_DIR.parent / "frontend"
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="desktop_frontend")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="warning"
    )
