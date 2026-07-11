from __future__ import annotations

import argparse
import ctypes
import json
import logging
import os
import sys
import tempfile
import urllib.request
import webbrowser
from pathlib import Path

try:
    from .bridge import DesktopApi
    from .diagnostics import DesktopDiagnostics
    from .instance import SingleInstanceCoordinator
    from .runtime import InProcessDesktopServer, application_root, desktop_paths, resolve_data_root
    from .tray import DesktopLifecycle, load_close_to_tray
    from .update import check_for_updates
except ImportError:
    from bridge import DesktopApi
    from diagnostics import DesktopDiagnostics
    from instance import SingleInstanceCoordinator
    from runtime import InProcessDesktopServer, application_root, desktop_paths, resolve_data_root
    from tray import DesktopLifecycle, load_close_to_tray
    from update import check_for_updates


WINDOW_TITLE = "SecretBase"
WEBVIEW2_DOWNLOAD_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start SecretBase as a Windows desktop application.")
    parser.add_argument("--data-root", help="Override the local SecretBase data directory.")
    test_mode = parser.add_mutually_exclusive_group()
    test_mode.add_argument("--self-test", action="store_true", help="Run a packaged backend/resource test without a window.")
    test_mode.add_argument(
        "--desktop-runtime-self-test",
        action="store_true",
        help="Load the packaged Windows desktop runtime without creating a window.",
    )
    parser.add_argument("--report", help="Write the self-test result as JSON.")
    return parser.parse_args()


def show_message(title: str, message: str, *, error: bool = False, yes_no: bool = False) -> bool:
    if os.name != "nt":
        print(f"{title}: {message}", file=sys.stderr if error else sys.stdout)
        return False
    flags = 0x00000004 if yes_no else 0x00000000
    flags |= 0x00000010 if error else 0x00000040
    return ctypes.windll.user32.MessageBoxW(None, message, title, flags) == 6


def write_report(path: str | None, payload: dict) -> None:
    if not path:
        return
    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def selected_file_path(selection) -> str | None:
    if isinstance(selection, (str, os.PathLike)):
        return os.fspath(selection)
    if not selection:
        return None
    try:
        selected = next(iter(selection))
    except (TypeError, StopIteration):
        return None
    return os.fspath(selected) if isinstance(selected, (str, os.PathLike)) else None


def run_self_test(data_root_value: str | None, report_path: str | None) -> int:
    temporary = None
    if data_root_value:
        data_root = resolve_data_root(data_root_value)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="secretbase-desktop-self-test-")
        data_root = Path(temporary.name)

    server = InProcessDesktopServer(data_root)
    result = {"success": False, "mode": "desktop", "data_root": str(data_root)}
    try:
        url = server.start()
        with urllib.request.urlopen(f"{url}/health", timeout=5) as response:
            health = json.loads(response.read().decode("utf-8"))
        with urllib.request.urlopen(f"{url}/", timeout=5) as response:
            index_html = response.read().decode("utf-8")
        result.update({
            "success": True,
            "health": health.get("data", {}),
            "frontend_loaded": '<div id="app"' in index_html,
        })
        return 0 if result["frontend_loaded"] else 1
    except Exception as error:
        result["error"] = str(error)
        return 1
    finally:
        server.stop()
        write_report(report_path, result)
        logging.shutdown()
        if temporary is not None:
            temporary.cleanup()


def run_desktop_runtime_self_test(report_path: str | None) -> int:
    result = {"success": False, "mode": "desktop-runtime"}
    try:
        if os.name != "nt":
            raise RuntimeError("桌面运行时自检只支持 Windows")

        import clr
        import pystray

        clr.AddReference("System")
        import System
        from PIL import Image
        from webview.platforms import winforms

        renderer = str(getattr(winforms, "renderer", ""))
        icon_path = application_root() / "desktop" / "assets" / "secretbase.ico"
        with Image.open(icon_path) as icon:
            tray_icon_size = list(icon.size)
        result.update({
            "success": renderer == "edgechromium" and bool(pystray.Icon) and tray_icon_size[0] > 0,
            "renderer": renderer,
            "dotnet_version": str(System.Environment.Version),
            "tray_available": True,
            "tray_icon_size": tray_icon_size,
        })
        if not result["success"]:
            result["error"] = f"未加载 Edge WebView2 渲染器：{renderer or 'unknown'}"
    except Exception as error:
        result["error"] = str(error)
    finally:
        write_report(report_path, result)
        logging.shutdown()
    return 0 if result["success"] else 1


