from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable

try:
    from .runtime import DesktopPaths
except ImportError:
    from runtime import DesktopPaths


PACKAGE_REGISTRY_KEY = r"Software\SecretBase"
DIRECTORY_LABELS = {
    "data": "数据目录",
    "backups": "备份目录",
    "logs": "日志目录",
}


def _directory_map(paths: DesktopPaths) -> dict[str, Path]:
    return {
        "data": paths.root,
        "backups": paths.backups,
        "logs": paths.logs,
    }


def _path_is_writable(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "目录不存在"
    if not path.is_dir():
        return False, "路径不是目录"

    probe = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".secretbase-diagnostic-", dir=path, delete=False) as file:
            probe = Path(file.name)
            file.write(b"ok")
            file.flush()
            os.fsync(file.fileno())
        return True, "目录存在且可写"
    except OSError as error:
        error_code = getattr(error, "winerror", None) or error.errno
        suffix = f"（系统错误 {error_code}）" if error_code is not None else ""
        return False, f"目录不可写{suffix}"
    finally:
        if probe is not None:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass


def _redact_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    candidates = []
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        candidates.append((Path(local_app_data).expanduser().resolve(), "%LOCALAPPDATA%"))
    candidates.append((Path.home().expanduser().resolve(), "~"))

    for base, replacement in candidates:
        try:
            relative = resolved.relative_to(base)
        except ValueError:
            continue
        suffix = str(relative).replace("/", "\\")
        return replacement if not suffix or suffix == "." else f"{replacement}\\{suffix}"
    return "<自定义数据目录>"


def _installed_path() -> Path | None:
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PACKAGE_REGISTRY_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, "InstallPath")
        return Path(str(value)).expanduser().resolve()
    except (FileNotFoundError, OSError, ValueError):
        return None


def detect_package_type(executable: Path | None = None) -> str:
    if not getattr(sys, "frozen", False):
        return "source"
    executable_path = (executable or Path(sys.executable)).expanduser().resolve()
    installed_path = _installed_path()
    if installed_path is not None and executable_path.parent == installed_path:
        return "installed"
    return "portable"


def default_directory_opener(path: Path) -> None:
    if os.name != "nt":
        raise RuntimeError("目录快捷入口只支持 Windows 桌面版")
    os.startfile(str(path))  # type: ignore[attr-defined]


class DesktopDiagnostics:
    def __init__(
        self,
        *,
        paths: DesktopPaths,
        backend_url: str,
        version: str,
        renderer: str,
        backend_running: Callable[[], bool],
        directory_opener: Callable[[Path], None] = default_directory_opener,
    ) -> None:
        self.paths = paths
        self.backend_url = backend_url.rstrip("/")
        self.version = version
        self.renderer = renderer
        self.backend_running = backend_running
        self.directory_opener = directory_opener
        self.health_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def open_directory(self, kind: str) -> dict[str, str]:
        key = str(kind or "").strip().lower()
        directories = _directory_map(self.paths)
        if key not in directories:
            raise ValueError("不允许打开该目录")
        target = directories[key]
        target.mkdir(parents=True, exist_ok=True)
        self.directory_opener(target)
        return {"status": "opened", "kind": key}

    def _backend_check(self) -> dict[str, str]:
        if not self.backend_running():
            return {
                "key": "backend",
                "label": "本地服务",
                "status": "error",
                "message": "本地服务线程未运行",
            }
        try:
            request = urllib.request.Request(f"{self.backend_url}/health", headers={"Accept": "application/json"})
            with self.health_opener.open(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            health = payload.get("data") or {}
            if health.get("status") != "healthy":
                raise ValueError("健康状态异常")
            remote_version = str(health.get("version") or "")
            if remote_version != self.version:
                return {
                    "key": "backend",
                    "label": "本地服务",
                    "status": "warning",
                    "message": f"服务可用，但版本为 {remote_version or '未知'}",
                }
            return {
                "key": "backend",
                "label": "本地服务",
                "status": "ok",
                "message": "本地服务运行正常",
            }
        except Exception as error:
            return {
                "key": "backend",
                "label": "本地服务",
                "status": "error",
                "message": f"健康检查失败：{error}",
            }

    def collect(self) -> dict:
        directories = _directory_map(self.paths)
        checks = [self._backend_check()]
        renderer_ok = self.renderer == "edgechromium"
        checks.append({
            "key": "renderer",
            "label": "桌面渲染器",
            "status": "ok" if renderer_ok else "error",
            "message": "Edge WebView2 已加载" if renderer_ok else f"当前渲染器：{self.renderer or '未知'}",
        })

        directory_payload = {}
        for key, path in directories.items():
            writable, message = _path_is_writable(path)
            checks.append({
                "key": f"directory_{key}",
                "label": DIRECTORY_LABELS[key],
                "status": "ok" if writable else "error",
                "message": message,
            })
            directory_payload[key] = {
                "label": DIRECTORY_LABELS[key],
                "path": str(path),
                "support_path": _redact_path(path),
            }

        package_type = detect_package_type()
        status = "error" if any(item["status"] == "error" for item in checks) else "ok"
        system = {
            "name": platform.system() or "Windows",
            "release": platform.release() or "未知",
            "architecture": platform.machine() or "未知",
        }
        support_lines = [
            f"SecretBase {self.version}",
            f"运行方式：{package_type}",
            f"系统：{system['name']} {system['release']} {system['architecture']}",
            f"渲染器：{self.renderer or '未知'}",
            f"数据目录：{_redact_path(self.paths.root)}",
        ]
        support_lines.extend(
            f"{item['label']}：{item['status']} - {item['message']}" for item in checks
        )
        return {
            "status": status,
            "version": self.version,
            "package_type": package_type,
            "renderer": self.renderer,
            "system": system,
            "vault_initialized": self.paths.vault.exists(),
            "directories": directory_payload,
            "checks": checks,
            "support_summary": "\n".join(support_lines),
        }
