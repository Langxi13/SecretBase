# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


ROOT = Path(SPECPATH).resolve().parent
DESKTOP_DIR = ROOT / "desktop"
BACKEND_DIR = ROOT / "backend"

hidden_imports = [
    "main",
    "webview.platforms.edgechromium",
    "webview.platforms.win32",
    "webview.platforms.winforms",
]
hidden_imports.extend(collect_submodules("uvicorn"))

a = Analysis(
    [str(DESKTOP_DIR / "app.py")],
    pathex=[str(DESKTOP_DIR), str(BACKEND_DIR), str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "frontend"), "frontend")],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "cefpython3",
        "tkinter",
        "webview.platforms.android",
        "webview.platforms.cef",
        "webview.platforms.cocoa",
        "webview.platforms.gtk",
        "webview.platforms.mshtml",
        "webview.platforms.qt",
    ],
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
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(DESKTOP_DIR / "assets" / "secretbase.ico"),
    version=str(DESKTOP_DIR / "windows-version.txt"),
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
