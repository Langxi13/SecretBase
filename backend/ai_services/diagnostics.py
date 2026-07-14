"""Synthetic, non-destructive compatibility diagnostics for configured AI providers."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import secrets
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException

from ai_services import client as ai_client
from ai_services.conversation import (
    ASSISTANT_SYSTEM_PROMPT,
    UNSTRUCTURED_RESPONSE_WARNING,
    _assistant_payload_from_content,
    _normalize_assistant_response,
)
from ai_services.diagnostic_cases import (
    SYNTHETIC_VALUE_MARKER,
    diagnostic_cases as _cases,
    synthetic_vault as _synthetic_vault,
)
from ai_services.privacy import entry_metadata, taxonomy_metadata
from models import VaultData
from storage import is_unlocked


logger = logging.getLogger(__name__)
DIAGNOSTIC_MAX_OUTPUT_TOKENS = 3000
DIAGNOSTIC_TOKEN_BUDGET = 300_000
REPORT_PATH = Path(tempfile.gettempdir()) / "secretbase-ai-diagnostics-latest.json"

_TASK: asyncio.Task | None = None
_STATE: dict = {
    "status": "idle",
    "run_id": "",
    "progress": 0,
    "total": 0,
    "results": [],
    "summary": {},
    "error": "",
}


def _turn_context(vault: VaultData) -> tuple[dict, dict]:
    aliases = {f"E{index + 1:03d}": entry for index, entry in enumerate(vault.entries)}
    metadata = [entry_metadata(entry, ref) for ref, entry in aliases.items()]
    taxonomy = taxonomy_metadata(vault)
    turn = {
        "entry_map": {ref: entry.id for ref, entry in aliases.items()},
        "field_map": {
            field["ref"]: {"entry_id": entry.id, "index": index, "name": entry.fields[index].name}
            for ref, entry in aliases.items()
            for index, field in enumerate(entry_metadata(entry, ref)["fields"])
        },
    }
    return turn, {"entries": metadata, **taxonomy}


def _messages_for_case(case: dict) -> tuple[list[dict], dict, VaultData, int]:
    vault = _synthetic_vault(bool(case.get("long_context")))
    turn, vault_context = _turn_context(vault)
    user_payload = {
        "instruction": case["instruction"],
        "vault_context": vault_context,
        "privacy_note": "诊断数据完全为合成数据，不包含任何真实字段值、备注或完整网址。",
    }
    serialized = json.dumps(user_payload, ensure_ascii=False)
    if SYNTHETIC_VALUE_MARKER in serialized or '"value"' in serialized:
        raise RuntimeError("诊断隐私断言失败：字段值进入了请求载荷")
    messages = [
        {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT},
        *(case.get("history") or []),
        {"role": "user", "content": serialized},
    ]
    estimated_tokens = sum(len(item.get("content", "")) for item in messages) + DIAGNOSTIC_MAX_OUTPUT_TOKENS
    return messages, turn, vault, estimated_tokens


def diagnostics_preview() -> dict:
    cases = _cases()
    estimates = [_messages_for_case(case)[3] for case in cases]
    estimated_tokens = sum(estimates)
    if estimated_tokens > DIAGNOSTIC_TOKEN_BUDGET:
        raise HTTPException(status_code=500, detail="AI 诊断预算配置超过安全上限")
    return {
        "case_count": len(cases),
        "estimated_max_tokens": estimated_tokens,
        "hard_token_budget": DIAGNOSTIC_TOKEN_BUDGET,
        "data_types": ["合成标题", "合成 hostname", "合成标签", "合成密码组", "合成字段名"],
        "includes_real_vault_data": False,
        "includes_field_values": False,
        "case_labels": [case["label"] for case in cases],
    }


def _evaluate_case(
    case: dict,
    domain: str,
    actions: list[dict],
    warnings: list[str],
    response_content: str,
) -> tuple[str, str]:
    if case.get("expect_no_actions"):
        if actions:
            return "failed", "该场景应仅解释或澄清，但模型生成了可执行操作。"
        if not isinstance(response_content, str) or not response_content.strip():
            return "degraded", "模型未返回可读取的回复，系统未生成任何操作。"
        if UNSTRUCTURED_RESPONSE_WARNING in warnings:
            return "degraded", "模型仅返回普通文本，系统未生成任何操作。"
        return "passed", "未生成越权或混合操作。"
    if not actions:
        return "degraded", "模型给出了文字回复，但没有生成预期的可审核计划。"
    if domain not in case.get("domains", set()):
        return "failed", f"计划类型为 {domain}，与场景预期不一致。"
    if UNSTRUCTURED_RESPONSE_WARNING in warnings:
        return "degraded", "模型未返回结构化计划，已降级为纯文本。"
    return "passed", "生成了可审核且类型正确的计划。"


async def _run_case(case: dict, config: dict) -> dict:
    messages, turn, vault, estimated_tokens = _messages_for_case(case)
    try:
        content = await ai_client._request_chat_completion(
            config["base_url"],
            config["api_key"],
            config["model"],
            messages,
            DIAGNOSTIC_MAX_OUTPUT_TOKENS,
            config.get("structured_output", "prompt_json"),
        )
        payload = _assistant_payload_from_content(content)
        message, domain, actions, display, warnings = _normalize_assistant_response(
            payload,
            turn,
            vault,
            instruction=case["instruction"],
        )
        status, detail = _evaluate_case(case, domain, actions, warnings, content)
        return {
            "id": case["id"],
            "label": case["label"],
            "status": status,
            "detail": detail,
            "domain": domain,
            "action_count": len(actions),
            "action_types": [action["type"] for action in actions],
            "reply": message,
            "warnings": warnings,
            "estimated_max_tokens": estimated_tokens,
            "response_chars": len(content) if isinstance(content, str) else 0,
            "safety_case": bool(case.get("safety_case")),
            "display": display,
            "failure_kind": "",
        }
    except HTTPException as error:
        safety_block = bool(case.get("safety_case") or case.get("expect_no_actions")) and error.status_code == 422
        return {
            "id": case["id"],
            "label": case["label"],
            "status": "blocked" if safety_block else "failed",
            "detail": f"系统安全校验已拦截模型输出：{error.detail}" if safety_block else str(error.detail),
            "domain": "none",
            "action_count": 0,
            "action_types": [],
            "reply": "",
            "warnings": [],
            "estimated_max_tokens": estimated_tokens,
            "response_chars": 0,
            "safety_case": bool(case.get("safety_case")),
            "display": [],
            "failure_kind": "provider" if error.status_code >= 500 else "validation",
        }
    except Exception as error:
        logger.exception("AI 诊断场景失败: %s", case["id"])
        return {
            "id": case["id"],
            "label": case["label"],
            "status": "failed",
            "detail": f"诊断执行失败：{type(error).__name__}",
            "domain": "none",
            "action_count": 0,
            "action_types": [],
            "reply": "",
            "warnings": [],
            "estimated_max_tokens": estimated_tokens,
            "response_chars": 0,
            "safety_case": bool(case.get("safety_case")),
            "display": [],
            "failure_kind": "internal",
        }


def _recommendations(results: list[dict]) -> list[str]:
    recommendations = []
    if any(UNSTRUCTURED_RESPONSE_WARNING in item.get("warnings", []) for item in results):
        recommendations.append("当前模型存在非结构化回复，系统会保留文字但无法生成计划。")
    if any(item["status"] == "blocked" for item in results):
        recommendations.append("模型曾生成不符合协议的内容，已被服务端安全层拦截。")
    missing = [item["label"] for item in results if item["status"] == "degraded"]
    if missing:
        recommendations.append(f"以下场景只返回文字或计划不完整：{'、'.join(missing[:5])}。")
    failed = [item["label"] for item in results if item["status"] == "failed"]
    if failed:
        recommendations.append(f"以下场景需要进一步兼容：{'、'.join(failed[:5])}。")
    if not recommendations:
        recommendations.append("当前模型在本轮合成数据诊断中表现稳定。")
    return recommendations


def _write_report(report: dict) -> None:
    tmp_path = REPORT_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, REPORT_PATH)


async def _run_diagnostics(run_id: str, config: dict) -> None:
    global _STATE
    cases = _cases()
    results = []
    consecutive_provider_failures = 0
    try:
        for index, case in enumerate(cases):
            if not is_unlocked():
                raise RuntimeError("密码库已锁定，诊断已停止")
            _STATE["current_case"] = case["label"]
            result = await _run_case(case, config)
            results.append(result)
            if result.get("failure_kind") == "provider":
                consecutive_provider_failures += 1
            else:
                consecutive_provider_failures = 0
            _STATE["results"] = copy.deepcopy(results)
            _STATE["progress"] = index + 1
            logger.info("AI 诊断 %s: %s", case["id"], result["status"])
            if consecutive_provider_failures >= 3:
                for skipped in cases[index + 1:]:
                    results.append({
                        "id": skipped["id"],
                        "label": skipped["label"],
                        "status": "failed",
                        "detail": "连续三次 AI 服务错误，已停止后续请求以避免继续消耗额度。",
                        "domain": "none",
                        "action_count": 0,
                        "action_types": [],
                        "reply": "",
                        "warnings": [],
                        "estimated_max_tokens": 0,
                        "response_chars": 0,
                        "safety_case": bool(skipped.get("safety_case")),
                        "display": [],
                        "failure_kind": "aborted",
                    })
                _STATE["results"] = copy.deepcopy(results)
                _STATE["progress"] = len(cases)
                break
            await asyncio.sleep(0.2)

        counts = {
            name: sum(1 for item in results if item["status"] == name)
            for name in ("passed", "degraded", "blocked", "failed")
        }
        report = {
            "status": "completed",
            "run_id": run_id,
            "started_at": _STATE["started_at"],
            "completed_at": datetime.now().isoformat(),
            "provider": _STATE["provider"],
            "progress": len(cases),
            "total": len(cases),
            "results": results,
            "summary": {
                **counts,
                "estimated_max_tokens": sum(item["estimated_max_tokens"] for item in results),
                "recommendations": _recommendations(results),
            },
            "error": "",
            "current_case": "",
        }
        _STATE = report
        _write_report(report)
    except Exception as error:
        logger.exception("AI 兼容性诊断中止")
        _STATE.update({
            "status": "failed",
            "results": results,
            "summary": {},
            "error": str(error),
            "current_case": "",
        })
        _write_report(copy.deepcopy(_STATE))


def get_diagnostics_status() -> dict:
    return copy.deepcopy(_STATE)


def start_diagnostics(acknowledge_cost: bool) -> dict:
    global _TASK, _STATE
    if not acknowledge_cost:
        raise HTTPException(status_code=422, detail="运行真实 AI 诊断前必须确认测试数据和额度消耗")
    if _TASK and not _TASK.done():
        raise HTTPException(status_code=409, detail="AI 兼容性诊断正在运行")
    config = ai_client._load_ai_config()
    if not config:
        raise HTTPException(status_code=502, detail="AI 服务未配置")
    preview = diagnostics_preview()
    run_id = secrets.token_urlsafe(10)
    _STATE = {
        "status": "running",
        "run_id": run_id,
        "started_at": datetime.now().isoformat(),
        "completed_at": "",
        "provider": {
            "provider_name": config.get("provider_name", "自定义接口"),
            "target_host": urlsplit(config["base_url"]).hostname or "",
            "model": config["model"],
        },
        "progress": 0,
        "total": preview["case_count"],
        "results": [],
        "summary": {},
        "error": "",
        "current_case": "准备诊断",
    }
    _TASK = asyncio.create_task(_run_diagnostics(run_id, config))
    return get_diagnostics_status()
