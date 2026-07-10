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
    from .instance import SingleInstanceCoordinator, focus_current_process_window
    from .runtime import InProcessDesktopServer, desktop_paths, resolve_data_root
except ImportError:
    from bridge import DesktopApi
    from instance import SingleInstanceCoordinator, focus_current_process_window
    from runtime import InProcessDesktopServer, desktop_paths, resolve_data_root


WINDOW_TITLE = "SecretBase"
WEBVIEW2_DOWNLOAD_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start SecretBase as a Windows desktop application.")
    parser.add_argument("--data-root", help="Override the local SecretBase data directory.")
    parser.add_argument("--self-test", action="store_true", help="Run a packaged backend/resource test without a window.")
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


def run_window(data_root_value: str | None) -> int:
    coordinator = SingleInstanceCoordinator()
    if not coordinator.acquire():
        return 0

    data_root = resolve_data_root(data_root_value)
    paths = desktop_paths(data_root)
    server = InProcessDesktopServer(data_root)
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

        bridge = DesktopApi(url, save_dialog)
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
        coordinator.start_listener(lambda: focus_current_process_window(window))
        webview.start(
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(paths.webview),
        )
        return 0
    except Exception as error:
        install_runtime = show_message(
            "SecretBase 桌面窗口启动失败",
            f"无法启动 Windows 桌面窗口。\n\n{error}\n\n是否打开 WebView2 官方下载页面？",
            error=True,
            yes_no=True,
        )
        if install_runtime:
            webbrowser.open(WEBVIEW2_DOWNLOAD_URL)
        return 1
    finally:
        coordinator.close()
        server.stop()
        logging.shutdown()


def main() -> int:
    args = parse_args()
    if args.self_test:
        return run_self_test(args.data_root, args.report)
    if args.report:
        raise SystemExit("--report 只能与 --self-test 一起使用")
    return run_window(args.data_root)


if __name__ == "__main__":
    raise SystemExit(main())
