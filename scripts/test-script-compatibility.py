from __future__ import annotations

import codecs
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def tracked_files(*patterns: str) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", *patterns],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return [ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def test_powershell_encoding() -> None:
    scripts = tracked_files("*.ps1")
    assert scripts
    for script in scripts:
        content = script.read_bytes()
        text = content.decode("utf-8-sig")
        if not text.isascii():
            assert content.startswith(codecs.BOM_UTF8), f"{script.relative_to(ROOT)} 必须使用 UTF-8 BOM"

    launcher = (ROOT / "scripts" / "start-local.ps1").read_bytes()
    assert launcher.startswith(codecs.BOM_UTF8), "Windows 启动脚本必须兼容 PowerShell 5.1"
    launcher_text = launcher.decode("utf-8-sig")
    assert '$env:PYTHONUTF8 = "1"' in launcher_text
    assert '$env:PYTHONIOENCODING = "utf-8"' in launcher_text
    assert '$env:PIP_PROGRESS_BAR = "off"' in launcher_text
    assert launcher_text.count("--progress-bar off") == 2


def test_cmd_encoding_and_entrypoint() -> None:
    scripts = tracked_files("*.cmd", "*.bat")
    assert scripts
    for script in scripts:
        script.read_bytes().decode("ascii")

    entrypoint = (ROOT / "start-secretbase.cmd").read_text(encoding="ascii").lower()
    assert "powershell.exe" in entrypoint
    assert "scripts\\start-local.ps1" in entrypoint


def test_shell_encoding_and_line_endings() -> None:
    scripts = tracked_files("*.sh")
    assert scripts
    for script in scripts:
        content = script.read_bytes()
        assert not content.startswith(codecs.BOM_UTF8), f"{script.relative_to(ROOT)} 不应包含 BOM"
        content.decode("utf-8")
        assert b"\r\n" not in content, f"{script.relative_to(ROOT)} 必须使用 LF 换行"


def test_git_attributes_define_script_line_endings() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="ascii").splitlines()
    assert "*.ps1 text eol=crlf" in attributes
    assert "*.cmd text eol=crlf" in attributes
    assert "*.bat text eol=crlf" in attributes
    assert "*.sh text eol=lf" in attributes
    assert "*.vault binary" in attributes


def test_workflows_exercise_real_windows_entrypoints() -> None:
    action = (ROOT / ".github" / "actions" / "verify-windows-bootstrap" / "action.yml").read_text(
        encoding="utf-8"
    )
    assert "git archive --format=zip" in action
    assert "start-secretbase.cmd" in action
    assert "shell: powershell" in action
    assert "shell: pwsh" in action
    assert "SecretBase 发布包 测试" in action

    for relative_path in (".github/workflows/ci.yml", ".github/workflows/release.yml"):
        workflow = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "uses: ./.github/actions/verify-windows-bootstrap" in workflow

    release_workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "needs: [vault-core, verify, windows-desktop, macos-desktop]" in release_workflow
    assert "uses: ./.github/workflows/reusable-vault-core.yml" in release_workflow
    assert "uses: ./.github/workflows/reusable-windows-desktop.yml" in release_workflow
    assert "uses: ./.github/workflows/reusable-macos-desktop.yml" in release_workflow


def main() -> None:
    tests = (
        test_powershell_encoding,
        test_cmd_encoding_and_entrypoint,
        test_shell_encoding_and_line_endings,
        test_git_attributes_define_script_line_endings,
        test_workflows_exercise_real_windows_entrypoints,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
