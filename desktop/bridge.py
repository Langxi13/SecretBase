from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse


EXPORT_PATHS = {
    ("POST", "/export/encrypted"),
    ("POST", "/export/plain"),
}
BACKUP_DOWNLOAD_PATTERN = re.compile(r"^/backups/[^/]+/download/(?:encrypted|plain)$")


def validate_download_request(method: str, path: str) -> tuple[str, str]:
    normalized_method = str(method or "POST").upper()
    normalized_path = str(path or "")
    if not normalized_path.startswith("/") or "%2f" in normalized_path.lower():
        raise ValueError("不允许的桌面下载路径")
    if (normalized_method, normalized_path) in EXPORT_PATHS:
        return normalized_method, normalized_path
    if normalized_method == "GET" and BACKUP_DOWNLOAD_PATTERN.fullmatch(normalized_path):
        return normalized_method, normalized_path
    raise ValueError("该接口不允许通过桌面保存桥调用")


def safe_filename(value: str) -> str:
    filename = Path(str(value or "")).name.strip()
    if not filename or filename in {".", ".."} or filename != str(value).strip():
        raise ValueError("无效的下载文件名")
    return filename


class DesktopApi:
    def __init__(
        self,
        backend_url: str,
        save_dialog: Callable[[str], str | None],
        external_opener: Callable[[str], bool] = webbrowser.open,
        diagnostics_provider: Callable[[], dict] | None = None,
        directory_opener: Callable[[str], dict] | None = None,
        update_checker: Callable[[], dict] | None = None,
        close_preferences_setter: Callable[[bool, bool], bool] | None = None,
        close_request_resolver: Callable[[str, bool], dict] | None = None,
        zoom_changer: Callable[[str], int] | None = None,
    ) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.save_dialog = save_dialog
        self.external_opener = external_opener
        self.diagnostics_provider = diagnostics_provider
        self.directory_opener = directory_opener
        self.update_checker = update_checker
        self.close_preferences_setter = close_preferences_setter
        self.close_request_resolver = close_request_resolver
        self.zoom_changer = zoom_changer
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def save_download(self, request: dict) -> dict[str, str]:
        request = request if isinstance(request, dict) else {}
        method, path = validate_download_request(request.get("method", "POST"), request.get("path", ""))
        filename = safe_filename(request.get("filename", ""))
        destination = self.save_dialog(filename)
        if not destination:
            return {"status": "cancelled"}

        headers = {"X-SecretBase-Token": str(request.get("token") or "")}
        body = None
        if method != "GET":
            headers["Content-Type"] = "application/json"
            body = json.dumps(request.get("body") or {}, ensure_ascii=False).encode("utf-8")

        http_request = urllib.request.Request(
            f"{self.backend_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(http_request, timeout=60) as response:
                content = response.read()
        except urllib.error.HTTPError as error:
            try:
                payload = json.loads(error.read().decode("utf-8"))
                message = payload.get("message") or "导出失败"
            except Exception:
                message = "导出失败"
            raise RuntimeError(message) from error

        target = Path(destination).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=target.parent,
                delete=False,
            ) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, target)
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
        return {"status": "saved", "filename": target.name}

    def open_external(self, url: str) -> bool:
        parsed = urlparse(str(url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("仅允许打开 HTTP 或 HTTPS 链接")
        return bool(self.external_opener(parsed.geturl()))

    def get_diagnostics(self) -> dict:
        if self.diagnostics_provider is None:
            raise RuntimeError("当前运行环境不支持桌面诊断")
        return self.diagnostics_provider()

    def open_directory(self, kind: str) -> dict:
        if self.directory_opener is None:
            raise RuntimeError("当前运行环境不支持目录快捷入口")
        return self.directory_opener(kind)

    def check_for_updates(self) -> dict:
        if self.update_checker is None:
            raise RuntimeError("当前运行环境不支持更新检查")
        return self.update_checker()

    def set_close_preferences(self, close_to_tray: bool, confirm_close: bool) -> dict[str, str | bool]:
        if type(close_to_tray) is not bool or type(confirm_close) is not bool:
            raise ValueError("关闭设置必须是布尔值")
        if self.close_preferences_setter is None:
            raise RuntimeError("当前运行环境不支持关闭设置")
        if not self.close_preferences_setter(close_to_tray, confirm_close):
            raise RuntimeError("无法更新关闭设置")
        return {
            "status": "updated",
            "close_to_tray": close_to_tray,
            "confirm_close": confirm_close,
        }

    def resolve_close_request(self, action: str, remember: bool) -> dict:
        if action not in {"tray", "exit"}:
            raise ValueError("不支持的关闭操作")
        if type(remember) is not bool:
            raise ValueError("记住选择必须是布尔值")
        if self.close_request_resolver is None:
            raise RuntimeError("当前运行环境不支持关闭操作")
        return self.close_request_resolver(action, remember)

    def change_zoom(self, action: str) -> dict[str, str | int]:
        normalized = str(action or "").strip().lower()
        if normalized not in {"in", "out", "reset"}:
            raise ValueError("不支持的缩放操作")
        if self.zoom_changer is None:
            raise RuntimeError("当前运行环境不支持桌面缩放")
        return {
            "status": "updated",
            "action": normalized,
            "percent": self.zoom_changer(normalized),
        }