def desktop_window_failure(error: Exception) -> tuple[str, bool]:
    message = str(error)
    normalized = message.lower()
    runtime_markers = (
        "python.runtime.loader.initialize",
        "pythonnet",
        "clr_loader",
        "null pointer pointer",
    )
    if any(marker in normalized for marker in runtime_markers):
        return (
            "Windows 桌面运行组件无法加载。\n\n"
            f"{message}\n\n"
            "请重新下载最新的完整 x64 ZIP，不要单独移动 EXE。"
            "如果仍使用旧测试包，请右键原始 ZIP，打开“属性”，勾选“解除锁定”后重新解压。",
            False,
        )
    return (
        f"无法启动 Windows 桌面窗口。\n\n{message}\n\n是否打开 WebView2 官方下载页面？",
        True,
    )


def run_window(data_root_value: str | None) -> int:
    coordinator = SingleInstanceCoordinator()
    if not coordinator.acquire():
        return 0

    data_root = resolve_data_root(data_root_value)
    paths = desktop_paths(data_root)
    server = InProcessDesktopServer(data_root)
    lifecycle = None
    try:
        url = server.start()
    except Exception as error:
        show_message(
            "SecretBase 启动失败",
            f"本地服务无法启动。\n\n{error}\n\n日志目录：{paths.logs}",
            error=True,
        )
        coordinator.close()
        return 1

    try:
        import webview

        window_holder = {}

        def save_dialog(filename: str) -> str | None:
            window = window_holder.get("window")
            if window is None:
                return None
            selected = window.create_file_dialog(
                webview.FileDialog.SAVE,
                save_filename=filename,
                file_types=("SecretBase 文件 (*.enc;*.bak;*.json)", "所有文件 (*.*)"),
            )
            return selected_file_path(selected)

        from version import APP_VERSION

        diagnostics = DesktopDiagnostics(
            paths=paths,
            backend_url=url,
            version=APP_VERSION,
            renderer="edgechromium",
            backend_running=lambda: server.is_running,
        )
        icon_path = application_root() / "desktop" / "assets" / "secretbase.ico"
        lifecycle = DesktopLifecycle(server, icon_path)
        bridge = DesktopApi(
            url,
            save_dialog,
            diagnostics_provider=diagnostics.collect,
            directory_opener=diagnostics.open_directory,
            update_checker=lambda: check_for_updates(APP_VERSION),
            tray_setter=lifecycle.set_close_to_tray,
        )
        window = webview.create_window(
            WINDOW_TITLE,
            url,
            js_api=bridge,
            width=1280,
            height=820,
            min_size=(960, 640),
            resizable=True,
            background_color="#111827",
            text_select=True,
        )
        if window is None:
            raise RuntimeError("无法创建 SecretBase 桌面窗口")
        window_holder["window"] = window
        lifecycle.attach_window(window)
        window.events.closing += lifecycle.on_closing
        coordinator.start_listener(lifecycle.restore)
        if load_close_to_tray(paths.settings) and not lifecycle.set_close_to_tray(True):
            logging.getLogger(__name__).warning("已保存托盘设置，但本次无法启动系统托盘")
        webview.start(
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(paths.webview),
        )
        return 0
    except Exception as error:
        failure_message, offer_webview2 = desktop_window_failure(error)
        install_runtime = show_message(
            "SecretBase 桌面窗口启动失败",
            failure_message,
            error=True,
            yes_no=offer_webview2,
        )
        if offer_webview2 and install_runtime:
            webbrowser.open(WEBVIEW2_DOWNLOAD_URL)
        return 1
    finally:
        if lifecycle is not None:
            lifecycle.shutdown()
        coordinator.close()
        server.stop()
        logging.shutdown()


def main() -> int:
    args = parse_args()
    if args.self_test:
        return run_self_test(args.data_root, args.report)
    if args.desktop_runtime_self_test:
        return run_desktop_runtime_self_test(args.report)
    if args.report:
        raise SystemExit("--report 只能与自检参数一起使用")
    return run_window(args.data_root)


if __name__ == "__main__":
    raise SystemExit(main())
