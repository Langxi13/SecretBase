from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = "5.0.1"


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_version_is_centralized() -> None:
    version_source = read("backend/version.py")
    assert f'APP_VERSION = "{RELEASE_VERSION}"' in version_source
    assert "version=APP_VERSION" in read("backend/main.py")
    assert '"version": APP_VERSION' in read("backend/routes/health.py")
    assert f"version: '{RELEASE_VERSION}'" in read("frontend/secretbase-runtime-config.js")
    assert f"## {RELEASE_VERSION} -" in read("CHANGELOG.md")


def test_runtime_dependencies_are_pinned() -> None:
    requirements = [
        line.strip()
        for line in read("backend/requirements.txt").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert requirements
    assert all("==" in requirement for requirement in requirements), requirements


def test_local_and_remote_release_entrypoints_exist() -> None:
    required_paths = (
        "start-secretbase.cmd",
        "scripts/start-local.ps1",
        "scripts/start-local.sh",
        "scripts/run-release-checks.py",
        ".github/workflows/ci.yml",
        ".github/workflows/release.yml",
        ".github/workflows/macos-desktop.yml",
        "scripts/build-desktop-macos.sh",
        "docs/v3.3-macos-desktop.md",
        "docs/manual-qa-checklist-v3.3.md",
        "docs/vault-format-v1.md",
        "docs/update-system.md",
        "docs/manual-qa-checklist-v5-updates.md",
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


def main() -> None:
    tests = [
        test_version_is_centralized,
        test_runtime_dependencies_are_pinned,
        test_local_and_remote_release_entrypoints_exist,
        test_sensitive_runtime_files_are_not_tracked,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
