from __future__ import annotations

import ctypes
import hashlib
import os
import socket
import sys
import tempfile
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Callable

try:
    from .platform_support import activate_application
except ImportError:
    from platform_support import activate_application


ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
SYNCHRONIZE = 0x00100000
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0
SW_RESTORE = 9
DEFAULT_MUTEX_NAME = "Local\\SecretBase.Desktop.Mutex"
DEFAULT_ACTIVATE_EVENT_NAME = "Local\\SecretBase.Desktop.Activate"
DEFAULT_EXIT_EVENT_NAME = "Local\\SecretBase.Desktop.Exit"
POSIX_LOCK_NAME = "instance.lock"


def _kernel32():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.OpenEventW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.OpenEventW.restype = wintypes.HANDLE
    kernel32.OpenMutexW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.OpenMutexW.restype = wintypes.HANDLE
    kernel32.CreateEventW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.SetEvent.argtypes = (wintypes.HANDLE,)
    kernel32.SetEvent.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    return kernel32


def _signal_named_event(event_name: str, attempts: int = 20) -> bool:
    if os.name != "nt":
        return False
    kernel32 = _kernel32()
    event = None
    for _attempt in range(attempts):
        event = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, event_name)
        if event:
            break
        time.sleep(0.05)
    if not event:
        return False
    try:
        return bool(kernel32.SetEvent(event))
    finally:
        kernel32.CloseHandle(event)


def _named_mutex_exists(mutex_name: str) -> bool:
    if os.name != "nt":
        return False
    kernel32 = _kernel32()
    mutex = kernel32.OpenMutexW(SYNCHRONIZE, False, mutex_name)
    if not mutex:
        return False
    kernel32.CloseHandle(mutex)
    return True


def _default_posix_data_root() -> Path:
    override = os.getenv("SECRETBASE_DESKTOP_DATA_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / "Library" / "Application Support" / "SecretBase").resolve()


def _posix_socket_path(data_root: Path) -> Path:
    digest = hashlib.sha256(str(data_root.expanduser().resolve()).encode("utf-8")).hexdigest()[:16]
    user_id = getattr(os, "getuid", lambda: 0)()
    return Path(tempfile.gettempdir()) / f"secretbase-{user_id}-{digest}.sock"


def _send_posix_command(data_root: Path, command: str) -> bool:
    socket_path = _posix_socket_path(data_root)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1.0)
            client.connect(str(socket_path))
            client.sendall(command.encode("ascii"))
        return True
    except OSError:
        return False


def _posix_instance_running(data_root: Path) -> bool:
    lock_path = data_root.expanduser().resolve() / POSIX_LOCK_NAME
    if not lock_path.exists():
        return False
    try:
        import fcntl

        with lock_path.open("a+") as lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            return False
    except OSError:
        return False


def request_existing_process_exit(timeout: float = 15.0, data_root: Path | None = None) -> bool:
    """Signal a running desktop instance and wait until it releases its mutex."""
    if os.name != "nt" and sys.platform != "darwin":
        return True
    if sys.platform == "darwin":
        root = (data_root or _default_posix_data_root()).expanduser().resolve()
        if not _posix_instance_running(root):
            return True
        if not _send_posix_command(root, "exit"):
            return not _posix_instance_running(root)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not _posix_instance_running(root):
                return True
            time.sleep(0.1)
        return not _posix_instance_running(root)
    if not _named_mutex_exists(DEFAULT_MUTEX_NAME):
        return True
    if not _signal_named_event(DEFAULT_EXIT_EVENT_NAME):
        return not _named_mutex_exists(DEFAULT_MUTEX_NAME)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _named_mutex_exists(DEFAULT_MUTEX_NAME):
            return True
        time.sleep(0.1)
    return not _named_mutex_exists(DEFAULT_MUTEX_NAME)


def _user32(enum_callback_type=None):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.restype = wintypes.BOOL
    if enum_callback_type is not None:
        user32.EnumWindows.argtypes = (enum_callback_type, wintypes.LPARAM)
        user32.EnumWindows.restype = wintypes.BOOL
    return user32


