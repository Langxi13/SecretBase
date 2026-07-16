import unittest
from types import SimpleNamespace

from pydantic import ValidationError

from models import (
    AiActionApplyRequest,
    AiParseRequest,
    BatchRequest,
    EntryCreate,
    EntryUpdate,
    GroupOrderRequest,
    TagMergeRequest,
)
from utils import request_log_path


class ModelValidationTests(unittest.TestCase):
    def test_entry_text_identifiers_are_trimmed(self):
        entry = EntryCreate(
            title="  示例条目  ",
            url="  https://example.test/path  ",
            fields=[{"name": "  用户名  ", "value": " keep spaces "}],
        )

        self.assertEqual(entry.title, "示例条目")
        self.assertEqual(entry.url, "https://example.test/path")
        self.assertEqual(entry.fields[0].name, "用户名")
        self.assertEqual(entry.fields[0].value, " keep spaces ")

    def test_blank_entry_titles_are_rejected_for_create_and_update(self):
        with self.assertRaises(ValidationError):
            EntryCreate(title="   ")
        with self.assertRaises(ValidationError):
            EntryUpdate(title="   ")

    def test_ai_parse_limit_matches_frontend_limit(self):
        self.assertEqual(len(AiParseRequest(text="a" * 6000).text), 6000)
        with self.assertRaises(ValidationError):
            AiParseRequest(text="a" * 6001)

    def test_batch_operations_have_a_bounded_item_count(self):
        self.assertEqual(len(BatchRequest(ids=["id"] * 1000).ids), 1000)
        with self.assertRaises(ValidationError):
            BatchRequest(ids=["id"] * 1001)

        names = [f"group-{index}" for index in range(500)]
        self.assertEqual(len(GroupOrderRequest(names=names).names), 500)
        with self.assertRaises(ValidationError):
            GroupOrderRequest(names=[f"group-{index}" for index in range(501)])
        with self.assertRaises(ValidationError):
            GroupOrderRequest(names=["x" * 51])

        merge = TagMergeRequest(source_tags=["  old  ", "old"], target_tag="new")
        self.assertEqual(merge.source_tags, ["old"])

        action = {"type": "create_group", "group": "example"}
        self.assertEqual(len(AiActionApplyRequest(actions=[action] * 100).actions), 100)
        with self.assertRaises(ValidationError):
            AiActionApplyRequest(actions=[action] * 101)

    def test_request_logging_uses_route_templates(self):
        request = SimpleNamespace(
            scope={"route": SimpleNamespace(path="/groups/{group_name}")},
            url=SimpleNamespace(path="/groups/私人密码组"),
        )
        self.assertEqual(request_log_path(request), "/groups/{group_name}")

        unmatched = SimpleNamespace(scope={}, url=SimpleNamespace(path="/private-value"))
        self.assertEqual(request_log_path(unmatched), "<unmatched>")


if __name__ == "__main__":
    unittest.main()
