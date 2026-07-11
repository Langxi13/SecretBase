from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes
from typing import Callable


ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
SYNCHRONIZE = 0x00100000
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0
SW_RESTORE = 9
DEFAULT_MUTEX_NAME = "Local\\SecretBase.Desktop.Mutex"
DEFAULT_ACTIVATE_EVENT_NAME = "Local\\SecretBase.Desktop.Activate"
DEFAULT_EXIT_EVENT_NAME = "Local\\SecretBase.Desktop.Exit"


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


def request_existing_process_exit(timeout: float = 15.0) -> bool:
    """Signal a running desktop instance and wait until it releases its mutex."""
    if os.name != "nt":
        return True
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
    ) -> None:
        self.mutex_name = mutex_name
        self.event_name = event_name
        self.exit_event_name = exit_event_name
        self._mutex = None
        self._event = None
        self._exit_event = None
        self._listeners: list[threading.Thread] = []
        self._closed = threading.Event()

    def acquire(self) -> bool:
        if os.name != "nt":
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
        if os.name != "nt" or not self._event or self._listeners:
            return
        self._start_event_listener(self._event, callback, "secretbase-activation-listener")
        if exit_callback is not None and self._exit_event:
            self._start_event_listener(self._exit_event, exit_callback, "secretbase-exit-listener")

    def close(self) -> None:
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
    try:
        window.show()
        window.restore()
    except Exception:
        pass

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
