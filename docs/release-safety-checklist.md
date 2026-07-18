# SecretBase 发布前数据安全检查清单

## 目的

SecretBase 已进入真实生产使用阶段。后续任何迭代默认不得破坏、迁移、清空、重写或隐式改变用户已有 vault 数据。

本清单用于每次发布前确认数据安全边界。

## 发布红线

- 不得在未获得用户明确确认的情况下删除 `backend/data/secretbase.enc`。
- 不得在未获得用户明确确认的情况下清空 `backend/data/backups/`。
- 不得在未获得用户明确确认的情况下升级 vault 文件格式。
- 不得自动重命名、合并、删除、规范化真实条目、标签或字段。
- 不得用生产 vault 运行会创建、修改、删除数据的测试脚本。
- 不得把主密码、Basic Auth 密码、session token、AI key 写入文档或日志。

## 发布前必须确认

- [ ] 本次变更是否涉及 vault 文件格式。
- [ ] 本次变更是否涉及 `Entry`、`FieldItem`、标签、回收站、备份、导入导出模型。
- [ ] 本次变更是否会自动写入、删除或迁移已有数据。
- [ ] 本次变更是否影响备份恢复流程。
- [ ] 本次变更是否影响解锁、自动锁定或 session token。
- [ ] 本次变更是否影响 nginx Basic Auth 或生产访问入口。
- [ ] 本次变更是否影响 AI 批量创建条目的行为。
- [ ] 本次测试是否只使用测试 vault 或空 vault。
- [ ] 如需生产验证，是否只执行只读检查或由用户在浏览器手动操作。
- [ ] Windows 发布包是否通过目录与 ZIP 敏感文件扫描。
- [ ] Windows 安装器是否通过安装后目录敏感文件扫描。
- [ ] Windows 发布包是否通过打包后 `--self-test`，且退出后无残留进程。
- [ ] 默认卸载是否保留 `%LOCALAPPDATA%\SecretBase`，双确认清除是否只删除该固定目录。
- [ ] 托盘隐藏前是否已锁定 vault、清除 session token，托盘退出后是否无残留进程。
- [ ] 关闭确认是否支持隐藏、退出、取消和“不再提醒”，设置切换是否不会立即启动托盘或锁死界面。
- [ ] Windows 窗口缩小到 `360 × 320` 时，关键操作是否仍可通过响应式布局和滚动访问。
- [ ] `SHA256SUMS.txt` 是否同时对应本次实际发布的 ZIP 和安装器。
- [ ] 签名更新清单和 `.sig` 是否通过内置公钥验证，三端文件大小与 SHA-256 是否一致。
- [ ] Windows 安装版更新是否先锁定 Vault，再通过相同 `AppId` 覆盖安装并只启动一个新实例。
- [ ] Windows 便携版和未签名 macOS 是否只提供正式下载链接，不尝试替换自身。
- [ ] macOS DMG 和 ZIP 是否只包含 arm64 `SecretBase.app`、公开运行资源和许可证。
- [ ] macOS 应用 Bundle ID、最低系统版本、WKWebView 自检和 Gatekeeper 真机流程是否已验证。
- [ ] Windows/macOS 键盘缩放、100% 重置、比例提示和重启恢复是否已真机验证。
- [ ] macOS 删除 `.app` 后是否保留应用支持目录，文档是否未暗示存在独立卸载器。
- [ ] Vault V1 Python 黄金向量和 Rust `fmt`、Clippy、release 测试是否全部通过。
- [ ] Rust 参考核心是否仍与 FastAPI、桌面打包和用户数据目录隔离。
- [ ] Vault envelope 是否保持 V1，未知根字段、条目字段和自定义字段是否能往返保留。
- [ ] 旧 Vault 缺少 `vault_id` 时是否仍原样往返，不会被写入 `vault_id: null`；首次启用同步后是否生成稳定 UUID。
- [ ] Sync Bundle V1 Python/Rust 黄金向量是否通过，错误密钥、篡改密文和错误 AAD 对象 ID 是否全部拒绝。
- [ ] WebDAV V1 能力测试是否要求 HTTPS、强 ETag、`If-Match`、`If-None-Match` 和条件删除，并清理探测对象和目录。
- [ ] WebDAV V2 能力测试是否要求 HTTPS、`PROPFIND` 和基础读写删除，允许缺少强 ETag，并通过不可变对象名、上传后读取校验和有限重试抵御弱一致性。
- [ ] V2 是否完整发现不可变快照 DAG，保留未处理并发分支，并拒绝把未知父快照或错误密钥对象导入 Vault。
- [ ] V2 是否拒绝超过 1000 个快照、累计 256 MiB 密文/解密历史或 32 个 frontier，且不会截断历史后继续合并。
- [ ] V2 压缩是否要求本机与远端内容基线一致，按条目 ID 集合比较顶层条目且保留字段顺序，清理失败是否不会破坏新空间。
- [ ] V2 远端清理是否在未知对象、并发新增或删除失败时停止；文档和 UI 是否未宣称弱 WebDAV 具备目录树原子 CAS，本机 Vault 是否始终保留。
- [ ] WebDAV 错误密码是否返回受控同步错误而不是 401，避免前端误锁定 SecretBase 会话。
- [ ] 同步冲突界面和 API 是否只展示标题、状态、时间、字段数量和变化区块，不包含字段值。
- [ ] 二维码、恢复码、配对 URI、WebDAV 密码和同步密钥是否不会写入日志、浏览器存储、诊断、文档或构建产物。
- [ ] 修改主密码后 `sync-settings.enc` 与 `sync-base.enc` 是否仍可读取；导入不同 `vault_id` 后是否自动停用旧同步。
- [ ] 密钥轮换是否只保留一个新历史版本、旧恢复码失效，并在本机配置保存失败时恢复旧密钥、原历史链和本机基线。
- [ ] 自动同步是否只在解锁、非同步写入后 5 秒、后台超过 60 秒返回和手动操作时触发，锁定后是否停止并清除敏感表单。
- [ ] Android 手动与自动同步是否共用全局互斥，锁定时是否取消活动 WebDAV 请求并清除 pending sync。
- [ ] Android 加入已在本机提交但首次合并上传失败时，是否保持已加入状态、清除未完成令牌并允许下次同步继续。
- [x] Android Flutter 分析、Widget 测试、移动端 Rust 测试和 Clippy 是否全部通过。
- [x] Android 三 ABI Release APK 是否包含对应的 `libsecretbase_mobile.so`，并通过 API 29/36 模拟器启动验证。
- [x] Android Manifest 是否保持 `allowBackup=false`、`usesCleartextTraffic=false`、API 29 最低版本和 `FLAG_SECURE` 运行时保护。
- [ ] Android 指纹解锁是否只保存 Keystore 加密的设备解锁密钥、不保存主密码，并在改密、导入、恢复和指纹变化后失效。
- [ ] Android V2 是否与 Web/桌面端使用同一加密协议、冲突语义、恢复码和压缩边界，并且同步配置与基线只保存在本机加密存储。
- [ ] Android 恢复码、历史恢复、密钥轮换、压缩和远端删除是否再次验证主密码；连接更新、轮换和删除的一次性令牌是否只能消费一次。
- [ ] Android AI 撤回是否受一次性令牌和 revision 约束，且任何后续 Vault 写入都会使旧撤回失效。
- [ ] Android 根页面双击返回退出是否不会截获弹窗、子页面和来源筛选的正常返回。
- [x] Android APK 是否通过 `scripts/verify_android_apk.sh`，且不含真实工作区、用户目录、私人域名、Vault 或签名密钥。
- [ ] 正式 Android APK 是否使用持久发布密钥；一次性 CI 密钥产物是否明确带 `-ci` 且未上传正式 Release。
- [ ] Android 更新是否拒绝错误包名、低 `versionCode`、错误哈希和非正式证书，并只允许缓存 `updates` 下的 APK。
- [ ] Android 的移动网络自动下载是否默认关闭，安装前是否锁定 Vault 并经过系统确认。
- [ ] Android 真机是否完成锁屏、后台超时、条目/标签/密码组、AI 确认、跨桌面备份和卸载删除私有数据验收。
- [ ] 统一 Release 是否同时包含当前版本的 Windows、macOS 与 Android 资产以及签名清单，避免更新入口缺少对应平台下载。
- [ ] 是否在 Windows 10/11 x64 真机完成独立窗口、原生导出和单实例验收。
- [ ] 是否在 Apple Silicon macOS 13+ 真机完成安装、导入导出、单实例、退出和数据保留验收。
- [ ] 正式标签是否与 `backend/version.py` 完全一致。

## 需要备份的情况

以下任何情况发生时，发布前必须先创建生产备份，并记录备份文件名和时间：

- 修改 `backend/crypto.py`、`backend/storage.py`、`backend/models.py`。
- 修改导入导出、备份恢复、标签批量处理、回收站清空相关逻辑。
- 修改会自动批量创建或删除条目的功能。
- 修改 vault 文件路径、备份路径或 systemd/nginx 生产配置。
- 用户明确要求清空、重置或迁移数据。

## 推荐验证顺序

1. 本地或测试 vault 跑自动测试。
2. 本地或测试 vault 做写入类 smoke test。
3. 生产只部署代码，不运行破坏性脚本。
4. 生产执行只读健康检查。
5. 如需生产写入验证，由用户在浏览器手动完成。
6. 验证通过后记录到 `docs/manual-qa-checklist.md`。

## 回滚要求

- 发布前保留可回滚的代码包或旧文件备份。
- 修改 nginx/systemd 前备份旧配置。
- 如果发布后出现写入异常，应先停止写入操作，不要反复重试。
- 如出现 `409 CONFLICT` 或 `423 VAULT_LOCKED`，应先定位原因，不要删除数据文件。
