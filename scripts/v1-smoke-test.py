import getpass
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import main


def assert_success(response, label):
    if response.status_code >= 400:
        raise AssertionError(f"{label} failed: {response.status_code} {response.text}")
    data = response.json()
    if data.get("success") is not True:
        raise AssertionError(f"{label} failed: {data}")
    return data


def main_test():
    client = TestClient(main.app)
    print("SecretBase V1 real-vault smoke test")

    health = assert_success(client.get("/health"), "health")
    print(f"health: {health['data']['status']}")

    status = assert_success(client.get("/auth/status"), "auth status")["data"]
    print(f"initialized: {status['initialized']}, locked: {status['locked']}")

    if not status["initialized"]:
        raise AssertionError("Real vault is not initialized; aborting real-data smoke test.")

    if status["locked"]:
        password = os.getenv("SECRETBASE_TEST_PASSWORD")
        if not password:
            if os.getenv("SECRETBASE_NO_PROMPT") == "1" or not sys.stdin.isatty():
                raise RuntimeError("Vault is locked and this shell is non-interactive. Set SECRETBASE_TEST_PASSWORD locally or run this script in a terminal.")
            password = getpass.getpass("Master password: ")
        assert_success(client.post("/auth/unlock", json={"password": password}), "unlock")
        print("unlock: ok")

    settings = assert_success(client.get("/settings"), "settings")["data"]
    print(f"settings: theme={settings['theme']}, page_size={settings['page_size']}")

    entries = assert_success(client.get("/entries"), "entries")["data"]
    print(f"entries: total={entries['pagination']['total']}")

    tags = assert_success(client.get("/tags"), "tags")["data"]
    print(f"tags: total={len(tags['tags'])}")

    trash = assert_success(client.get("/trash"), "trash")["data"]
    print(f"trash: total={trash['pagination']['total']}")

    export_encrypted = client.post("/export/encrypted")
    if export_encrypted.status_code != 200 or not export_encrypted.content:
        raise AssertionError(f"encrypted export failed: {export_encrypted.status_code}")
    print(f"export encrypted: {len(export_encrypted.content)} bytes")

    export_plain = client.post("/export/plain", json={"confirm": True})
    if export_plain.status_code != 200 or not export_plain.content:
        raise AssertionError(f"plain export failed: {export_plain.status_code}")
    print(f"export plain: {len(export_plain.content)} bytes")

    if entries["items"]:
        first = entries["items"][0]
        detail = assert_success(client.get(f"/entries/{first['id']}"), "entry detail")["data"]
        print(f"entry detail: {detail['title']}")

    print("V1 real-vault smoke test passed")


if __name__ == "__main__":
    try:
        main_test()
    except Exception as exc:
        print(f"V1 real-vault smoke test failed: {exc}", file=sys.stderr)
        sys.exit(1)
