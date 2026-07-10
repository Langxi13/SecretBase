"""AI 标签系统治理路由。"""

import json
import logging

from fastapi import APIRouter, HTTPException

from ai_services import client as ai_client
from ai_services.organize import _filter_entries_for_organize, existing_groups
from ai_services.parsing import _clean_text
from ai_services.prompts import AI_ORGANIZE_MAX_ENTRIES, TAG_GOVERNANCE_SYSTEM_PROMPT
from ai_services.tag_governance import (
    _entry_for_ai_tag_governance,
    _normalize_tag_governance_payload,
    _tag_governance_summary,
    apply_tag_governance,
)
from models import AiTagGovernanceApplyRequest, AiTagGovernancePreviewRequest
from storage import get_vault_data, is_unlocked, save_vault_data
from tag_utils import list_tag_entities


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/tags/preview")
async def ai_tag_governance_preview(request: AiTagGovernancePreviewRequest):
    """AI 生成全局标签系统管理建议，不直接写入。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    vault = get_vault_data()
    entries = _filter_entries_for_organize(vault, request.filters)
    if not entries:
        raise HTTPException(status_code=422, detail="当前密码库没有可分析条目")
    if len(entries) > AI_ORGANIZE_MAX_ENTRIES:
        raise HTTPException(status_code=413, detail=f"AI 标签系统管理最多支持 {AI_ORGANIZE_MAX_ENTRIES} 条，请先缩小范围")
    ai_config = ai_client._load_ai_config()
    if not ai_config:
        raise HTTPException(status_code=502, detail="AI 服务未配置")

    user_payload = {
        "user_prompt": _clean_text(request.user_prompt, 1000),
        "existing_tags": list_tag_entities(vault),
        "existing_groups": existing_groups(vault),
        "entries": [_entry_for_ai_tag_governance(entry) for entry in entries],
        "privacy_note": "字段值不会发送给 AI，只有字段名和条目结构信息。",
    }

    try:
        content = await ai_client._request_chat_completion(
            ai_config["base_url"],
            ai_config["api_key"],
            ai_config["model"],
            [
                {"role": "system", "content": TAG_GOVERNANCE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            4000,
        )
        payload = ai_client._extract_json_content(content)
        suggestions, warnings = _normalize_tag_governance_payload(payload, {entry.id for entry in entries})
    except HTTPException:
        raise
    except json.JSONDecodeError as error:
        logger.error("AI 标签系统管理返回的 JSON 解析失败: %s", error)
        raise HTTPException(status_code=422, detail="AI 返回格式错误")
    except Exception as error:
        logger.error("AI 标签系统管理失败: %s", error)
        raise HTTPException(status_code=502, detail="AI 服务调用失败")

    return {
        "success": True,
        "data": {
            "entry_count": len(entries),
            "suggestions": suggestions,
            "summary": _tag_governance_summary(suggestions),
            "warnings": warnings,
            "privacy_note": "本次标签系统管理不会发送任何字段值。",
        },
    }


@router.post("/tags/apply")
async def ai_tag_governance_apply(request: AiTagGovernanceApplyRequest):
    """应用用户确认后的 AI 标签系统管理建议。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    vault = get_vault_data()
    result = apply_tag_governance(vault, request.suggestions)
    if result["applied_count"] > 0:
        save_vault_data(vault)
    return {
        "success": True,
        "data": result,
        "message": f"已应用 {result['applied_count']} 条标签管理建议",
    }
