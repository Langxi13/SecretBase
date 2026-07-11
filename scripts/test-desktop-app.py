from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desktop.app import desktop_window_failure, run_shutdown_wait_self_test, selected_file_path  # noqa: E402
from desktop.bridge import DesktopApi, safe_filename, validate_download_request  # noqa: E402
from desktop.diagnostics import DesktopDiagnostics, detect_package_type  # noqa: E402
import desktop.instance as desktop_instance  # noqa: E402
from desktop.instance import SingleInstanceCoordinator, request_existing_process_exit  # noqa: E402
from desktop.runtime import desktop_paths, prepare_data_root  # noqa: E402
from desktop.tray import DesktopLifecycle, load_close_to_tray  # noqa: E402
from desktop.update import check_for_updates, parse_version, validate_release_url  # noqa: E402


class DownloadHandler(BaseHTTPRequestHandler):
    received_token = None

    def do_POST(self) -> None:  # noqa: N802
        self.__class__.received_token = self.headers.get("X-SecretBase-Token")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"encrypted-test-backup")

    def log_message(self, _format: str, *_args) -> None:
        return


class JsonResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, _limit: int | None = None) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class StaticOpener:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.requests = []

    def open(self, request, timeout: float):
        self.requests.append((request, timeout))
        return JsonResponse(self.payload)


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


def test_desktop_runtime_error_does_not_mislabel_webview2() -> None:
    message, offer_webview2 = desktop_window_failure(
        RuntimeError("Failed to resolve Python.Runtime.Loader.Initialize from Python.Runtime.dll")
    )
    assert offer_webview2 is False
    assert "桌面运行组件无法加载" in message
    assert "解除锁定" in message

    generic_message, generic_offer = desktop_window_failure(RuntimeError("WebView2 runtime unavailable"))
    assert generic_offer is True
    assert "WebView2 官方下载页面" in generic_message


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


def test_desktop_diagnostics_and_directory_allowlist() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        paths = prepare_data_root(root, include_webview=True)
        opened = []
        diagnostics = DesktopDiagnostics(
            paths=paths,
            backend_url="http://127.0.0.1:12345",
            version="3.2.0",
            renderer="edgechromium",
            backend_running=lambda: True,
            directory_opener=lambda path: opened.append(path),
        )
        diagnostics.health_opener = StaticOpener({
            "success": True,
            "data": {"status": "healthy", "version": "3.2.0"},
        })

        result = diagnostics.collect()
        assert result["status"] == "ok"
        assert result["package_type"] == "source"
        assert detect_package_type() == "source"
        assert str(paths.root) not in result["support_summary"]
        assert result["directories"]["data"]["path"] == str(paths.root)

        with patch(
            "desktop.diagnostics.tempfile.NamedTemporaryFile",
            side_effect=PermissionError(13, "Permission denied", str(paths.root)),
        ):
            failed = diagnostics.collect()
        assert failed["status"] == "error"
        assert str(paths.root) not in failed["support_summary"]
        assert "系统错误 13" in failed["support_summary"]

        assert diagnostics.open_directory("logs") == {"status": "opened", "kind": "logs"}
        assert opened == [paths.logs]
        try:
            diagnostics.open_directory("../private")
        except ValueError:
            pass
        else:
            raise AssertionError("Desktop directory bridge must reject arbitrary paths")


def test_desktop_update_check_validation() -> None:
    assert parse_version("v3.2.0") == (3, 2, 0)
    release_url = "https://github.com/Langxi13/SecretBase/releases/tag/v3.2.0"
    assert validate_release_url(release_url) == release_url
    opener = StaticOpener({
        "tag_name": "v3.2.0",
        "html_url": release_url,
        "draft": False,
        "prerelease": False,
        "published_at": "2026-07-11T00:00:00Z",
    })
    available = check_for_updates("3.1.0", opener=opener)
    assert available["status"] == "available"
    assert available["latest_version"] == "3.2.0"
    current = check_for_updates("3.2.0", opener=opener)
    assert current["status"] == "up_to_date"

    unsafe = StaticOpener({
        "tag_name": "v9.0.0",
        "html_url": "https://example.com/download",
        "draft": False,
        "prerelease": False,
    })
    assert check_for_updates("3.2.0", opener=unsafe)["status"] == "error"


def test_desktop_bridge_productization_methods() -> None:
    tray_values = []
    api = DesktopApi(
        "http://127.0.0.1:1",
        lambda _filename: None,
        diagnostics_provider=lambda: {"status": "ok"},
        directory_opener=lambda kind: {"status": "opened", "kind": kind},
        update_checker=lambda: {"status": "up_to_date"},
        tray_setter=lambda enabled: not tray_values.append(enabled),
    )
    assert api.get_diagnostics() == {"status": "ok"}
    assert api.open_directory("data") == {"status": "opened", "kind": "data"}
    assert api.check_for_updates() == {"status": "up_to_date"}
    assert api.set_close_to_tray(True) == {"status": "updated", "enabled": True}
    assert tray_values == [True]


