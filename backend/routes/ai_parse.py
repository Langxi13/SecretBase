"""AI 文本解析路由。"""

import hashlib
import json
import logging
import time

from fastapi import APIRouter, HTTPException

from ai_services import client as ai_client
from ai_services.parsing import _normalize_ai_payload, _quality_warnings
from ai_services.prompts import AI_PARSE_COOLDOWN_SECONDS, AI_PARSE_MAX_INPUT_CHARS, SYSTEM_PROMPT
from models import AiParseRequest
from storage import is_unlocked


logger = logging.getLogger(__name__)
router = APIRouter()
_last_parse_at = 0.0
_last_parse_text_hash = ""


@router.post("/parse")
async def ai_parse(request: AiParseRequest):
    """AI 解析文本为一个或多个待确认条目。"""
    global _last_parse_at, _last_parse_text_hash

    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")
    ai_config = ai_client._load_ai_config()
    if not ai_config:
        raise HTTPException(status_code=502, detail="AI 服务未配置")

    text = request.text.strip()
    if len(text) > AI_PARSE_MAX_INPUT_CHARS:
        raise HTTPException(status_code=413, detail=f"AI 输入过长，请分批解析，单次最多 {AI_PARSE_MAX_INPUT_CHARS} 字符")

    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    now = time.time()
    if text_hash == _last_parse_text_hash:
        raise HTTPException(status_code=429, detail="内容未变化，请修改后再解析")
    remaining = AI_PARSE_COOLDOWN_SECONDS - (now - _last_parse_at)
    if remaining > 0:
        raise HTTPException(status_code=429, detail=f"AI 解析过于频繁，请等待 {int(remaining) + 1} 秒")

    _last_parse_at = now
    _last_parse_text_hash = text_hash
    try:
        content = await ai_client._request_chat_completion(
            ai_config["base_url"],
            ai_config["api_key"],
            ai_config["model"],
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            3000,
        )
        payload = ai_client._extract_json_content(content)
        parsed_entries = _normalize_ai_payload(payload)
        warnings = _quality_warnings(parsed_entries, text)
    except HTTPException:
        raise
    except json.JSONDecodeError as error:
        logger.error("AI 返回的 JSON 解析失败: %s", error)
        raise HTTPException(status_code=422, detail="AI 返回格式错误")
    except Exception as error:
        logger.error("AI 解析失败: %s", error)
        raise HTTPException(status_code=502, detail="AI 服务调用失败")

    logger.info("AI 解析成功: %s 条", len(parsed_entries))
    return {
        "success": True,
        "data": {
            "parsed": parsed_entries[0],
            "parsed_entries": parsed_entries,
            "entry_count": len(parsed_entries),
            "warnings": warnings,
            "confidence": 0.9,
        },
    }
