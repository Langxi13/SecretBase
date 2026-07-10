"""AI 条目整理路由。"""

import json
import logging

from fastapi import APIRouter, HTTPException

from ai_services import client as ai_client
from ai_services.organize import (
    _append_unique,
    _entry_for_ai_organize,
    _fallback_group_suggestions,
    _filter_entries_for_organize,
    _group_description,
    _infer_organize_groups,
    _normalize_organize_payload,
    _organize_summary,
    apply_organize_suggestions,
    existing_groups,
)
from ai_services.parsing import _clean_text
from ai_services.prompts import AI_ORGANIZE_MAX_ENTRIES, ORGANIZE_SYSTEM_PROMPT
from models import AiOrganizeApplyRequest, AiOrganizePreviewRequest
from storage import get_vault_data, is_unlocked, save_vault_data


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/organize/preview")
async def ai_organize_preview(request: AiOrganizePreviewRequest):
    """AI 生成标签或密码组整理建议，不直接写入。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")
    if not request.organize_tags and not request.organize_groups:
        raise HTTPException(status_code=422, detail="请至少选择整理标签或密码组")
    if request.organize_tags and request.organize_groups:
        raise HTTPException(status_code=422, detail="标签和密码组请分开整理，避免建议冲突")

    ai_config = ai_client._load_ai_config()
    if not ai_config:
        raise HTTPException(status_code=502, detail="AI 服务未配置")

    vault = get_vault_data()
    entries = _filter_entries_for_organize(vault, request.filters)
    if not entries:
        raise HTTPException(status_code=422, detail="当前筛选范围没有可整理条目")
    if len(entries) > AI_ORGANIZE_MAX_ENTRIES:
        raise HTTPException(status_code=413, detail=f"单次 AI 整理最多支持 {AI_ORGANIZE_MAX_ENTRIES} 条，请缩小筛选范围")

    groups = existing_groups(vault)
    user_payload = {
        "organize_tags": request.organize_tags,
        "organize_groups": request.organize_groups,
        "user_prompt": _clean_text(request.user_prompt, 1000),
        "existing_tags": sorted({tag for entry in vault.entries if not entry.deleted for tag in entry.tags}),
        "existing_groups": groups,
        "entries": [_entry_for_ai_organize(entry) for entry in entries],
        "privacy_note": "字段值不会发送给 AI，只有字段名和条目结构信息。",
    }

    try:
        content = await ai_client._request_chat_completion(
            ai_config["base_url"],
            ai_config["api_key"],
            ai_config["model"],
            [
                {"role": "system", "content": ORGANIZE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            4000,
        )
        payload = ai_client._extract_json_content(content)
        suggestions, warnings = _normalize_organize_payload(payload, {entry.id for entry in entries})
        if request.organize_groups and not suggestions:
            suggestions = _fallback_group_suggestions(entries, groups)

        entries_by_id = {entry.id: entry for entry in entries}
        for suggestion in suggestions:
            entry = entries_by_id[suggestion["entry_id"]]
            if request.organize_groups and not suggestion.get("add_groups") and not suggestion.get("remove_groups"):
                for group in _infer_organize_groups(entry, suggestion, groups):
                    if _append_unique(suggestion["add_groups"], group):
                        suggestion["group_descriptions"].setdefault(group, _group_description(group))
                if suggestion["add_groups"] and not suggestion.get("reason"):
                    suggestion["reason"] = "根据标题、字段名、标签和备注推断适合加入这些密码组"
            if not request.organize_tags:
                suggestion["add_tags"] = []
                suggestion["remove_tags"] = []
            if not request.organize_groups:
                suggestion["add_groups"] = []
                suggestion["remove_groups"] = []
                suggestion["group_descriptions"] = {}
            suggestion["entry_title"] = entry.title
            suggestion["current_tags"] = entry.tags
            suggestion["current_groups"] = getattr(entry, "groups", []) or []
    except HTTPException:
        raise
    except json.JSONDecodeError as error:
        logger.error("AI 整理返回的 JSON 解析失败: %s", error)
        raise HTTPException(status_code=422, detail="AI 返回格式错误")
    except Exception as error:
        logger.error("AI 整理失败: %s", error)
        raise HTTPException(status_code=502, detail="AI 服务调用失败")

    return {
        "success": True,
        "data": {
            "entry_count": len(entries),
            "suggestions": suggestions,
            "summary": _organize_summary(suggestions, groups),
            "warnings": warnings,
            "privacy_note": "本次整理未向 AI 发送任何字段值。",
        },
    }


@router.post("/organize/apply")
async def ai_organize_apply(request: AiOrganizeApplyRequest):
    """应用用户确认后的 AI 整理建议。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    vault = get_vault_data()
    result = apply_organize_suggestions(vault, request.suggestions)
    if result["updated_count"] > 0 or result["created_groups"] or result["updated_groups"]:
        save_vault_data(vault)
    return {
        "success": True,
        "data": result,
        "message": f"已整理 {result['updated_count']} 个条目",
    }
