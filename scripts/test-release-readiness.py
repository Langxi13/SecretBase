from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def release_version() -> str:
    match = re.search(
        r'APP_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"',
        read("backend/version.py"),
    )
    if not match:
        raise AssertionError("backend/version.py 缺少有效 APP_VERSION")
    return match.group(1)


def test_version_is_centralized() -> None:
    release = release_version()
    version_source = read("backend/version.py")
    assert f'APP_VERSION = "{release}"' in version_source
    assert "version=APP_VERSION" in read("backend/main.py")
    assert '"version": APP_VERSION' in read("backend/routes/health.py")
    assert f"version: '{release}'" in read("frontend/secretbase-runtime-config.js")
    assert f"## {release} -" in read("CHANGELOG.md")


def test_runtime_dependencies_are_pinned() -> None:
    requirements = [
        line.strip()
        for line in read("backend/requirements.txt").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert requirements
    assert all("==" in requirement for requirement in requirements), requirements


def test_local_and_remote_release_entrypoints_exist() -> None:
    release_assessment = f"docs/release-assessment-v{release_version()}.md"
    required_paths = (
        "start-secretbase.cmd",
        "scripts/start-local.ps1",
        "scripts/start-local.sh",
        "scripts/run-release-checks.py",
        ".github/workflows/ci.yml",
        ".github/workflows/release.yml",
        ".github/workflows/macos-desktop.yml",
        "scripts/build-desktop-macos.sh",
        "scripts/macos-hdiutil.sh",
        "docs/v3.3-macos-desktop.md",
        "docs/manual-qa-checklist-v3.3.md",
        "docs/vault-format-v1.md",
        "docs/update-system.md",
        "docs/manual-qa-checklist-v5-updates.md",
        release_assessment,
        "tests/fixtures/vault-v1/manifest.json",
        "vault-core/Cargo.toml",
        "vault-core/Cargo.lock",
        ".github/workflows/reusable-vault-core.yml",
        "docs/release-assessment-v3.0.0.md",
    )
    for relative_path in required_paths:
        assert (ROOT / relative_path).is_file(), relative_path


def test_sensitive_runtime_files_are_not_tracked() -> None:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    tracked = set(result.stdout.splitlines())
    forbidden_patterns = (
        re.compile(r"^backend/\.env$"),
        re.compile(r"^backend/data/"),
        re.compile(r"^backend/logs/"),
        re.compile(r"^backups/"),
        re.compile(r"(?:^|/)secretbase\.enc$"),
        re.compile(r"\.bak$"),
    )
    violations = sorted(
        path
        for path in tracked
        if any(pattern.search(path) for pattern in forbidden_patterns)
    )
    assert not violations, violations


def test_android_update_permissions_are_release_gated() -> None:
    manifest = read("mobile/secretbase_app/android/app/src/main/AndroidManifest.xml")
    verifier = read("scripts/verify_android_apk.sh")
    required_permissions = (
        "android.permission.INTERNET",
        "android.permission.ACCESS_NETWORK_STATE",
        "android.permission.REQUEST_INSTALL_PACKAGES",
    )
    for permission in required_permissions:
        assert permission in manifest, permission
        assert permission in verifier, permission


def test_android_release_keeps_universal_and_abi_specific_packages() -> None:
    workflow = read(".github/workflows/reusable-android.yml")
    generator = read("scripts/generate-update-manifest.py")
    updater = read(
        "mobile/secretbase_app/lib/src/features/update/mobile_update_service.dart"
    )
    verifier = read("scripts/verify_android_apk.sh")
    for abi in ("armeabi-v7a", "arm64-v8a", "x86_64"):
        assert f"android-{abi}" in workflow, abi
        assert f'"android-{abi}"' in generator, abi
        assert f"'android-{abi}'" in updater, abi
    assert "android-universal" in workflow
    assert '"version_codes"' in workflow
    for library in ("libflutter.so", "libapp.so", "libsecretbase_mobile.so"):
        assert library in verifier, library


def main() -> None:
    tests = [
        test_version_is_centralized,
        test_runtime_dependencies_are_pinned,
        test_local_and_remote_release_entrypoints_exist,
        test_sensitive_runtime_files_are_not_tracked,
        test_android_update_permissions_are_release_gated,
        test_android_release_keeps_universal_and_abi_specific_packages,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
