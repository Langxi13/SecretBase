from __future__ import annotations

import base64
import hashlib
import os
import sys
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from test_runtime_support import close_logging_before_temp_cleanup


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


class DavState:
    def __init__(self):
        self.collections = {"/dav"}
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.lock = threading.Lock()

    def etag(self, content: bytes) -> str:
        return f'"{hashlib.sha256(content).hexdigest()}"'


STATE = DavState()
AUTH = "Basic " + base64.b64encode(b"tester:app-password").decode("ascii")


class DavHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        return

    def _authorized(self) -> bool:
        if self.headers.get("Authorization") == AUTH:
            return True
        self.send_response(401)
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def _finish(self, status: int, content: bytes = b"", etag: str | None = None):
        self.send_response(status)
        if etag:
            self.send_header("ETag", etag)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        if content:
            self.wfile.write(content)

    def do_MKCOL(self):
        if not self._authorized():
            return
        with STATE.lock:
            if self.path in STATE.collections:
                self._finish(405)
                return
            parent = self.path.rsplit("/", 1)[0] or "/"
            if parent not in STATE.collections:
                self._finish(409)
                return
            STATE.collections.add(self.path)
        self._finish(201)

    def do_GET(self):
        if not self._authorized():
            return
        with STATE.lock:
            stored = STATE.objects.get(self.path)
        if stored is None:
            self._finish(404)
            return
        self._finish(200, stored[0], stored[1])

    def do_PUT(self):
        if not self._authorized():
            return
        length = int(self.headers.get("Content-Length", "0"))
        content = self.rfile.read(length)
        with STATE.lock:
            current = STATE.objects.get(self.path)
            if self.headers.get("If-None-Match") == "*" and current is not None:
                self._finish(412)
                return
            if self.headers.get("If-Match") and (
                current is None or current[1] != self.headers["If-Match"]
            ):
                self._finish(412)
                return
            etag = STATE.etag(content + uuid.uuid4().bytes)
            STATE.objects[self.path] = (content, etag)
        self._finish(204 if current else 201, etag=etag)

    def do_DELETE(self):
        if not self._authorized():
            return
        with STATE.lock:
            if self.path in STATE.objects:
                if self.headers.get("If-Match") and STATE.objects[self.path][1] != self.headers["If-Match"]:
                    self._finish(412)
                    return
                del STATE.objects[self.path]
                self._finish(204)
                return
            if self.path in STATE.collections:
                prefix = self.path.rstrip("/") + "/"
                if any(path.startswith(prefix) for path in set(STATE.objects) | STATE.collections):
                    self._finish(409)
                    return
                STATE.collections.remove(self.path)
                self._finish(204)
                return
        self._finish(404)


