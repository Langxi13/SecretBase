from __future__ import annotations

import ast
import plistlib
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_desktop_package import PackageValidationError, verify_package  # noqa: E402
from verify_macos_package import MacPackageValidationError, verify_macos_package  # noqa: E402


def create_valid_package(root: Path) -> Path:
    package = root / "SecretBase"
    (package / "_internal" / "frontend").mkdir(parents=True)
    (package / "LICENSE.txt").write_text("test license", encoding="ascii")
    (package / "SecretBase.exe").write_bytes(b"desktop-test")
    (package / "SecretBase.exe.config").write_text("<configuration />", encoding="ascii")
    (package / "_internal" / "frontend" / "index.html").write_text("<div id=\"app\"></div>", encoding="utf-8")
    return package


def create_valid_macos_app(root: Path) -> Path:
    app = root / "SecretBase.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "Frameworks" / "frontend").mkdir(parents=True)
    (app / "Contents" / "Resources").mkdir(parents=True)
    executable = app / "Contents" / "MacOS" / "SecretBase"
    if sys.platform == "darwin":
        shutil.copy2(sys.executable, executable)
    else:
        executable.write_bytes(b"macos-test")
    (app / "Contents" / "Frameworks" / "frontend" / "index.html").write_text(
        '<div id="app"></div>', encoding="utf-8"
    )
    (app / "Contents" / "Resources" / "LICENSE.txt").write_text("test license", encoding="ascii")
    with (app / "Contents" / "Info.plist").open("wb") as file:
        plistlib.dump(
            {
                "CFBundleIdentifier": "io.github.langxi13.secretbase",
                "LSMinimumSystemVersion": "13.0",
            },
            file,
        )
    return app


def app_version() -> str:
    module = ast.parse((ROOT / "backend" / "version.py").read_text(encoding="utf-8"))
    assignment = next(node for node in module.body if isinstance(node, ast.Assign))
    return ast.literal_eval(assignment.value)


def test_desktop_dependency_pins() -> None:
    requirements = (ROOT / "desktop" / "requirements.txt").read_text(encoding="ascii")
    assert "-r ../backend/requirements.txt" in requirements
    assert "pywebview==6.2.1" in requirements
    assert "pyinstaller==6.21.0" in requirements
    assert 'pystray==0.19.5; sys_platform == "win32"' in requirements
    assert "Pillow==12.3.0" in requirements
    assert "six==1.17.0" in requirements
    assert 'pythonnet==3.0.5; sys_platform == "win32"' in requirements
    assert 'clr_loader==0.2.10; sys_platform == "win32"' in requirements
    assert 'pyobjc-core==12.2.1; sys_platform == "darwin"' in requirements
    assert 'pyobjc-framework-Cocoa==12.2.1; sys_platform == "darwin"' in requirements
    assert 'pyobjc-framework-WebKit==12.2.1; sys_platform == "darwin"' in requirements


def test_spec_only_collects_public_runtime_assets() -> None:
    spec = (ROOT / "desktop" / "SecretBase.spec").read_text(encoding="utf-8")
    assert '(str(ROOT / "frontend"), "frontend")' in spec
    assert "backend/.env" not in spec
    assert "backend/data" not in spec
    assert 'console=False' in spec
    assert '"webview.platforms.mshtml"' in spec
    assert "icon=str(executable_icon)" in spec
    assert '"pythonnet": "3.0.5"' in spec
    assert '"clr-loader": "0.2.10"' in spec
    assert '"pystray": "0.19.5"' in spec
    assert '"Pillow": "12.3.0"' in spec
    assert '"six": "1.17.0"' in spec
    assert '"pystray._win32"' in spec
    assert '"webview.platforms.cocoa"' in spec
    assert '"pyobjc-core": "12.2.1"' in spec
    assert 'bundle_identifier="io.github.langxi13.secretbase"' in spec
    assert '"LSMinimumSystemVersion": "13.0"' in spec
    assert "target_arch=target_arch" in spec
    assert '"PIL.Image"' in spec
    assert '(str(DESKTOP_DIR / "assets" / "secretbase.ico"), "desktop/assets")' in spec


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


def test_windows_app_config_allows_downloaded_managed_runtime() -> None:
    app_config = (ROOT / "desktop" / "SecretBase.exe.config").read_text(encoding="ascii")
    assert '<loadFromRemoteSources enabled="true" />' in app_config


