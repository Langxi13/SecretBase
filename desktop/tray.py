from __future__ import annotations

import json
import logging
import os
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


def load_close_to_tray(settings_path: Path) -> bool:
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        return payload.get("close_to_tray") is True
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


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
    def __init__(self, server, icon_path: Path, tray_factory=TrayIcon) -> None:
        self.server = server
        self.icon_path = icon_path
        self.tray_factory = tray_factory
        self.window = None
        self.tray = None
        self.close_to_tray = False
        self.hidden_to_tray = False
        self.exit_requested = False
        self._lock = threading.RLock()

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

    def set_close_to_tray(self, enabled: bool) -> bool:
        if type(enabled) is not bool:
            raise ValueError("托盘设置必须是布尔值")
        with self._lock:
            if enabled and not self._ensure_tray():
                self.close_to_tray = False
                return False
            self.close_to_tray = enabled
            if not enabled and self.tray is not None:
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

    def _reload_locked_page(self) -> None:
        if self.window is not None:
            self.window.load_url(self.server.url)

    def on_closing(self):
        with self._lock:
            if self.exit_requested or not self.close_to_tray:
                return None
            if not self._ensure_tray():
                self.close_to_tray = False
                return None
            self._lock_vault()
            frontend_locked = self._apply_frontend_lock()
            self.window.hide()
            self.hidden_to_tray = True
            if not frontend_locked:
                self._reload_locked_page()
            return False

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