def expect(response, label: str):
    assert response.status_code == 200, f"{label}: {response.status_code} {response.text}"
    payload = response.json()
    assert payload["success"] is True, f"{label}: {payload}"
    return payload["data"]


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), DavHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    transport_base_url = f"http://127.0.0.1:{server.server_port}/dav"
    base_url = "https://dav.example.invalid/secretbase"

    try:
        with tempfile.TemporaryDirectory() as raw, close_logging_before_temp_cleanup():
            root = Path(raw)
            os.environ.update({
                "DATA_DIR": str(root / "data"),
                "BACKUP_DIR": str(root / "data" / "backups"),
                "LOG_DIR": str(root / "logs"),
                "SETTINGS_PATH": str(root / "data" / "settings.json"),
                "VAULT_PATH": str(root / "data" / "secretbase.enc"),
            })

            from sync_crypto import decode_recovery_code
            from sync_remote import SyncRepository
            from sync_webdav import WebDavClient, normalize_webdav_url
            import sync_runtime

            def local_webdav_client(config):
                return WebDavClient(
                    transport_base_url,
                    config["username"],
                    config["password"],
                    allow_loopback_http=True,
                )

            def local_test_connection(payload):
                normalized = normalize_webdav_url(payload.get("base_url", ""))
                with WebDavClient(
                    transport_base_url,
                    payload.get("username", ""),
                    payload.get("password", ""),
                    allow_loopback_http=True,
                ) as webdav:
                    capabilities = webdav.test_capabilities()
                return {
                    "base_url": normalized,
                    "host": urlsplit(normalized).hostname or "",
                    "capabilities": capabilities,
                }

            sync_runtime.client = local_webdav_client
            sync_runtime.test_connection = local_test_connection

            from fastapi.testclient import TestClient
            from main import app
            import sync_management

            client = TestClient(app)
            master = "SecretBase-Sync-Test-123!"
            auth = expect(client.post("/auth/init", json={"password": master}), "init")
            headers = {"X-SecretBase-Token": auth["token"]}
            wrong_auth = client.post(
                "/sync/config/test",
                headers=headers,
                json={
                    "base_url": base_url,
                    "username": "tester",
                    "password": "wrong-password",
                    "device_name": "测试设备一",
                    "auto_sync": True,
                },
            )
            assert wrong_auth.status_code == 502, wrong_auth.text
            assert wrong_auth.json()["error"] == "WEBDAV_AUTH_FAILED"
            created_entry = expect(
                client.post(
                    "/entries",
                    headers=headers,
                    json={
                        "title": "同步测试条目",
                        "url": "https://example.test",
                        "tags": ["同步"],
                        "groups": ["测试"],
                        "fields": [{
                            "name": "密码",
                            "value": "never-visible-on-webdav",
                            "copyable": True,
                            "hidden": True,
                        }],
                        "remarks": "",
                    },
                ),
                "create entry",
            )
            create_result = expect(
                client.post(
                    "/sync/create",
                    headers=headers,
                    json={
                        "base_url": base_url,
                        "username": "tester",
                        "password": "app-password",
                        "device_name": "测试设备一",
                        "auto_sync": True,
                    },
                ),
                "create sync",
            )
            assert create_result["status"]["configured"] is True
            assert "recovery_code" not in create_result
            with patch.object(sync_management, "client", side_effect=AssertionError("偏好保存不应访问 WebDAV")):
                disabled_auto = expect(
                    client.put("/sync/config", headers=headers, json={"auto_sync": False}),
                    "disable auto sync locally",
                )
                assert disabled_auto["auto_sync"] is False
                enabled_auto = expect(
                    client.put("/sync/config", headers=headers, json={"auto_sync": True}),
                    "enable auto sync locally",
                )
                assert enabled_auto["auto_sync"] is True
            with STATE.lock:
                assert all("probe-" not in path for path in STATE.objects)
                assert len([path for path in STATE.collections if path.count("/") >= 3]) == 2
            recovery = expect(
                client.post("/sync/recovery-code", headers=headers, json={"password": master}),
                "reveal recovery",
            )
            assert recovery["recovery_code"].startswith("SBSYNC1-")
            assert recovery["qr_data_uri"].startswith("data:image/svg+xml;base64,")
            with STATE.lock:
                remote_bytes = b"".join(content for content, _ in STATE.objects.values())
            assert b"never-visible-on-webdav" not in remote_bytes

            detail = expect(client.get(f"/entries/{created_entry['id']}", headers=headers), "entry detail")
            detail["title"] = "本机修改"
            expect(client.put(f"/entries/{created_entry['id']}", headers=headers, json=detail), "local edit")

            vault_id, sync_key = decode_recovery_code(recovery["recovery_code"])
            with WebDavClient(transport_base_url, "tester", "app-password", allow_loopback_http=True) as dav:
                repository = SyncRepository(dav, vault_id=vault_id, sync_key=sync_key)
                head, snapshot = repository.current()
                remote_document = snapshot["document"]
                remote_document["entries"][0]["title"] = "远端修改"
                repository.publish(
                    remote_document,
                    current_head=head,
                    device_id=str(uuid.uuid4()),
                    device_name="测试设备二",
                )

            conflict_result = expect(client.post("/sync/run", headers=headers), "run with conflict")
            assert conflict_result["status"]["phase"] == "conflict"
            assert conflict_result["conflicts"][0]["label"] == "本机修改"
            token = conflict_result["conflict_token"]
            conflict_id = conflict_result["conflicts"][0]["conflict_id"]
            expect(
                client.post(
                    "/sync/conflicts/resolve",
                    headers=headers,
                    json={"conflict_token": token, "resolutions": {conflict_id: "both"}},
                ),
                "resolve conflict",
            )
            entries = expect(client.get("/entries?page_size=10", headers=headers), "list entries")
            titles = {item["title"] for item in entries["items"]}
            assert "远端修改" in titles
            assert "本机修改（本机冲突副本）" in titles

            history = expect(client.get("/sync/history", headers=headers), "history")
            assert 2 <= len(history["items"]) <= 10
            invalid_master = client.post(
                "/sync/recovery-code",
                headers=headers,
                json={"password": "wrong-master"},
            )
            assert invalid_master.status_code == 422

            new_master = "SecretBase-Sync-New-456!"
            expect(
                client.post(
                    "/auth/change-password",
                    headers=headers,
                    json={"old_password": master, "new_password": new_master},
                ),
                "change master password",
            )
            password_status = expect(client.get("/sync/status", headers=headers), "status after password change")
            assert password_status["configured"] is True
            expect(client.get("/sync/history", headers=headers), "history after password change")
            migrated_recovery = expect(
                client.post("/sync/recovery-code", headers=headers, json={"password": new_master}),
                "recovery after password change",
            )
            assert migrated_recovery["recovery_code"] == recovery["recovery_code"]

            rotated = expect(
                client.post("/sync/rotate-key", headers=headers, json={"password": new_master}),
                "rotate sync key",
            )
            assert rotated["previous_key_invalidated"] is True
            assert rotated["recovery_code"] != recovery["recovery_code"]
            rotated_history = expect(client.get("/sync/history", headers=headers), "history after rotation")
            assert len(rotated_history["items"]) == 1
            with WebDavClient(transport_base_url, "tester", "app-password", allow_loopback_http=True) as dav:
                old_repository = SyncRepository(dav, vault_id=vault_id, sync_key=sync_key)
                try:
                    old_repository.load_head()
                except Exception:
                    pass
                else:
                    raise AssertionError("旧同步密钥在轮换后必须失效")

            from crypto import encrypt_vault
            from models import VaultData
            from vault_document import encode_vault_document

            replacement = VaultData(vault_id=str(uuid.uuid4()))
            replacement_bytes = encrypt_vault(new_master, encode_vault_document(replacement))
            expect(
                client.post(
                    "/import/encrypted",
                    headers=headers,
                    files={"file": ("replacement.enc", replacement_bytes, "application/octet-stream")},
                    data={"password": new_master},
                ),
                "import different vault",
            )
            imported_status = expect(client.get("/sync/status", headers=headers), "status after vault replacement")
            assert imported_status["configured"] is False
            failed_join = client.post(
                "/sync/join",
                headers=headers,
                json={
                    "base_url": base_url,
                    "username": "tester",
                    "password": "wrong-password",
                    "device_name": "失败加入测试",
                    "auto_sync": True,
                    "recovery_code": rotated["recovery_code"],
                    "merge_existing": False,
                },
            )
            assert failed_join.status_code == 502
            failed_join_status = expect(client.get("/sync/status", headers=headers), "status after failed join")
            assert failed_join_status["configured"] is False

            rotated_vault_id, rotated_key = decode_recovery_code(rotated["recovery_code"])
            with WebDavClient(transport_base_url, "tester", "app-password", allow_loopback_http=True) as dav:
                SyncRepository(dav, vault_id=rotated_vault_id, sync_key=rotated_key).delete_remote()
            remote_prefix = f"/dav/secretbase-sync-v1/{rotated_vault_id}"
            with STATE.lock:
                assert not any(path == remote_prefix or path.startswith(remote_prefix + "/") for path in STATE.collections)
                assert not any(path.startswith(remote_prefix + "/") for path in STATE.objects)
            print("PASS encrypted WebDAV synchronization")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
