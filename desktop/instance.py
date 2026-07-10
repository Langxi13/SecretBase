from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes
from typing import Callable


ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0
SW_RESTORE = 9


def _kernel32():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.OpenEventW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.OpenEventW.restype = wintypes.HANDLE
    kernel32.CreateEventW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.SetEvent.argtypes = (wintypes.HANDLE,)
    kernel32.SetEvent.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    return kernel32


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
        mutex_name: str = "Local\\SecretBase.Desktop.Mutex",
        event_name: str = "Local\\SecretBase.Desktop.Activate",
    ) -> None:
        self.mutex_name = mutex_name
        self.event_name = event_name
        self._mutex = None
        self._event = None
        self._listener: threading.Thread | None = None
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
            event = None
            for _attempt in range(20):
                event = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, self.event_name)
                if event:
                    break
                time.sleep(0.05)
            if event:
                kernel32.SetEvent(event)
                kernel32.CloseHandle(event)
            kernel32.CloseHandle(mutex)
            return False

        event = kernel32.CreateEventW(None, False, False, self.event_name)
        if not event:
            kernel32.CloseHandle(mutex)
            raise OSError("无法创建 SecretBase 激活事件")

        self._mutex = mutex
        self._event = event
        return True

    def start_listener(self, callback: Callable[[], None]) -> None:
        if os.name != "nt" or not self._event or self._listener:
            return

        def listen() -> None:
            kernel32 = _kernel32()
            while not self._closed.is_set():
                result = kernel32.WaitForSingleObject(self._event, INFINITE)
                if self._closed.is_set():
                    return
                if result == WAIT_OBJECT_0:
                    callback()

        self._listener = threading.Thread(target=listen, name="secretbase-activation-listener", daemon=True)
        self._listener.start()

    def close(self) -> None:
        if os.name != "nt":
            return
        self._closed.set()
        kernel32 = _kernel32()
        if self._event:
            kernel32.SetEvent(self._event)
        if self._listener and self._listener.is_alive():
            self._listener.join(timeout=1)
        if self._event:
            kernel32.CloseHandle(self._event)
            self._event = None
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
