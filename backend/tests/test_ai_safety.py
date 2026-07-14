import asyncio
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

from ai_services import conversation
from ai_services import history as ai_history
from ai_services import pending as ai_pending
from ai_services.privacy import entry_metadata
from ai_services.providers import normalize_base_url
from models import AiTurnPrepareRequest, AiTurnPreviewRequest, Entry, FieldItem, VaultData


class AiSafetyTests(unittest.TestCase):
    def setUp(self):
        self.entry = Entry(
            title="生产控制台",
            url="https://console.example.test/private/path?account=owner",
            tags=["开发"],
            groups=["服务器"],
            fields=[
                FieldItem(
                    name="登录密码",
                    value="never-send-this-value",
                    copyable=True,
                    hidden=True,
                )
            ],
            remarks="never-send-this-remark",
        )
        self.vault = VaultData(entries=[self.entry])
        self.turn = {
            "entry_map": {"E001": self.entry.id},
            "field_map": {
                "E001.F01": {
                    "entry_id": self.entry.id,
                    "index": 0,
                    "name": "登录密码",
                }
            },
        }

    def test_group_management_prompt_is_not_misclassified_as_password_generation(self):
        result = conversation._local_response(
            "检查当前范围内密码组的分类是否合理，只生成密码组管理计划",
            [self.entry],
        )

        self.assertIsNone(result)

    def test_password_generation_remains_a_local_action(self):
        result = conversation._local_response("帮我生成一个新密码", [self.entry])

        self.assertEqual(result["local_action"]["type"], "generate_password")

    def test_password_generation_inside_a_group_remains_a_local_action(self):
        result = conversation._local_response("在工作密码组中生成一个新密码", [self.entry])

        self.assertEqual(result["local_action"]["type"], "generate_password")

    def test_plain_text_ai_response_is_preserved_without_executable_actions(self):
        payload = conversation._assistant_payload_from_content("建议先整理现有密码组，再逐项确认。")

        self.assertEqual(payload["message"], "建议先整理现有密码组，再逐项确认。")
        self.assertEqual(payload["domain"], "none")
        self.assertEqual(payload["actions"], [])
        self.assertTrue(any("未生成任何可执行操作" in item for item in payload["warnings"]))

    def test_non_object_json_ai_response_is_discarded_as_a_plan(self):
        payload = conversation._assistant_payload_from_content('[{"type":"create_group"}]')

        self.assertEqual(payload["domain"], "none")
        self.assertEqual(payload["actions"], [])
        self.assertIn("无法识别", payload["message"])

    def test_json_extractor_treats_non_string_content_as_invalid_json(self):
        with self.assertRaises(json.JSONDecodeError):
            conversation.ai_client._extract_json_content(None)

    def test_metadata_dto_excludes_values_full_urls_remarks_and_real_ids(self):
        metadata = entry_metadata(self.entry, "E001")
        serialized = repr(metadata)

        self.assertEqual(metadata["ref"], "E001")
        self.assertEqual(metadata["hostname"], "console.example.test")
        self.assertNotIn(self.entry.id, serialized)
        self.assertNotIn("never-send-this-value", serialized)
        self.assertNotIn("never-send-this-remark", serialized)
        self.assertNotIn("/private/path", serialized)
        self.assertNotIn("value", metadata["fields"][0])

    def test_forbidden_value_key_is_rejected_before_plan_creation(self):
        payload = {
            "message": "建议",
            "domain": "entry_structure",
            "actions": [
                {
                    "type": "rename_field",
                    "field_ref": "E001.F01",
                    "new_name": "密码",
                    "value": "must-never-enter-plan",
                }
            ],
            "warnings": [],
        }

        with self.assertRaises(HTTPException) as raised:
            conversation._normalize_assistant_response(payload, self.turn)

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("禁止", raised.exception.detail)

    def test_alias_is_resolved_locally_and_display_uses_entry_title(self):
        payload = {
            "message": "建议重命名",
            "domain": "entry_structure",
            "actions": [
                {
                    "type": "rename_entry",
                    "entry_ref": "E001",
                    "new_title": "控制台",
                }
            ],
            "warnings": [],
        }

        with patch.object(conversation, "get_vault_data", return_value=self.vault):
            _, domain, actions, display, _ = conversation._normalize_assistant_response(
                payload,
                self.turn,
            )

        self.assertEqual(domain, "entry_structure")
        self.assertEqual(actions[0]["entry_id"], self.entry.id)
        self.assertIn("生产控制台", display[0]["title"])
        self.assertNotIn(self.entry.id, display[0]["title"])

    def test_mixed_tag_and_group_plan_keeps_reply_but_discards_actions(self):
        payload = {
            "message": "混合建议",
            "domain": "tags",
            "actions": [
                {"type": "create_tag", "name": "开发"},
                {"type": "create_group", "name": "工作"},
            ],
            "warnings": [],
        }

        with patch.object(conversation, "get_vault_data", return_value=self.vault):
            message, domain, actions, display, warnings = conversation._normalize_assistant_response(
                payload,
                self.turn,
            )

        self.assertEqual(message, "混合建议")
        self.assertEqual(domain, "none")
        self.assertEqual(actions, [])
        self.assertEqual(display, [])
        self.assertTrue(any("不会生成可执行计划" in warning for warning in warnings))

    def test_mismatched_domain_is_corrected_without_losing_plan(self):
        payload = {
            "message": "建议整理密码组",
            "domain": "tags",
            "actions": [{"type": "create_group", "name": "工作"}],
            "warnings": [],
        }

        with patch.object(conversation, "get_vault_data", return_value=self.vault):
            message, domain, actions, display, warnings = conversation._normalize_assistant_response(
                payload,
                self.turn,
            )

        self.assertEqual(message, "建议整理密码组")
        self.assertEqual(domain, "groups")
        self.assertEqual(actions[0]["type"], "create_group")
        self.assertEqual(display[0]["title"], "新建密码组「工作」")
        self.assertTrue(any("重新归类" in warning for warning in warnings))

    def test_unknown_or_blacklisted_action_is_rejected(self):
        payload = {
            "message": "危险建议",
            "domain": "entry_structure",
            "actions": [{"type": "delete_entry", "entry_ref": "E001"}],
            "warnings": [],
        }

        with patch.object(conversation, "get_vault_data", return_value=self.vault):
            with self.assertRaises(HTTPException) as raised:
                conversation._normalize_assistant_response(payload, self.turn)

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("不允许", raised.exception.detail)

    def test_missing_entry_reference_is_rejected_as_validation_error(self):
        payload = {
            "message": "建议重命名",
            "domain": "entry_structure",
            "actions": [{"type": "rename_entry", "new_title": "控制台"}],
            "warnings": [],
        }

        with patch.object(conversation, "get_vault_data", return_value=self.vault):
            with self.assertRaises(HTTPException) as raised:
                conversation._normalize_assistant_response(payload, self.turn)

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("引用", raised.exception.detail)

    def test_invalid_port_is_reported_as_validation_error(self):
        with self.assertRaises(HTTPException) as raised:
            normalize_base_url("https://api.example.test:not-a-port/v1")

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("端口", raised.exception.detail)

    def test_preview_turn_stores_only_metadata_and_alias_maps_without_prompt(self):
        captured = {}

        def capture_pending(kind, payload, source_revision=None):
            captured["kind"] = kind
            captured["payload"] = payload
            return "pending-token"

        request = AiTurnPreviewRequest(
            mode="assistant",
            scope="all",
        )
        with (
            patch.object(
                conversation.ai_client,
                "_load_ai_config",
                return_value={
                    "provider_id": "custom",
                    "provider_name": "测试接口",
                    "base_url": "https://api.example.test/v1",
                    "api_key": "test-key",
                    "model": "test-model",
                },
            ),
            patch.object(conversation, "get_vault_data", return_value=self.vault),
            patch.object(conversation, "put_pending", side_effect=capture_pending),
            patch.object(conversation, "vault_revision", return_value=3),
        ):
            result = conversation.preview_turn(request)

        serialized = repr(captured["payload"])
        self.assertEqual(captured["kind"], "assistant-preview")
        self.assertEqual(result["source_revision"], 3)
        self.assertEqual(result["preview_token"], "pending-token")
        self.assertNotIn("message", captured["payload"])
        self.assertNotIn("conversation_id", captured["payload"])
        self.assertIn("本轮提示词", result["manifest"]["data_types"])
        self.assertIn("E001", serialized)
        self.assertNotIn(self.entry.id, repr(captured["payload"]["metadata"]))
        self.assertNotIn("never-send-this-value", serialized)
        self.assertNotIn("never-send-this-remark", serialized)
        self.assertNotIn("/private/path", serialized)

    def test_normal_mode_rejects_user_supplied_secret_before_pending_plan(self):
        request = AiTurnPrepareRequest(
            preview_token="p" * 32,
            message="password: never-send-this-value",
        )
        config = {
            "provider_id": "custom",
            "base_url": "https://api.example.test/v1",
            "api_key": "test-key",
            "model": "test-model",
        }
        preview = SimpleNamespace(
            source_revision=3,
            payload={
                "mode": "assistant",
                "entry_ids": [self.entry.id],
                "ai_target": conversation._config_identity(config),
                "manifest": {},
            },
        )
        with (
            patch.object(
                conversation.ai_client,
                "_load_ai_config",
                return_value=config,
            ),
            patch.object(conversation, "consume_pending", return_value=preview),
            patch.object(conversation, "get_vault_data", return_value=self.vault),
            patch.object(
                conversation,
                "ensure_conversation",
                return_value={"id": "conversation"},
            ),
            patch.object(conversation, "put_pending") as pending,
        ):
            with self.assertRaises(HTTPException) as raised:
                conversation.prepare_turn(request)

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("AI 新建", raised.exception.detail)
        pending.assert_not_called()

    def test_pending_turn_can_only_be_consumed_once(self):
        ai_pending._ITEMS.clear()
        with (
            patch.object(ai_pending, "vault_session_id", return_value="session-a"),
            patch.object(ai_pending, "vault_revision", return_value=4),
        ):
            token = ai_pending.put_pending("assistant-turn", {"message": "test"})
            item = ai_pending.consume_pending(token, "assistant-turn")
            with self.assertRaises(HTTPException) as raised:
                ai_pending.consume_pending(token, "assistant-turn")

        self.assertEqual(item.payload["message"], "test")
        self.assertEqual(raised.exception.status_code, 410)

    def test_submit_turn_requires_explicit_user_confirmation(self):
        request_model = AsyncMock()
        pending = SimpleNamespace(payload={"mode": "assistant"})
        with (
            patch.object(conversation, "consume_pending", return_value=pending),
            patch.object(conversation.ai_client, "_request_chat_completion", request_model),
        ):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(conversation.submit_turn("t" * 32, False))

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("确认", raised.exception.detail)
        request_model.assert_not_awaited()

    def test_submit_turn_returns_plain_text_ai_reply_without_a_server_error(self):
        config = {
            "provider_id": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key": "test-key",
            "model": "test-model",
            "structured_output": "response_format",
        }
        pending = SimpleNamespace(payload={
            "mode": "assistant",
            "conversation_id": "conversation",
            "message": "只生成密码组管理计划",
            "metadata": [],
            "taxonomy": {},
            "entry_map": {},
            "field_map": {},
            "ai_target": conversation._config_identity(config),
        })
        append_messages = Mock()
        with (
            patch.object(conversation, "consume_pending", return_value=pending),
            patch.object(conversation.ai_client, "_load_ai_config", return_value=config),
            patch.object(
                conversation.ai_client,
                "_request_chat_completion",
                AsyncMock(return_value="建议按用途整理密码组。"),
            ),
            patch.object(conversation, "model_context", return_value=[]),
            patch.object(conversation, "get_vault_data", return_value=self.vault),
            patch.object(conversation, "append_messages", append_messages),
            patch.object(conversation, "put_pending") as put_pending,
            patch.object(conversation, "vault_revision", return_value=4),
        ):
            result = asyncio.run(conversation.submit_turn("t" * 32, True))

        self.assertEqual(result["message"], "建议按用途整理密码组。")
        self.assertIsNone(result["plan_token"])
        self.assertEqual(result["actions"], [])
        self.assertTrue(result["warnings"])
        put_pending.assert_not_called()
        append_messages.assert_called_once()

    def test_changed_ai_target_requires_a_new_confirmation(self):
        expected = {
            "provider_id": "custom",
            "base_url": "https://first.example.test/v1",
            "model": "model-a",
        }
        current = {
            "provider_id": "custom",
            "base_url": "https://second.example.test/v1",
            "model": "model-a",
        }
        with self.assertRaises(HTTPException) as raised:
            conversation._require_same_ai_target(expected, current)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("重新确认", raised.exception.detail)

    def test_conversation_history_is_encrypted_at_rest(self):
        key = bytes(range(32))
        salt = bytes(reversed(range(32)))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "ai-history.enc"
            with (
                patch.object(ai_history, "HISTORY_PATH", path),
                patch.object(
                    ai_history,
                    "derive_unlocked_purpose_key",
                    return_value=(key, salt),
                ),
            ):
                summary = ai_history.create_conversation("安全测试")
                ai_history.append_messages(
                    summary["id"],
                    [
                        {"role": "user", "content": "普通整理请求"},
                        {"role": "assistant", "content": "已生成建议"},
                    ],
                )
                loaded = ai_history.get_conversation(summary["id"])

            self.assertIsNotNone(loaded)
            self.assertEqual(len(loaded["messages"]), 2)
            content = path.read_bytes()
            self.assertNotIn("普通整理请求".encode("utf-8"), content)
            self.assertNotIn("已生成建议".encode("utf-8"), content)

    def test_pending_plan_is_bound_to_session_and_revision(self):
        ai_pending._ITEMS.clear()
        with (
            patch.object(ai_pending, "vault_session_id", return_value="session-a"),
            patch.object(ai_pending, "vault_revision", return_value=4),
        ):
            token = ai_pending.put_pending("assistant-plan", {"actions": []})

        with (
            patch.object(ai_pending, "vault_session_id", return_value="session-a"),
            patch.object(ai_pending, "vault_revision", return_value=5),
        ):
            with self.assertRaises(HTTPException) as raised:
                ai_pending.get_pending(token, "assistant-plan")

        self.assertEqual(raised.exception.status_code, 409)
        self.assertNotIn(token, ai_pending._ITEMS)


if __name__ == "__main__":
    unittest.main()
