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
        tray_setter: Callable[[bool], bool] | None = None,
    ) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.save_dialog = save_dialog
        self.external_opener = external_opener
        self.diagnostics_provider = diagnostics_provider
        self.directory_opener = directory_opener
        self.update_checker = update_checker
        self.tray_setter = tray_setter
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

    def set_close_to_tray(self, enabled: bool) -> dict[str, str | bool]:
        if type(enabled) is not bool:
            raise ValueError("托盘设置必须是布尔值")
        if self.tray_setter is None:
            raise RuntimeError("当前运行环境不支持系统托盘")
        if not self.tray_setter(enabled):
            raise RuntimeError("系统托盘启动失败，已保持直接退出模式")
        return {"status": "updated", "enabled": enabled}