def test_build_script_is_ascii_and_runs_post_build_checks() -> None:
    build_script = (ROOT / "scripts" / "build-desktop-windows.ps1").read_bytes()
    build_script.decode("ascii")
    text = build_script.decode("ascii")
    assert "--self-test" in text
    assert "--desktop-runtime-self-test" in text
    assert "Start-Process -FilePath $Executable" in text
    assert "-Wait -PassThru" in text
    assert "--data-root self-test-data --report self-test-report.json" in text
    assert "-WorkingDirectory $BuildRoot" in text
    assert "SecretBase.exe.config" in text
    assert "verify_desktop_package.py" in text
    assert "SecretBase.generated.iss" in text
    assert "ChineseSimplified.isl" in text
    assert "/DMyLanguageFile" in text
    assert "sign-windows-artifacts.ps1" in text
    assert "windows-x64-setup.exe" in text
    assert "ISCC.exe" in text
    assert "SHA256SUMS.txt" in text
    assert '$Checksum = "$ArchiveHash  $ArchiveName`n$InstallerHash  $InstallerName`n"' in text
    assert re.search(r"sys\.version_info\[:2\].*\(3, 11\)", text)
    assert "sys.maxsize > 2**32" in text
    assert "struct.calcsize" not in text

    app_source = (ROOT / "desktop" / "app.py").read_text(encoding="utf-8")
    assert '"--shutdown-existing"' in app_source
    assert '"--wait-for-shutdown-self-test"' in app_source
    assert "request_existing_process_exit" in app_source
    assert "min_size=(360, 320)" in app_source
    assert "min_size=(960, 640)" not in app_source
    assert "resizable=True" in app_source
    assert "zoomable=True" in app_source
    assert "DesktopZoomMonitor" in app_source
    assert "window.events.loaded += zoom_monitor.attach" in app_source
    assert "close_preferences_setter=lifecycle.set_close_preferences" in app_source
    assert "close_request_resolver=lifecycle.resolve_close_request" in app_source


