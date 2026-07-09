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

        from fastapi.testclient import TestClient  # noqa: E402
        from main import app  # noqa: E402

        client = TestClient(app)
        password = "SecretBase-Test-123456!"
        init_data = expect_success(client.post("/auth/init", json={"password": password}), "init")
        headers = {"X-SecretBase-Token": init_data["token"]}

        first = expect_success(
            client.post(
                "/entries",
                json={
                    "title": "工作邮箱",
                    "url": "",
                    "groups": ["工作账号", "邮箱"],
                    "tags": ["公司"],
                    "fields": [{"name": "账号", "value": "work@example.test", "copyable": True, "hidden": False}],
                    "remarks": "",
                },
                headers=headers,
            ),
            "create first entry",
        )
        second = expect_success(
            client.post(
                "/entries",
                json={
                    "title": "服务器",
                    "url": "",
                    "groups": ["工作账号", "服务器"],
                    "tags": ["生产"],
                    "fields": [{"name": "IP", "value": "192.0.2.10", "copyable": True, "hidden": False}],
                    "remarks": "",
                },
                headers=headers,
            ),
            "create second entry",
        )
        outside = expect_success(
            client.post(
                "/entries",
                json={
                    "title": "代码仓库",
                    "url": "",
                    "groups": ["开发资源"],
                    "tags": ["代码"],
                    "fields": [{"name": "用户名", "value": "developer", "copyable": True, "hidden": False}],
                    "remarks": "",
                },
                headers=headers,
            ),
            "create outside entry",
        )

        expect_success(
            client.post("/groups", json={"name": "工作账号", "description": "公司系统、云平台、协作工具"}, headers=headers),
            "create group",
        )

        groups = expect_success(client.get("/groups", headers=headers), "list groups")["groups"]
        work_group = next(group for group in groups if group["name"] == "工作账号")
        assert work_group["description"] == "公司系统、云平台、协作工具"
        assert work_group["count"] == 2
        assert work_group["updated_at"]
        assert [group["name"] for group in groups[:4]] == ["工作账号", "开发资源", "服务器", "邮箱"]

        ordered_groups = expect_success(
            client.post(
                "/groups/order",
                json={"names": ["邮箱", "服务器", "工作账号", "开发资源"]},
                headers=headers,
            ),
            "save custom group order",
        )["groups"]
        assert [group["name"] for group in ordered_groups[:4]] == ["邮箱", "服务器", "工作账号", "开发资源"]
        assert ordered_groups[0]["order_index"] == 0

        persisted_order = expect_success(client.get("/groups", headers=headers), "list custom ordered groups")["groups"]
        assert [group["name"] for group in persisted_order[:4]] == ["邮箱", "服务器", "工作账号", "开发资源"]

        reset_order = expect_success(
            client.post("/groups/order", json={"names": []}, headers=headers),
            "reset custom group order",
        )["groups"]
        assert [group["name"] for group in reset_order[:4]] == ["工作账号", "开发资源", "服务器", "邮箱"]
        assert all(group["order_index"] is None for group in reset_order[:4])

        filtered = expect_success(client.get("/entries?group=工作账号&page_size=10", headers=headers), "filter group")
        filtered_ids = {entry["id"] for entry in filtered["items"]}
        assert filtered_ids == {first["id"], second["id"]}
        assert all("工作账号" in entry["groups"] for entry in filtered["items"])

        assign_result = expect_success(
            client.post(
                "/groups/工作账号/entries",
                json={"ids": [outside["id"], first["id"]]},
                headers=headers,
            ),
            "assign entries to group",
        )
        assert assign_result["updated_count"] == 1
        assert assign_result["skipped_count"] == 1

        outside_detail = expect_success(client.get(f"/entries/{outside['id']}", headers=headers), "outside detail after assign")
        assert set(outside_detail["groups"]) == {"开发资源", "工作账号"}
        filtered_after_assign = expect_success(client.get("/entries?group=工作账号&page_size=10", headers=headers), "filter group after assign")
        assert filtered_after_assign["pagination"]["total"] == 3

        expect_success(
            client.put("/groups/工作账号", json={"name": "工作", "description": "工作相关密码"}, headers=headers),
            "rename group",
        )
        renamed = expect_success(client.get("/groups", headers=headers), "list renamed groups")["groups"]
        assert any(group["name"] == "工作" and group["description"] == "工作相关密码" for group in renamed)
        assert not any(group["name"] == "工作账号" for group in renamed)

        filtered_after_rename = expect_success(client.get("/entries?group=工作&page_size=10", headers=headers), "filter renamed group")
        assert filtered_after_rename["pagination"]["total"] == 3

        expect_success(client.delete("/groups/工作", headers=headers), "delete group")
        filtered_after_delete = expect_success(client.get("/entries?group=工作&page_size=10", headers=headers), "filter deleted group")
        assert filtered_after_delete["pagination"]["total"] == 0

        print("PASS password groups")


if __name__ == "__main__":
    main()
