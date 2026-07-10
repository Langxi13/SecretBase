from __future__ import annotations

import ast
import re
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_desktop_package import PackageValidationError, verify_package  # noqa: E402


def create_valid_package(root: Path) -> Path:
    package = root / "SecretBase"
    (package / "_internal" / "frontend").mkdir(parents=True)
    (package / "LICENSE.txt").write_text("test license", encoding="ascii")
    (package / "SecretBase.exe").write_bytes(b"desktop-test")
    (package / "_internal" / "frontend" / "index.html").write_text("<div id=\"app\"></div>", encoding="utf-8")
    return package


def app_version() -> str:
    module = ast.parse((ROOT / "backend" / "version.py").read_text(encoding="utf-8"))
    assignment = next(node for node in module.body if isinstance(node, ast.Assign))
    return ast.literal_eval(assignment.value)


def test_desktop_dependency_pins() -> None:
    requirements = (ROOT / "desktop" / "requirements.txt").read_text(encoding="ascii")
    assert "-r ../backend/requirements.txt" in requirements
    assert "pywebview==6.2.1" in requirements
    assert "pyinstaller==6.21.0" in requirements


def test_spec_only_collects_public_runtime_assets() -> None:
    spec = (ROOT / "desktop" / "SecretBase.spec").read_text(encoding="utf-8")
    assert '(str(ROOT / "frontend"), "frontend")' in spec
    assert "backend/.env" not in spec
    assert "backend/data" not in spec
    assert 'console=False' in spec
    assert '"webview.platforms.mshtml"' in spec
    assert 'icon=str(DESKTOP_DIR / "assets" / "secretbase.ico")' in spec


def test_version_resources_match_application_version() -> None:
    version = app_version()
    resource = (ROOT / "desktop" / "windows-version.txt").read_text(encoding="ascii")
    assert f"StringStruct('FileVersion', '{version}')" in resource
    assert f"StringStruct('ProductVersion', '{version}')" in resource
    version_tuple = tuple(int(item) for item in version.split(".")) + (0,)
    assert f"filevers={version_tuple}".replace(" ", "") in resource.replace(" ", "")


def test_desktop_icon_contains_multiple_windows_sizes() -> None:
    icon = (ROOT / "desktop" / "assets" / "secretbase.ico").read_bytes()
    assert icon[:4] == b"\x00\x00\x01\x00"
    assert int.from_bytes(icon[4:6], "little") >= 7


def test_build_script_is_ascii_and_runs_post_build_checks() -> None:
    build_script = (ROOT / "scripts" / "build-desktop-windows.ps1").read_bytes()
    build_script.decode("ascii")
    text = build_script.decode("ascii")
    assert "--self-test" in text
    assert "verify_desktop_package.py" in text
    assert "SHA256SUMS.txt" in text
    assert re.search(r"sys\.version_info\[:2\].*\(3, 11\)", text)


def test_package_validator_accepts_clean_directory_and_archive() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        package = create_valid_package(root)
        assert len(verify_package(package).files) == 3

        archive = root / "SecretBase.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            for path in package.rglob("*"):
                if path.is_file():
                    bundle.write(path, Path("SecretBase") / path.relative_to(package))
        assert verify_package(archive).package_root == "SecretBase"


def test_package_validator_rejects_private_runtime_files() -> None:
    with tempfile.TemporaryDirectory() as raw:
        package = create_valid_package(Path(raw))
        private_file = package / "_internal" / "backend" / "data" / "secretbase.enc"
        private_file.parent.mkdir(parents=True)
        private_file.write_bytes(b"private")
        try:
            verify_package(package)
        except PackageValidationError as error:
            assert "secretbase.enc" in str(error)
        else:
            raise AssertionError("Private vault data must fail package validation")


def test_package_validator_rejects_archive_traversal() -> None:
    with tempfile.TemporaryDirectory() as raw:
        archive = Path(raw) / "unsafe.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("SecretBase/SecretBase.exe", b"test")
            bundle.writestr("SecretBase/_internal/frontend/index.html", b"test")
            bundle.writestr("SecretBase/../settings.json", b"private")
        try:
            verify_package(archive)
        except PackageValidationError as error:
            assert "Unsafe package path" in str(error)
        else:
            raise AssertionError("Archive traversal must fail package validation")


def main() -> None:
    tests = (
        test_desktop_dependency_pins,
        test_spec_only_collects_public_runtime_assets,
        test_version_resources_match_application_version,
        test_desktop_icon_contains_multiple_windows_sizes,
        test_build_script_is_ascii_and_runs_post_build_checks,
        test_package_validator_accepts_clean_directory_and_archive,
        test_package_validator_rejects_private_runtime_files,
        test_package_validator_rejects_archive_traversal,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