class SingleInstanceCoordinator:
    def __init__(
        self,
        mutex_name: str = DEFAULT_MUTEX_NAME,
        event_name: str = DEFAULT_ACTIVATE_EVENT_NAME,
        exit_event_name: str = DEFAULT_EXIT_EVENT_NAME,
        data_root: Path | None = None,
    ) -> None:
        self.mutex_name = mutex_name
        self.event_name = event_name
        self.exit_event_name = exit_event_name
        self.data_root = (data_root or _default_posix_data_root()).expanduser().resolve()
        self._mutex = None
        self._event = None
        self._exit_event = None
        self._listeners: list[threading.Thread] = []
        self._closed = threading.Event()
        self._posix_lock_file = None
        self._posix_server: socket.socket | None = None
        self._posix_socket_path: Path | None = None

    def acquire(self) -> bool:
        if os.name != "nt" and sys.platform != "darwin":
            return True

        if sys.platform == "darwin":
            import fcntl

            self.data_root.mkdir(parents=True, exist_ok=True)
            self.data_root.chmod(0o700)
            lock_path = self.data_root / POSIX_LOCK_NAME
            lock_file = lock_path.open("a+")
            os.chmod(lock_path, 0o600)
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                lock_file.close()
                _send_posix_command(self.data_root, "activate")
                return False

            socket_path = _posix_socket_path(self.data_root)
            socket_path.unlink(missing_ok=True)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                server.bind(str(socket_path))
                os.chmod(socket_path, 0o600)
                server.listen(4)
                server.settimeout(0.25)
            except Exception:
                server.close()
                socket_path.unlink(missing_ok=True)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
                raise
            self._posix_lock_file = lock_file
            self._posix_server = server
            self._posix_socket_path = socket_path
            return True

        kernel32 = _kernel32()
        ctypes.set_last_error(0)
        mutex = kernel32.CreateMutexW(None, False, self.mutex_name)
        if not mutex:
            raise OSError("无法创建 SecretBase 单实例互斥量")

        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            _signal_named_event(self.event_name)
            kernel32.CloseHandle(mutex)
            return False

        event = kernel32.CreateEventW(None, False, False, self.event_name)
        if not event:
            kernel32.CloseHandle(mutex)
            raise OSError("无法创建 SecretBase 激活事件")

        exit_event = kernel32.CreateEventW(None, False, False, self.exit_event_name)
        if not exit_event:
            kernel32.CloseHandle(event)
            kernel32.CloseHandle(mutex)
            raise OSError("无法创建 SecretBase 退出事件")

        self._mutex = mutex
        self._event = event
        self._exit_event = exit_event
        return True

    def _start_event_listener(self, event, callback: Callable[[], None], name: str) -> None:
        def listen() -> None:
            kernel32 = _kernel32()
            while not self._closed.is_set():
                result = kernel32.WaitForSingleObject(event, INFINITE)
                if self._closed.is_set():
                    return
                if result == WAIT_OBJECT_0:
                    callback()

        listener = threading.Thread(target=listen, name=name, daemon=True)
        self._listeners.append(listener)
        listener.start()

    def start_listener(
        self,
        callback: Callable[[], None],
        exit_callback: Callable[[], None] | None = None,
    ) -> None:
        if sys.platform == "darwin":
            if self._posix_server is None or self._listeners:
                return
            server = self._posix_server

            def listen() -> None:
                while not self._closed.is_set():
                    try:
                        connection, _address = server.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        return
                    with connection:
                        try:
                            command = connection.recv(32).decode("ascii", errors="ignore").strip()
                        except OSError:
                            continue
                    if command == "activate":
                        callback()
                    elif command == "exit" and exit_callback is not None:
                        exit_callback()

            listener = threading.Thread(target=listen, name="secretbase-posix-instance-listener", daemon=True)
            self._listeners.append(listener)
            listener.start()
            return

        if os.name != "nt" or not self._event or self._listeners:
            return
        self._start_event_listener(self._event, callback, "secretbase-activation-listener")
        if exit_callback is not None and self._exit_event:
            self._start_event_listener(self._exit_event, exit_callback, "secretbase-exit-listener")

    def close(self) -> None:
        if sys.platform == "darwin":
            self._closed.set()
            if self._posix_server is not None:
                try:
                    self._posix_server.close()
                except OSError:
                    pass
                self._posix_server = None
            for listener in self._listeners:
                if listener.is_alive():
                    listener.join(timeout=1)
            self._listeners.clear()
            if self._posix_socket_path is not None:
                self._posix_socket_path.unlink(missing_ok=True)
                self._posix_socket_path = None
            if self._posix_lock_file is not None:
                try:
                    import fcntl

                    fcntl.flock(self._posix_lock_file.fileno(), fcntl.LOCK_UN)
                finally:
                    self._posix_lock_file.close()
                    self._posix_lock_file = None
            return

        if os.name != "nt":
            return
        self._closed.set()
        kernel32 = _kernel32()
        if self._event:
            kernel32.SetEvent(self._event)
        if self._exit_event:
            kernel32.SetEvent(self._exit_event)
        for listener in self._listeners:
            if listener.is_alive():
                listener.join(timeout=1)
        self._listeners.clear()
        if self._event:
            kernel32.CloseHandle(self._event)
            self._event = None
        if self._exit_event:
            kernel32.CloseHandle(self._exit_event)
            self._exit_event = None
        if self._mutex:
            kernel32.CloseHandle(self._mutex)
            self._mutex = None


def focus_current_process_window(window) -> None:
    activate_application(window)

    if os.name != "nt":
        return

    process_id = os.getpid()
    target = None

    enum_callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @enum_callback_type
    def enum_window(hwnd, _lparam):
        nonlocal target
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == process_id and user32.IsWindowVisible(hwnd):
            target = hwnd
            return False
        return True

    user32 = _user32(enum_callback_type)
    user32.EnumWindows(enum_window, 0)
    if target:
        user32.ShowWindow(target, SW_RESTORE)
        user32.SetForegroundWindow(target)
