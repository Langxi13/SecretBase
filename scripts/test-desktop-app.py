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

import desktop.app as desktop_app  # noqa: E402
from desktop.app import desktop_window_failure, run_shutdown_wait_self_test, selected_file_path  # noqa: E402
from desktop.bridge import DesktopApi, safe_filename, validate_download_request  # noqa: E402
from desktop.diagnostics import DesktopDiagnostics, detect_package_type  # noqa: E402
import desktop.instance as desktop_instance  # noqa: E402
from desktop.instance import SingleInstanceCoordinator, request_existing_process_exit  # noqa: E402
import desktop.platform_support as platform_support  # noqa: E402
from desktop.platform_support import (  # noqa: E402
    WINDOWS_PROFILE,
    current_platform_profile,
    desktop_runtime_environment,
    normalized_architecture,
)
from desktop.preferences import load_preferences  # noqa: E402
from desktop.runtime import desktop_paths, prepare_data_root  # noqa: E402
from desktop.tray import (  # noqa: E402
    DesktopLifecycle,
    load_close_preferences,
    load_close_to_tray,
    save_close_preferences,
)
from desktop.update import check_for_updates, parse_version, validate_release_url  # noqa: E402
from desktop.zoom import DesktopZoomController, load_zoom_preference  # noqa: E402


