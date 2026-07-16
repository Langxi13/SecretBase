import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import routes.ai as ai_routes  # noqa: E402


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def main() -> None:
    timeout = getattr(ai_routes, "AI_CHAT_TIMEOUT_SECONDS", None)
    assert timeout is not None, "AI 对话请求必须使用命名超时常量"
    assert timeout >= 120, f"AI 对话请求超时不能低于 120 秒，当前为 {timeout}"
    for relative_path in ("scripts/install.sh", "docs/deployment.md"):
        source = read(relative_path)
        assert "location /api/ai/" in source, f"{relative_path} 必须覆盖全部 AI 接口"
        assert "proxy_read_timeout 180s;" in source, f"{relative_path} 的 AI 读取超时必须高于上游默认值"
        assert "proxy_send_timeout 180s;" in source, f"{relative_path} 的 AI 发送超时必须高于上游默认值"
        assert "api/ai/(parse|organize/preview|tags/preview)" not in source, f"{relative_path} 不应只覆盖旧 AI 接口"
    print("PASS ai timeouts")


if __name__ == "__main__":
    main()
