from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desktop.app import selected_file_path  # noqa: E402
from desktop.bridge import DesktopApi, safe_filename, validate_download_request  # noqa: E402
from desktop.instance import SingleInstanceCoordinator  # noqa: E402


class DownloadHandler(BaseHTTPRequestHandler):
    received_token = None

    def do_POST(self) -> None:  # noqa: N802
        self.__class__.received_token = self.headers.get("X-SecretBase-Token")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"encrypted-test-backup")

    def log_message(self, _format: str, *_args) -> None:
        return


def test_desktop_app_self_test() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        report = root / "self-test.json"
        result = subprocess.run(
            [
                sys.executable,
                "desktop/app.py",
                "--self-test",
                "--data-root",
                str(root / "runtime"),
                "--report",
                str(report),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(report.read_text(encoding="utf-8"))
        assert payload["success"] is True
        assert payload["health"]["status"] == "healthy"
        assert payload["frontend_loaded"] is True


def test_windowed_self_test_without_standard_streams() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        report = root / "self-test.json"
        exit_code = root / "exit-code.txt"
        script = (
            "import sys\n"
            "from pathlib import Path\n"
            "sys.stdout = None\n"
            "sys.stderr = None\n"
            "from desktop.app import run_self_test\n"
            f"code = run_self_test({str(root / 'runtime')!r}, {str(report)!r})\n"
            f"Path({str(exit_code)!r}).write_text(str(code), encoding='ascii')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode == 0
        assert exit_code.read_text(encoding="ascii") == "0"
        payload = json.loads(report.read_text(encoding="utf-8"))
        assert payload["success"] is True
        assert payload["frontend_loaded"] is True


def test_desktop_download_bridge() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), DownloadHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "backup.enc"
            api = DesktopApi(
                f"http://127.0.0.1:{server.server_port}",
                lambda _filename: str(target),
            )
            result = api.save_download({
                "path": "/export/encrypted",
                "method": "POST",
                "body": {},
                "filename": "backup.enc",
                "token": "desktop-test-token",
            })
            assert result == {"status": "saved", "filename": "backup.enc"}
            assert target.read_bytes() == b"encrypted-test-backup"
            assert DownloadHandler.received_token == "desktop-test-token"
    finally:
        server.shutdown()
        server.server_close()


def test_desktop_download_cancel_stops_before_request() -> None:
    class RejectingOpener:
        def open(self, *_args, **_kwargs):
            raise AssertionError("取消保存后不应发起 HTTP 请求")

    api = DesktopApi("http://127.0.0.1:1", lambda _filename: None)
    api.opener = RejectingOpener()
    result = api.save_download({
        "path": "/export/encrypted",
        "method": "POST",
        "filename": "backup.enc",
    })
    assert result == {"status": "cancelled"}


def test_desktop_file_dialog_result_compatibility() -> None:
    assert selected_file_path(r"C:\\Exports\\backup.enc") == r"C:\\Exports\\backup.enc"
    assert selected_file_path((r"C:\\Exports\\backup.enc",)) == r"C:\\Exports\\backup.enc"
    assert selected_file_path([]) is None
    assert selected_file_path(None) is None


def test_desktop_bridge_rejects_unsafe_requests() -> None:
    assert validate_download_request("POST", "/export/plain") == ("POST", "/export/plain")
    assert validate_download_request("GET", "/backups/demo.bak/download/encrypted") == (
        "GET",
        "/backups/demo.bak/download/encrypted",
    )
    for method, path in (("GET", "/settings"), ("POST", "/entries"), ("GET", "/backups/%2Fetc/download/plain")):
        try:
            validate_download_request(method, path)
        except ValueError:
            pass
        else:
            raise AssertionError((method, path))
    assert safe_filename("backup.enc") == "backup.enc"
    for filename in ("../backup.enc", "folder/backup.enc", ""):
        try:
            safe_filename(filename)
        except ValueError:
            pass
        else:
            raise AssertionError(filename)


def test_desktop_external_link_validation() -> None:
    opened = []
    api = DesktopApi("http://127.0.0.1:1", lambda _filename: None, lambda url: not opened.append(url))
    assert api.open_external("https://example.com/path") is True
    assert opened == ["https://example.com/path"]
    for url in ("file:///tmp/test", "javascript:alert(1)", "not-a-url"):
        try:
            api.open_external(url)
        except ValueError:
            pass
        else:
            raise AssertionError(url)


def test_non_windows_single_instance_fallback() -> None:
    coordinator = SingleInstanceCoordinator()
    assert coordinator.acquire() is True
    coordinator.start_listener(lambda: None)
    coordinator.close()


def main() -> None:
    tests = (
        test_desktop_app_self_test,
        test_windowed_self_test_without_standard_streams,
        test_desktop_download_bridge,
        test_desktop_download_cancel_stops_before_request,
        test_desktop_file_dialog_result_compatibility,
        test_desktop_bridge_rejects_unsafe_requests,
        test_desktop_external_link_validation,
        test_non_windows_single_instance_fallback,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
