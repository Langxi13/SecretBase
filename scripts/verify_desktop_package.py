from __future__ import annotations

import argparse
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


REQUIRED_FILES = {
    "LICENSE.txt",
    "SecretBase.exe",
    "_internal/frontend/index.html",
}
ALLOWED_ROOT_ITEMS = {"LICENSE.txt", "SecretBase.exe", "_internal"}
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


class PackageValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PackageInventory:
    files: tuple[PurePosixPath, ...]
    package_root: str | None = None


def normalize_member(value: str) -> PurePosixPath:
    normalized = value.replace("\\", "/").rstrip("/")
    if normalized.startswith("/") or (len(normalized) >= 2 and normalized[1] == ":"):
        raise PackageValidationError(f"Unsafe package path: {value}")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise PackageValidationError(f"Unsafe package path: {value}")
    return path


def directory_inventory(package_dir: Path) -> PackageInventory:
    root = package_dir.expanduser().resolve()
    if not root.is_dir():
        raise PackageValidationError(f"Package directory does not exist: {root}")
    files = tuple(
        PurePosixPath(path.relative_to(root).as_posix())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )
    return PackageInventory(files=files)


def archive_inventory(archive_path: Path) -> PackageInventory:
    archive = archive_path.expanduser().resolve()
    if not archive.is_file():
        raise PackageValidationError(f"Package archive does not exist: {archive}")
    with zipfile.ZipFile(archive) as bundle:
        members = tuple(normalize_member(info.filename) for info in bundle.infolist() if not info.is_dir())
    roots = {member.parts[0] for member in members}
    if roots != {"SecretBase"}:
        raise PackageValidationError("Archive must contain exactly one SecretBase root directory")
    files = tuple(PurePosixPath(*member.parts[1:]) for member in members)
    return PackageInventory(files=files, package_root="SecretBase")


def validate_inventory(inventory: PackageInventory) -> None:
    file_names = {path.as_posix() for path in inventory.files}
    missing = sorted(REQUIRED_FILES - file_names)
    if missing:
        raise PackageValidationError(f"Missing required package files: {', '.join(missing)}")

    root_items = {path.parts[0] for path in inventory.files if path.parts}
    unexpected_root_items = sorted(root_items - ALLOWED_ROOT_ITEMS)
    if unexpected_root_items:
        raise PackageValidationError(f"Unexpected package root items: {', '.join(unexpected_root_items)}")

    violations = []
    for path in inventory.files:
        lowered_parts = tuple(part.lower() for part in path.parts)
        lowered_name = path.name.lower()
        if lowered_name in FORBIDDEN_NAMES:
            violations.append(path.as_posix())
            continue
        if any(part in FORBIDDEN_PARTS for part in lowered_parts):
            violations.append(path.as_posix())
            continue
        if Path(lowered_name).suffix in FORBIDDEN_SUFFIXES:
            violations.append(path.as_posix())
            continue
        if lowered_name.startswith(("test-", "test_")) and Path(lowered_name).suffix in {".py", ".pyc", ".js"}:
            violations.append(path.as_posix())

    if violations:
        raise PackageValidationError(f"Forbidden files found in package: {', '.join(sorted(violations))}")


def verify_package(package_path: Path) -> PackageInventory:
    inventory = archive_inventory(package_path) if package_path.suffix.lower() == ".zip" else directory_inventory(package_path)
    validate_inventory(inventory)
    return inventory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a SecretBase Windows desktop package.")
    parser.add_argument("package", type=Path, help="Path to the SecretBase directory or ZIP archive.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        inventory = verify_package(args.package)
    except (PackageValidationError, OSError, zipfile.BadZipFile) as error:
        print(f"Desktop package verification failed: {error}", file=sys.stderr)
        return 1
    print(f"Desktop package verified: {len(inventory.files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
