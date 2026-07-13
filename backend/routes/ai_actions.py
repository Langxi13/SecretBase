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
from ai_services.pending import discard_pending, get_pending, put_pending
from ai_services.organize import _filter_entries_for_organize, existing_groups
from ai_services.parsing import _clean_text
from ai_services.privacy import detect_sensitive_metadata
from ai_services.prompts import AI_ACTIONS_SYSTEM_PROMPT, AI_ORGANIZE_MAX_ENTRIES
from models import AiActionPlanItem, AiPendingPlanApplyRequest, AiActionPreviewRequest
from storage import create_ai_snapshot, get_vault_data, is_unlocked, save_vault_data, vault_revision


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
    if detect_sensitive_metadata([("操作指令", instruction)]):
        raise HTTPException(
            status_code=422,
            detail="操作指令中检测到疑似密码或 Token；请改用 AI 新建处理需要主动发送的字段值",
        )
    ai_config = ai_client._load_ai_config()
    if not ai_config:
        raise HTTPException(status_code=502, detail="AI 服务未配置")

    vault = get_vault_data()
    source_revision = vault_revision()
    entries = _filter_entries_for_organize(vault, request.filters)
    if not entries:
        raise HTTPException(status_code=422, detail="当前筛选范围没有可供 AI 分析的条目")
    if len(entries) > AI_ORGANIZE_MAX_ENTRIES:
        raise HTTPException(status_code=413, detail=f"AI 交互最多支持 {AI_ORGANIZE_MAX_ENTRIES} 条，请缩小筛选范围")
    entries_by_ref = {f"E{index + 1:03d}": entry for index, entry in enumerate(entries)}

    user_payload = {
        "instruction": instruction,
        "existing_tags": sorted({tag for entry in vault.entries if not entry.deleted for tag in entry.tags}),
        "existing_groups": existing_groups(vault),
        "entries": [_entry_for_ai_actions(entry, ref) for ref, entry in entries_by_ref.items()],
        "allowed_actions": ["create_group", "update_group", "create_entry", "create_entry_from_field", "update_entry"],
        "privacy_note": "仅发送标题、网址 hostname、分类和字段名，不发送字段值、完整网址或备注。",
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
            ai_config.get("structured_output", "prompt_json"),
        )
        payload = ai_client._extract_json_content(content)
        entries_by_id = {entry.id: entry for entry in entries}
        actions, warnings = _normalize_ai_actions_payload(payload, set(entries_by_ref.keys()))
        for action in actions:
            if action.get("entry_id"):
                action["entry_id"] = entries_by_ref[action["entry_id"]].id
            if action.get("source_entry_id"):
                action["source_entry_id"] = entries_by_ref[action["source_entry_id"]].id
        actions = _attach_ai_action_entry_titles(actions, entries_by_id)
        for index, action in enumerate(actions):
            action["id"] = f"action-{index + 1}"
    except HTTPException:
        raise
    except json.JSONDecodeError as error:
        logger.error("AI 操作计划返回的 JSON 解析失败: %s", error)
        raise HTTPException(status_code=422, detail="AI 返回格式错误")
    except Exception as error:
        logger.error("AI 操作计划生成失败: %s", error)
        raise HTTPException(status_code=502, detail="AI 服务调用失败")

    if vault_revision() != source_revision:
        raise HTTPException(status_code=409, detail="密码库已变化，请重新生成 AI 计划")
    plan_token = put_pending("actions", {"actions": actions}, source_revision)
    return {
        "success": True,
        "data": {
            "entry_count": len(entries),
            "actions": actions,
            "plan_token": plan_token,
            "source_revision": source_revision,
            "summary": _ai_actions_summary(actions),
            "warnings": warnings,
            "privacy_note": "本次仅发送标题、网址 hostname、分类和字段名；不发送字段值、完整网址或备注。",
        },
    }


@router.post("/actions/apply")
async def ai_actions_apply(request: AiPendingPlanApplyRequest):
    """应用用户确认后的 AI 操作计划。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    pending = get_pending(request.plan_token, "actions", request.expected_revision)
    selected_ids = set(request.selected_ids)
    selected_actions = [
        AiActionPlanItem(**action)
        for action in pending.payload.get("actions", [])
        if action.get("id") in selected_ids
    ]
    if not selected_actions:
        raise HTTPException(status_code=422, detail="请选择要应用的操作计划")

    snapshot = create_ai_snapshot()
    vault = get_vault_data()
    result = apply_actions(vault, selected_actions)
    if result["applied_count"] > 0:
        save_vault_data(vault)
        result["undo_token"] = put_pending("assistant-undo", {"filename": snapshot.name}, vault_revision())
        result["revision"] = vault_revision()
    discard_pending(request.plan_token)
    return {
        "success": True,
        "data": result,
        "message": f"已应用 {result['applied_count']} 项 AI 操作计划",
    }
