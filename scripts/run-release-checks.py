from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_TESTS = [
    "scripts/test-backup-separation.py",
    "scripts/test-desktop-foundation.py",
    "scripts/test-desktop-app.py",
    "scripts/test-desktop-packaging.py",
    "scripts/v1-fake-smoke-test.py",
    "scripts/test-ai-organize.py",
    "scripts/test-ai-actions.py",
    "scripts/test-ai-tag-governance.py",
    "scripts/test-ai-timeouts.py",
    "scripts/test-field-hidden-semantics.py",
    "scripts/test-password-groups.py",
    "scripts/test-tag-entities.py",
    "scripts/test-vault-v1-compatibility.py",
    "scripts/test-sync-protocol-v1.py",
    "scripts/test-webdav-sync.py",
    "scripts/test-backend-module-split.py",
    "scripts/test-release-readiness.py",
    "scripts/test-script-compatibility.py",
    "scripts/test-update-manifest.py",
]


def run(command: list[str], cwd: Path = ROOT) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("未找到 Node.js，无法执行前端发布检查")
    cargo = shutil.which("cargo")
    if not cargo:
        raise RuntimeError("未找到 Cargo，无法执行同步协议兼容检查")

    run([sys.executable, "-m", "compileall", "-q", "backend", "desktop", "scripts"])
    run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT / "backend",
    )
    for test in PYTHON_TESTS:
        run([sys.executable, test])

    for test in sorted((ROOT / "scripts").glob("test-frontend-*.js")):
        run([node, str(test.relative_to(ROOT))])

    run([cargo, "test", "--locked", "--test", "sync_bundle"], cwd=ROOT / "vault-core")

    javascript_files = sorted((ROOT / "frontend" / "js").glob("*.js"))
    javascript_files.extend(sorted((ROOT / "frontend" / "js" / "controllers").glob("*.js")))
    for source in javascript_files:
        run([node, "--check", str(source.relative_to(ROOT))])

    run(["git", "diff", "--check"])
    print("PASS release checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
