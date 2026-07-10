import json
import os
import sys
import tempfile
from pathlib import Path

from test_runtime_support import close_logging_before_temp_cleanup

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
    with tempfile.TemporaryDirectory() as tmpdir, close_logging_before_temp_cleanup():
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
            assert "work-password" not in serialized
            assert "glpat-secret" not in serialized
            assert "value" not in serialized
            mail_entry = next(entry for entry in user_payload["entries"] if entry["title"] == "公司邮箱")
            dev_entry = next(entry for entry in user_payload["entries"] if entry["title"] == "项目 GitLab")
            return json.dumps(
                {
                    "suggestions": [
                        {
                            "action": "create_tag",
                            "tag": "开发资源",
                            "description": "代码仓库、开发平台和令牌类账号",
                            "color": "#7c3aed",
                            "entry_ids": [dev_entry["id"]],
                            "reason": "字段名和网址显示这是开发平台账号",
                        },
                        {
                            "action": "update_tag",
                            "tag": "工作",
                            "new_tag": "工作账号",
                            "description": "公司邮箱、协作工具和内部系统",
                            "color": "#2563eb",
                            "reason": "标签命名更明确",
                        },
                        {
                            "action": "merge_tags",
                            "source_tags": ["git", "代码"],
                            "target_tag": "代码仓库",
                            "description": "代码托管和版本管理账号",
                            "color": "#0891b2",
                            "reason": "两个标签语义高度相近",
                        },
                        {
                            "action": "delete_tag",
                            "tag": "待整理",
                            "reason": "整理后不再需要临时标签",
                        },
                        {
                            "action": "assign_tag",
                            "tag": "邮箱",
                            "entry_ids": [mail_entry["id"]],
                            "reason": "标题显示这是邮箱条目",
                        },
                    ],
                    "warnings": ["请逐项确认后再应用"],
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

        mail = expect_success(
            client.post(
                "/entries",
                json={
                    "title": "公司邮箱",
                    "url": "https://mail.example.test",
                    "tags": ["工作", "待整理"],
                    "fields": [
                        {"name": "账号", "value": "work@example.test", "copyable": True, "hidden": False},
                        {"name": "密码", "value": "work-password", "copyable": True, "hidden": True},
                    ],
                    "remarks": "公司邮箱登录",
                },
                headers=headers,
            ),
            "create mail entry",
        )
        dev = expect_success(
            client.post(
                "/entries",
                json={
                    "title": "项目 GitLab",
                    "url": "https://gitlab.example.test",
                    "tags": ["git", "代码"],
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

        preview = expect_success(
            client.post(
                "/ai/tags/preview",
                json={"user_prompt": "本次优先合并语义重复标签，不要删除高频标签"},
                headers=headers,
            ),
            "tag governance preview",
        )
        assert captured_payloads, "AI 标签治理必须调用模型生成建议"
        assert captured_payloads[-1]["user_prompt"] == "本次优先合并语义重复标签，不要删除高频标签"
        assert preview["entry_count"] == 2
        assert preview["summary"]["total_actions"] == 5
        assert preview["suggestions"][0]["selected"] is True
        assert {item["action"] for item in preview["suggestions"]} == {
            "create_tag",
            "update_tag",
            "merge_tags",
            "delete_tag",
            "assign_tag",
        }
        assert "不会发送任何字段值" in preview["privacy_note"]

        apply_result = expect_success(
            client.post("/ai/tags/apply", json={"suggestions": preview["suggestions"]}, headers=headers),
            "tag governance apply",
        )
        assert apply_result["applied_count"] == 5
        assert apply_result["updated_entries"] == 2

        mail_detail = expect_success(client.get(f"/entries/{mail['id']}", headers=headers), "mail detail after apply")
        dev_detail = expect_success(client.get(f"/entries/{dev['id']}", headers=headers), "dev detail after apply")
        assert set(mail_detail["tags"]) == {"工作账号", "邮箱"}
        assert set(dev_detail["tags"]) == {"代码仓库", "开发资源"}

        tags = expect_success(client.get("/tags", headers=headers), "tags after governance")["tags"]
        tags_by_name = {tag["name"]: tag for tag in tags}
        assert tags_by_name["开发资源"]["description"] == "代码仓库、开发平台和令牌类账号"
        assert tags_by_name["工作账号"]["description"] == "公司邮箱、协作工具和内部系统"
        assert tags_by_name["代码仓库"]["description"] == "代码托管和版本管理账号"
        assert "待整理" not in tags_by_name
        assert "git" not in tags_by_name
        assert "代码" not in tags_by_name

        stale_update = expect_success(
            client.post(
                "/ai/tags/apply",
                json={
                    "suggestions": [
                        {
                            "action": "update_tag",
                            "tag": "不存在的旧标签",
                            "new_tag": "不应被创建",
                            "description": "过期建议不应创建新标签",
                        }
                    ]
                },
                headers=headers,
            ),
            "stale tag update must not create a tag",
        )
        assert stale_update["applied_count"] == 0
        tags_after_stale_update = expect_success(client.get("/tags", headers=headers), "tags after stale update")["tags"]
        assert "不应被创建" not in {tag["name"] for tag in tags_after_stale_update}

        for index in range(99):
            expect_success(
                client.post(
                    "/entries",
                    json={
                        "title": f"批量条目 {index}",
                        "tags": ["批量"],
                        "fields": [{"name": "账号", "value": f"user{index}", "copyable": True, "hidden": False}],
                        "remarks": "",
                    },
                    headers=headers,
                ),
                f"create bulk entry {index}",
            )
        too_many = expect_error(client.post("/ai/tags/preview", json={}, headers=headers), 413, "tag governance max entries")
        assert "最多支持 100 条" in too_many["message"]

        print("PASS ai tag governance")


if __name__ == "__main__":
    main()
