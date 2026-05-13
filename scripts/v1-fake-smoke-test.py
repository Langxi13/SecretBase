import json
import os
import sys
import tempfile
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"

TMP = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
TMP_ROOT = Path(TMP.name)

os.environ["DATA_DIR"] = str(TMP_ROOT)
os.environ["VAULT_PATH"] = str(TMP_ROOT / "secretbase.enc")
os.environ["BACKUP_DIR"] = str(TMP_ROOT / "backups")
os.environ["LOG_DIR"] = str(TMP_ROOT / "logs")
os.environ["SETTINGS_PATH"] = str(TMP_ROOT / "settings.json")

sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
import storage  # noqa: E402
import routes.ai as ai_route  # noqa: E402
from crypto import encrypt_vault  # noqa: E402


PASSWORD = "SecretBase-Test-123456!"
NEW_PASSWORD = "SecretBase-New-Test-123456!"


def expect_json(response, status_code, label):
    if response.status_code != status_code:
        raise AssertionError(f"{label}: expected {status_code}, got {response.status_code}: {response.text}")
    try:
        return response.json()
    except Exception as exc:
        raise AssertionError(f"{label}: response is not JSON: {exc}") from exc


def expect_success(response, label):
    data = expect_json(response, 200, label)
    if data.get("success") is not True:
        raise AssertionError(f"{label}: expected success=true, got {data}")
    return data


def assert_file_response(response, label):
    if response.status_code != 200 or not response.content:
        raise AssertionError(f"{label}: expected file response, got {response.status_code}: {response.text[:200]}")
    return response.content


def use_token(client, result, label):
    token = result["data"].get("token")
    if not token or token == "authenticated":
        raise AssertionError(f"{label}: expected random V2 session token, got {token!r}")
    client.headers.update({"Authorization": f"Bearer {token}"})
    return token


def entry_payload(title, tag, starred=False):
    return {
        "title": title,
        "url": "https://example.com",
        "starred": starred,
        "tags": ["fake", tag],
        "fields": [
            {"name": "username", "value": f"{title.lower()}@example.com", "copyable": False},
            {"name": "password", "value": f"{title}-secret-value", "copyable": True},
        ],
        "remarks": f"Fake smoke-test entry {title}",
    }


def sample_entry_payloads():
    return [
        {
            "title": "示例：云服务器控制台",
            "url": "https://example.invalid/cloud",
            "starred": True,
            "tags": ["示例", "云服务"],
            "fields": [
                {"name": "账号", "value": "demo-cloud-user", "copyable": True},
                {"name": "密码", "value": "Demo-Password-123!", "copyable": True},
            ],
            "remarks": "这是示例数据，可删除。用于体验字段复制、星标和标签筛选。",
        },
        {
            "title": "示例：测试邮箱",
            "url": "https://example.invalid/mail",
            "starred": False,
            "tags": ["示例", "邮箱"],
            "fields": [
                {"name": "邮箱", "value": "demo@example.invalid", "copyable": True},
                {"name": "恢复码", "value": "DEMO-CODE-0000", "copyable": True},
            ],
            "remarks": "这是示例数据，可删除。这里不包含任何真实账号。",
        },
        {
            "title": "示例：本地开发密钥",
            "url": "",
            "starred": False,
            "tags": ["示例", "开发"],
            "fields": [
                {"name": "API Key", "value": "demo_api_key_not_real", "copyable": True},
                {"name": "环境", "value": "local-demo", "copyable": False},
            ],
            "remarks": "这是示例数据，可删除。用于体验备注和自定义字段。",
        },
    ]


class FakeAiResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data or {}

    def json(self):
        return self._data


