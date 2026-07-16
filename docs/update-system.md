# SecretBase 跨端更新系统

## 1. 能力矩阵

| 平台 | 自动检查 | 自动预下载 | 安装方式 |
| --- | --- | --- | --- |
| Windows 安装版 | 默认每天一次 | 默认开启 | 用户确认后锁库、退出、覆盖安装并重启 |
| Windows 便携版 | 默认每天一次 | 不支持 | 打开正式 Release 下载链接 |
| Android GitHub 版 | 默认每天一次 | 默认仅 Wi-Fi，可允许移动网络 | 用户确认后进入 Android 系统安装界面 |
| macOS arm64 | 默认每天一次 | 不支持 | 打开正式 DMG，用户手动覆盖应用 |

更新失败或 GitHub 不可访问时，密码库继续完全离线工作。当前只跟踪稳定 Release，不接受草稿、预发布版本或降级。

Actions 候选包不是正式更新源。在第一个包含签名清单的 V5 Release 发布前，客户端会显示“暂无支持自动更新的正式版本”，不会把 GitHub 返回的 404 当作应用故障。正式 Release 创建后，三个客户端会自动读取其中的签名清单。

## 2. 签名清单

正式 Release 包含 `secretbase-update-v1.json` 和 `secretbase-update-v1.json.sig`。签名覆盖清单原始 UTF-8 字节，客户端必须先通过 Ed25519 验证再信任其中的版本和文件信息。

清单固定包含：

- `schema_version`、`key_id`、`channel`、统一产品版本和发布时间。
- 正式 Release 页面及简短更新说明。
- Windows 安装器、macOS DMG 和 Android APK 的文件名、大小、SHA-256 与官方 GitHub 地址。
- Android 包名、`versionCode` 和正式证书 SHA-256 指纹。

客户端只允许 `Langxi13/SecretBase` 的 HTTPS Release 地址，不执行清单提供的命令或安装参数。更新公钥支持 `key_id`；轮换时必须先发布同时信任旧、新公钥的过渡版本。

## 3. 平台行为

Windows 下载到用户应用数据目录的 `updates` 缓存。安装前再次计算完整哈希，写入待更新状态，锁定 Vault 后启动同一 `AppId` 的 Inno Setup 安装器。安装器不调用卸载数据清理逻辑。

Android 下载到应用缓存目录，之后由原生受限桥检查包名、版本号和签名。桥只接受缓存 `updates` 子目录中的 `.apk`，不能安装任意路径。没有“安装未知应用”权限时，应用只打开本包对应的系统授权页。

macOS 尚无 Developer ID 签名与公证，因此不自动替换 `/Applications`。手动覆盖 `.app` 不会删除 `~/Library/Application Support/SecretBase`。

Windows 和 macOS 桌面包同时加载操作系统信任库与随包提供的 Mozilla CA 证书集。打包检查会拒绝缺少 `certifi/cacert.pem` 的产物；证书异常只影响联网更新，不影响本地密码库。

## 4. 密钥与发布

普通 CI 使用临时 Android 密钥并输出带 `-ci` 的 APK。正式发布必须经过 GitHub `release` 环境审批，并读取以下 Environment Secrets：

```text
ANDROID_KEYSTORE_BASE64
ANDROID_KEYSTORE_PASSWORD
ANDROID_KEY_ALIAS
ANDROID_KEY_PASSWORD
UPDATE_SIGNING_PRIVATE_KEY_PEM_BASE64
```

私钥不得进入仓库、日志、Actions 产物或应用包。Android JKS 与更新签名密钥必须在仓库外保留恢复副本。

## 5. 首次迁移

- Windows V3 用户最后一次手动运行 V5 安装器覆盖旧版，无需卸载，数据保持不变。
- 当前 Android CI APK 的临时私钥已经销毁，必须先导出加密备份，再卸载测试包并安装永久签名 V5 基线。
- macOS 继续通过 DMG 手动覆盖，直到未来完成 Developer ID 签名和 Sparkle 接入。
