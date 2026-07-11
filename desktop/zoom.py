from __future__ import annotations

import json
import logging
import threading
from typing import Callable


logger = logging.getLogger(__name__)


def zoom_changed_script(percent: int) -> str:
    payload = json.dumps({"percent": percent}, separators=(",", ":"))
    return (
        "window.dispatchEvent(new CustomEvent('secretbase:desktop-zoom-changed', "
        f"{{ detail: {payload} }}));"
    )


class DesktopZoomMonitor:
    def __init__(
        self,
        window,
        *,
        action_scheduler: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        self.window = window
        self.action_scheduler = action_scheduler or self._schedule_action
        self._native_webview = None
        self._zoom_event = None
        self._generation = 0
        self._closed = False
        self._lock = threading.RLock()
        self._zoom_handler = self._on_zoom_factor_changed

    @staticmethod
    def _schedule_action(callback: Callable[[], None]) -> None:
        timer = threading.Timer(0.08, callback)
        timer.daemon = True
        timer.start()

    def attach(self) -> bool:
        native_window = getattr(self.window, "native", None)
        native_webview = getattr(native_window, "webview", None)
        zoom_event = getattr(native_webview, "ZoomFactorChanged", None)
        if native_webview is None or zoom_event is None:
            logger.warning("无法监听 WebView2 缩放比例")
            return False

        with self._lock:
            if self._closed:
                return False
            if self._native_webview is native_webview:
                return True
            if self._native_webview is not None:
                logger.warning("WebView2 缩放监听器已绑定到其他窗口")
                return False
            try:
                zoom_event += self._zoom_handler
            except Exception:
                self._native_webview = None
                self._zoom_event = None
                logger.exception("绑定 WebView2 缩放监听器失败")
                return False
            self._native_webview = native_webview
            self._zoom_event = zoom_event
            return True

    def detach(self) -> None:
        with self._lock:
            zoom_event = self._zoom_event
            self._native_webview = None
            self._zoom_event = None
            self._generation += 1
            self._closed = True

        if zoom_event is not None:
            try:
                zoom_event -= self._zoom_handler
            except Exception:
                logger.debug("解除 WebView2 缩放监听器失败", exc_info=True)

    def _on_zoom_factor_changed(self, sender, _event_args=None) -> None:
        try:
            percent = int(round(float(sender.ZoomFactor) * 100))
        except (AttributeError, TypeError, ValueError, OverflowError):
            logger.warning("WebView2 返回了无效缩放比例")
            return

        if not 25 <= percent <= 500:
            logger.warning("忽略超出范围的 WebView2 缩放比例: %s", percent)
            return

        with self._lock:
            if self._native_webview is None:
                return
            self._generation += 1
            generation = self._generation

        try:
            self.action_scheduler(lambda: self._notify_if_current(generation, percent))
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
