from __future__ import annotations

import argparse
import plistlib
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


BUNDLE_ID = "io.github.langxi13.secretbase"
MINIMUM_MACOS_VERSION = "13.0"
FORBIDDEN_NAMES = {
    ".env",
    ".env.example",
    "secretbase.enc",
    "secure-settings.enc",
    "settings.json",
}
FORBIDDEN_PARTS = {
    ".git",
    ".github",
    "backups",
    "docs",
    "logs",
    "screenshots",
    "scripts",
}
FORBIDDEN_SUFFIXES = {".bak", ".enc", ".log"}


class MacPackageValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class MacPackageInventory:
    files: tuple[PurePosixPath, ...]
    plist: dict


def _safe_member(value: str) -> PurePosixPath:
    normalized = value.replace("\\", "/").rstrip("/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise MacPackageValidationError(f"Unsafe package path: {value}")
    return path


def _directory_inventory(app_path: Path) -> MacPackageInventory:
    app = app_path.expanduser().resolve()
    if not app.is_dir() or app.suffix != ".app":
        raise MacPackageValidationError(f"macOS app bundle does not exist: {app}")
    files = tuple(
        PurePosixPath(path.relative_to(app).as_posix())
        for path in sorted(app.rglob("*"))
        if path.is_file() or path.is_symlink()
    )
    plist_path = app / "Contents" / "Info.plist"
    if not plist_path.is_file():
        raise MacPackageValidationError("Missing Contents/Info.plist")
    with plist_path.open("rb") as file:
        plist = plistlib.load(file)
    return MacPackageInventory(files=files, plist=plist)


def _archive_inventory(archive_path: Path) -> MacPackageInventory:
    archive = archive_path.expanduser().resolve()
    if not archive.is_file() or archive.suffix.lower() != ".zip":
        raise MacPackageValidationError(f"macOS ZIP does not exist: {archive}")
    with zipfile.ZipFile(archive) as bundle:
        members = tuple(_safe_member(info.filename) for info in bundle.infolist() if not info.is_dir())
        roots = {member.parts[0] for member in members if member.parts[0] != "__MACOSX"}
        if roots != {"SecretBase.app"}:
            raise MacPackageValidationError("Archive must contain exactly one SecretBase.app root")
        app_members = tuple(
            PurePosixPath(*member.parts[1:])
            for member in members
            if member.parts[0] == "SecretBase.app"
        )
        plist_name = "SecretBase.app/Contents/Info.plist"
        try:
            plist = plistlib.loads(bundle.read(plist_name))
        except KeyError as error:
            raise MacPackageValidationError("Missing Contents/Info.plist") from error
    return MacPackageInventory(files=app_members, plist=plist)


def _validate_inventory(inventory: MacPackageInventory) -> None:
    names = {path.as_posix() for path in inventory.files}
    required = {"Contents/Info.plist", "Contents/MacOS/SecretBase"}
    missing = sorted(required - names)
    if missing:
        raise MacPackageValidationError(f"Missing required app files: {', '.join(missing)}")
    if not any(path.as_posix().endswith("frontend/index.html") for path in inventory.files):
        raise MacPackageValidationError("Bundled frontend/index.html is missing")
    if not any(path.as_posix().endswith("certifi/cacert.pem") for path in inventory.files):
        raise MacPackageValidationError("Bundled certifi/cacert.pem is missing")
    if not any(path.name == "LICENSE.txt" for path in inventory.files):
        raise MacPackageValidationError("Bundled LICENSE.txt is missing")

    violations = []
    for path in inventory.files:
        lowered_parts = tuple(part.lower() for part in path.parts)
        lowered_name = path.name.lower()
        if lowered_name in FORBIDDEN_NAMES:
            violations.append(path.as_posix())
        elif any(part in FORBIDDEN_PARTS for part in lowered_parts):
            violations.append(path.as_posix())
        elif Path(lowered_name).suffix in FORBIDDEN_SUFFIXES:
            violations.append(path.as_posix())
        elif lowered_name.startswith(("test-", "test_")) and Path(lowered_name).suffix in {".py", ".pyc", ".js"}:
            violations.append(path.as_posix())
    if violations:
        raise MacPackageValidationError(f"Forbidden files found in app: {', '.join(sorted(violations))}")

    plist = inventory.plist
    if plist.get("CFBundleIdentifier") != BUNDLE_ID:
        raise MacPackageValidationError("Unexpected CFBundleIdentifier")
    if plist.get("LSMinimumSystemVersion") != MINIMUM_MACOS_VERSION:
        raise MacPackageValidationError("Unexpected LSMinimumSystemVersion")


def _validate_arm64_executable(app_path: Path) -> None:
    if sys.platform != "darwin":
        return
    executable = app_path.expanduser().resolve() / "Contents" / "MacOS" / "SecretBase"
    result = subprocess.run(["lipo", "-archs", str(executable)], check=True, capture_output=True, text=True)
    architectures = result.stdout.strip().split()
    if architectures != ["arm64"]:
        raise MacPackageValidationError(f"Expected arm64 executable, found: {' '.join(architectures)}")


def verify_macos_package(package_path: Path) -> MacPackageInventory:
    path = package_path.expanduser().resolve()
    inventory = _archive_inventory(path) if path.suffix.lower() == ".zip" else _directory_inventory(path)
    _validate_inventory(inventory)
    if path.suffix == ".app":
        _validate_arm64_executable(path)
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a SecretBase macOS app bundle or ZIP archive.")
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    try:
        inventory = verify_macos_package(args.package)
    except (MacPackageValidationError, OSError, plistlib.InvalidFileException, zipfile.BadZipFile) as error:
        print(f"macOS package verification failed: {error}", file=sys.stderr)
        return 1
    print(f"macOS package verified: {len(inventory.files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
