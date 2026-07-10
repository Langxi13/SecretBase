"""AI 自然语言操作计划路由。"""

import json
import logging

from fastapi import APIRouter, HTTPException

from ai_services import client as ai_client
from ai_services.actions import (
    _ai_actions_summary,
    _attach_ai_action_entry_titles,
    _entry_for_ai_actions,
    _normalize_ai_actions_payload,
    apply_actions,
)
from ai_services.organize import _filter_entries_for_organize, existing_groups
from ai_services.parsing import _clean_text
from ai_services.prompts import AI_ACTIONS_SYSTEM_PROMPT, AI_ORGANIZE_MAX_ENTRIES
from models import AiActionApplyRequest, AiActionPreviewRequest
from storage import get_vault_data, is_unlocked, save_vault_data


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/actions/preview")
async def ai_actions_preview(request: AiActionPreviewRequest):
    """AI 生成自然语言操作计划，不直接写入。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    instruction = _clean_text(request.instruction, 2000)
    if not instruction:
        raise HTTPException(status_code=422, detail="请输入 AI 交互指令")
    ai_config = ai_client._load_ai_config()
    if not ai_config:
        raise HTTPException(status_code=502, detail="AI 服务未配置")

    vault = get_vault_data()
    entries = _filter_entries_for_organize(vault, request.filters)
    if not entries:
        raise HTTPException(status_code=422, detail="当前筛选范围没有可供 AI 分析的条目")
    if len(entries) > AI_ORGANIZE_MAX_ENTRIES:
        raise HTTPException(status_code=413, detail=f"AI 交互最多支持 {AI_ORGANIZE_MAX_ENTRIES} 条，请缩小筛选范围")

    user_payload = {
        "instruction": instruction,
        "existing_tags": sorted({tag for entry in vault.entries if not entry.deleted for tag in entry.tags}),
        "existing_groups": existing_groups(vault),
        "entries": [_entry_for_ai_actions(entry) for entry in entries],
        "allowed_actions": ["create_group", "update_group", "create_entry", "create_entry_from_field", "update_entry"],
        "privacy_note": "不发送字段值；AI 只能看到字段名、字段索引、隐藏状态和条目结构。",
    }

    try:
        content = await ai_client._request_chat_completion(
            ai_config["base_url"],
            ai_config["api_key"],
            ai_config["model"],
            [
                {"role": "system", "content": AI_ACTIONS_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            5000,
        )
        payload = ai_client._extract_json_content(content)
        entries_by_id = {entry.id: entry for entry in entries}
        actions, warnings = _normalize_ai_actions_payload(payload, set(entries_by_id.keys()))
        actions = _attach_ai_action_entry_titles(actions, entries_by_id)
    except HTTPException:
        raise
    except json.JSONDecodeError as error:
        logger.error("AI 操作计划返回的 JSON 解析失败: %s", error)
        raise HTTPException(status_code=422, detail="AI 返回格式错误")
    except Exception as error:
        logger.error("AI 操作计划生成失败: %s", error)
        raise HTTPException(status_code=502, detail="AI 服务调用失败")

    return {
        "success": True,
        "data": {
            "entry_count": len(entries),
            "actions": actions,
            "summary": _ai_actions_summary(actions),
            "warnings": warnings,
            "privacy_note": "本次 AI 交互不会发送任何字段值，字段拆分由后端本地复制真实值。",
        },
    }


@router.post("/actions/apply")
async def ai_actions_apply(request: AiActionApplyRequest):
    """应用用户确认后的 AI 操作计划。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    selected_actions = [action for action in request.actions if action.selected]
    if not selected_actions:
        raise HTTPException(status_code=422, detail="请选择要应用的操作计划")

    vault = get_vault_data()
    result = apply_actions(vault, selected_actions)
    if result["applied_count"] > 0:
        save_vault_data(vault)
    return {
        "success": True,
        "data": result,
        "message": f"已应用 {result['applied_count']} 项 AI 操作计划",
    }
