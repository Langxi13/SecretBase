import unittest

from ai_services.scope_catalog import assistant_scope_catalog, entries_for_assistant_scope
from ai_services.organize import _filter_entries_for_organize
from models import AiScopeCatalogRequest, AiTurnPreviewRequest, Entry, FieldItem, VaultData


class AiScopeTests(unittest.TestCase):
    def setUp(self):
        self.starred = Entry(
            title="收藏控制台",
            url="https://console.example.test/private/path",
            starred=True,
            tags=["云服务"],
            groups=["工作"],
            fields=[FieldItem(name="密码", value="must-not-appear", hidden=True)],
            remarks="must-not-appear-remark",
        )
        self.regular = Entry(
            title="普通邮箱",
            url="https://mail.example.test/login",
            starred=False,
            tags=["邮箱"],
            groups=[],
            fields=[FieldItem(name="账号", value="user@example.test")],
        )
        self.deleted = Entry(title="已删除", deleted=True)
        self.vault = VaultData(entries=[self.starred, self.regular, self.deleted])

    def test_inactive_favorite_toggle_does_not_exclude_starred_entries(self):
        entries = entries_for_assistant_scope(
            self.vault,
            {"starred": False},
            "current_view",
        )

        self.assertEqual({entry.id for entry in entries}, {self.starred.id, self.regular.id})
        organize_entries = _filter_entries_for_organize(self.vault, {"starred": False})
        self.assertEqual(
            {entry.id for entry in organize_entries},
            {self.starred.id, self.regular.id},
        )

    def test_explicit_unstarred_filter_remains_available(self):
        entries = entries_for_assistant_scope(
            self.vault,
            {"starred": "false"},
            "current_view",
        )

        self.assertEqual([entry.id for entry in entries], [self.regular.id])

    def test_custom_selection_does_not_inherit_current_view_filters(self):
        entries = entries_for_assistant_scope(
            self.vault,
            {"entryIds": [self.starred.id], "starred": False},
            "selection",
        )

        self.assertEqual([entry.id for entry in entries], [self.starred.id])

    def test_catalog_returns_only_metadata_and_scope_counts(self):
        result = assistant_scope_catalog(
            self.vault,
            current_filters={"starred": False},
            selected_ids=[self.starred.id, self.deleted.id],
            page=1,
            page_size=5,
        )

        self.assertEqual(result["counts"], {"all": 2, "current_view": 2})
        self.assertEqual(result["valid_selected_ids"], [self.starred.id])
        self.assertEqual(result["pagination"]["total"], 2)
        serialized = repr(result["items"])
        self.assertIn("console.example.test", serialized)
        self.assertNotIn("/private/path", serialized)
        self.assertNotIn("must-not-appear", serialized)
        self.assertNotIn("fields", result["items"][0])
        self.assertNotIn("remarks", result["items"][0])

    def test_catalog_searches_title_and_hostname_without_field_values(self):
        by_title = assistant_scope_catalog(
            self.vault,
            current_filters={},
            search="收藏",
            page_size=5,
        )
        by_host = assistant_scope_catalog(
            self.vault,
            current_filters={},
            search="mail.example",
            page_size=5,
        )
        by_value = assistant_scope_catalog(
            self.vault,
            current_filters={},
            search="user@example",
            page_size=5,
        )

        self.assertEqual([item["id"] for item in by_title["items"]], [self.starred.id])
        self.assertEqual([item["id"] for item in by_host["items"]], [self.regular.id])
        self.assertEqual(by_value["items"], [])

    def test_scope_requests_default_to_all_and_clean_selected_ids(self):
        preview = AiTurnPreviewRequest(mode="assistant")
        catalog = AiScopeCatalogRequest(
            selected_ids=[self.starred.id, f" {self.starred.id} "],
        )

        self.assertEqual(preview.scope, "all")
        self.assertEqual(catalog.selected_ids, [self.starred.id])


if __name__ == "__main__":
    unittest.main()
