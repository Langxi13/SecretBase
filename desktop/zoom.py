from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Callable

try:
    from .preferences import load_preferences, update_preferences
except ImportError:
    from preferences import load_preferences, update_preferences


logger = logging.getLogger(__name__)

DEFAULT_ZOOM_PERCENT = 100
MIN_ZOOM_PERCENT = 25
MAX_ZOOM_PERCENT = 500
ZOOM_LEVELS = (25, 33, 50, 67, 75, 80, 90, 100, 110, 125, 150, 175, 200, 250, 300, 400, 500)


def normalize_zoom_percent(value, default: int = DEFAULT_ZOOM_PERCENT) -> int:
    if isinstance(value, bool):
        return default
    try:
        percent = int(round(float(value)))
    except (TypeError, ValueError, OverflowError):
        return default
    return percent if MIN_ZOOM_PERCENT <= percent <= MAX_ZOOM_PERCENT else default


def next_zoom_percent(current: int, action: str) -> int:
    if action == "reset":
        return DEFAULT_ZOOM_PERCENT
    if action not in {"in", "out"}:
        raise ValueError("不支持的缩放操作")

    current = normalize_zoom_percent(current)
    if action == "in":
        return next((level for level in ZOOM_LEVELS if level > current), ZOOM_LEVELS[-1])
    return next((level for level in reversed(ZOOM_LEVELS) if level < current), ZOOM_LEVELS[0])


def load_zoom_preference(settings_path: Path) -> int:
    return normalize_zoom_percent(load_preferences(settings_path).get("desktop_zoom_percent"))


def save_zoom_preference(settings_path: Path, percent: int) -> None:
    update_preferences(settings_path, {"desktop_zoom_percent": normalize_zoom_percent(percent)})


def zoom_changed_script(percent: int) -> str:
    payload = json.dumps({"percent": percent}, separators=(",", ":"))
    return (
        "window.dispatchEvent(new CustomEvent('secretbase:desktop-zoom-changed', "
        f"{{ detail: {payload} }}));"
    )