def test_windows_workflows_build_once_and_retest_downloaded_artifact() -> None:
    reusable = (ROOT / ".github" / "workflows" / "reusable-windows-desktop.yml").read_text(encoding="utf-8")
    desktop = (ROOT / ".github" / "workflows" / "windows-desktop.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "runs-on: windows-2022" in reusable
    assert "runs-on: windows-2025" in reusable
    assert "actions/upload-artifact@v7" in reusable
    assert "actions/download-artifact@v8" in reusable
    assert "choco install innosetup --version=6.7.1" in reusable
    assert "build-desktop-windows.ps1 -SkipDependencyInstall" in reusable
    assert "SecretBase\\SecretBase.exe" in reusable
    assert "Start-Process -FilePath $Executable" in reusable
    assert "-Wait -PassThru" in reusable
    assert "--desktop-runtime-self-test" in reusable
    assert "Zone.Identifier" in reusable
    assert "Unblock-File -LiteralPath $InstallerPath" in reusable
    assert "Python.Runtime.dll" in reusable
    assert "SecretBase-v*-windows-x64-setup.exe" in reusable
    assert "test-windows-installer.ps1" in reusable
    assert "secretbase-desktop-self-test.json" in reusable
    assert "secretbase-desktop-runtime*-self-test.json" in reusable
    assert "secretbase-installer*-self-test.json" in reusable
    assert "retention-days: 14" in desktop
    assert "uses: ./.github/workflows/reusable-windows-desktop.yml" in desktop
    assert "needs: [verify, windows-desktop, macos-desktop]" in release
    assert "path: release-input/windows" in release
    assert "path: release-input/macos" in release
    assert "Prepare unified release assets" in release
    assert 'gh release create "$GITHUB_REF_NAME" release-assets/*' in release
    assert "gh release upload" in release


def test_macos_build_and_workflows_are_arm64_and_reproducible() -> None:
    build_script = (ROOT / "scripts" / "build-desktop-macos.sh").read_bytes()
    build_script.decode("ascii")
    text = build_script.decode("ascii")
    assert '"$(uname -m)" != "arm64"' in text
    assert 'MACOSX_DEPLOYMENT_TARGET="13.0"' in text
    assert 'SECRETBASE_TARGET_ARCH="arm64"' in text
    assert "iconutil -c icns" in text
    assert "--self-test" in text
    assert "--desktop-runtime-self-test" in text
    assert "verify_macos_package.py" in text
    assert "ditto -c -k --keepParent" in text
    assert "hdiutil create" in text
    assert "macos-arm64.dmg" in text
    assert "macos-arm64.zip" in text
    assert "SHA256SUMS.txt" in text

    reusable = (ROOT / ".github" / "workflows" / "reusable-macos-desktop.yml").read_text(encoding="utf-8")
    entry = (ROOT / ".github" / "workflows" / "macos-desktop.yml").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "runs-on: macos-15" in reusable
    assert 'test "$(uname -m)" = "arm64"' in reusable
    assert "build-desktop-macos.sh --skip-dependency-install" in reusable
    assert "actions/upload-artifact@v7" in reusable
    assert "actions/download-artifact@v8" in reusable
    assert "secretbase-macos-arm64" in reusable
    assert "verify_macos_package.py" in reusable
    assert "uses: ./.github/workflows/reusable-macos-desktop.yml" in entry
    assert "macos-15" in ci
    assert "macos-desktop:" in release


def test_macos_package_validator_accepts_public_app_and_rejects_private_data() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        app = create_valid_macos_app(root)
        assert len(verify_macos_package(app).files) == 4

        archive = root / "SecretBase.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            for path in app.rglob("*"):
                if path.is_file():
                    bundle.write(path, Path("SecretBase.app") / path.relative_to(app))
        assert len(verify_macos_package(archive).files) == 4

        private_file = app / "Contents" / "Frameworks" / "data" / "secretbase.enc"
        private_file.parent.mkdir(parents=True)
        private_file.write_bytes(b"private")
        try:
            verify_macos_package(app)
        except MacPackageValidationError as error:
            assert "secretbase.enc" in str(error)
        else:
            raise AssertionError("Private macOS app data must fail validation")


def test_installer_preserves_data_unless_delete_is_confirmed() -> None:
    installer = (ROOT / "desktop" / "installer" / "SecretBase.iss").read_text(encoding="utf-8")
    assert "AppId={{D03B47A4-2BF0-4891-B7A0-A792A5462978}" in installer
    assert 'MessagesFile: "{#MyLanguageFile}"' in installer
    assert "DefaultDirName={localappdata}\\Programs\\SecretBase" in installer
    assert "PrivilegesRequired=lowest" in installer
    assert "AppMutex=" not in installer
    assert "[UninstallRun]" in installer
    assert 'Parameters: "--shutdown-existing"' in installer
    assert 'Filename: "{sys}\\taskkill.exe"' in installer
    assert "Check: IsSecretBaseRunning" in installer
    assert "CheckForMutexes('Local\\SecretBase.Desktop.Mutex')" in installer
    assert "function PrepareToInstall" in installer
    assert "PurgeCheckBox.Checked := False" in installer
    assert "CompareText(Trim(ConfirmationEdit.Text), 'DELETE') = 0" in installer
    assert "{param:PURGEDATA|0}" in installer
    assert "{param:CONFIRMDELETE|}" in installer
    assert "DelTree(DataPath, True, True, True)" in installer
    assert "[UninstallDelete]" not in installer

    language = (ROOT / "desktop" / "installer" / "languages" / "ChineseSimplified.isl").read_text(
        encoding="utf-8"
    )
    assert "LanguageName=简体中文" in language
    assert "LanguageID=$0804" in language

    installer_test = (ROOT / "scripts" / "test-windows-installer.ps1").read_bytes()
    installer_test.decode("ascii")
    text = installer_test.decode("ascii")
    assert "Default uninstall removed SecretBase user data" in text
    assert "/PURGEDATA=1 /CONFIRMDELETE=DELETE" in text
    assert "--wait-for-shutdown-self-test" in text
    assert "did not stop the running SecretBase instance" in text
    assert "Confirmed uninstall did not remove" in text

    signing = (ROOT / "scripts" / "sign-windows-artifacts.ps1").read_bytes()
    signing.decode("ascii")
    signing_text = signing.decode("ascii")
    assert "WINDOWS_SIGNING_CERT_BASE64" in signing_text
    assert "WINDOWS_SIGNING_CERT_PASSWORD" in signing_text
    assert "Import-PfxCertificate" in signing_text
    assert "signtool.exe" in signing_text


def test_package_validator_accepts_clean_directory_and_archive() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        package = create_valid_package(root)
        assert len(verify_package(package).files) == 4

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
        test_windows_app_config_allows_downloaded_managed_runtime,
        test_build_script_is_ascii_and_runs_post_build_checks,
        test_windows_workflows_build_once_and_retest_downloaded_artifact,
        test_macos_build_and_workflows_are_arm64_and_reproducible,
        test_macos_package_validator_accepts_public_app_and_rejects_private_data,
        test_installer_preserves_data_unless_delete_is_confirmed,
        test_package_validator_accepts_clean_directory_and_archive,
        test_package_validator_rejects_private_runtime_files,
        test_package_validator_rejects_archive_traversal,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
