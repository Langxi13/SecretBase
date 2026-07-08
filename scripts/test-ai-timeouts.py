import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import routes.ai as ai_routes  # noqa: E402


def main() -> None:
    timeout = getattr(ai_routes, "AI_CHAT_TIMEOUT_SECONDS", None)
    assert timeout is not None, "AI 对话请求必须使用命名超时常量"
    assert timeout >= 120, f"AI 对话请求超时不能低于 120 秒，当前为 {timeout}"
    print("PASS ai timeouts")


if __name__ == "__main__":
    main()