def test_desktop_lifecycle_locks_before_hiding() -> None:
    events = []

    class FakeServer:
        url = "http://127.0.0.1:12345"

        def __init__(self) -> None:
            self.lock_count = 0

        def lock_vault(self) -> None:
            self.lock_count += 1
            events.append("backend-lock")

    class FakeWindow:
        def __init__(self) -> None:
            self.hidden = False
            self.destroyed = False
            self.loaded_urls = []
            self.evaluated_scripts = []
            self.shown = 0
            self.restored = 0

        def hide(self) -> None:
            self.hidden = True
            events.append("hide")

        def evaluate_js(self, script: str) -> bool:
            self.evaluated_scripts.append(script)
            events.append("frontend-lock")
            return True

        def load_url(self, url: str) -> None:
            self.loaded_urls.append(url)

        def show(self) -> None:
            self.shown += 1
            self.hidden = False

        def restore(self) -> None:
            self.restored += 1

        def destroy(self) -> None:
            self.destroyed = True

    class FakeTray:
        def __init__(self, _path, **callbacks) -> None:
            self.callbacks = callbacks
            self.running = False
            self.stopped = 0

        def start(self) -> bool:
            self.running = True
            return True

        def stop(self) -> None:
            self.running = False
            self.stopped += 1

    server = FakeServer()
    window = FakeWindow()
    lifecycle = DesktopLifecycle(server, Path("icon.ico"), tray_factory=FakeTray)
    lifecycle.attach_window(window)
    assert lifecycle.set_close_to_tray(True) is True
    assert lifecycle.on_closing() is False
    assert server.lock_count == 1
    assert window.hidden is True
    assert events[:3] == ["backend-lock", "frontend-lock", "hide"]
    assert "secretbase:desktop-lock" in window.evaluated_scripts[0]
    assert window.loaded_urls == []

    lifecycle.restore()
    assert window.hidden is False
    assert window.shown == 1
    assert window.restored == 1
    assert len(window.evaluated_scripts) == 2
    assert window.loaded_urls == []

    lifecycle.lock()
    assert server.lock_count == 2
    assert len(window.evaluated_scripts) == 3
    assert window.loaded_urls == []

    lifecycle.exit()
    assert server.lock_count == 3
    assert window.destroyed is True
    assert lifecycle.tray.stopped >= 1


def test_close_to_tray_preference_defaults_safely() -> None:
    with tempfile.TemporaryDirectory() as raw:
        settings = Path(raw) / "settings.json"
        assert load_close_to_tray(settings) is False
        settings.write_text('{"close_to_tray": true}', encoding="utf-8")
        assert load_close_to_tray(settings) is True
        settings.write_text('{"close_to_tray": "true"}', encoding="utf-8")
        assert load_close_to_tray(settings) is False


def test_shutdown_wait_self_test_protocol() -> None:
    class FakeCoordinator:
        def acquire(self) -> bool:
            return True

        def start_listener(self, _activate_callback, exit_callback) -> None:
            exit_callback()

        def close(self) -> None:
            return None

    with tempfile.TemporaryDirectory() as raw:
        report = Path(raw) / "shutdown-report.json"
        with patch("desktop.app.SingleInstanceCoordinator", FakeCoordinator):
            assert run_shutdown_wait_self_test(str(report), timeout=0.1) == 0
        payload = json.loads(report.read_text(encoding="utf-8"))
        assert payload == {"success": True, "mode": "shutdown-wait", "ready": True}


def test_existing_process_exit_protocol_handles_windows_races() -> None:
    with (
        patch.object(desktop_instance.os, "name", "nt"),
        patch.object(desktop_instance, "_named_mutex_exists", side_effect=[True, True, False]),
        patch.object(desktop_instance, "_signal_named_event", return_value=True) as signal,
        patch.object(desktop_instance.time, "sleep"),
    ):
        assert request_existing_process_exit(timeout=0.1) is True
        signal.assert_called_once_with(desktop_instance.DEFAULT_EXIT_EVENT_NAME)

    with (
        patch.object(desktop_instance.os, "name", "nt"),
        patch.object(desktop_instance, "_named_mutex_exists", side_effect=[True, False]),
        patch.object(desktop_instance, "_signal_named_event", return_value=False),
    ):
        assert request_existing_process_exit(timeout=0.1) is True

    with (
        patch.object(desktop_instance.os, "name", "nt"),
        patch.object(desktop_instance, "_named_mutex_exists", side_effect=[True, True]),
        patch.object(desktop_instance, "_signal_named_event", return_value=False),
    ):
        assert request_existing_process_exit(timeout=0.1) is False


def test_non_windows_single_instance_fallback() -> None:
    coordinator = SingleInstanceCoordinator()
    assert coordinator.acquire() is True
    coordinator.start_listener(lambda: None)
    coordinator.close()
    assert request_existing_process_exit() is True
    result = subprocess.run(
        [sys.executable, "desktop/app.py", "--shutdown-existing"],
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0


def main() -> None:
    tests = (
        test_desktop_app_self_test,
        test_windowed_self_test_without_standard_streams,
        test_desktop_download_bridge,
        test_desktop_download_cancel_stops_before_request,
        test_desktop_file_dialog_result_compatibility,
        test_desktop_runtime_error_does_not_mislabel_webview2,
        test_desktop_bridge_rejects_unsafe_requests,
        test_desktop_external_link_validation,
        test_desktop_diagnostics_and_directory_allowlist,
        test_desktop_update_check_validation,
        test_desktop_bridge_productization_methods,
        test_desktop_lifecycle_locks_before_hiding,
        test_close_to_tray_preference_defaults_safely,
        test_shutdown_wait_self_test_protocol,
        test_existing_process_exit_protocol_handles_windows_races,
        test_non_windows_single_instance_fallback,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
