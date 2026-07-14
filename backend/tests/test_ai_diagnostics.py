import asyncio
import copy
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from ai_services import diagnostics


class AiDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "provider_id": "deepseek",
            "provider_name": "DeepSeek",
            "base_url": "https://api.deepseek.com",
            "api_key": "test-key",
            "model": "test-model",
            "structured_output": "response_format",
        }

    def test_preview_stays_within_budget_and_uses_only_synthetic_metadata(self):
        preview = diagnostics.diagnostics_preview()

        self.assertGreaterEqual(preview["case_count"], 12)
        self.assertLessEqual(preview["estimated_max_tokens"], preview["hard_token_budget"])
        self.assertFalse(preview["includes_real_vault_data"])
        self.assertFalse(preview["includes_field_values"])

        messages, _, _, _ = diagnostics._messages_for_case(diagnostics._cases()[0])
        serialized = json.dumps(messages, ensure_ascii=False)
        self.assertNotIn(diagnostics.SYNTHETIC_VALUE_MARKER, serialized)
        self.assertNotIn('"value"', serialized)

    def test_group_case_accepts_a_valid_reviewable_plan(self):
        content = json.dumps({
            "message": "建议新建开发服务密码组。",
            "domain": "groups",
            "actions": [{"type": "create_group", "name": "开发服务"}],
            "warnings": [],
        }, ensure_ascii=False)
        case = next(item for item in diagnostics._cases() if item["id"] == "group_exact")
        with patch.object(
            diagnostics.ai_client,
            "_request_chat_completion",
            AsyncMock(return_value=content),
        ):
            result = asyncio.run(diagnostics._run_case(case, self.config))

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["domain"], "groups")
        self.assertEqual(result["action_types"], ["create_group"])

    def test_plain_text_plan_is_visible_but_marked_degraded(self):
        case = next(item for item in diagnostics._cases() if item["id"] == "group_exact")
        with patch.object(
            diagnostics.ai_client,
            "_request_chat_completion",
            AsyncMock(return_value="建议按用途建立开发服务密码组。"),
        ):
            result = asyncio.run(diagnostics._run_case(case, self.config))

        self.assertEqual(result["status"], "degraded")
        self.assertIn("建议按用途", result["reply"])
        self.assertEqual(result["action_count"], 0)

    def test_empty_clarification_response_is_marked_degraded(self):
        case = next(item for item in diagnostics._cases() if item["id"] == "ambiguous")
        with patch.object(
            diagnostics.ai_client,
            "_request_chat_completion",
            AsyncMock(return_value=""),
        ):
            result = asyncio.run(diagnostics._run_case(case, self.config))

        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["action_count"], 0)
        self.assertIn("空内容", result["reply"])

    def test_field_value_request_strips_model_navigation_actions(self):
        content = json.dumps({
            "message": "我可以打开所有条目供你查看。",
            "domain": "navigation",
            "actions": [
                {"type": "open_entry", "entry_ref": "E001"},
                {"type": "open_entry", "entry_ref": "E002"},
            ],
            "warnings": [],
        }, ensure_ascii=False)
        case = next(item for item in diagnostics._cases() if item["id"] == "read_values")
        with patch.object(
            diagnostics.ai_client,
            "_request_chat_completion",
            AsyncMock(return_value=content),
        ):
            result = asyncio.run(diagnostics._run_case(case, self.config))

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["domain"], "none")
        self.assertEqual(result["action_count"], 0)
        self.assertTrue(any("忽略模型返回" in item for item in result["warnings"]))

    def test_forbidden_delete_action_is_reported_as_safely_blocked(self):
        content = json.dumps({
            "message": "执行删除。",
            "domain": "entry_structure",
            "actions": [{"type": "delete_entry", "entry_ref": "E005"}],
            "warnings": [],
        }, ensure_ascii=False)
        case = next(item for item in diagnostics._cases() if item["id"] == "delete_entry")
        with patch.object(
            diagnostics.ai_client,
            "_request_chat_completion",
            AsyncMock(return_value=content),
        ):
            result = asyncio.run(diagnostics._run_case(case, self.config))

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["action_count"], 0)
        self.assertIn("安全校验", result["detail"])

    def test_real_diagnostics_requires_explicit_cost_confirmation(self):
        with self.assertRaises(HTTPException) as raised:
            diagnostics.start_diagnostics(False)

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("确认", raised.exception.detail)

    def test_diagnostics_stop_after_three_provider_failures(self):
        original_state = copy.deepcopy(diagnostics._STATE)
        failure = {
            "id": "provider-failure",
            "label": "服务失败",
            "status": "failed",
            "failure_kind": "provider",
            "estimated_max_tokens": 100,
        }
        diagnostics._STATE = {
            "status": "running",
            "started_at": "2026-07-14T00:00:00",
            "provider": {},
            "progress": 0,
            "total": 16,
            "results": [],
        }
        try:
            with (
                patch.object(diagnostics, "is_unlocked", return_value=True),
                patch.object(diagnostics, "_run_case", AsyncMock(return_value=failure)) as run_case,
                patch.object(diagnostics, "_write_report"),
                patch.object(diagnostics.asyncio, "sleep", AsyncMock()),
            ):
                asyncio.run(diagnostics._run_diagnostics("run-id", self.config))

            self.assertEqual(run_case.await_count, 3)
            self.assertEqual(len(diagnostics._STATE["results"]), 16)
            self.assertTrue(any(item.get("failure_kind") == "aborted" for item in diagnostics._STATE["results"]))
        finally:
            diagnostics._STATE = original_state


if __name__ == "__main__":
    unittest.main()
