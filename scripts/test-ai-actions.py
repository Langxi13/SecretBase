import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def expect_success(response, label: str):
    assert response.status_code == 200, f"{label}: {response.status_code} {response.text}"
    payload = response.json()
    assert payload["success"] is True, f"{label}: {payload}"
    return payload["data"]


def expect_error(response, status_code: int, label: str):
    assert response.status_code == status_code, f"{label}: {response.status_code} {response.text}"
    return response.json()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DATA_DIR"] = tmpdir
        os.environ["BACKUP_DIR"] = str(Path(tmpdir) / "backups")
        os.environ["LOG_DIR"] = str(Path(tmpdir) / "logs")
        os.environ["SETTINGS_PATH"] = str(Path(tmpdir) / "settings.json")
        os.environ["VAULT_PATH"] = str(Path(tmpdir) / "secretbase.enc")
        os.environ["SECURE_SETTINGS_FILE"] = str(Path(tmpdir) / "secure-settings.enc")

        from fastapi.testclient import TestClient  # noqa: E402
        from ai_services import client as ai_client  # noqa: E402
        import routes.ai as ai_routes  # noqa: E402
        from main import app  # noqa: E402

        captured_payloads = []

        async def fake_chat_completion(*args, **kwargs):
            messages = args[3]
            user_payload = json.loads(messages[-1]["content"])
            captured_payloads.append(user_payload)
            serialized = json.dumps(user_payload, ensure_ascii=False)
            assert "main-user" not in serialized
            assert "demo-service-password" not in serialized
            assert "sk-secret" not in serialized
            assert '"value"' not in serialized
            entry_payload = next(entry for entry in user_payload["entries"] if entry["title"] == "demo.example")
            assert entry_payload["fields"][0]["name"] == "账号"
            assert entry_payload["fields"][1]["hidden"] is True
            assert "创建 demo-service 密码组" in user_payload["instruction"]
            assert "不发送字段值" in user_payload["privacy_note"]
            return json.dumps(
                {
                    "actions": [
                        {
                            "type": "create_group",
                            "group": "demo-service",
                            "description": "demo.example 相关凭据",
                            "reason": "用户要求创建独立密码组",
                        },
                        {
                            "type": "update_group",
                            "group": "待归档",
                            "group_new": "客户系统",
                            "description": "客户系统和业务资料相关凭据",
                            "reason": "用户希望整理现有密码组",
                        },
                        {
                            "type": "create_entry_from_field",
                            "source_entry_id": entry_payload["id"],
                            "field_index": 0,
                            "field_name": "账号",
                            "title": "demo-service 账号",
                            "groups": ["demo-service"],
                            "tags": ["demo-service"],
                            "reason": "把字段拆成独立条目",
                        },
                        {
                            "type": "create_entry_from_field",
                            "source_entry_id": entry_payload["id"],
                            "field_index": 1,
                            "field_name": "密码",
                            "title": "demo-service 密码",
                            "groups": ["demo-service"],
                            "tags": ["demo-service"],
                            "reason": "把字段拆成独立条目",
                        },
                        {
                            "type": "create_entry_from_field",
                            "source_entry_id": entry_payload["id"],
                            "field_index": 2,
                            "field_name": "API Key",
                            "title": "demo-service API Key",
                            "groups": ["demo-service"],
                            "tags": ["demo-service", "API"],
                            "reason": "把字段拆成独立条目",
                        },
                        {
                            "type": "update_entry",
                            "entry_id": entry_payload["id"],
                            "field_index": 0,
                            "field_name": "账号",
                            "add_tags": ["云平台"],
                            "reason": "给原条目补充分类标签",
                        },
                        {
                            "type": "delete_entry",
                            "entry_id": entry_payload["id"],
                            "reason": "不允许执行的危险动作",
                        },
                    ],
                    "warnings": ["请确认字段拆分计划"],
                },
                ensure_ascii=False,
            )

        ai_client._request_chat_completion = fake_chat_completion
        ai_client._load_ai_config = lambda: {
            "base_url": "https://ai.example.test/v1",
            "api_key": "test-key",
            "model": "test-model",
            "api_key_mask": "tes...key",
        }

        client = TestClient(app)
        password = "SecretBase-Test-123456!"
        init_data = expect_success(client.post("/auth/init", json={"password": password}), "init")
        headers = {"X-SecretBase-Token": init_data["token"]}

        source = expect_success(
            client.post(
                "/entries",
                json={
                    "title": "demo.example",
                    "url": "https://demo.example",
                    "tags": ["待整理"],
                    "groups": ["待归档"],
                    "fields": [
                        {"name": "账号", "value": "main-user", "copyable": True, "hidden": False},
                        {"name": "密码", "value": "demo-service-password", "copyable": True, "hidden": True},
                        {"name": "API Key", "value": "sk-secret", "copyable": True, "hidden": True},
                    ],
                    "remarks": "需要拆分字段",
                },
                headers=headers,
            ),
            "create source entry",
        )
        expect_success(
            client.post("/groups", json={"name": "待归档", "description": "临时分组"}, headers=headers),
            "create existing group",
        )

        preview = expect_success(
            client.post(
                "/ai/actions/preview",
                json={
                    "instruction": "创建 demo-service 密码组，将 demo.example 条目的三个字段独立作为条目，从属于该密码组",
                    "filters": {"search": "demo-service", "searchScopes": ["title"]},
                },
                headers=headers,
            ),
            "ai actions preview",
        )
        assert captured_payloads, "AI 交互必须调用模型生成操作计划"
        assert preview["entry_count"] == 1
        assert len(preview["actions"]) == 6
        assert preview["summary"]["create_group"] == 1
        assert preview["summary"]["update_group"] == 1
        assert preview["summary"]["create_entry_from_field"] == 3
        assert preview["summary"]["update_entry"] == 1
        assert preview["actions"][0]["selected"] is True
        assert preview["actions"][1]["group"] == "待归档"
        assert preview["actions"][1]["group_new"] == "客户系统"
        assert preview["actions"][2]["source_entry_title"] == "demo.example"
        assert preview["actions"][5]["entry_title"] == "demo.example"
        assert preview["actions"][5]["title"] is None
        assert preview["actions"][5]["field_index"] is None
        assert preview["actions"][5]["field_name"] is None
        assert "delete_entry" not in {action["type"] for action in preview["actions"]}
        assert any("不支持" in warning or "已忽略" in warning for warning in preview["warnings"])
        assert "不会发送任何字段值" in preview["privacy_note"]

        bad_actions = [dict(item) for item in preview["actions"]]
        bad_actions[2]["field_name"] = "已改名字段"
        expect_error(
            client.post("/ai/actions/apply", json={"actions": bad_actions}, headers=headers),
            422,
            "ai actions apply mismatched field",
        )

        apply_result = expect_success(
            client.post("/ai/actions/apply", json={"actions": preview["actions"]}, headers=headers),
            "ai actions apply",
        )
        assert apply_result["created_groups"] == 1
        assert apply_result["created_entries"] == 3
        assert apply_result["updated_entries"] == 1
        assert apply_result["updated_groups"] == 1
        assert apply_result["applied_count"] == 6

        groups = expect_success(client.get("/groups", headers=headers), "groups")["groups"]
        demo-service_group = next(group for group in groups if group["name"] == "demo-service")
        assert demo-service_group["description"] == "demo.example 相关凭据"
        renamed_group = next(group for group in groups if group["name"] == "客户系统")
        assert renamed_group["description"] == "客户系统和业务资料相关凭据"
        assert not any(group["name"] == "待归档" for group in groups)

        entries = expect_success(
            client.get("/entries", params={"search": "demo-service", "search_scopes": "title", "page_size": 20}, headers=headers),
            "entries after ai actions",
        )["items"]
        titles = {entry["title"] for entry in entries}
        assert {"demo.example", "demo-service 账号", "demo-service 密码", "demo-service API Key"}.issubset(titles)
        source_detail = expect_success(client.get(f"/entries/{source['id']}", headers=headers), "source detail")
        assert [field["value"] for field in source_detail["fields"]] == ["main-user", "demo-service-password", "sk-secret"]
        assert [field["name"] for field in source_detail["fields"]] == ["账号", "密码", "API Key"]
        assert "客户系统" in source_detail["groups"]
        assert "待归档" not in source_detail["groups"]
        assert "云平台" in source_detail["tags"]

        details_by_title = {}
        for entry in entries:
            details_by_title[entry["title"]] = expect_success(
                client.get(f"/entries/{entry['id']}", headers=headers),
                f"detail {entry['title']}",
            )

        assert details_by_title["demo-service 账号"]["fields"][0]["value"] == "main-user"
        assert details_by_title["demo-service 账号"]["fields"][0]["hidden"] is False
        assert details_by_title["demo-service 密码"]["fields"][0]["value"] == "demo-service-password"
        assert details_by_title["demo-service 密码"]["fields"][0]["hidden"] is True
        assert details_by_title["demo-service API Key"]["fields"][0]["value"] == "sk-secret"
        assert details_by_title["demo-service API Key"]["groups"] == ["demo-service"]
        assert set(details_by_title["demo-service API Key"]["tags"]) == {"demo-service", "API"}

        rename_only_result = expect_success(
            client.post(
                "/ai/actions/apply",
                json={
                    "actions": [
                        {
                            "type": "update_group",
                            "selected": True,
                            "group": "客户系统",
                            "group_new": "客户资料",
                        }
                    ]
                },
                headers=headers,
            ),
            "ai actions apply rename group only",
        )
        assert rename_only_result["updated_groups"] == 1
        groups_after_rename = expect_success(client.get("/groups", headers=headers), "groups after rename only")["groups"]
        renamed_only_group = next(group for group in groups_after_rename if group["name"] == "客户资料")
        assert renamed_only_group["description"] == "客户系统和业务资料相关凭据"
        source_after_rename = expect_success(client.get(f"/entries/{source['id']}", headers=headers), "source after rename only")
        assert "客户资料" in source_after_rename["groups"]
        assert "客户系统" not in source_after_rename["groups"]

        print("PASS ai actions")


if __name__ == "__main__":
    main()
