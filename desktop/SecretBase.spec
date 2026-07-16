# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from importlib import metadata
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path(SPECPATH).resolve().parent
DESKTOP_DIR = ROOT / "desktop"
BACKEND_DIR = ROOT / "backend"

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"

expected_common_dependencies = {
    "certifi": "2026.4.22",
}
for package, expected_version in expected_common_dependencies.items():
    installed_version = metadata.version(package)
    if installed_version != expected_version:
        raise SystemExit(
            f"SecretBase.spec: {package} {installed_version} is not supported; "
            f"install the pinned {expected_version} release from desktop/requirements.txt."
        )

if IS_WINDOWS:
    expected_desktop_dependencies = {
        "pythonnet": "3.0.5",
        "clr-loader": "0.2.10",
        "pystray": "0.19.5",
        "Pillow": "12.3.0",
        "six": "1.17.0",
    }
    for package, expected_version in expected_desktop_dependencies.items():
        installed_version = metadata.version(package)
        if installed_version != expected_version:
            raise SystemExit(
                f"SecretBase.spec: {package} {installed_version} is not supported; "
                f"install the pinned {expected_version} release from desktop/requirements.txt."
            )
elif IS_MACOS:
    expected_macos_dependencies = {
        "pyobjc-core": "12.2.1",
        "pyobjc-framework-Cocoa": "12.2.1",
        "pyobjc-framework-Quartz": "12.2.1",
        "pyobjc-framework-WebKit": "12.2.1",
        "pyobjc-framework-Security": "12.2.1",
        "pyobjc-framework-UniformTypeIdentifiers": "12.2.1",
    }
    for package, expected_version in expected_macos_dependencies.items():
        installed_version = metadata.version(package)
        if installed_version != expected_version:
            raise SystemExit(
                f"SecretBase.spec: {package} {installed_version} is not supported; "
                f"install the pinned {expected_version} release from desktop/requirements.txt."
            )

hidden_imports = ["main", "PIL.Image"]
if IS_WINDOWS:
    hidden_imports.extend([
        "pystray._win32",
        "webview.platforms.edgechromium",
        "webview.platforms.win32",
        "webview.platforms.winforms",
    ])
elif IS_MACOS:
    hidden_imports.append("webview.platforms.cocoa")
hidden_imports.extend(collect_submodules("uvicorn"))

excludes = [
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    "cefpython3",
    "tkinter",
    "webview.platforms.android",
    "webview.platforms.cef",
    "webview.platforms.gtk",
    "webview.platforms.mshtml",
    "webview.platforms.qt",
]
if IS_WINDOWS:
    excludes.append("webview.platforms.cocoa")
elif IS_MACOS:
    excludes.extend([
        "webview.platforms.edgechromium",
        "webview.platforms.win32",
        "webview.platforms.winforms",
    ])

windows_icon = DESKTOP_DIR / "assets" / "secretbase.ico"
macos_icon = Path(os.getenv("SECRETBASE_MACOS_ICON", DESKTOP_DIR / "assets" / "secretbase.icns"))
executable_icon = macos_icon if IS_MACOS else windows_icon
target_arch = os.getenv("SECRETBASE_TARGET_ARCH") if IS_MACOS else None
runtime_data = [
    (str(ROOT / "frontend"), "frontend"),
    (str(DESKTOP_DIR / "assets" / "secretbase.ico"), "desktop/assets"),
]
runtime_data.extend(collect_data_files("certifi"))

a = Analysis(
    [str(DESKTOP_DIR / "app.py")],
    pathex=[str(DESKTOP_DIR), str(BACKEND_DIR), str(ROOT)],
    binaries=[],
    datas=runtime_data,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SecretBase",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=target_arch,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(executable_icon),
    version=str(DESKTOP_DIR / "windows-version.txt") if IS_WINDOWS else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SecretBase",
)

if IS_MACOS:
    app = BUNDLE(
        coll,
        name="SecretBase.app",
        icon=str(macos_icon),
        bundle_identifier="io.github.langxi13.secretbase",
        info_plist={
            "CFBundleDisplayName": "SecretBase",
            "CFBundleName": "SecretBase",
            "LSMinimumSystemVersion": "13.0",
            "NSHighResolutionCapable": True,
        },
    )