class DesktopZoomController:
    def __init__(
        self,
        window,
        *,
        platform_key: str,
        settings_path: Path,
        gui_scheduler: Callable[[Callable[[], None]], None] | None = None,
        notification_scheduler: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        self.window = window
        self.platform_key = platform_key
        self.settings_path = settings_path
        self.gui_scheduler = gui_scheduler
        self.notification_scheduler = notification_scheduler or self._schedule_notification
        self._native_window = None
        self._native_webview = None
        self._zoom_event = None
        self._current_percent = DEFAULT_ZOOM_PERCENT
        self._pending_native_percent: int | None = None
        self._generation = 0
        self._closed = False
        self._lock = threading.RLock()
        self._zoom_handler = self._on_zoom_factor_changed

    @staticmethod
    def _schedule_notification(callback: Callable[[], None]) -> None:
        timer = threading.Timer(0.08, callback)
        timer.daemon = True
        timer.start()

    def _discover_native_webview(self):
        native_window = getattr(self.window, "native", None)
        if native_window is None:
            return None, None, None
        if self.platform_key == "windows":
            native_webview = getattr(native_window, "webview", None)
            return native_window, native_webview, getattr(native_webview, "ZoomFactorChanged", None)
        if self.platform_key == "macos":
            content_view = getattr(native_window, "contentView", None)
            native_webview = content_view() if callable(content_view) else None
            if not callable(getattr(native_webview, "pageZoom", None)):
                native_webview = None
            if not callable(getattr(native_webview, "setPageZoom_", None)):
                native_webview = None
            return native_window, native_webview, None
        return native_window, None, None

    def attach(self) -> bool:
        native_window, native_webview, zoom_event = self._discover_native_webview()
        if native_webview is None or (self.platform_key == "windows" and zoom_event is None):
            logger.warning("无法初始化 %s 桌面缩放控制器", self.platform_key)
            return False

        with self._lock:
            if self._closed:
                return False
            if self._native_webview is native_webview:
                return True
            if self._native_webview is not None:
                logger.warning("桌面缩放控制器已绑定到其他窗口")
                return False
            if zoom_event is not None:
                try:
                    zoom_event += self._zoom_handler
                except Exception:
                    logger.exception("绑定 WebView2 缩放监听器失败")
                    return False
            self._native_window = native_window
            self._native_webview = native_webview
            self._zoom_event = zoom_event
            self._current_percent = load_zoom_preference(self.settings_path)
            self._pending_native_percent = self._current_percent if zoom_event is not None else None
            initial_percent = self._current_percent

        try:
            self._dispatch_gui(lambda: self._set_native_percent(initial_percent))
        except Exception:
            logger.exception("恢复桌面缩放比例失败")
            self.detach()
            return False
        return True

    def detach(self) -> None:
        with self._lock:
            zoom_event = self._zoom_event
            self._native_window = None
            self._native_webview = None
            self._zoom_event = None
            self._pending_native_percent = None
            self._generation += 1
            self._closed = True

        if zoom_event is not None:
            try:
                zoom_event -= self._zoom_handler
            except Exception:
                logger.debug("解除 WebView2 缩放监听器失败", exc_info=True)

    def change(self, action: str) -> int:
        action = str(action or "").strip().lower()
        if action not in {"in", "out", "reset"}:
            raise ValueError("不支持的缩放操作")

        with self._lock:
            if self._native_webview is None or self._closed:
                raise RuntimeError("桌面缩放尚未就绪")
            percent = next_zoom_percent(self._current_percent, action)
            self._current_percent = percent
            if self._zoom_event is not None:
                self._pending_native_percent = percent

        try:
            save_zoom_preference(self.settings_path, percent)
        except OSError:
            logger.warning("保存桌面缩放比例失败", exc_info=True)

        def apply() -> None:
            self._set_native_percent(percent)
            self._queue_notification(percent)

        self._dispatch_gui(apply)
        return percent

    def _dispatch_gui(self, callback: Callable[[], None]) -> None:
        if self.gui_scheduler is not None:
            self.gui_scheduler(callback)
            return
        if self.platform_key == "windows":
            native_window = self._native_window
            if native_window is None:
                raise RuntimeError("Windows 桌面窗口不可用")
            if getattr(native_window, "InvokeRequired", False):
                from System import Func, Type

                native_window.Invoke(Func[Type](callback))
            else:
                callback()
            return
        if self.platform_key == "macos":
            from PyObjCTools import AppHelper

            AppHelper.callAfter(callback)
            return
        raise RuntimeError("当前平台不支持桌面缩放")

    def _set_native_percent(self, percent: int) -> None:
        with self._lock:
            native_webview = self._native_webview
        if native_webview is None:
            return
        factor = normalize_zoom_percent(percent) / 100
        if self.platform_key == "windows":
            native_webview.ZoomFactor = factor
        elif self.platform_key == "macos":
            native_webview.setPageZoom_(factor)

    def _on_zoom_factor_changed(self, sender, _event_args=None) -> None:
        try:
            percent = normalize_zoom_percent(float(sender.ZoomFactor) * 100, default=-1)
        except (AttributeError, TypeError, ValueError, OverflowError):
            percent = -1
        if not MIN_ZOOM_PERCENT <= percent <= MAX_ZOOM_PERCENT:
            logger.warning("WebView2 返回了无效缩放比例")
            return

        with self._lock:
            if self._native_webview is None:
                return
            pending = self._pending_native_percent
            self._pending_native_percent = None
            self._current_percent = percent
        if pending == percent:
            return

        try:
            save_zoom_preference(self.settings_path, percent)
        except OSError:
            logger.warning("保存 WebView2 缩放比例失败", exc_info=True)
        self._queue_notification(percent)

    def _queue_notification(self, percent: int) -> None:
        with self._lock:
            if self._native_webview is None:
                return
            self._generation += 1
            generation = self._generation
        try:
            self.notification_scheduler(lambda: self._notify_if_current(generation, percent))
        except Exception:
            logger.exception("调度桌面缩放比例提示失败")

    def _notify_if_current(self, generation: int, percent: int) -> None:
        with self._lock:
            if generation != self._generation or self._native_webview is None:
                return
        try:
            self.window.evaluate_js(zoom_changed_script(percent))
        except Exception:
            logger.warning("通知前端显示缩放比例失败", exc_info=True)
