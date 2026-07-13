# SecretBase Android

SecretBase V5 Android 客户端是一个完全本地运行的 Flutter + Rust 密码库，不启动浏览器、Python、FastAPI 或本地 HTTP 服务。应用读写 Vault V1，并通过加密备份与 Web、Windows 和 macOS 版本迁移数据。

## 当前状态

- 最低 Android 10（API 29），目标 API 36。
- Flutter 3.44.6、Dart 3.12、Java 17、Rust 1.88.0、NDK 28.2、CMake 3.22.1。
- 核心功能已实现；`v5.0.0` 尚未发布，仍需 arm64 真机、跨桌面迁移和持久签名验收。
- Android CI 已通过 `armeabi-v7a`、`arm64-v8a`、`x86_64` 通用 APK 构建及 API 29/36 模拟器启动验证。

## 功能范围

- 创建、解锁、锁定、修改主密码、后台保护和设备锁屏立即锁定。
- 条目分页、搜索、筛选、详情、新建、编辑、复制模板和回收站。
- 条目、标签和密码组默认每页显示 5 条，可切换为 10、20 或 50 条，并在本机记住各自的分页偏好。
- 自定义字段可复制与隐藏；隐藏值在 Rust 列表接口中先行掩码。
- 标签分页、批量删除；密码组分页、增删改、筛选、成员关系和手动排序。
- 支持标准与大字体两种显示模式；窄屏筛选栏、条目卡片和密码组卡片使用紧凑布局。
- 加密备份导入导出、恢复记录和写入 revision 冲突保护。
- 文本解析、单条目标签整理、密码组整理、标签治理和自然语言操作计划。AI 建议必须由用户预览和确认后才能写入。

## 数据与隐私

Vault、恢复副本和加密 AI 配置保存在 Android 应用私有 `filesDir`。普通应用和文件管理器不能直接读取该目录；Android 卸载应用时会删除私有数据，因此卸载前必须先导出可用的加密备份。

应用禁止系统备份和明文网络流量，窗口启用 `FLAG_SECURE`。敏感剪贴板内容会标记为敏感并按用户设置自动清理。AI 默认只接受 HTTPS 地址，API Key 使用当前 Vault 会话派生的用途隔离密钥加密，不进入 Vault 备份。

## 本地检查

先安装 API 36、NDK 28.2、CMake 3.22.1，并为 Rust 1.88.0 安装 Android targets。低内存环境应保持单任务构建：

```bash
flutter pub get
flutter analyze
flutter test --concurrency=1

cd rust
CARGO_BUILD_JOBS=1 cargo test --locked --all-targets --all-features
CARGO_BUILD_JOBS=1 cargo clippy --locked --all-targets --all-features -- -D warnings
cd ..

CARGO_BUILD_JOBS=1 CARGOKIT_RUST_TOOLCHAIN=1.88.0 \
  flutter build apk --debug --target-platform android-arm64 --no-pub
```

验证 APK 的 Manifest、ABI 和构建路径：

```bash
../../scripts/verify_android_apk.sh \
  build/app/outputs/flutter-apk/app-debug.apk arm64-v8a
```

本机不要为了验证而同时构建三个 ABI；三架构 Release APK 与 API 29/36 模拟器交给 `.github/workflows/android.yml`。

## 正式签名

开发机可继续使用未提交的 `android/key.properties`。GitHub Actions 使用以下四个 Secrets，必须成套配置：

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

普通 CI 在未配置 Secrets 时生成 30 天有效的一次性测试密钥，产物文件名带 `-ci`，只能用于自动化和人工测试。正式发布必须手动运行 Android workflow 并启用 `require-release-signing`，缺少持久密钥时构建会失败。
