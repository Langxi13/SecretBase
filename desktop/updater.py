from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

try:
    from .preferences import load_preferences, update_preferences
    from .update import check_for_updates
except ImportError:
    from preferences import load_preferences, update_preferences
    from update import check_for_updates


logger = logging.getLogger(__name__)
AUTO_CHECK_INTERVAL_SECONDS = 24 * 60 * 60
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
UPDATE_PREFERENCE_KEYS = {
    "auto_check": "desktop_update_auto_check",
    "auto_download": "desktop_update_auto_download",
    "last_check_at": "desktop_update_last_check_at",
}


def _default_preferences(settings_path: Path) -> dict[str, bool | float]:
    payload = load_preferences(settings_path)
    return {
        "auto_check": payload.get(UPDATE_PREFERENCE_KEYS["auto_check"]) is not False,
        "auto_download": payload.get(UPDATE_PREFERENCE_KEYS["auto_download"]) is not False,
        "last_check_at": float(payload.get(UPDATE_PREFERENCE_KEYS["last_check_at"]) or 0),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(DOWNLOAD_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DesktopUpdateManager:
    def __init__(
        self,
        *,
        current_version: str,
        platform: str,
        architecture: str,
        package_type: str,
        updates_dir: Path,
        settings_path: Path,
        exit_callback: Callable[[], None],
        opener=None,
        process_launcher: Callable[..., Any] = subprocess.Popen,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.current_version = current_version
        self.platform = platform
        self.architecture = architecture
        self.package_type = package_type
        self.updates_dir = updates_dir.expanduser().resolve()
        self.settings_path = settings_path
        self.exit_callback = exit_callback
        self.opener = opener or urllib.request.build_opener()
        self.process_launcher = process_launcher
        self.clock = clock
        self._lock = threading.RLock()
        self._cancel_download = threading.Event()
        self._shutdown = threading.Event()
        self._worker: threading.Thread | None = None
        self._asset: dict[str, Any] | None = None
        self._downloaded_path: Path | None = None
        preferences = _default_preferences(settings_path)
        self._state: dict[str, Any] = {
            "status": "idle",
            "current_version": current_version,
            "latest_version": None,
            "release_url": None,
            "manual_download_url": None,
            "notes": "",
            "install_supported": False,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "progress": 0,
            "message": "",
            "preferences": {
                "auto_check": preferences["auto_check"],
                "auto_download": preferences["auto_download"],
            },
            "last_check_at": preferences["last_check_at"],
        }
        self.updates_dir.mkdir(parents=True, exist_ok=True)
        self._reconcile_pending_update()

    def _reconcile_pending_update(self) -> None:
        pending = self.updates_dir / "pending-update.json"
        if not pending.is_file():
            return
        try:
            payload = json.loads(pending.read_text(encoding="utf-8"))
            expected = str(payload.get("version") or "")
            if expected == self.current_version:
                pending.unlink(missing_ok=True)
                self._state["message"] = "更新已安装完成"
            else:
                self._state["message"] = "上次更新未完成，可重新检查并安装"
        except (OSError, ValueError, json.JSONDecodeError):
            pending.unlink(missing_ok=True)

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._state))

    def set_preferences(self, auto_check: bool, auto_download: bool) -> dict[str, Any]:
        if type(auto_check) is not bool or type(auto_download) is not bool:
            raise ValueError("更新偏好必须是布尔值")
        update_preferences(
            self.settings_path,
            {
                UPDATE_PREFERENCE_KEYS["auto_check"]: auto_check,
                UPDATE_PREFERENCE_KEYS["auto_download"]: auto_download,
            },
        )
        with self._lock:
            self._state["preferences"] = {
                "auto_check": auto_check,
                "auto_download": auto_download,
            }
            return self.get_state()

    def start_background_check(self, *, delay: float = 8.0) -> bool:
        with self._lock:
            if not self._state["preferences"]["auto_check"]:
                return False
            elapsed = self.clock() - float(self._state.get("last_check_at") or 0)
            if (0 <= elapsed < AUTO_CHECK_INTERVAL_SECONDS) or self._worker_alive():
                return False
            self._state["status"] = "scheduled"

        def delayed() -> None:
            if self._shutdown.wait(max(0.0, delay)):
                return
            self.check(force=False)

        self._start_worker(delayed, name="secretbase-update-check")
        return True

    def check(self, *, force: bool = True) -> dict[str, Any]:
        with self._lock:
            if self._state["status"] in {"checking", "downloading", "installing"}:
                return self.get_state()
            if not force:
                if not self._state["preferences"]["auto_check"]:
                    if self._state["status"] == "scheduled":
                        self._state["status"] = "idle"
                    return self.get_state()
                elapsed = self.clock() - float(self._state.get("last_check_at") or 0)
                if 0 <= elapsed < AUTO_CHECK_INTERVAL_SECONDS:
                    return self.get_state()
            self._state.update({"status": "checking", "message": "", "progress": 0})

        result = check_for_updates(
            self.current_version,
            platform=self.platform,
            architecture=self.architecture,
            package_type=self.package_type,
            opener=self.opener,
        )
        checked_at = self.clock()
        update_preferences(self.settings_path, {UPDATE_PREFERENCE_KEYS["last_check_at"]: checked_at})
        with self._lock:
            self._state.update({
                key: result.get(key)
                for key in (
                    "status",
                    "latest_version",
                    "release_url",
                    "manual_download_url",
                    "notes",
                    "install_supported",
                    "message",
                )
            })
            self._state["last_check_at"] = checked_at
            self._asset = result.get("asset") if result.get("install_supported") else None
            self._downloaded_path = None
            if self._asset is not None:
                self._state["total_bytes"] = int(self._asset["size"])
            if result.get("status") == "available" and self._asset is not None:
                cached = self._asset_path(self._asset)
                if self._valid_download(cached, self._asset):
                    self._downloaded_path = cached
                    self._state.update({
                        "status": "ready",
                        "downloaded_bytes": self._asset["size"],
                        "progress": 100,
                    })
                elif self._state["preferences"]["auto_download"]:
                    self._start_download_locked()
            return self.get_state()

    def start_download(self) -> dict[str, Any]:
        with self._lock:
            if self._asset is None or not self._state.get("install_supported"):
                raise RuntimeError("当前版本不支持应用内下载更新")
            if self._state["status"] == "ready":
                return self.get_state()
            if self._worker_alive() or self._state["status"] == "downloading":
                return self.get_state()
            self._start_download_locked()
            return self.get_state()

    def _start_download_locked(self) -> None:
        self._cancel_download.clear()
        self._state.update({
            "status": "downloading",
            "downloaded_bytes": 0,
            "progress": 0,
            "message": "",
        })
        self._start_worker(self._download_worker, name="secretbase-update-download")

    def cancel_download(self) -> dict[str, Any]:
        self._cancel_download.set()
        with self._lock:
            if self._state["status"] == "downloading":
                self._state.update({"status": "available", "message": "更新下载已取消"})
            return self.get_state()

    def _download_worker(self) -> None:
        with self._lock:
            asset = dict(self._asset or {})
        if not asset:
            return
        target = self._asset_path(asset)
        temporary = target.with_suffix(target.suffix + ".part")
        target.parent.mkdir(parents=True, exist_ok=True)
        required_space = int(asset["size"]) * 2 + 64 * 1024 * 1024
        if shutil.disk_usage(target.parent).free < required_space:
            self._set_error("磁盘空间不足，无法下载更新")
            return
        try:
            request = urllib.request.Request(
                str(asset["url"]),
                headers={"User-Agent": f"SecretBase/{self.current_version}"},
            )
            downloaded = 0
            digest = hashlib.sha256()
            with self.opener.open(request, timeout=30) as response, temporary.open("wb") as output:
                while True:
                    if self._cancel_download.is_set():
                        raise InterruptedError("更新下载已取消")
                    chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    output.write(chunk)
                    digest.update(chunk)
                    downloaded += len(chunk)
                    if downloaded > int(asset["size"]):
                        raise ValueError("下载文件超过清单大小")
                    with self._lock:
                        self._state["downloaded_bytes"] = downloaded
                        self._state["progress"] = min(99, int(downloaded * 100 / int(asset["size"])))
                output.flush()
                os.fsync(output.fileno())
            if downloaded != int(asset["size"]) or digest.hexdigest() != asset["sha256"]:
                raise ValueError("更新文件完整性校验失败")
            os.replace(temporary, target)
            with self._lock:
                self._downloaded_path = target
                self._state.update({
                    "status": "ready",
                    "downloaded_bytes": downloaded,
                    "progress": 100,
                    "message": "更新已下载，确认后即可安装",
                })
        except InterruptedError:
            temporary.unlink(missing_ok=True)
            with self._lock:
                if self._state["status"] == "downloading":
                    self._state.update({"status": "available", "message": "更新下载已取消"})
        except Exception as error:
            temporary.unlink(missing_ok=True)
            logger.warning("下载桌面更新失败: %s", error)
            self._set_error(f"更新下载失败：{error}")

    def install(self) -> dict[str, Any]:
        with self._lock:
            asset = dict(self._asset or {})
            downloaded = self._downloaded_path
            if self.platform != "windows" or self.package_type != "installed":
                raise RuntimeError("当前桌面版本不支持原地安装")
            if downloaded is None or not self._valid_download(downloaded, asset):
                raise RuntimeError("更新文件尚未准备完成")
            self._state.update({"status": "installing", "message": "正在启动安装程序"})

        pending_path = self.updates_dir / "pending-update.json"
        log_path = self.updates_dir / "installer.log"
        command = [
            str(downloaded),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/CLOSEAPPLICATIONS",
            "/AUTOUPDATE=1",
            f"/LOG={log_path}",
        ]
        try:
            pending_path.write_text(
                json.dumps({"version": self._state["latest_version"]}, ensure_ascii=False),
                encoding="utf-8",
            )
            self.process_launcher(command, close_fds=True)
        except Exception as error:
            pending_path.unlink(missing_ok=True)
            self._set_error(f"无法准备或启动更新安装程序：{error}")
            return self.get_state()

        timer = threading.Timer(0.35, self.exit_callback)
        timer.daemon = True
        timer.start()
        return self.get_state()

    def shutdown(self) -> None:
        self._shutdown.set()
        self._cancel_download.set()

    def _asset_path(self, asset: dict[str, Any]) -> Path:
        version = str(self._state.get("latest_version") or "unknown")
        return self.updates_dir / version / str(asset["filename"])

    @staticmethod
    def _valid_download(path: Path, asset: dict[str, Any]) -> bool:
        try:
            return path.is_file() and path.stat().st_size == int(asset["size"]) and _sha256(path) == asset["sha256"]
        except (OSError, KeyError, ValueError):
            return False

    def _worker_alive(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def _start_worker(self, callback: Callable[[], None], *, name: str) -> None:
        worker = threading.Thread(target=callback, name=name, daemon=True)
        self._worker = worker
        worker.start()

    def _set_error(self, message: str) -> None:
        with self._lock:
            self._state.update({"status": "error", "message": message})