class DownloadHandler(BaseHTTPRequestHandler):
    received_token = None

    def do_POST(self) -> None:  # noqa: N802
        self.__class__.received_token = self.headers.get("X-SecretBase-Token")
        content_length = int(self.headers.get("Content-Length") or 0)
        if content_length:
            self.rfile.read(content_length)
        payload = b"encrypted-test-backup"
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

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
    with patch.object(desktop_app, "current_platform_profile", return_value=WINDOWS_PROFILE):
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
            version="4.0.0",
            renderer="edgechromium",
            platform_key="windows",
            capabilities={"tray": True, "directory_open": True},
            backend_running=lambda: True,
            directory_opener=lambda path: opened.append(path),
        )
        diagnostics.health_opener = StaticOpener({
            "success": True,
            "data": {"status": "healthy", "version": "4.0.0"},
        })

        result = diagnostics.collect()
        assert result["status"] == "ok"
        assert result["package_type"] == "source"
        assert result["platform"] == "windows"
        assert result["capabilities"]["tray"] is True
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
    assert parse_version("3.2.0") == (3, 2, 0)
    release_url = "https://github.com/Langxi13/SecretBase/releases/tag/v3.2.0"
    assert validate_release_url(release_url) == release_url
    for invalid in ("v3.2.0", "3.2", "3.2.0-beta"):
        try:
            parse_version(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(invalid)


def test_desktop_bridge_productization_methods() -> None:
    close_preferences = []
    close_requests = []
    zoom_actions = []
    api = DesktopApi(
        "http://127.0.0.1:1",
        lambda _filename: None,
        diagnostics_provider=lambda: {"status": "ok"},
        directory_opener=lambda kind: {"status": "opened", "kind": kind},
        update_checker=lambda: {"status": "up_to_date"},
        close_preferences_setter=lambda close_to_tray, confirm_close: not close_preferences.append(
            (close_to_tray, confirm_close)
        ),
        close_request_resolver=lambda action, remember: close_requests.append((action, remember)) or {
            "status": "hidden"
        },
        zoom_changer=lambda action: zoom_actions.append(action) or 110,
    )
    assert api.get_diagnostics() == {"status": "ok"}
    assert api.open_directory("data") == {"status": "opened", "kind": "data"}
    assert api.check_for_updates() == {"status": "up_to_date"}
    assert api.set_close_preferences(True, False) == {
        "status": "updated",
        "close_to_tray": True,
        "confirm_close": False,
    }
    assert close_preferences == [(True, False)]
    assert api.resolve_close_request("tray", True) == {"status": "hidden"}
    assert close_requests == [("tray", True)]
    assert api.change_zoom("in") == {"status": "updated", "action": "in", "percent": 110}
    assert zoom_actions == ["in"]
    try:
        api.change_zoom("invalid")
    except ValueError as error:
        assert "不支持的缩放操作" in str(error)
    else:
        raise AssertionError("Desktop bridge must reject unknown zoom actions")


def test_windows_zoom_controller_persists_and_coalesces_notifications() -> None:
    class FakeNativeEvent:
        def __init__(self) -> None:
            self.handlers = []

        def __iadd__(self, handler):
            self.handlers.append(handler)
            return self

        def __isub__(self, handler):
            self.handlers.remove(handler)
            return self

        def fire(self, sender) -> None:
            for handler in list(self.handlers):
                handler(sender, None)

    class FakeNativeWebView:
        def __init__(self) -> None:
            self.ZoomFactor = 1.0
            self.ZoomFactorChanged = FakeNativeEvent()

    class FakeWindow:
        def __init__(self) -> None:
            self.native = type("NativeWindow", (), {"webview": FakeNativeWebView()})()
            self.evaluated_scripts = []

        def evaluate_js(self, script: str) -> None:
            self.evaluated_scripts.append(script)

    with tempfile.TemporaryDirectory() as raw:
        settings = Path(raw) / "settings.json"
        settings.write_text('{"theme":"dark","desktop_zoom_percent":90}', encoding="utf-8")
        scheduled_actions = []
        window = FakeWindow()
        controller = DesktopZoomController(
            window,
            platform_key="windows",
            settings_path=settings,
            gui_scheduler=lambda callback: callback(),
            notification_scheduler=scheduled_actions.append,
        )
        assert controller.attach() is True
        assert controller.attach() is True
        assert window.native.webview.ZoomFactor == 0.9
        assert len(window.native.webview.ZoomFactorChanged.handlers) == 1

        assert controller.change("in") == 100
        assert window.native.webview.ZoomFactor == 1.0
        assert load_zoom_preference(settings) == 100
        assert load_preferences(settings)["theme"] == "dark"
        assert len(scheduled_actions) == 1
        scheduled_actions.pop(0)()
        assert '"percent":100' in window.evaluated_scripts[-1]

        window.native.webview.ZoomFactorChanged.fire(window.native.webview)
        assert scheduled_actions == []

        window.native.webview.ZoomFactor = 1.1
        window.native.webview.ZoomFactorChanged.fire(window.native.webview)
        assert load_zoom_preference(settings) == 110
        window.native.webview.ZoomFactor = 1.25
        window.native.webview.ZoomFactorChanged.fire(window.native.webview)
        assert len(scheduled_actions) == 2
        evaluated_count = len(window.evaluated_scripts)
        scheduled_actions.pop(0)()
        assert len(window.evaluated_scripts) == evaluated_count
        scheduled_actions.pop(0)()
        assert len(window.evaluated_scripts) == evaluated_count + 1
        assert '"percent":125' in window.evaluated_scripts[-1]

        with patch("desktop.zoom.logger.warning") as warning:
            window.native.webview.ZoomFactor = 0.1
            window.native.webview.ZoomFactorChanged.fire(window.native.webview)
            warning.assert_called_once()
        assert scheduled_actions == []

        controller.detach()
        assert window.native.webview.ZoomFactorChanged.handlers == []
        assert controller.attach() is False


def test_macos_zoom_controller_uses_wkwebview_and_restores_default() -> None:
    class FakeMacWebView:
        def __init__(self) -> None:
            self.factor = 0.0

        def pageZoom(self) -> float:
            return self.factor

        def setPageZoom_(self, factor: float) -> None:
            self.factor = factor

    class FakeMacWindow:
        def __init__(self) -> None:
            self.webview = FakeMacWebView()
            self.native = type("NativeWindow", (), {"contentView": lambda native: self.webview})()
            self.evaluated_scripts = []

        def evaluate_js(self, script: str) -> None:
            self.evaluated_scripts.append(script)

    with tempfile.TemporaryDirectory() as raw:
        settings = Path(raw) / "settings.json"
        settings.write_text('{"desktop_zoom_percent":900,"confirm_close":true}', encoding="utf-8")
        scheduled_actions = []
        window = FakeMacWindow()
        controller = DesktopZoomController(
            window,
            platform_key="macos",
            settings_path=settings,
            gui_scheduler=lambda callback: callback(),
            notification_scheduler=scheduled_actions.append,
        )
        assert controller.attach() is True
        assert window.webview.factor == 1.0
        assert controller.change("in") == 110
        assert window.webview.factor == 1.1
        assert load_zoom_preference(settings) == 110
        assert load_preferences(settings)["confirm_close"] is True
        scheduled_actions.pop(0)()
        assert '"percent":110' in window.evaluated_scripts[-1]
        assert controller.change("reset") == 100
        assert window.webview.factor == 1.0
        controller.detach()


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
            if "desktop-close-request" in script:
                events.append("close-prompt")
            else:
                events.append("frontend-lock")
            return True

        def load_url(self, url: str) -> None:
            self.loaded_urls.append(url)

        def show(self) -> None:
            self.shown += 1
            self.hidden = False
            events.append("show")

        def restore(self) -> None:
            self.restored += 1
            events.append("restore")

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

    with tempfile.TemporaryDirectory() as raw:
        settings = Path(raw) / "settings.json"
        settings.write_text('{"theme": "dark"}', encoding="utf-8")
        server = FakeServer()
        window = FakeWindow()
        scheduled_actions = []
        lifecycle = DesktopLifecycle(
            server,
            Path("icon.ico"),
            settings,
            tray_factory=FakeTray,
            action_scheduler=scheduled_actions.append,
        )
        lifecycle.attach_window(window)
        assert lifecycle.set_close_preferences(True, True) is True
        assert lifecycle.tray is None

        assert lifecycle.on_closing() is False
        assert lifecycle.on_closing() is False
        assert server.lock_count == 0
        assert window.hidden is False
        assert events == []
        assert window.evaluated_scripts == []
        assert len(scheduled_actions) == 1

        scheduled_actions.pop(0)()
        assert events == ["close-prompt"]
        assert "secretbase:desktop-close-request" in window.evaluated_scripts[0]

        result = lifecycle.resolve_close_request("tray", True)
        assert result == {"status": "hiding", "action": "tray", "remembered": False}
        assert server.lock_count == 0
        assert window.hidden is False
        assert len(scheduled_actions) == 1
        assert load_close_preferences(settings) == (False, True)

        scheduled_actions.pop(0)()
        assert server.lock_count == 1
        assert window.hidden is True
        assert events[1:4] == ["backend-lock", "frontend-lock", "hide"]
        assert "secretbase:desktop-lock" in window.evaluated_scripts[1]
        saved = json.loads(settings.read_text(encoding="utf-8"))
        assert saved["theme"] == "dark"
        assert saved["close_to_tray"] is True
        assert saved["confirm_close"] is False

        restore_event_start = len(events)
        lifecycle.restore()
        assert window.hidden is False
        assert window.shown == 1
        assert window.restored == 1
        assert events[restore_event_start:] == ["frontend-lock", "show", "restore"]

        evaluated_before_close = len(window.evaluated_scripts)
        assert lifecycle.on_closing() is False
        assert server.lock_count == 1
        assert window.hidden is False
        assert len(scheduled_actions) == 1

        scheduled_actions.pop(0)()
        assert server.lock_count == 2
        assert window.hidden is True
        assert "desktop-close-request" not in window.evaluated_scripts[evaluated_before_close]
        lifecycle.restore()

        lifecycle.lock()
        assert server.lock_count == 3
        assert window.loaded_urls == []

        lifecycle.exit()
        assert server.lock_count == 4
        assert window.destroyed is True
        assert lifecycle.tray.stopped >= 1

        exit_server = FakeServer()
        exit_window = FakeWindow()
        exit_settings = Path(raw) / "exit-settings.json"
        exit_actions = []
        exit_lifecycle = DesktopLifecycle(
            exit_server,
            Path("icon.ico"),
            exit_settings,
            tray_factory=FakeTray,
            action_scheduler=exit_actions.append,
        )
        exit_lifecycle.attach_window(exit_window)
        assert exit_lifecycle.resolve_close_request("exit", True) == {
            "status": "exiting",
            "action": "exit",
            "remembered": False,
        }
        assert exit_window.destroyed is False
        assert len(exit_actions) == 1
        assert load_close_preferences(exit_settings) == (False, True)
        exit_actions[0]()
        assert exit_window.destroyed is True
        assert load_close_preferences(exit_settings) == (False, False)


def test_close_to_tray_preference_defaults_safely() -> None:
    with tempfile.TemporaryDirectory() as raw:
        settings = Path(raw) / "settings.json"
        assert load_close_to_tray(settings) is False
        assert load_close_preferences(settings) == (False, True)
        settings.write_text('{"close_to_tray": true}', encoding="utf-8")
        assert load_close_to_tray(settings) is True
        assert load_close_preferences(settings) == (True, True)
        settings.write_text('{"close_to_tray": "true"}', encoding="utf-8")
        assert load_close_to_tray(settings) is False
        settings.write_text('{"desktop_zoom_percent":125,"close_to_tray":"true"}', encoding="utf-8")
        save_close_preferences(settings, True, False)
        assert load_close_preferences(settings) == (True, False)
        assert load_zoom_preference(settings) == 125


def test_tray_start_failure_keeps_window_open() -> None:
    class FakeServer:
        url = "http://127.0.0.1:12345"

        def __init__(self) -> None:
            self.lock_count = 0

        def lock_vault(self) -> None:
            self.lock_count += 1

    class FakeWindow:
        def __init__(self) -> None:
            self.hidden = False

        def hide(self) -> None:
            self.hidden = True

    class FailingTray:
        def __init__(self, _path, **_callbacks) -> None:
            self.running = False

        def start(self) -> bool:
            return False

        def stop(self) -> None:
            return None

    with tempfile.TemporaryDirectory() as raw:
        settings = Path(raw) / "settings.json"
        server = FakeServer()
        window = FakeWindow()
        scheduled_actions = []
        lifecycle = DesktopLifecycle(
            server,
            Path("icon.ico"),
            settings,
            tray_factory=FailingTray,
            action_scheduler=scheduled_actions.append,
        )
        lifecycle.attach_window(window)
        with patch("desktop.tray.show_tray_failure_message") as show_failure:
            assert lifecycle.resolve_close_request("tray", True) == {
                "status": "hiding",
                "action": "tray",
                "remembered": False,
            }
            show_failure.assert_not_called()
            assert len(scheduled_actions) == 1
            assert load_close_preferences(settings) == (False, True)
            scheduled_actions[0]()
            show_failure.assert_called_once_with()
        assert window.hidden is False
        assert server.lock_count == 0
        assert lifecycle.exit_requested is False
        assert lifecycle.close_to_tray is False
        assert lifecycle.confirm_close is True
        assert load_close_preferences(settings) == (False, True)


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
        patch.object(desktop_instance.sys, "platform", "win32"),
        patch.object(desktop_instance, "_named_mutex_exists", side_effect=[True, True, False]),
        patch.object(desktop_instance, "_signal_named_event", return_value=True) as signal,
        patch.object(desktop_instance.time, "sleep"),
    ):
        assert request_existing_process_exit(timeout=0.1) is True
        signal.assert_called_once_with(desktop_instance.DEFAULT_EXIT_EVENT_NAME)

    with (
        patch.object(desktop_instance.os, "name", "nt"),
        patch.object(desktop_instance.sys, "platform", "win32"),
        patch.object(desktop_instance, "_named_mutex_exists", side_effect=[True, False]),
        patch.object(desktop_instance, "_signal_named_event", return_value=False),
    ):
        assert request_existing_process_exit(timeout=0.1) is True

    with (
        patch.object(desktop_instance.os, "name", "nt"),
        patch.object(desktop_instance.sys, "platform", "win32"),
        patch.object(desktop_instance, "_named_mutex_exists", side_effect=[True, True]),
        patch.object(desktop_instance, "_signal_named_event", return_value=False),
    ):
        assert request_existing_process_exit(timeout=0.1) is False


