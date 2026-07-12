from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DesktopPlatformProfile:
    key: str
    display_name: str
    renderer: str
    gui: str | None
    tray: bool
    native_zoom_feedback: bool

    @property
    def capabilities(self) -> dict[str, bool]:
        supported = self.key in {"windows", "macos"}
        return {
            "single_instance": supported,
            "directory_open": supported,
            "close_confirmation": supported,
            "tray": self.tray,
            "zoom_controls": self.native_zoom_feedback,
            "native_zoom_feedback": self.native_zoom_feedback,
        }


WINDOWS_PROFILE = DesktopPlatformProfile(
    key="windows",
    display_name="Windows",
    renderer="edgechromium",
    gui="edgechromium",
    tray=True,
    native_zoom_feedback=True,
)
MACOS_PROFILE = DesktopPlatformProfile(
    key="macos",
    display_name="macOS",
    renderer="wkwebview",
    gui="cocoa",
    tray=False,
    native_zoom_feedback=True,
)
UNSUPPORTED_PROFILE = DesktopPlatformProfile(
    key="unsupported",
    display_name=platform.system() or "Unknown",
    renderer="unknown",
    gui=None,
    tray=False,
    native_zoom_feedback=False,
)


def current_platform_profile() -> DesktopPlatformProfile:
    if sys.platform.startswith("win"):
        return WINDOWS_PROFILE
    if sys.platform == "darwin":
        return MACOS_PROFILE
    return UNSUPPORTED_PROFILE


def normalized_architecture(value: str | None = None) -> str:
    machine = str(value or platform.machine() or "unknown").strip().lower()
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    if machine in {"x86_64", "amd64", "x64"}:
        return "x64"
    return machine or "unknown"


def desktop_runtime_environment(*, shell: bool) -> dict[str, str]:
    profile = current_platform_profile()
    capabilities = profile.capabilities if shell else {}
    return {
        "SECRETBASE_DESKTOP_SHELL": "true" if shell else "false",
        "SECRETBASE_DESKTOP_PLATFORM": profile.key if shell else "",
        "SECRETBASE_DESKTOP_ARCHITECTURE": normalized_architecture() if shell else "",
        "SECRETBASE_DESKTOP_CAPABILITIES": json.dumps(capabilities, separators=(",", ":")),
    }


def open_directory(path: Path) -> None:
    resolved = path.expanduser().resolve()
    if sys.platform.startswith("win"):
        os.startfile(str(resolved))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.run(["open", str(resolved)], check=True)
        return
    raise RuntimeError("当前桌面平台不支持目录快捷入口")


def activate_application(window) -> None:
    try:
        window.show()
        window.restore()
    except Exception:
        pass

    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication

        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except Exception:
        pass


def _apple_script_string(value: str) -> str:
    parts = []
    for line in value.split("\n"):
        escaped = line.replace("\\", "\\\\").replace('"', '\\"')
        parts.append(f'"{escaped}"')
    return " & return & ".join(parts)


def show_native_message(title: str, message: str, *, error: bool = False, yes_no: bool = False) -> bool:
    if sys.platform.startswith("win"):
        import ctypes

        flags = 0x00000004 if yes_no else 0x00000000
        flags |= 0x00000010 if error else 0x00000040
        return ctypes.windll.user32.MessageBoxW(None, message, title, flags) == 6

    if sys.platform == "darwin":
        buttons = '{"打开下载页面", "取消"}' if yes_no else '{"好"}'
        default_button = ' default button "打开下载页面" cancel button "取消"' if yes_no else ""
        script = (
            f"display dialog {_apple_script_string(message)} "
            f"with title {_apple_script_string(title)} buttons {buttons}{default_button}"
        )
        result = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True)
        return yes_no and result.returncode == 0 and "打开下载页面" in result.stdout

    print(f"{title}: {message}", file=sys.stderr if error else sys.stdout)
    return False
