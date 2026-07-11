from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Callable

try:
    from .instance import focus_current_process_window
except ImportError:
    from instance import focus_current_process_window


logger = logging.getLogger(__name__)

FRONTEND_LOCK_SCRIPT = """
(() => {
    document.documentElement.setAttribute('data-secretbase-desktop-locking', 'true');
    const ready = window.SECRETBASE_DESKTOP_LOCK_READY === true;
    window.dispatchEvent(new CustomEvent('secretbase:desktop-lock'));
    return ready;
})()
"""

FRONTEND_CLOSE_REQUEST_SCRIPT = """
(() => {
    const ready = window.SECRETBASE_DESKTOP_CLOSE_READY === true;
    if (!ready) return false;
    window.dispatchEvent(new CustomEvent('secretbase:desktop-close-request'));
    return true;
})()
"""


def load_close_preferences(settings_path: Path) -> tuple[bool, bool]:
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("设置文件必须是对象")
        return payload.get("close_to_tray") is True, payload.get("confirm_close") is not False
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return False, True


def load_close_to_tray(settings_path: Path) -> bool:
    return load_close_preferences(settings_path)[0]


def save_close_preferences(settings_path: Path, close_to_tray: bool, confirm_close: bool) -> None:
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            payload = {}
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        payload = {}

    payload["close_to_tray"] = close_to_tray
    payload["confirm_close"] = confirm_close
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{settings_path.name}.",
            suffix=".tmp",
            dir=settings_path.parent,
            delete=False,
        ) as temporary:
            json.dump(payload, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, settings_path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def fallback_close_action(default_to_tray: bool) -> str:
    if os.name != "nt":
        return "tray" if default_to_tray else "exit"
    import ctypes

    flags = 0x00000003 | 0x00000020
    if not default_to_tray:
        flags |= 0x00000100
    result = ctypes.windll.user32.MessageBoxW(
        None,
        "选择“是”隐藏到系统托盘，选择“否”完全退出，选择“取消”返回应用。",
        "关闭 SecretBase",
        flags,
    )
    if result == 6:
        return "tray"
    if result == 7:
        return "exit"
    return "cancel"


def show_tray_failure_message() -> None:
    if os.name != "nt":
        return
    import ctypes

    ctypes.windll.user32.MessageBoxW(
        None,
        "系统托盘启动失败，SecretBase 将保持打开。请检查系统通知区域设置后重试。",
        "无法隐藏到托盘",
        0x00000010,
    )


class TrayIcon:
    def __init__(
        self,
        icon_path: Path,
        *,
        on_open: Callable[[], None],
        on_lock: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.icon_path = icon_path
        self.on_open = on_open
        self.on_lock = on_lock
        self.on_exit = on_exit
        self._icon = None
        self._ready = threading.Event()
        self._error: Exception | None = None

    @property
    def running(self) -> bool:
        return bool(self._icon and getattr(self._icon, "visible", False))

    def start(self, timeout: float = 5.0) -> bool:
        if self.running:
            return True
        if os.name != "nt":
            return False
        try:
            import pystray
            from PIL import Image

            image = Image.open(self.icon_path).convert("RGBA")
            menu = pystray.Menu(
                pystray.MenuItem("打开 SecretBase", lambda _icon, _item: self.on_open(), default=True),
                pystray.MenuItem("锁定", lambda _icon, _item: self.on_lock()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", lambda _icon, _item: self.on_exit()),
            )
            self._ready.clear()
            self._error = None
            self._icon = pystray.Icon("SecretBase", image, "SecretBase", menu)

            def setup(icon) -> None:
                try:
                    icon.visible = True
                except Exception as error:
                    self._error = error
                finally:
                    self._ready.set()

            self._icon.run_detached(setup)
            if not self._ready.wait(timeout) or self._error is not None or not self.running:
                self.stop()
                return False
            return True
        except Exception as error:
            logger.error("启动系统托盘失败: %s", error)
            self.stop()
            return False

    def stop(self) -> None:
        icon = self._icon
        self._icon = None
        if icon is not None:
            try:
                icon.stop()
            except Exception as error:
                logger.warning("停止系统托盘失败: %s", error)


class DesktopLifecycle:
    def __init__(
        self,
        server,
        icon_path: Path,
        settings_path: Path | None = None,
        tray_factory=TrayIcon,
        action_scheduler: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        self.server = server
        self.icon_path = icon_path
        self.settings_path = settings_path
        self.tray_factory = tray_factory
        self.action_scheduler = action_scheduler or self._schedule_action
        self.window = None
        self.tray = None
        self.close_to_tray = False
        self.confirm_close = True
        self.hidden_to_tray = False
        self.exit_requested = False
        self._close_action_pending = False
        self._lock = threading.RLock()

    @staticmethod
    def _schedule_action(callback: Callable[[], None]) -> None:
        timer = threading.Timer(0.1, callback)
        timer.daemon = True
        timer.start()

    def attach_window(self, window) -> None:
        self.window = window

    def _ensure_tray(self) -> bool:
        if self.tray is None:
            self.tray = self.tray_factory(
                self.icon_path,
                on_open=self.restore,
                on_lock=self.lock,
                on_exit=self.exit,
            )
        return self.tray.start()

    def set_close_preferences(self, close_to_tray: bool, confirm_close: bool) -> bool:
        if type(close_to_tray) is not bool or type(confirm_close) is not bool:
            raise ValueError("关闭设置必须是布尔值")
        with self._lock:
            self.close_to_tray = close_to_tray
            self.confirm_close = confirm_close
            if not close_to_tray and self.tray is not None:
                self.tray.stop()
            return True

    def _lock_vault(self) -> None:
        self.server.lock_vault()

    def _apply_frontend_lock(self) -> bool:
        if self.window is None:
            return False
        try:
            return self.window.evaluate_js(FRONTEND_LOCK_SCRIPT) is True
        except Exception as error:
            logger.warning("通知前端锁定失败: %s", error)
            return False

    def _request_frontend_close_confirmation(self) -> bool:
        if self.window is None:
            return False
        try:
            return self.window.evaluate_js(FRONTEND_CLOSE_REQUEST_SCRIPT) is True
        except Exception as error:
            logger.warning("显示前端关闭确认失败: %s", error)
            return False

    def _schedule_close_action(self, callback: Callable[[], None]) -> bool:
        with self._lock:
            if self.exit_requested or self._close_action_pending:
                return False
            self._close_action_pending = True

        def run() -> None:
            try:
                callback()
            except Exception:
                logger.exception("执行桌面关闭操作失败")
            finally:
                with self._lock:
                    self._close_action_pending = False

        try:
            self.action_scheduler(run)
            return True
        except Exception:
            with self._lock:
                self._close_action_pending = False
            raise

    def _reload_locked_page(self) -> None:
        if self.window is not None:
            self.window.load_url(self.server.url)

    def _hide_to_tray(self) -> bool:
        with self._lock:
            if self.window is None or self.exit_requested:
                return False
            window = self.window

        if not self._ensure_tray():
            return False

        with self._lock:
            if self.exit_requested or self.window is not window:
                return False

        self._lock_vault()
        frontend_locked = self._apply_frontend_lock()
        window.hide()
        with self._lock:
            self.hidden_to_tray = True
        if not frontend_locked:
            self._reload_locked_page()
        return True

    def _remember_close_action(self, action: str) -> bool:
        close_to_tray = action == "tray"
        with self._lock:
            self.close_to_tray = close_to_tray
            self.confirm_close = False
        if self.settings_path is None:
            return False
        try:
            save_close_preferences(self.settings_path, close_to_tray, False)
            return True
        except OSError as error:
            logger.warning("保存关闭偏好失败: %s", error)
            return False

    def _hide_to_tray_or_notify(self, *, remember: bool = False) -> bool:
        try:
            hidden = self._hide_to_tray()
        except Exception:
            logger.exception("隐藏到系统托盘失败")
            hidden = False

        if hidden:
            if remember:
                self._remember_close_action("tray")
            return True

        with self._lock:
            exiting = self.exit_requested
        if not exiting:
            show_tray_failure_message()
        return False

    def _exit_after_request(self, remember: bool) -> None:
        if remember:
            self._remember_close_action("exit")
        self.exit()

    def _show_close_confirmation_after_cancel(self, default_to_tray: bool) -> None:
        with self._lock:
            if self.exit_requested:
                return

        if self._request_frontend_close_confirmation():
            return

        action = fallback_close_action(default_to_tray)
        if action == "tray":
            self._hide_to_tray_or_notify()
        elif action == "exit":
            self.exit()

    def on_closing(self):
        with self._lock:
            if self.exit_requested:
                return None
            confirm_close = self.confirm_close
            close_to_tray = self.close_to_tray

        if confirm_close:
            # pywebview 的 closing 回调运行在 GUI 生命周期中，必须先返回，
            # 再从后台任务调用 JavaScript 或原生窗口 API，避免桥接重入死锁。
            self._schedule_close_action(
                lambda: self._show_close_confirmation_after_cancel(close_to_tray)
            )
            return False

        if close_to_tray:
            self._schedule_close_action(self._hide_to_tray_or_notify)
            return False

        with self._lock:
            self.exit_requested = True
        return None

    def resolve_close_request(self, action: str, remember: bool) -> dict[str, str | bool]:
        if action not in {"tray", "exit"}:
            raise ValueError("不支持的关闭操作")
        if type(remember) is not bool:
            raise ValueError("记住选择必须是布尔值")

        if action == "tray":
            if not self._schedule_close_action(
                lambda: self._hide_to_tray_or_notify(remember=remember)
            ):
                raise RuntimeError("关闭操作正在处理中")
            return {"status": "hiding", "action": action, "remembered": False}

        if not self._schedule_close_action(lambda: self._exit_after_request(remember)):
            raise RuntimeError("关闭操作正在处理中")
        return {"status": "exiting", "action": action, "remembered": False}

    def restore(self) -> None:
        with self._lock:
            if self.window is None:
                return
            if self.hidden_to_tray:
                if not self._apply_frontend_lock():
                    self._reload_locked_page()
                self.hidden_to_tray = False
            focus_current_process_window(self.window)

    def lock(self) -> None:
        with self._lock:
            self._lock_vault()
            if not self._apply_frontend_lock():
                self._reload_locked_page()

    def exit(self) -> None:
        with self._lock:
            if self.exit_requested:
                return
            self.exit_requested = True
            tray = self.tray
            window = self.window
        try:
            self._lock_vault()
        except Exception as error:
            logger.warning("退出前锁定密码库失败: %s", error)
        if tray is not None:
            tray.stop()
        if window is not None:
            window.destroy()

    def shutdown(self) -> None:
        with self._lock:
            self.exit_requested = True
            tray = self.tray
        try:
            self._lock_vault()
        except Exception:
            pass
        if tray is not None:
            tray.stop()
