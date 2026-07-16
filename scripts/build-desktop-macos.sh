#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

SKIP_DEPENDENCY_INSTALL=false
if [[ "${1:-}" == "--skip-dependency-install" ]]; then
    SKIP_DEPENDENCY_INSTALL=true
elif [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--skip-dependency-install]" >&2
    exit 2
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "The macOS desktop package must be built on macOS." >&2
    exit 1
fi
if [[ "$(uname -m)" != "arm64" ]]; then
    echo "The V3.3 macOS package must be built on Apple Silicon arm64." >&2
    exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -c 'import platform, sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) and platform.machine() == "arm64" else 1)' || {
    echo "SecretBase macOS builds require arm64 Python 3.11." >&2
    exit 1
}

if [[ "$SKIP_DEPENDENCY_INSTALL" != true ]]; then
    "$PYTHON_BIN" -m pip install --disable-pip-version-check --progress-bar off \
        -r backend/requirements.txt -r desktop/requirements.txt
fi

VERSION="$($PYTHON_BIN -c 'import ast, pathlib; tree=ast.parse(pathlib.Path("backend/version.py").read_text()); print(ast.literal_eval(next(node for node in tree.body if isinstance(node, ast.Assign)).value))')"
BUILD_ROOT="$PROJECT_ROOT/.desktop-build/macos"
WORK_ROOT="$BUILD_ROOT/work"
DIST_ROOT="$BUILD_ROOT/dist"
ICONSET_ROOT="$BUILD_ROOT/SecretBase.iconset"
ICON_PATH="$BUILD_ROOT/secretbase.icns"
ARTIFACTS_ROOT="$PROJECT_ROOT/artifacts"
APP_PATH="$DIST_ROOT/SecretBase.app"
ZIP_NAME="SecretBase-v${VERSION}-macos-arm64.zip"
DMG_NAME="SecretBase-v${VERSION}-macos-arm64.dmg"
ZIP_PATH="$ARTIFACTS_ROOT/$ZIP_NAME"
DMG_PATH="$ARTIFACTS_ROOT/$DMG_NAME"
CHECKSUM_PATH="$ARTIFACTS_ROOT/SHA256SUMS.txt"

rm -rf "$BUILD_ROOT" "$ARTIFACTS_ROOT"
mkdir -p "$WORK_ROOT" "$DIST_ROOT" "$ICONSET_ROOT" "$ARTIFACTS_ROOT"

"$PYTHON_BIN" - "$PROJECT_ROOT/desktop/assets/secretbase.ico" "$ICONSET_ROOT" <<'PY'
from pathlib import Path
import sys
from PIL import Image

source = Image.open(sys.argv[1])
sizes = source.info.get("sizes") or {(source.width, source.height)}
largest = max(sizes, key=lambda item: item[0] * item[1])
image = source.ico.getimage(largest).convert("RGBA") if hasattr(source, "ico") else source.convert("RGBA")
targets = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}
output = Path(sys.argv[2])
for name, size in targets.items():
    image.resize((size, size), Image.Resampling.LANCZOS).save(output / name)
PY
iconutil -c icns "$ICONSET_ROOT" -o "$ICON_PATH"

export SECRETBASE_MACOS_ICON="$ICON_PATH"
export SECRETBASE_TARGET_ARCH="arm64"
export MACOSX_DEPLOYMENT_TARGET="13.0"
"$PYTHON_BIN" -m PyInstaller \
    --clean \
    --noconfirm \
    --distpath "$DIST_ROOT" \
    --workpath "$WORK_ROOT" \
    desktop/SecretBase.spec

if [[ ! -x "$APP_PATH/Contents/MacOS/SecretBase" ]]; then
    echo "PyInstaller did not create a runnable SecretBase.app." >&2
    exit 1
fi
mkdir -p "$APP_PATH/Contents/Resources"
cp LICENSE "$APP_PATH/Contents/Resources/LICENSE.txt"

SELF_TEST_ROOT="$BUILD_ROOT/self-test"
mkdir -p "$SELF_TEST_ROOT"
"$APP_PATH/Contents/MacOS/SecretBase" \
    --self-test \
    --data-root "$SELF_TEST_ROOT/data" \
    --report "$SELF_TEST_ROOT/self-test.json"
"$APP_PATH/Contents/MacOS/SecretBase" \
    --desktop-runtime-self-test \
    --report "$SELF_TEST_ROOT/runtime-self-test.json"
"$PYTHON_BIN" scripts/verify_macos_package.py "$APP_PATH"

ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
"$PYTHON_BIN" scripts/verify_macos_package.py "$ZIP_PATH"

DMG_ROOT="$BUILD_ROOT/dmg"
mkdir -p "$DMG_ROOT"
ditto "$APP_PATH" "$DMG_ROOT/SecretBase.app"
ln -s /Applications "$DMG_ROOT/Applications"
hdiutil create -quiet -volname "SecretBase" -srcfolder "$DMG_ROOT" -ov -format UDZO "$DMG_PATH"

MOUNT_ROOT="$BUILD_ROOT/mount"
mkdir -p "$MOUNT_ROOT"
hdiutil attach -quiet -readonly -nobrowse -mountpoint "$MOUNT_ROOT" "$DMG_PATH"
trap 'hdiutil detach -quiet "$MOUNT_ROOT" >/dev/null 2>&1 || true' EXIT
"$PYTHON_BIN" scripts/verify_macos_package.py "$MOUNT_ROOT/SecretBase.app"
hdiutil detach -quiet "$MOUNT_ROOT"
trap - EXIT

(
    cd "$ARTIFACTS_ROOT"
    shasum -a 256 "$DMG_NAME" "$ZIP_NAME" > "$(basename "$CHECKSUM_PATH")"
)

echo "macOS app: $APP_PATH"
echo "macOS DMG: $DMG_PATH"
echo "macOS ZIP: $ZIP_PATH"
echo "Checksums: $CHECKSUM_PATH"
