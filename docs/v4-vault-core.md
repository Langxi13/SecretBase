# SecretBase V4 共享 Vault 核心

本文档记录 V4.0 共享 Vault 核心准备阶段的范围、验收结果和后续交接边界。

状态：已完成。PR #4 已于 2026-07-12 合并到 `main`，合并提交为 `949616c`。Linux、Windows、macOS 发布检查、Rust 核心门禁、Windows 安装包复测、macOS 下载产物复测和 Apple Silicon 真机验证均已通过。

当前公开稳定版本仍为 `v3.3.0`。V4.0 是移动端之前的数据核心开发里程碑，没有单独改变 Web 或桌面交互，也尚未创建正式发布标签。

## 1. 已完成范围

- 固化 SecretBase Vault V1 二进制封装、JSON payload 和错误分类规范。
- 新增统一 Python Vault 文档编解码层，并接入解锁、保存、导入、导出和恢复流程。
- 保留根文档、条目和自定义字段中的未知 JSON 字段。
- 新增公开、可重复生成的 Python 黄金向量，覆盖空库、UTF-8、标签、密码组、回收站、隐藏字段和未知字段。
- 新增独立 `vault-core` Rust crate，提供头部检查、payload 校验、加密、解密和稳定错误码。
- 将 Rust 格式检查、Clippy 和 release 测试接入普通 CI 与正式 Release 门禁。

## 2. 兼容性边界

- 现有 Vault 继续使用 `SB01`、envelope version 1 和 payload version 1。
- 生产加密参数和字节布局未改变，V3 数据不需要迁移。
- 错误密码与认证标签损坏统一返回认证失败，避免暴露密码探测差异。
- Web、Windows 和 macOS 继续使用 Python 生产核心。
- Rust 核心只处理内存中的字节和结构化数据，不直接访问 FastAPI、文件锁、备份目录或用户数据目录。

## 3. 验收命令

```bash
python scripts/run-release-checks.py
cd vault-core
cargo fmt --check
cargo clippy --locked --all-targets --all-features -- -D warnings
cargo test --locked --release --all-features
```

GitHub CI 还会在 Windows Server 2022/2025 和 macOS 15 arm64 上构建并重新下载桌面产物，验证安装包、应用结构、架构、运行时和敏感文件扫描。

## 4. 明确非目标

V4.0 不包含 Flutter 工程、Android/iOS UI、Rust FFI、移动端文件持久化、桌面 Rust 替换、云同步、账号体系、浏览器自动填充或生物识别解锁。

## 5. 下一阶段交接

V4 已满足移动端启动条件：格式已规范化、Python 与 Rust 有共同黄金向量、错误边界稳定、跨平台门禁可重复执行。V5 将在不修改 Vault V1 的前提下，以 Android 为首个平台建立 Flutter + Rust 应用，详见 [V5 Android 实施计划](v5-android-plan.md)。
