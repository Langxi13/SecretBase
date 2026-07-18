"""Run a bounded end-to-end V2 test against a deliberately weak WebDAV server."""

from __future__ import annotations

import base64
import copy
import hashlib
import os
import sys
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlsplit

from test_runtime_support import close_logging_before_temp_cleanup

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


class DavState:
    def __init__(self):
        self.collections = {"/dav"}
        self.objects: dict[str, bytes] = {}
        self.lock = threading.Lock()


STATE = DavState()
AUTH = "Basic " + base64.b64encode(b"tester:app-password").decode("ascii")


class WeakDavHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        return

    def authorized(self) -> bool:
        if self.headers.get("Authorization") == AUTH:
            return True
        self._respond(401)
        return False

    def _respond(self, status: int, content: bytes = b""):
        self.send_response(status)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        if content:
            self.wfile.write(content)

    def do_MKCOL(self):
        if not self.authorized():
            return
        with STATE.lock:
            if self.path in STATE.collections:
                self._respond(405)
                return
            parent = self.path.rstrip("/").rsplit("/", 1)[0] or "/"
            if parent not in STATE.collections:
                self._respond(409)
                return
            STATE.collections.add(self.path.rstrip("/"))
        self._respond(201)

    def do_PUT(self):
        if not self.authorized():
            return
        if self.headers.get("If-Match") or self.headers.get("If-None-Match"):
            self._respond(405)
            return
        length = int(self.headers.get("Content-Length", "0"))
        content = self.rfile.read(length)
        parent = self.path.rsplit("/", 1)[0]
        with STATE.lock:
            if parent not in STATE.collections:
                self._respond(409)
                return
            STATE.objects[self.path] = content
        # Intentionally no ETag header.
        self._respond(201)

    def do_GET(self):
        if not self.authorized():
            return
        with STATE.lock:
            content = STATE.objects.get(self.path)
        if content is None:
            self._respond(404)
            return
        self._respond(200, content)

    def do_DELETE(self):
        if not self.authorized():
            return
        with STATE.lock:
            if self.path in STATE.objects:
                del STATE.objects[self.path]
                self._respond(204)
                return
            if self.path in STATE.collections:
                prefix = self.path.rstrip("/") + "/"
                if any(path.startswith(prefix) for path in STATE.objects) or any(
                    path.startswith(prefix) and path != self.path for path in STATE.collections
                ):
                    self._respond(409)
                    return
                if self.path != "/dav":
                    STATE.collections.remove(self.path)
                self._respond(204)
                return
        self._respond(404)

    def do_PROPFIND(self):
        if not self.authorized():
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)
        with STATE.lock:
            if self.path not in STATE.collections:
                self._respond(404)
                return
            prefix = self.path.rstrip("/") + "/"
            children = []
            for collection in STATE.collections:
                if collection.startswith(prefix) and "/" not in collection[len(prefix):]:
                    children.append((collection, True, 0))
            for path, content in STATE.objects.items():
                if path.startswith(prefix) and "/" not in path[len(prefix):]:
                    children.append((path, False, len(content)))
        rows = [
            f'<d:response><d:href>/dav{quote(path[len("/dav"):])}</d:href>'
            f'<d:propstat><d:prop><d:resourcetype>{"<d:collection/>" if collection else ""}</d:resourcetype>'
            f'<d:getcontentlength>{size}</d:getcontentlength></d:prop></d:propstat></d:response>'
            for path, collection, size in [(self.path, True, 0), *children]
        ]
        body = ('<?xml version="1.0" encoding="utf-8"?><d:multistatus xmlns:d="DAV:">'
                + "".join(rows) + "</d:multistatus>").encode()
        self.send_response(207)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def expect(response, label: str):
    assert response.status_code == 200, f"{label}: {response.status_code} {response.text}"
    payload = response.json()
    assert payload.get("success") is True, f"{label}: {payload}"
    return payload["data"]


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), WeakDavHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    transport_url = f"http://127.0.0.1:{server.server_port}/dav"
    public_url = "https://dav.example.invalid/secretbase"
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
            from fastapi.testclient import TestClient
            from main import app
            import routes.sync as sync_routes
            import sync_runtime

            def local_client(config):
                from sync_webdav import WebDavClient

                return WebDavClient(transport_url, config["username"], config["password"], allow_loopback_http=True)

            def local_test(payload):
                from sync_webdav import WebDavClient

                with WebDavClient(transport_url, payload["username"], payload["password"], allow_loopback_http=True) as dav:
                    return {
                        "base_url": public_url,
                        "host": "dav.example.invalid",
                        "capabilities": dav.test_basic_capabilities(),
                    }

            sync_runtime.client = local_client
            sync_runtime.test_connection_v2 = local_test
            sync_routes.test_connection_v2 = local_test
            client = TestClient(app)
            master = "SecretBase-V2-Test-123!"
            auth = expect(client.post("/auth/init", json={"password": master}), "init")
            headers = {"X-SecretBase-Token": auth["token"]}
            created = expect(client.post("/entries", headers=headers, json={
                "title": "V2 条目",
                "url": "https://example.invalid",
                "tags": [],
                "groups": [],
                "fields": [{"name": "密码", "value": "never-visible-v2", "copyable": True, "hidden": True}],
                "remarks": "",
            }), "entry")
            tested = expect(client.post("/sync/config/test", headers=headers, json={
                "base_url": public_url,
                "username": "tester",
                "password": "app-password",
                "protocol_version": 2,
            }), "capabilities")
            assert tested["capabilities"]["propfind"] is True
            expect(client.post("/sync/create", headers=headers, json={
                "base_url": public_url,
                "username": "tester",
                "password": "app-password",
                "protocol_version": 2,
                "device_name": "设备 A",
            }), "create")
            recovery = expect(client.post("/sync/recovery-code", headers=headers, json={"password": master}), "recovery")
            with STATE.lock:
                assert b"never-visible-v2" not in b"".join(STATE.objects.values())

            detail = expect(client.get(f"/entries/{created['id']}", headers=headers), "detail")
            detail["title"] = "本机修改"
            expect(client.put(f"/entries/{created['id']}", headers=headers, json=detail), "local edit")
            uploaded = expect(client.post("/sync/run", headers=headers), "upload")
            assert uploaded["action"] == "uploaded"
            detail = expect(client.get(f"/entries/{created['id']}", headers=headers), "detail before conflict")
            detail["title"] = "本机再次修改"
            expect(client.put(f"/entries/{created['id']}", headers=headers, json=detail), "local conflict edit")

            from sync_v2_crypto import decode_recovery_code
            from sync_v2_remote import SyncV2Repository

            vault_id, space_id, key = decode_recovery_code(recovery["recovery_code"])
            with local_client({"username": "tester", "password": "app-password"}) as dav:
                other = SyncV2Repository(dav, vault_id=vault_id, space_id=space_id, sync_key=key)
                graph = other.discover()
                current = graph.get(graph.frontier[0])
                remote_document = current.payload["document"]
                remote_document["entries"][0]["title"] = "远端修改"
                other.publish(
                    remote_document,
                    parents=[current.snapshot_id],
                    generation=current.generation + 1,
                    device_id=str(uuid.uuid4()),
                    device_name="设备 B",
                )
            conflict = expect(client.post("/sync/run", headers=headers), "conflict")
            assert conflict["status"]["phase"] == "conflict"
            expect(client.post("/sync/conflicts/resolve", headers=headers, json={
                "conflict_token": conflict["conflict_token"],
                "resolutions": {conflict["conflicts"][0]["conflict_id"]: "both"},
            }), "resolve")
            detail = expect(client.get(f"/entries/{created['id']}", headers=headers), "detail before three-way branches")
            detail["title"] = "本机三分支修改"
            expect(client.put(f"/entries/{created['id']}", headers=headers, json=detail), "three-way local edit")
            with local_client({"username": "tester", "password": "app-password"}) as dav:
                other = SyncV2Repository(dav, vault_id=vault_id, space_id=space_id, sync_key=key)
                graph = other.discover()
                parent = graph.frontier[0]
                parent_snapshot = graph.get(parent)
                for index in range(3):
                    branch_document = copy.deepcopy(parent_snapshot.payload["document"])
                    branch_document["entries"][0]["title"] = f"远端三分支 {index + 1}"
                    other.publish(
                        branch_document,
                        parents=[parent],
                        generation=parent_snapshot.generation + 1,
                        device_id=str(uuid.uuid4()),
                        device_name=f"设备 C{index + 1}",
                    )
            staged = expect(client.post("/sync/run", headers=headers), "three-frontier conflict")
            assert staged["status"]["phase"] == "conflict"
            stage_count = 0
            while staged.get("conflicts"):
                stage_count += 1
                assert stage_count <= 6, "多分支冲突未能在有限步骤内完成"
                staged = expect(client.post("/sync/conflicts/resolve", headers=headers, json={
                    "conflict_token": staged["conflict_token"],
                    "resolutions": {
                        item["conflict_id"]: "remote" for item in staged["conflicts"]
                    },
                }), "resolve staged conflict")
            assert stage_count >= 2, "三分支冲突没有分阶段呈现"
            history = expect(client.get("/sync/history", headers=headers), "history")
            assert history["protocol_version"] == 2
            compacted = expect(client.post("/sync/compact", headers=headers, json={
                "password": master,
                "confirmation": "COMPACT",
            }), "compact")
            assert compacted["snapshot_count"] == 1
            assert compacted["new_space_id"] != compacted["old_space_id"]
            rotated = expect(client.post("/sync/rotate-key", headers=headers, json={"password": master}), "rotate")
            assert rotated["previous_key_invalidated"] is True
            expect(client.post("/sync/reset", headers=headers, json={"password": master, "confirmation": "DELETE"}), "reset")
            print("PASS V2 weak-WebDAV synchronization")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
