"""AI 标签系统治理路由。"""

import json
import logging

from fastapi import APIRouter, HTTPException

from ai_services import client as ai_client
from ai_services.organize import _filter_entries_for_organize, existing_groups
from ai_services.parsing import _clean_text
from ai_services.privacy import detect_sensitive_metadata
from ai_services.pending import discard_pending, get_pending, put_pending
from ai_services.prompts import AI_ORGANIZE_MAX_ENTRIES, TAG_GOVERNANCE_SYSTEM_PROMPT
from ai_services.tag_governance import (
    _entry_for_ai_tag_governance,
    _normalize_tag_governance_payload,
    _tag_governance_summary,
    apply_tag_governance,
)
from models import AiPendingPlanApplyRequest, AiTagGovernanceSuggestion, AiTagGovernancePreviewRequest
from storage import create_ai_snapshot, get_vault_data, is_unlocked, save_vault_data, vault_revision
from tag_utils import list_tag_entities


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/tags/preview")
async def ai_tag_governance_preview(request: AiTagGovernancePreviewRequest):
    """AI 生成全局标签系统管理建议，不直接写入。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    vault = get_vault_data()
    source_revision = vault_revision()
    entries = _filter_entries_for_organize(vault, request.filters)
    if not entries:
        raise HTTPException(status_code=422, detail="当前密码库没有可分析条目")
    if len(entries) > AI_ORGANIZE_MAX_ENTRIES:
        raise HTTPException(status_code=413, detail=f"AI 标签系统管理最多支持 {AI_ORGANIZE_MAX_ENTRIES} 条，请先缩小范围")
    entries_by_ref = {f"E{index + 1:03d}": entry for index, entry in enumerate(entries)}
    ai_config = ai_client._load_ai_config()
    if not ai_config:
        raise HTTPException(status_code=502, detail="AI 服务未配置")

    user_prompt = _clean_text(request.user_prompt, 1000)
    if detect_sensitive_metadata([("标签管理偏好", user_prompt)]):
        raise HTTPException(
            status_code=422,
            detail="标签管理偏好中检测到疑似密码或 Token；普通标签管理不会发送字段值",
        )

    user_payload = {
        "user_prompt": user_prompt,
        "existing_tags": list_tag_entities(vault),
        "existing_groups": existing_groups(vault),
        "entries": [_entry_for_ai_tag_governance(entry, ref) for ref, entry in entries_by_ref.items()],
        "privacy_note": "仅发送标题、网址 hostname、分类和字段名，不发送字段值、完整网址或备注。",
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
            ai_config.get("structured_output", "prompt_json"),
        )
        payload = ai_client._extract_json_content(content)
        suggestions, warnings = _normalize_tag_governance_payload(payload, set(entries_by_ref.keys()))
        for suggestion in suggestions:
            suggestion["entry_ids"] = [entries_by_ref[ref].id for ref in suggestion.get("entry_ids", [])]
        for index, suggestion in enumerate(suggestions):
            suggestion["id"] = f"tag-{index + 1}"
    except HTTPException:
        raise
    except json.JSONDecodeError as error:
        logger.error("AI 标签系统管理返回的 JSON 解析失败: %s", error)
        raise HTTPException(status_code=422, detail="AI 返回格式错误")
    except Exception as error:
        logger.error("AI 标签系统管理失败: %s", error)
        raise HTTPException(status_code=502, detail="AI 服务调用失败")

    if vault_revision() != source_revision:
        raise HTTPException(status_code=409, detail="密码库已变化，请重新生成 AI 计划")
    plan_token = put_pending("tag-governance", {"suggestions": suggestions}, source_revision)
    return {
        "success": True,
        "data": {
            "entry_count": len(entries),
            "suggestions": suggestions,
            "plan_token": plan_token,
            "source_revision": source_revision,
            "summary": _tag_governance_summary(suggestions),
            "warnings": warnings,
            "privacy_note": "本次仅发送标题、网址 hostname、分类和字段名；不发送字段值、完整网址或备注。",
        },
    }


@router.post("/tags/apply")
async def ai_tag_governance_apply(request: AiPendingPlanApplyRequest):
    """应用用户确认后的 AI 标签系统管理建议。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    pending = get_pending(request.plan_token, "tag-governance", request.expected_revision)
    selected_ids = set(request.selected_ids)
    suggestions = [
        AiTagGovernanceSuggestion(**suggestion)
        for suggestion in pending.payload.get("suggestions", [])
        if suggestion.get("id") in selected_ids
    ]
    if not suggestions:
        raise HTTPException(status_code=422, detail="请选择要应用的标签建议")

    snapshot = create_ai_snapshot()
    vault = get_vault_data()
    result = apply_tag_governance(vault, suggestions)
    if result["applied_count"] > 0:
        save_vault_data(vault)
        result["undo_token"] = put_pending("assistant-undo", {"filename": snapshot.name}, vault_revision())
        result["revision"] = vault_revision()
    discard_pending(request.plan_token)
    return {
        "success": True,
        "data": result,
        "message": f"已应用 {result['applied_count']} 条标签管理建议",
    }
