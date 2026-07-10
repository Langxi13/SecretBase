from __future__ import annotations

import importlib
import json
import os
import socket
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable


SOURCE_ROOT = Path(__file__).resolve().parents[1]
LOCAL_URL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class DesktopStartupError(RuntimeError):
    """Raised when the local desktop backend cannot become healthy."""


@dataclass(frozen=True)
class DesktopPaths:
    root: Path
    data: Path
    backups: Path
    logs: Path
    vault: Path
    settings: Path
    secure_settings: Path
    webview: Path


def application_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and bundle_root:
        return Path(bundle_root).resolve()
    return SOURCE_ROOT


def bundled_backend_dir() -> Path:
    return application_root() / "backend"


def bundled_frontend_dir() -> Path:
    return application_root() / "frontend"


def choose_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def default_data_root() -> Path:
    override = os.getenv("SECRETBASE_DESKTOP_DATA_ROOT")
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform.startswith("win"):
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return (Path(local_app_data) / "SecretBase").resolve()

    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / "SecretBase").resolve()

    return (Path.home() / ".local" / "share" / "SecretBase").resolve()


def resolve_data_root(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return default_data_root()


def desktop_paths(data_root: Path) -> DesktopPaths:
    root = data_root.expanduser().resolve()
    data = root / "data"
    return DesktopPaths(
        root=root,
        data=data,
        backups=data / "backups",
        logs=root / "logs",
        vault=data / "secretbase.enc",
        settings=root / "settings.json",
        secure_settings=data / "secure-settings.enc",
        webview=root / "webview",
    )


def prepare_data_root(data_root: Path, *, include_webview: bool = False) -> DesktopPaths:
    paths = desktop_paths(data_root)
    directories = [paths.root, paths.data, paths.backups, paths.logs]
    if include_webview:
        directories.append(paths.webview)
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            directory.chmod(0o700)
    return paths


def build_desktop_env(data_root: Path, port: int) -> dict[str, str]:
    paths = desktop_paths(data_root)
    env = os.environ.copy()
    env.update({
        "SECRETBASE_MODE": "desktop",
        "SECRETBASE_FRONTEND_DIR": str(bundled_frontend_dir()),
        "HOST": "127.0.0.1",
        "PORT": str(port),
        "DATA_DIR": str(paths.data),
        "VAULT_PATH": str(paths.vault),
        "BACKUP_DIR": str(paths.backups),
        "LOG_DIR": str(paths.logs),
        "SETTINGS_PATH": str(paths.settings),
        "CORS_ORIGINS": f"http://127.0.0.1:{port}",
        "PYTHONPATH": str(bundled_backend_dir()),
        "PYTHONUNBUFFERED": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    return env


def apply_desktop_env(data_root: Path, port: int) -> dict[str, str]:
    env = build_desktop_env(data_root, port)
    os.environ.update(env)
    backend_dir = str(bundled_backend_dir())
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    return env


def config_snapshot(data_root: Path, port: int) -> dict[str, str | int]:
    paths = desktop_paths(data_root)
    return {
        "mode": "desktop",
        "host": "127.0.0.1",
        "port": port,
        "data_root": str(paths.root),
        "data_dir": str(paths.data),
        "vault_path": str(paths.vault),
        "backup_dir": str(paths.backups),
        "log_dir": str(paths.logs),
        "settings_path": str(paths.settings),
        "frontend_dir": str(bundled_frontend_dir()),
    }


def snapshot_json(data_root: Path, port: int) -> str:
    return json.dumps(config_snapshot(data_root, port), ensure_ascii=False, indent=2)


def wait_for_health(
    url: str,
    *,
    timeout: float = 20.0,
    is_running: Callable[[], bool] | None = None,
) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_running is not None and not is_running():
            return False
        try:
            with LOCAL_URL_OPENER.open(f"{url}/health", timeout=1) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


class InProcessDesktopServer:
    def __init__(self, data_root: Path, port: int | None = None) -> None:
        self.paths = desktop_paths(data_root)
        self.port = port or choose_free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self._server = None
        self._thread: threading.Thread | None = None
        self._main_module: ModuleType | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self, timeout: float = 20.0) -> str:
        if self.is_running:
            return self.url

        prepare_data_root(self.paths.root, include_webview=True)
        apply_desktop_env(self.paths.root, self.port)

        import uvicorn

        self._main_module = importlib.import_module("main")
        config = uvicorn.Config(
            self._main_module.app,
            host="127.0.0.1",
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(
            target=self._server.run,
            name="secretbase-desktop-backend",
            daemon=False,
        )
        self._thread.start()

        if not wait_for_health(self.url, timeout=timeout, is_running=lambda: self.is_running):
            self.stop()
            raise DesktopStartupError("SecretBase 本地后端未能在限定时间内启动")
        return self.url

    def stop(self, timeout: float = 8.0) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        if self._thread is not None and self._thread.is_alive() and self._server is not None:
            self._server.force_exit = True
            self._thread.join(timeout=2)

