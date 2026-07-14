"""Conversational AI manager routes."""

from fastapi import APIRouter, HTTPException

from ai_services.conversation import apply_plan, prepare_turn, preview_turn, submit_turn, undo_plan
from ai_services.diagnostics import diagnostics_preview, get_diagnostics_status, start_diagnostics
from ai_services.history import (
    clear_history,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
)
from models import (
    AiConversationCreateRequest,
    AiDiagnosticsRunRequest,
    AiPendingPlanApplyRequest,
    AiTurnPrepareRequest,
    AiTurnPreviewRequest,
    AiTurnSubmitRequest,
    AiUndoRequest,
)
from storage import is_unlocked


router = APIRouter()


def _require_unlocked() -> None:
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")


@router.get("/assistant/conversations")
async def conversations():
    _require_unlocked()
    return {"success": True, "data": {"conversations": list_conversations()}}


@router.post("/assistant/conversations")
async def new_conversation(request: AiConversationCreateRequest):
    _require_unlocked()
    return {"success": True, "data": create_conversation(request.title)}


@router.get("/assistant/conversations/{conversation_id}")
async def conversation_detail(conversation_id: str):
    _require_unlocked()
    conversation = get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="AI 对话不存在")
    return {"success": True, "data": conversation}


@router.delete("/assistant/conversations/{conversation_id}")
async def remove_conversation(conversation_id: str):
    _require_unlocked()
    if not delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="AI 对话不存在")
    return {"success": True, "data": None, "message": "AI 对话已删除"}


@router.delete("/assistant/conversations")
async def remove_all_conversations():
    _require_unlocked()
    clear_history()
    return {"success": True, "data": None, "message": "AI 对话历史已清除"}


@router.post("/assistant/turns/prepare")
async def prepare_assistant_turn(request: AiTurnPrepareRequest):
    _require_unlocked()
    return {"success": True, "data": prepare_turn(request)}


@router.post("/assistant/turns/preview")
async def preview_assistant_turn(request: AiTurnPreviewRequest):
    _require_unlocked()
    return {"success": True, "data": preview_turn(request)}


@router.post("/assistant/turns/submit")
async def submit_assistant_turn(request: AiTurnSubmitRequest):
    _require_unlocked()
    return {
        "success": True,
        "data": await submit_turn(request.turn_token, request.acknowledge_risk),
    }


@router.get("/assistant/diagnostics/preview")
async def assistant_diagnostics_preview():
    _require_unlocked()
    return {"success": True, "data": diagnostics_preview()}


@router.get("/assistant/diagnostics/status")
async def assistant_diagnostics_status():
    _require_unlocked()
    return {"success": True, "data": get_diagnostics_status()}


@router.post("/assistant/diagnostics/run")
async def run_assistant_diagnostics(request: AiDiagnosticsRunRequest):
    _require_unlocked()
    return {"success": True, "data": start_diagnostics(request.acknowledge_cost)}


@router.post("/assistant/plans/apply")
async def apply_assistant_plan(request: AiPendingPlanApplyRequest):
    _require_unlocked()
    result = apply_plan(request.plan_token, request.selected_ids, request.expected_revision)
    return {
        "success": True,
        "data": result,
        "message": f"已应用 {result['applied_count']} 项 AI 操作",
    }


@router.post("/assistant/plans/undo")
async def undo_assistant_plan(request: AiUndoRequest):
    _require_unlocked()
    result = undo_plan(request.undo_token, request.expected_revision)
    return {
        "success": True,
        "data": result,
        "message": "已撤销本次 AI 操作",
    }