class FakeAiClient:
    calls = []
    init_options = []

    def __init__(self, timeout=30.0, trust_env=True):
        self.timeout = timeout
        self.trust_env = trust_env
        self.init_options.append({"timeout": timeout, "trust_env": trust_env})

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None):
        self.calls.append({"method": "GET", "url": url, "headers": headers or {}})
        return FakeAiResponse(200, {
            "object": "list",
            "data": [
                {"id": "deepseek-chat"},
                {"id": "gpt-test"},
            ],
        })

    async def post(self, url, headers=None, json=None):
        self.calls.append({"method": "POST", "url": url, "headers": headers or {}, "json": json or {}})
        payload = json or {}
        if payload.get("max_tokens") == 100:
            return FakeAiResponse(200, {
                "choices": [{"message": {"content": "{\"ok\": true}"}}],
            })
        return FakeAiResponse(200, {
            "choices": [{
                "message": {
                    "content": json_module.dumps({
                        "entries": [{
                            "title": "Fake AI Account",
                            "url": "",
                            "fields": [{"name": "password", "value": "from-saved-ai", "copyable": True}],
                            "tags": ["AI"],
                            "remarks": ""
                        }]
                    })
                }
            }]
        })


json_module = json


def run():
    client = TestClient(main.app)

    print("SecretBase fake V1 smoke test")
    expect_success(client.get("/health"), "health")

    status = expect_success(client.get("/auth/status"), "initial auth status")["data"]
    assert status["initialized"] is False
    assert status["locked"] is True

    expect_json(client.get("/settings"), 401, "settings while locked")

    init = expect_success(client.post("/auth/init", json={"password": PASSWORD}), "init")
    init_token = use_token(client, init, "init token")
    client.headers.pop("Authorization", None)
    expect_json(client.get("/settings"), 401, "settings without token after init")
    expect_json(client.get("/settings", headers={"Authorization": "Bearer wrong-token"}), 401, "settings with wrong token")
    client.headers.update({"Authorization": f"Bearer {init_token}"})
    expect_json(client.post("/auth/init", json={"password": PASSWORD}), 409, "init conflict")

    status = expect_success(client.get("/auth/status"), "unlocked auth status")["data"]
    assert status["initialized"] is True
    assert status["locked"] is False
    assert "auto_lock_minutes" in status

    old_token = init_token
    reunlock = expect_success(client.post("/auth/unlock", json={"password": PASSWORD}), "reunlock replaces token")
    new_token = use_token(client, reunlock, "reunlock token")
    assert new_token != old_token
    expect_json(client.get("/settings", headers={"Authorization": f"Bearer {old_token}"}), 401, "old token invalid after reunlock")

    settings = expect_success(client.get("/settings"), "get settings")["data"]
    assert settings["theme"] == "system"
    settings = expect_success(client.put("/settings", json={"theme": "dark", "page_size": 2, "auto_lock_minutes": 1}), "update settings")["data"]
    assert settings["theme"] == "dark"
    assert settings["page_size"] == 2

    ai_status = expect_success(client.get("/ai/status"), "ai status unconfigured")["data"]
    assert ai_status == {"configured": False, "base_url": "", "model": "", "api_key_mask": ""}
    expect_json(client.post("/ai/parse", json={"text": "cannot parse before ai setup"}), 502, "ai parse before configuration")

    original_ai_client = ai_route.httpx.AsyncClient
    ai_route.httpx.AsyncClient = FakeAiClient
    try:
        models = expect_success(
            client.post("/ai/models", json={"baseUrl": "https://api.example.test/v1/", "apiKey": "sk-test-secret"}),
            "ai models"
        )["data"]["models"]
        assert models == ["deepseek-chat", "gpt-test"]
        assert FakeAiClient.init_options[-1]["trust_env"] is False
        assert FakeAiClient.calls[-1]["url"] == "https://api.example.test/v1/models"
        assert FakeAiClient.calls[-1]["headers"]["Authorization"] == "Bearer sk-test-secret"

        saved = expect_success(
            client.put("/ai/settings", json={
                "baseUrl": "https://api.example.test/v1/",
                "apiKey": "sk-test-secret",
                "model": "deepseek-chat",
            }),
            "save ai settings"
        )["data"]
        assert saved == {
            "configured": True,
            "base_url": "https://api.example.test/v1",
            "model": "deepseek-chat",
            "api_key_mask": "sk-...cret",
        }
        assert any(call["method"] == "GET" and call["url"] == "https://api.example.test/v1/models" for call in FakeAiClient.calls)
        assert any(
            call["method"] == "POST"
            and call["url"] == "https://api.example.test/v1/chat/completions"
            and call["json"].get("model") == "deepseek-chat"
            and call["json"].get("max_tokens") == 100
            for call in FakeAiClient.calls
        )
        settings_text = Path(os.environ["SETTINGS_PATH"]).read_text(encoding="utf-8")
        assert "sk-test-secret" not in settings_text
        secure_bytes = Path(ai_route.SECURE_SETTINGS_FILE).read_bytes()
        assert b"sk-test-secret" not in secure_bytes

        ai_status = expect_success(client.get("/ai/status"), "ai status configured")["data"]
        assert ai_status == saved

        models_with_saved_key = expect_success(
            client.post("/ai/models", json={"baseUrl": "https://api.example.test/v1"}),
            "ai models with saved key"
        )["data"]["models"]
        assert models_with_saved_key == ["deepseek-chat", "gpt-test"]

        updated = expect_success(
            client.put("/ai/settings", json={
                "baseUrl": "https://api.example.test/v1",
                "model": "gpt-test",
            }),
            "save ai settings with saved key"
        )["data"]
        assert updated == {
            "configured": True,
            "base_url": "https://api.example.test/v1",
            "model": "gpt-test",
            "api_key_mask": "sk-...cret",
        }
        saved = updated

        parsed = expect_success(client.post("/ai/parse", json={"text": "fake account password unique ai"}), "ai parse configured")["data"]
        assert parsed["parsed"]["title"] == "Fake AI Account"
        assert any(
            call["method"] == "POST"
            and call["url"] == "https://api.example.test/v1/chat/completions"
            and call["headers"]["Authorization"] == "Bearer sk-test-secret"
            and call["json"].get("model") == "gpt-test"
            and call["json"].get("max_tokens") == 3000
            for call in FakeAiClient.calls
        )

        cleared = expect_success(client.delete("/ai/settings"), "clear ai settings")["data"]
        assert cleared == {"configured": False, "base_url": "", "model": "", "api_key_mask": ""}
        expect_json(client.post("/ai/parse", json={"text": "cannot parse after ai setup cleared"}), 502, "ai parse after configuration cleared")

        secure_path = Path(ai_route.SECURE_SETTINGS_FILE)
        secure_path.write_bytes(b"stale local secure settings")
        ai_status = expect_success(client.get("/ai/status"), "ai status with stale secure settings")["data"]
        assert ai_status == {"configured": False, "base_url": "", "model": "", "api_key_mask": ""}
        resaved = expect_success(
            client.put("/ai/settings", json={
                "baseUrl": "https://api.example.test/v1",
                "apiKey": "sk-test-secret",
                "model": "deepseek-chat",
            }),
            "resave ai settings over stale secure settings"
        )["data"]
        assert resaved["configured"] is True
        secure_path.write_bytes(b"stale local secure settings")
        cleared_stale = expect_success(client.delete("/ai/settings"), "clear stale ai settings")["data"]
        assert cleared_stale == {"configured": False, "base_url": "", "model": "", "api_key_mask": ""}
        assert not secure_path.exists()
    finally:
        ai_route.httpx.AsyncClient = original_ai_client

    expect_json(client.post("/entries", json={"title": ""}), 422, "invalid empty title")
    duplicate_fields = entry_payload("Invalid Duplicate", "invalid")
    duplicate_fields["fields"].append({"name": "password", "value": "duplicate", "copyable": True})
    expect_json(client.post("/entries", json=duplicate_fields), 422, "invalid duplicate fields")

    created = expect_success(client.post("/entries", json=entry_payload("Fake Cloud Console", "cloud")), "create entry") ["data"]
    entry_id = created["id"]
    assert {"id", "title", "created_at", "updated_at"}.issubset(created.keys())

    time.sleep(0.01)
    second_payload = entry_payload("Alpha Mail", "mail", starred=True)
    second_payload["tags"].append("zz-shared")
    second = expect_success(client.post("/entries", json=second_payload), "create second entry")["data"]
    time.sleep(0.01)
    third_payload = entry_payload("Zulu Server", "server")
    third_payload["tags"].append("zz-shared")
    third = expect_success(client.post("/entries", json=third_payload), "create third entry")["data"]

    external_content = storage._encrypt_with_current_key(storage.get_vault_data().model_dump_json().encode("utf-8"))
    Path(storage.VAULT_PATH).write_bytes(external_content)
    expect_json(client.post("/entries", json=entry_payload("Conflict Probe", "conflict")), 409, "optimistic lock conflict")
    unlock_after_conflict = expect_success(client.post("/auth/unlock", json={"password": PASSWORD}), "unlock after optimistic conflict")
    use_token(client, unlock_after_conflict, "unlock after conflict token")

    entries = expect_success(client.get("/entries?page_size=2"), "list entries")["data"]
    assert entries["pagination"]["total"] == 3
    assert entries["pagination"]["page_size"] == 2
    assert entries["pagination"]["total_pages"] == 2
    list_all = expect_success(client.get("/entries?page_size=10"), "list all entries")["data"]
    assert [item["title"] for item in list_all["items"]] == ["Zulu Server", "Alpha Mail", "Fake Cloud Console"]
    updated_values = [item["updated_at"] for item in list_all["items"]]
    assert updated_values == sorted(updated_values, reverse=True)
    listed = next(item for item in list_all["items"] if item["id"] == entry_id)
    masked = next(field for field in listed["fields"] if field["name"] == "password")
    visible = next(field for field in listed["fields"] if field["name"] == "username")
    assert masked["value"] == "••••••"
    assert masked["masked"] is True
    assert visible["value"] == "fake cloud console@example.com"
    assert visible["masked"] is False

    detail = expect_success(client.get(f"/entries/{entry_id}"), "entry detail")["data"]
    password_field = next(field for field in detail["fields"] if field["name"] == "password")
    assert password_field["value"] == "Fake Cloud Console-secret-value"

    search = expect_success(client.get("/entries?search=mail"), "search entries")["data"]
    assert search["pagination"]["total"] == 0
    title_scope_search = expect_success(client.get("/entries?search=mail&search_scopes=title"), "title scope search") ["data"]
    assert title_scope_search["pagination"]["total"] == 1
    url_scope_search = expect_success(client.get("/entries?search=mail&search_scopes=url"), "url scope search") ["data"]
    assert url_scope_search["pagination"]["total"] == 0
    field_value_scope_search = expect_success(client.get("/entries?search=example.com&search_scopes=field_values"), "field value scope search") ["data"]
    assert field_value_scope_search["pagination"]["total"] == 3
    empty_scope_search = expect_success(client.get("/entries?search=mail&search_scopes="), "empty scope search") ["data"]
    assert empty_scope_search["pagination"]["total"] == 0
    hidden_secret_search = expect_success(client.get("/entries?search=secret-value"), "hidden copyable value search") ["data"]
    assert hidden_secret_search["pagination"]["total"] == 0
    tag_filter = expect_success(client.get("/entries?tag=server"), "tag filter entries")["data"]
    assert tag_filter["pagination"]["total"] == 1
    starred = expect_success(client.get("/entries?starred=true"), "starred filter entries")["data"]
    assert starred["pagination"]["total"] == 1
    sort_asc = expect_success(client.get("/entries?sort_by=title&sort_order=asc&page_size=10"), "sort asc entries")["data"]
    assert [item["title"] for item in sort_asc["items"]] == ["Alpha Mail", "Fake Cloud Console", "Zulu Server"]
    sort_desc = expect_success(client.get("/entries?sort_by=title&sort_order=desc&page_size=10"), "sort desc entries")["data"]
    assert [item["title"] for item in sort_desc["items"]] == ["Zulu Server", "Fake Cloud Console", "Alpha Mail"]
    search_sort = expect_success(client.get("/entries?search=example.com&search_scopes=field_values&sort_by=title&sort_order=desc&page_size=10"), "search sort desc entries")["data"]
    assert [item["title"] for item in search_sort["items"]] == ["Zulu Server", "Fake Cloud Console", "Alpha Mail"]
    tag_sort = expect_success(client.get("/entries?tag=fake&sort_by=title&sort_order=asc&page_size=10"), "tag sort asc entries")["data"]
    assert [item["title"] for item in tag_sort["items"]] == ["Alpha Mail", "Fake Cloud Console", "Zulu Server"]
    multi_tag = expect_success(client.get("/entries?tags=fake,server&page_size=10"), "multi tag filter")['data']
    assert multi_tag["pagination"]["total"] == 1
    date_filter = expect_success(client.get("/entries?created_from=2000-01-01&updated_to=9999-12-31&page_size=10"), "date range filter")['data']
    assert date_filter["pagination"]["total"] == 3
    has_url = expect_success(client.get("/entries?has_url=true&page_size=10"), "has url filter")['data']
    assert has_url["pagination"]["total"] == 3
    no_url = expect_success(client.get("/entries?has_url=false&page_size=10"), "no url filter")['data']
    assert no_url["pagination"]["total"] == 0
    has_remarks = expect_success(client.get("/entries?has_remarks=true&page_size=10"), "has remarks filter")['data']
    assert has_remarks["pagination"]["total"] == 3
    no_remarks = expect_success(client.get("/entries?has_remarks=false&page_size=10"), "no remarks filter")['data']
    assert no_remarks["pagination"]["total"] == 0
    page_2 = expect_success(client.get("/entries?page=2&page_size=2"), "entries page 2")["data"]
    assert page_2["pagination"]["page"] == 2
    assert len(page_2["items"]) == 1

    updated = expect_success(client.put(f"/entries/{entry_id}", json={"starred": True, "tags": ["fake", "updated"]}), "update entry")["data"]
    assert updated["id"] == entry_id
    starred_sort = expect_success(client.get("/entries?starred=true&sort_by=title&sort_order=desc&page_size=10"), "starred sort desc entries")["data"]
    assert [item["title"] for item in starred_sort["items"]] == ["Fake Cloud Console", "Alpha Mail"]

    tags = expect_success(client.get("/tags"), "tags")["data"]["tags"]
    assert [(tag["name"], tag["count"]) for tag in tags[:2]] == [("fake", 3), ("zz-shared", 2)]
    tag_names = {tag["name"] for tag in tags}
    assert "updated" in tag_names

    expect_success(client.post("/entries/batch-star", json={"ids": [entry_id], "starred": False}), "batch star")
    expect_success(client.post("/entries/batch-update-tags", json={"ids": [entry_id], "add_tags": ["batch"], "remove_tags": ["updated"]}), "batch tags")
    detail = expect_success(client.get(f"/entries/{entry_id}"), "entry detail after batch") ["data"]
    assert detail["starred"] is False
    assert "batch" in detail["tags"] and "updated" not in detail["tags"]

    expect_success(client.put("/tags/batch", json={"new_name": "batch-renamed"}), "rename tag")
    expect_success(client.post("/tags/merge", json={"source_tags": ["fake"], "target_tag": "merged-fake"}), "merge tag")
    expect_success(client.delete("/tags/batch-renamed"), "delete tag")
    detail = expect_success(client.get(f"/entries/{entry_id}"), "entry detail after tag ops") ["data"]
    assert "merged-fake" in detail["tags"] and "fake" not in detail["tags"] and "batch-renamed" not in detail["tags"]

    export_encrypted = assert_file_response(client.post("/export/encrypted"), "export encrypted")
    export_plain_response = client.post("/export/plain", json={"confirm": True})
    export_plain = assert_file_response(export_plain_response, "export plain")
    assert "application/octet-stream" in client.post("/export/encrypted").headers.get("content-type", "")
    assert "application/json" in export_plain_response.headers.get("content-type", "")
    plain_data = json.loads(export_plain.decode("utf-8"))
    assert any(entry["id"] == entry_id for entry in plain_data["entries"])
    expect_json(client.post("/export/plain", json={"confirm": False}), 422, "export plain confirm required")

    backups = expect_success(client.get("/backups"), "list backups")["data"]
    assert backups["total"] >= 1
    assert {"filename", "size", "modified_at"}.issubset(backups["items"][0].keys())
    manual_backup = expect_success(client.post("/backups"), "create manual backup")["data"]
    assert {"filename", "size", "modified_at"}.issubset(manual_backup.keys())
    backup_summary = expect_success(client.get(f"/backups/{manual_backup['filename']}/summary"), "backup summary")["data"]
    assert backup_summary["entry_count"] == 3
    assert backup_summary["filename"] == manual_backup["filename"]

    legacy_backup_content = encrypt_vault(PASSWORD, export_plain)
    legacy_backup_path = Path(storage.BACKUP_DIR) / "secretbase.enc.legacy-test.bak"
    legacy_backup_path.write_bytes(legacy_backup_content)
    legacy_summary_error = expect_json(client.get(f"/backups/{legacy_backup_path.name}/summary"), 422, "legacy backup summary needs password")
    assert legacy_summary_error["error"] == "BACKUP_PASSWORD_REQUIRED"
    assert legacy_summary_error["data"]["needs_password"] is True
    legacy_summary = expect_success(
        client.post(f"/backups/{legacy_backup_path.name}/summary", json={"password": PASSWORD}),
        "legacy backup summary with password"
    )["data"]
    assert legacy_summary["entry_count"] == 3
    legacy_restore_error = expect_json(client.post(f"/backups/{legacy_backup_path.name}/restore", json={}), 422, "legacy restore needs password")
    assert legacy_restore_error["data"]["needs_password"] is True
    legacy_restore = expect_success(
        client.post(f"/backups/{legacy_backup_path.name}/restore", json={"password": PASSWORD}),
        "legacy restore with password"
    )["data"]
    assert legacy_restore["imported_count"] == 3

    preview_files = {"file": ("fake-vault.json", export_plain, "application/json")}
    preview = expect_success(client.post("/import/plain/preview", files=preview_files), "plain import preview")["data"]
    assert preview["total_count"] == 3
    assert preview["conflict_count"] == 3
    assert preview["new_count"] == 0
    assert len(preview["entries"]) == 3
    assert {"id", "title", "is_conflict", "field_count", "tag_count"}.issubset(preview["entries"][0].keys())

    conflict_files = {"file": ("fake-vault.json", export_plain, "application/json")}
    conflict = expect_json(client.post("/import/plain", files=conflict_files, data={"conflict_strategy": "ask"}), 409, "plain import conflict")
    assert conflict["error"] == "CONFLICT"
    assert conflict["data"]["conflicts"]
    first_conflict = conflict["data"]["conflicts"][0]
    assert {"existing_title", "import_title"}.issubset(first_conflict.keys())

    selected_files = {"file": ("fake-vault.json", export_plain, "application/json")}
    selected_import = expect_success(
        client.post(
            "/import/plain",
            files=selected_files,
            data={"conflict_strategy": "skip", "selected_entry_ids": json.dumps([preview["entries"][0]["id"]])}
        ),
        "plain import selected skip"
    )["data"]
    assert selected_import["skipped_count"] == 1
    assert selected_import["created_count"] == 0
    assert selected_import["overwritten_count"] == 0

    overwrite_files = {"file": ("fake-vault.json", export_plain, "application/json")}
    overwrite_import = expect_success(
        client.post(
            "/import/plain",
            files=overwrite_files,
            data={
                "conflict_strategy": "skip",
                "selected_entry_ids": json.dumps([preview["entries"][0]["id"]]),
                "conflict_resolutions": json.dumps({preview["entries"][0]["id"]: "overwrite"}),
            }
        ),
        "plain import selected overwrite"
    )["data"]
    assert overwrite_import["imported_count"] == 1
    assert overwrite_import["overwritten_count"] == 1
    assert overwrite_import["created_count"] == 0

    skip_files = {"file": ("fake-vault.json", export_plain, "application/json")}
    imported = expect_success(client.post("/import/plain", files=skip_files, data={"conflict_strategy": "skip"}), "plain import skip")["data"]
    assert imported["skipped_count"] >= 3

    encrypted_files = {"file": ("fake-vault.enc", export_encrypted, "application/octet-stream")}
    encrypted_import = expect_success(client.post("/import/encrypted", files=encrypted_files), "encrypted import")["data"]
    assert encrypted_import["imported_count"] >= 3

    legacy_files = {"file": ("legacy-vault.enc", legacy_backup_content, "application/octet-stream")}
    legacy_import_error = expect_json(client.post("/import/encrypted", files=legacy_files), 422, "legacy encrypted import needs password")
    assert legacy_import_error["data"]["needs_password"] is True
    legacy_files = {"file": ("legacy-vault.enc", legacy_backup_content, "application/octet-stream")}
    legacy_import = expect_success(client.post("/import/encrypted", files=legacy_files, data={"password": PASSWORD}), "legacy encrypted import with password")["data"]
    assert legacy_import["imported_count"] >= 3

    lock_path = Path(f"{storage.VAULT_PATH}.lock")
    original_lock = storage.VaultFileLock
    class FastVaultFileLock(original_lock):
        def __init__(self, filepath, timeout=0.01):
            super().__init__(filepath, timeout=timeout)
    try:
        lock_path.write_text("stale test lock", encoding="utf-8")
        storage.VaultFileLock = FastVaultFileLock
        locked_response = expect_json(client.post("/entries", json=entry_payload("Lock Timeout Probe", "lock")), 423, "vault lock timeout")
        assert locked_response["error"] == "VAULT_LOCKED"
    finally:
        storage.VaultFileLock = original_lock
        lock_path.unlink(missing_ok=True)

    expect_json(client.post("/entries", json={"title": "Oversized", "fields": [{"name": "blob", "value": "x" * (1024 * 1024), "copyable": False}]}), 413, "request too large")

    expect_success(client.delete(f"/entries/{entry_id}"), "delete entry")
    trash = expect_success(client.get("/trash"), "trash after delete")["data"]
    assert trash["pagination"]["total"] >= 1
    trash_item = next(item for item in trash["items"] if item["id"] == entry_id)
    assert trash_item["deleted_at"] and trash_item["expires_at"]

    restored = expect_success(client.post(f"/trash/{entry_id}/restore"), "restore entry")["data"]
    assert restored["id"] == entry_id
    assert "restored_at" in restored

    expect_success(client.post("/entries/batch-delete", json={"ids": [second["id"]]}), "batch delete")
    trash = expect_success(client.get("/trash"), "trash after batch delete")["data"]
    assert any(item["id"] == second["id"] for item in trash["items"])
    expect_success(client.delete(f"/trash/{second['id']}"), "permanent delete")
    expect_success(client.delete(f"/entries/{third['id']}"), "delete third entry")
    expect_success(client.post("/trash/empty"), "empty trash")
    assert expect_success(client.get("/trash"), "trash after empty")["data"]["pagination"]["total"] == 0

    sample_ids = []
    for payload in sample_entry_payloads():
        sample = expect_success(client.post("/entries", json=payload), f"create sample {payload['title']}")["data"]
        sample_ids.append(sample["id"])
        sample_detail = expect_success(client.get(f"/entries/{sample['id']}"), f"sample detail {payload['title']}")["data"]
        assert "示例" in sample_detail["tags"]
        assert "这是示例数据，可删除" in sample_detail["remarks"]

    samples = expect_success(client.get("/entries?tag=示例&page_size=10"), "sample tag filter")["data"]
    assert samples["pagination"]["total"] == 3
    assert all(item["title"].startswith("示例：") for item in samples["items"])

    health_report = expect_success(client.get("/tools/health-report"), "health report")["data"]
    assert health_report["total_entries"] >= 3
    assert "weak_count" in health_report
    maintenance_report = expect_success(client.get("/tools/maintenance-report"), "maintenance report")["data"]
    assert maintenance_report["sample_count"] == 3
    assert len(maintenance_report["sample_items"]) == 3
    assert "untagged_items" in maintenance_report
    security_report = expect_success(client.get("/tools/security-report"), "security report")["data"]
    assert "checks" in security_report and "summary" in security_report
    assert "vault_path" in security_report["config"]
    expect_success(client.post("/entries/batch-delete", json={"ids": sample_ids}), "delete sample entries")

    expect_json(client.post("/ai/parse", json={"text": "fake account password"}), 502, "ai unconfigured")

    expect_success(client.post("/auth/lock"), "lock")
    expect_json(client.get("/entries"), 401, "entries after lock")
    expect_json(client.get("/tags"), 401, "tags after lock")
    expect_json(client.get("/trash"), 401, "trash after lock")
    expect_json(client.post("/export/encrypted"), 401, "export after lock")
    expect_json(client.get("/backups"), 401, "backups after lock")
    expect_json(client.get("/tools/health-report"), 401, "tools after lock")
    expect_json(client.get("/ai/status"), 401, "ai status after lock")
    expect_json(client.post("/ai/models", json={"baseUrl": "https://api.example.test/v1", "apiKey": "sk-test-secret"}), 401, "ai models after lock")
    expect_json(client.put("/ai/settings", json={"baseUrl": "https://api.example.test/v1", "apiKey": "sk-test-secret", "model": "deepseek-chat"}), 401, "ai settings after lock")
    expect_json(client.post("/ai/parse", json={"text": "fake"}), 401, "ai after lock")

    unlock = expect_success(client.post("/auth/unlock", json={"password": PASSWORD}), "unlock")
    use_token(client, unlock, "unlock token")
    expect_success(client.get("/entries"), "entries after unlock")

    expect_json(client.post("/auth/change-password", json={"old_password": "wrong", "new_password": NEW_PASSWORD}), 401, "change password wrong old")
    expect_success(client.post("/auth/change-password", json={"old_password": PASSWORD, "new_password": NEW_PASSWORD}), "change password")
    expect_success(client.post("/auth/lock"), "lock after password change")
    expect_json(client.post("/auth/unlock", json={"password": PASSWORD}), 401, "old password rejected")
    new_unlock = expect_success(client.post("/auth/unlock", json={"password": NEW_PASSWORD}), "new password unlock")
    use_token(client, new_unlock, "new password unlock token")

    storage._last_activity_at = storage.time.time() - 61
    expect_json(client.get("/entries"), 401, "server auto lock")

    print("fake_v1_smoke_ok")


if __name__ == "__main__":
    try:
        run()
    finally:
        TMP.cleanup()
