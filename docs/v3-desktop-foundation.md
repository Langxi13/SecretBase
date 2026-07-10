# SecretBase V3.0 桌面基础模式

## 状态

V3.0 已实现，首个正式基线版本为 `v3.0.0`。

本阶段交付的是可稳定本地启动的桌面基础模式，不是 Windows 安装包。它复用现有 FastAPI 后端和静态前端，在用户本机启动仅监听回环地址的服务，并自动打开浏览器。

[V3.1 Windows 桌面 MVP](v3.1-windows-desktop-mvp.md) 已在本基础上实现 `SecretBase.exe`、独立桌面窗口和 Windows 自动构建，并在 `v3.1.0` 正式发布。

## 已实现能力

- `server` 与 `desktop` 两种运行模式互不干扰。
- 桌面模式使用随机本机端口，只监听 `127.0.0.1`。
- FastAPI 同源托管完整前端，不需要单独启动静态服务器。
- Vue 运行时已内置，页面不依赖 CDN、Google Fonts 或第三方 favicon 服务。
- Windows、Linux 和 macOS 源码环境提供一键启动脚本。
- 首次启动自动创建隔离虚拟环境并安装固定版本依赖。
- 桌面数据写入用户目录，不读取仓库内的服务器 vault 或 `.env`。
- 桌面模式限制 CORS 来源和 Host，阻止非本机站点直接复用本地服务。
- 认证表单在 JavaScript 失效时使用 POST 降级，避免主密码进入 URL。
- API 与静态页面返回基础浏览器安全头。
- Linux/macOS 本地数据根目录权限收紧为当前用户可访问。
- 完整发布检查同时覆盖 Linux 和 Windows GitHub Actions。

## 一键启动

### Windows

双击仓库根目录的：

```text
start-secretbase.cmd
```

该入口兼容 Windows 自带的 PowerShell 5.1 和 PowerShell 7。发布检查会从模拟源码压缩包中执行 CMD 入口，并覆盖包含中文和空格的解压路径。

也可以从 PowerShell 启动：

```powershell
.\scripts\start-local.ps1
```

常用参数：

```powershell
.\scripts\start-local.ps1 -NoBrowser
.\scripts\start-local.ps1 -DryRun
.\scripts\start-local.ps1 -DataRoot D:\SecretBaseData
```

### Linux / macOS

```bash
./scripts/start-local.sh
```

常用参数直接传给启动器：

```bash
./scripts/start-local.sh --no-browser
./scripts/start-local.sh --dry-run
./scripts/start-local.sh --data-root /path/to/secretbase-data
```

启动脚本会在仓库根目录创建被 Git 忽略的 `.venv/`。只有首次安装依赖或 `backend/requirements.txt` 变化时才需要访问 Python 包源；应用运行时不依赖前端外部资源。

## 直接启动器

已经准备好 Python 环境时，可以直接执行：

```bash
python desktop/launcher.py
```

启动器支持：

- `--no-browser`：只启动服务，不自动打开浏览器。
- `--dry-run`：只输出解析后的路径和随机端口，不创建目录或启动服务。
- `--data-root PATH`：覆盖本次运行的数据根目录。
- `SECRETBASE_DESKTOP_DATA_ROOT`：环境变量形式的数据根目录覆盖；命令行参数优先。

## 数据目录

Windows 默认目录：

```text
%LOCALAPPDATA%\SecretBase\
├── data\
│   ├── secretbase.enc
│   ├── secure-settings.enc
│   └── backups\
│       ├── auto\
│       └── manual\
├── logs\
│   └── secretbase.log
└── settings.json
```

macOS 默认目录：

```text
~/Library/Application Support/SecretBase
```

Linux 默认目录：

```text
~/.local/share/SecretBase
```

桌面模式不会自动扫描、复制或迁移服务器 vault。跨环境迁移应使用应用内的加密备份导出和恢复流程。

## 安全边界

- 主密码不会写入配置、日志或 URL。
- vault、备份和 AI 安全设置保持加密存储。
- 桌面服务只监听回环地址，CORS 只允许当前随机端口来源。
- `TrustedHostMiddleware` 只接受 `127.0.0.1` 和 `localhost`。
- 前端不自动请求第三方 favicon，也不从 CDN 执行代码。
- 外部网址只有在用户主动点击后才会打开，并使用 `noopener,noreferrer`。
- 桌面模式不读取 `backend/.env`，也不读写 `backend/data/`。

## 验证

完整发布检查：

```bash
python scripts/run-release-checks.py
```

桌面基础专项检查：

```bash
python scripts/test-desktop-foundation.py
node scripts/test-frontend-offline-security.js
```

隔离手动冒烟：

```bash
./scripts/start-local.sh --no-browser --data-root /tmp/secretbase-v3-smoke
```

测试不得使用生产 vault。

## 当前边界

V3.0 暂不包含：

- 独立桌面窗口和 Windows 可执行文件。
- 安装器、代码签名、自动更新和系统托盘。
- 浏览器关闭后自动结束后台进程。
- 多实例启动协调。
- 系统钥匙串和主密码记忆。
- 云同步、浏览器扩展和自动填充。

这些限制不影响本地浏览器模式的核心密码库功能，但属于 V3.1/V3.2 的产品化工作。

## V3.1 交接结果

V3.1 已按本阶段边界复用 vault、API 和前端，增加 pywebview 窗口壳、进程内后端与 PyInstaller one-folder 构建，并已通过 Windows 真机验收。下一阶段进入桌面产品化和 macOS 打包；手机端仍需先完成跨语言 vault 兼容层设计。
