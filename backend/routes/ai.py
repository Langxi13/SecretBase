"""AI 路由聚合入口，保持 ``main.py`` 的注册方式不变。"""

from fastapi import APIRouter

from ai_services import client as ai_client
from ai_services.organize import _organize_summary
from ai_services.prompts import (
    AI_CHAT_TIMEOUT_SECONDS,
    AI_ORGANIZE_MAX_ENTRIES,
    AI_PARSE_COOLDOWN_SECONDS,
    AI_PARSE_MAX_INPUT_CHARS,
)
from routes import ai_actions, ai_organize, ai_parse, ai_settings, ai_tags


router = APIRouter()
router.include_router(ai_settings.router)
router.include_router(ai_organize.router)
router.include_router(ai_actions.router)
router.include_router(ai_tags.router)
router.include_router(ai_parse.router)

# 保留少量内部兼容导出，便于已有运维脚本读取超时与整理摘要。
_extract_json_content = ai_client._extract_json_content
_load_ai_config = ai_client._load_ai_config
_request_chat_completion = ai_client._request_chat_completion
