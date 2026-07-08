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
        from main import app  # noqa: E402

        client = TestClient(app)
        password = "SecretBase-Test-123456!"
        init_data = expect_success(client.post("/auth/init", json={"password": password}), "init")
        headers = {"X-SecretBase-Token": init_data["token"]}

        empty_tag = expect_success(
            client.post(
                "/tags",
                json={"name": "云服务", "description": "云平台和控制台账号", "color": "#2563eb"},
                headers=headers,
            ),
            "create empty tag",
        )
        assert empty_tag["name"] == "云服务"

        tags = expect_success(client.get("/tags", headers=headers), "list empty tags")["tags"]
        cloud = next(tag for tag in tags if tag["name"] == "云服务")
        assert cloud["description"] == "云平台和控制台账号"
        assert cloud["color"] == "#2563eb"
        assert cloud["count"] == 0

        entry = expect_success(
            client.post(
                "/entries",
                json={
                    "title": "生产控制台",
                    "url": "https://console.example.test",
                    "tags": ["云服务", "待整理"],
                    "fields": [{"name": "账号", "value": "ops@example.test", "copyable": True, "hidden": False}],
                    "remarks": "",
                },
                headers=headers,
            ),
            "create tagged entry",
        )

        updated = expect_success(
            client.put(
                "/tags/云服务",
                json={"name": "云平台", "description": "云平台、控制台和资源管理账号", "color": "#16a34a"},
                headers=headers,
            ),
            "update tag meta and name",
        )
        assert updated["old_name"] == "云服务"
        assert updated["new_name"] == "云平台"

        detail = expect_success(client.get(f"/entries/{entry['id']}", headers=headers), "entry after tag rename")
        assert "云平台" in detail["tags"]
        assert "云服务" not in detail["tags"]

        tags_after_update = expect_success(client.get("/tags", headers=headers), "list updated tags")["tags"]
        cloud_platform = next(tag for tag in tags_after_update if tag["name"] == "云平台")
        assert cloud_platform["description"] == "云平台、控制台和资源管理账号"
        assert cloud_platform["color"] == "#16a34a"
        assert cloud_platform["count"] == 1

        expect_success(
            client.post(
                "/tags/merge",
                json={"source_tags": ["待整理"], "target_tag": "待办", "description": "需要继续整理的条目", "color": "#f97316"},
                headers=headers,
            ),
            "merge tag with metadata",
        )
        merged_tags = expect_success(client.get("/tags", headers=headers), "list merged tags")["tags"]
        todo = next(tag for tag in merged_tags if tag["name"] == "待办")
        assert todo["description"] == "需要继续整理的条目"
        assert todo["color"] == "#f97316"
        assert todo["count"] == 1
        assert not any(tag["name"] == "待整理" for tag in merged_tags)

        expect_success(client.delete("/tags/待办", headers=headers), "delete bound tag")
        expect_success(client.delete("/tags/云平台", headers=headers), "delete empty-capable tag")
        final_detail = expect_success(client.get(f"/entries/{entry['id']}", headers=headers), "entry after tag delete")
        assert final_detail["tags"] == []

        batch_entry = expect_success(
            client.post(
                "/entries",
                json={
                    "title": "批量标签条目",
                    "url": "https://batch-tags.example.test",
                    "tags": ["临时标签A", "临时标签B", "保留标签"],
                    "fields": [{"name": "账号", "value": "batch@example.test", "copyable": True, "hidden": False}],
                    "remarks": "",
                },
                headers=headers,
            ),
            "create batch tagged entry",
        )
        batch_deleted = expect_success(
            client.post(
                "/tags/batch-delete",
                json={"names": ["临时标签A", "临时标签B", "不存在标签", "临时标签A"]},
                headers=headers,
            ),
            "batch delete tags",
        )
        assert batch_deleted["deleted_tags"] == ["临时标签A", "临时标签B"]
        assert batch_deleted["missing_tags"] == ["不存在标签"]
        assert batch_deleted["affected_count"] == 1
        batch_detail = expect_success(client.get(f"/entries/{batch_entry['id']}", headers=headers), "entry after batch tag delete")
        assert batch_detail["tags"] == ["保留标签"]

        expect_success(
            client.post("/tags", json={"name": "空标签", "description": "", "color": "#64748b"}, headers=headers),
            "create standalone tag",
        )
        expect_success(client.delete("/tags/空标签", headers=headers), "delete standalone tag")
        final_tags = expect_success(client.get("/tags", headers=headers), "list final tags")["tags"]
        assert not any(tag["name"] == "空标签" for tag in final_tags)

        print("PASS tag entities")


if __name__ == "__main__":
    main()
