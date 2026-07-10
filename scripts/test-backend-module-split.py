from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def line_count(relative_path: str) -> int:
    return len(read(relative_path).splitlines())


def assert_contains(content: str, needle: str, message: str) -> None:
    if needle not in content:
        raise AssertionError(message)


def assert_less_than(value: int, maximum: int, message: str) -> None:
    if value >= maximum:
        raise AssertionError(f"{message}: 当前 {value}，期望小于 {maximum}")


def main() -> None:
    aggregator = read("backend/routes/ai.py")
    transfer_aggregator = read("backend/routes/transfer.py")
    client = read("backend/ai_services/client.py")
    actions = read("backend/ai_services/actions.py")
    tag_governance = read("backend/ai_services/tag_governance.py")
    entry_service = read("backend/entry_service.py")

    required_files = [
        "backend/ai_services/__init__.py",
        "backend/ai_services/prompts.py",
        "backend/ai_services/client.py",
        "backend/ai_services/parsing.py",
        "backend/ai_services/organize.py",
        "backend/ai_services/actions.py",
        "backend/ai_services/tag_governance.py",
        "backend/routes/ai_settings.py",
        "backend/routes/ai_organize.py",
        "backend/routes/ai_actions.py",
        "backend/routes/ai_tags.py",
        "backend/routes/ai_parse.py",
        "backend/routes/transfer_common.py",
        "backend/routes/transfer_exports.py",
        "backend/routes/transfer_imports.py",
        "backend/routes/transfer_backups.py",
        "backend/entry_service.py",
        "backend/import_service.py",
        "backend/secure_settings.py",
    ]
    for relative_path in required_files:
        if not (ROOT / relative_path).is_file():
            raise AssertionError(f"AI 模块缺失：{relative_path}")

    assert_less_than(line_count("backend/routes/ai.py"), 100, "AI 聚合路由必须保持轻量")
    assert_less_than(line_count("backend/routes/transfer.py"), 80, "导入导出聚合路由必须保持轻量")
    assert_less_than(line_count("backend/routes/transfer_common.py"), 220, "导入导出共享辅助模块必须保持可审阅体量")
    assert_less_than(line_count("backend/routes/transfer_backups.py"), 220, "备份路由必须保持可审阅体量")
    assert_less_than(line_count("backend/entry_service.py"), 150, "条目服务必须保持单一职责体量")
    assert_less_than(line_count("backend/import_service.py"), 250, "明文导入服务必须保持可审阅体量")
    assert_less_than(line_count("backend/ai_services/actions.py"), 450, "AI 操作服务必须保持可审阅体量")
    assert_less_than(line_count("backend/ai_services/organize.py"), 400, "AI 整理服务必须保持可审阅体量")
    assert_less_than(line_count("backend/ai_services/client.py"), 300, "AI 客户端必须保持单一职责体量")
    assert_less_than(line_count("backend/storage.py"), 700, "加密存储核心不能继续无控制增长")

    for module_name in ("ai_settings", "ai_organize", "ai_actions", "ai_tags", "ai_parse"):
        assert_contains(aggregator, f"router.include_router({module_name}.router)", f"AI 聚合路由必须挂载 {module_name}")
    if "@router." in aggregator:
        raise AssertionError("AI 聚合路由不应继续承载具体接口实现")

    for module_name in ("transfer_exports", "transfer_imports", "transfer_backups"):
        assert_contains(
            transfer_aggregator,
            f"router.include_router({module_name}.router)",
            f"导入导出聚合路由必须挂载 {module_name}",
        )
    if "@router." in transfer_aggregator:
        raise AssertionError("导入导出聚合路由不应继续承载具体接口实现")

    assert_contains(client, "httpx.AsyncClient", "AI 上游 HTTP 调用必须集中在客户端模块")
    assert_contains(actions, "def apply_actions", "AI 操作计划的应用逻辑必须独立于路由")
    assert_contains(tag_governance, "def apply_tag_governance", "AI 标签治理的应用逻辑必须独立于路由")
    assert_contains(tag_governance, "if not tag or not _tag_exists", "过期标签治理建议不得意外创建标签")
    assert_contains(entry_service, "def add_entry", "条目写入逻辑必须独立于加密存储核心")

    print("PASS backend module split")


if __name__ == "__main__":
    main()
