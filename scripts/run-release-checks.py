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
    "scripts/v1-fake-smoke-test.py",
    "scripts/test-ai-organize.py",
    "scripts/test-ai-actions.py",
    "scripts/test-ai-tag-governance.py",
    "scripts/test-ai-timeouts.py",
    "scripts/test-field-hidden-semantics.py",
    "scripts/test-password-groups.py",
    "scripts/test-tag-entities.py",
    "scripts/test-backend-module-split.py",
    "scripts/test-release-readiness.py",
    "scripts/test-script-compatibility.py",
]


def run(command: list[str]) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("未找到 Node.js，无法执行前端发布检查")

    run([sys.executable, "-m", "compileall", "-q", "backend", "desktop", "scripts"])
    for test in PYTHON_TESTS:
        run([sys.executable, test])

    for test in sorted((ROOT / "scripts").glob("test-frontend-*.js")):
        run([node, str(test.relative_to(ROOT))])

    javascript_files = sorted((ROOT / "frontend" / "js").glob("*.js"))
    javascript_files.extend(sorted((ROOT / "frontend" / "js" / "controllers").glob("*.js")))
    for source in javascript_files:
        run([node, "--check", str(source.relative_to(ROOT))])

    run(["git", "diff", "--check"])
    print("PASS release checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