def test_non_windows_single_instance_fallback() -> None:
    if sys.platform != "linux":
        return
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        coordinator = SingleInstanceCoordinator(data_root=root)
        assert coordinator.acquire() is True
        coordinator.start_listener(lambda: None)
        coordinator.close()
        assert request_existing_process_exit(data_root=root) is True
        result = subprocess.run(
            [sys.executable, "desktop/app.py", "--shutdown-existing", "--data-root", str(root)],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode == 0


def test_platform_profiles_and_runtime_capabilities() -> None:
    with (
        patch.object(platform_support.sys, "platform", "darwin"),
        patch.object(platform_support.platform, "machine", return_value="arm64"),
    ):
        profile = current_platform_profile()
        assert profile.key == "macos"
        assert profile.renderer == "wkwebview"
        assert profile.gui == "cocoa"
        assert profile.capabilities["tray"] is False
        assert profile.capabilities["single_instance"] is True
        assert profile.capabilities["zoom_controls"] is True
        assert profile.capabilities["native_zoom_feedback"] is True
        assert normalized_architecture() == "arm64"
        environment = desktop_runtime_environment(shell=True)
        assert environment["SECRETBASE_DESKTOP_PLATFORM"] == "macos"
        assert environment["SECRETBASE_DESKTOP_ARCHITECTURE"] == "arm64"
        assert json.loads(environment["SECRETBASE_DESKTOP_CAPABILITIES"])["tray"] is False


def test_macos_single_instance_activation_and_exit_protocol() -> None:
    if sys.platform == "win32":
        return
    with tempfile.TemporaryDirectory() as raw, patch.object(desktop_instance.sys, "platform", "darwin"):
        root = Path(raw)
        activated = threading.Event()
        exit_requested = threading.Event()
        first = SingleInstanceCoordinator(data_root=root)
        assert first.acquire() is True
        first.start_listener(activated.set, exit_requested.set)

        duplicate = SingleInstanceCoordinator(data_root=root)
        assert duplicate.acquire() is False
        assert activated.wait(2)
        duplicate.close()

        result = []
        requester = threading.Thread(
            target=lambda: result.append(request_existing_process_exit(timeout=2, data_root=root)),
            daemon=True,
        )
        requester.start()
        assert exit_requested.wait(2)
        first.close()
        requester.join(timeout=3)
        assert result == [True]

        replacement = SingleInstanceCoordinator(data_root=root)
        assert replacement.acquire() is True
        replacement.close()


def test_macos_lifecycle_rejects_tray_preferences() -> None:
    class FakeServer:
        def lock_vault(self) -> None:
            return None

    lifecycle = DesktopLifecycle(FakeServer(), ROOT / "desktop" / "assets" / "secretbase.ico", supports_tray=False)
    assert lifecycle.set_close_preferences(False, False) is True
    try:
        lifecycle.set_close_preferences(True, True)
    except ValueError as error:
        assert "不支持系统托盘" in str(error)
    else:
        raise AssertionError("macOS lifecycle must reject tray preferences")
    try:
        lifecycle.resolve_close_request("tray", False)
    except ValueError as error:
        assert "不支持系统托盘" in str(error)
    else:
        raise AssertionError("macOS lifecycle must reject tray close actions")
    assert lifecycle.on_closing() is None
    assert lifecycle.exit_requested is True


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
        test_windows_zoom_controller_persists_and_coalesces_notifications,
        test_macos_zoom_controller_uses_wkwebview_and_restores_default,
        test_desktop_lifecycle_locks_before_hiding,
        test_close_to_tray_preference_defaults_safely,
        test_tray_start_failure_keeps_window_open,
        test_shutdown_wait_self_test_protocol,
        test_existing_process_exit_protocol_handles_windows_races,
        test_non_windows_single_instance_fallback,
        test_platform_profiles_and_runtime_capabilities,
        test_macos_single_instance_activation_and_exit_protocol,
        test_macos_lifecycle_rejects_tray_preferences,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
