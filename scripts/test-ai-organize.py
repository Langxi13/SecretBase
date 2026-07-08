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


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DATA_DIR"] = tmpdir
        os.environ["BACKUP_DIR"] = str(Path(tmpdir) / "backups")
        os.environ["LOG_DIR"] = str(Path(tmpdir) / "logs")
        os.environ["SETTINGS_PATH"] = str(Path(tmpdir) / "settings.json")
        os.environ["VAULT_PATH"] = str(Path(tmpdir) / "secretbase.enc")
        os.environ["SECURE_SETTINGS_FILE"] = str(Path(tmpdir) / "secure-settings.enc")

        from fastapi.testclient import TestClient  # noqa: E402
        import routes.ai as ai_routes  # noqa: E402
        from main import app  # noqa: E402

        async def fake_chat_completion(*args, **kwargs):
            messages = args[3]
            user_payload = json.loads(messages[-1]["content"])
            entry_payload = user_payload["entries"][0]
            assert "value" not in json.dumps(entry_payload, ensure_ascii=False)
            if entry_payload["title"] == "家庭路由器":
                return json.dumps({"suggestions": [], "warnings": []}, ensure_ascii=False)
            if entry_payload["title"] == "项目 GitLab":
                return json.dumps(
                    {
                        "suggestions": [
                            {
                                "entry_id": entry_payload["id"],
                                "add_tags": ["开发资源"],
                                "remove_tags": [],
                                "add_groups": [],
                                "remove_groups": [],
                                "group_descriptions": {},
                                "reason": "标题和字段名显示这是开发平台账号",
                            }
                        ],
                        "warnings": [],
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "suggestions": [
                        {
                            "entry_id": entry_payload["id"],
                            "add_tags": ["邮箱", "工作"],
                            "remove_tags": ["待整理"],
                            "add_groups": ["工作账号"],
                            "remove_groups": ["旧分组"],
                            "group_descriptions": {"工作账号": "公司邮箱、协作工具和内部系统"},
                            "reason": "标题和字段名显示这是工作邮箱账号",
                        }
                    ],
                    "warnings": ["建议由用户确认后应用"],
                },
                ensure_ascii=False,
            )

        ai_routes._request_chat_completion = fake_chat_completion
        ai_routes._load_ai_config = lambda: {
            "base_url": "https://ai.example.test/v1",
            "api_key": "test-key",
            "model": "test-model",
            "api_key_mask": "tes...key",
        }

        client = TestClient(app)
        password = "SecretBase-Test-123456!"
        init_data = expect_success(client.post("/auth/init", json={"password": password}), "init")
        headers = {"X-SecretBase-Token": init_data["token"]}

        created = expect_success(
            client.post(
                "/entries",
                json={
                    "title": "公司邮箱",
                    "url": "https://mail.example.test",
                    "groups": ["旧分组"],
                    "tags": ["待整理"],
                    "fields": [
                        {"name": "账号", "value": "work@example.test", "copyable": True, "hidden": False},
                        {"name": "密码", "value": "secret-password", "copyable": True, "hidden": True},
                    ],
                    "remarks": "公司邮箱登录",
                },
                headers=headers,
            ),
            "create entry",
        )
        dev_entry = expect_success(
            client.post(
                "/entries",
                json={
                    "title": "项目 GitLab",
                    "url": "https://gitlab.example.test",
                    "tags": ["待分组"],
                    "fields": [
                        {"name": "用户名", "value": "developer", "copyable": True, "hidden": False},
                        {"name": "Access Token", "value": "glpat-secret", "copyable": True, "hidden": True},
                    ],
                    "remarks": "代码仓库和 CI 登录",
                },
                headers=headers,
            ),
            "create dev entry",
        )
        router_entry = expect_success(
            client.post(
                "/entries",
                json={
                    "title": "家庭路由器",
                    "tags": ["待自动分组"],
                    "fields": [
                        {"name": "管理地址", "value": "192.168.1.1", "copyable": True, "hidden": False},
                        {"name": "WiFi 密码", "value": "router-secret", "copyable": True, "hidden": True},
                    ],
                    "remarks": "家里网络设备",
                },
                headers=headers,
            ),
            "create router entry",
        )

        preview = expect_success(
            client.post(
                "/ai/organize/preview",
                json={
                    "filters": {"tag": "待整理"},
                    "organize_tags": True,
                    "organize_groups": True,
                },
                headers=headers,
            ),
            "organize preview",
        )
        assert preview["entry_count"] == 1
        assert preview["summary"]["affected_entries"] == 1
        assert preview["summary"]["add_tags"] == 2
        assert preview["summary"]["remove_tags"] == 1
        assert preview["summary"]["add_groups"] == 1
        suggestion = preview["suggestions"][0]
        assert suggestion["entry_id"] == created["id"]
        assert suggestion["selected"] is True
        assert suggestion["add_tags"] == ["邮箱", "工作"]
        assert suggestion["remove_tags"] == ["待整理"]
        assert suggestion["add_groups"] == ["工作账号"]
        assert suggestion["remove_groups"] == ["旧分组"]
        assert suggestion["reason"]

        tag_only_preview = expect_success(
            client.post(
                "/ai/organize/preview",
                json={
                    "filters": {"tag": "待整理"},
                    "organize_tags": True,
                    "organize_groups": False,
                },
                headers=headers,
            ),
            "organize preview tag only",
        )
        tag_only_suggestion = tag_only_preview["suggestions"][0]
        assert tag_only_suggestion["add_tags"] == ["邮箱", "工作"]
        assert tag_only_suggestion["remove_tags"] == ["待整理"]
        assert tag_only_suggestion["add_groups"] == []
        assert tag_only_suggestion["remove_groups"] == []
        assert tag_only_suggestion["group_descriptions"] == {}
        assert tag_only_preview["summary"]["add_groups"] == 0
        assert tag_only_preview["summary"]["remove_groups"] == 0

        group_only_preview = expect_success(
            client.post(
                "/ai/organize/preview",
                json={
                    "filters": {"tag": "待整理"},
                    "organize_tags": False,
                    "organize_groups": True,
                },
                headers=headers,
            ),
            "organize preview group only",
        )
        group_only_suggestion = group_only_preview["suggestions"][0]
        assert group_only_suggestion["add_tags"] == []
        assert group_only_suggestion["remove_tags"] == []
        assert group_only_suggestion["add_groups"] == ["工作账号"]
        assert group_only_suggestion["remove_groups"] == ["旧分组"]
        assert group_only_preview["summary"]["add_tags"] == 0
        assert group_only_preview["summary"]["remove_tags"] == 0

        fallback_group_preview = expect_success(
            client.post(
                "/ai/organize/preview",
                json={
                    "filters": {"tag": "待分组"},
                    "organize_tags": False,
                    "organize_groups": True,
                },
                headers=headers,
            ),
            "organize preview group fallback",
        )
        fallback_group_suggestion = fallback_group_preview["suggestions"][0]
        assert fallback_group_suggestion["entry_id"] == dev_entry["id"]
        assert fallback_group_suggestion["add_tags"] == []
        assert fallback_group_suggestion["add_groups"] == ["开发资源"]
        assert fallback_group_suggestion["group_descriptions"]["开发资源"]
        assert fallback_group_preview["summary"]["add_groups"] == 1

        empty_ai_group_preview = expect_success(
            client.post(
                "/ai/organize/preview",
                json={
                    "filters": {"tag": "待自动分组"},
                    "organize_tags": False,
                    "organize_groups": True,
                },
                headers=headers,
            ),
            "organize preview empty ai group fallback",
        )
        empty_ai_group_suggestion = empty_ai_group_preview["suggestions"][0]
        assert empty_ai_group_suggestion["entry_id"] == router_entry["id"]
        assert empty_ai_group_suggestion["add_groups"] == ["家庭设备"]
        assert empty_ai_group_suggestion["group_descriptions"]["家庭设备"]
        assert empty_ai_group_preview["summary"]["add_groups"] == 1

        apply_result = expect_success(
            client.post(
                "/ai/organize/apply",
                json={"suggestions": preview["suggestions"]},
                headers=headers,
            ),
            "organize apply",
        )
        assert apply_result["updated_count"] == 1
        assert apply_result["created_groups"] == ["工作账号"]

        detail = expect_success(client.get(f"/entries/{created['id']}", headers=headers), "entry detail")
        assert set(detail["tags"]) == {"邮箱", "工作"}
        assert detail["groups"] == ["工作账号"]

        groups = expect_success(client.get("/groups", headers=headers), "groups")["groups"]
        work_group = next(group for group in groups if group["name"] == "工作账号")
        assert work_group["description"] == "公司邮箱、协作工具和内部系统"

        print("PASS ai organize")


if __name__ == "__main__":
    main()
