<p align="center">
  <strong>SecretBase</strong>
</p>

<p align="center">
  Self-hosted single-user encrypted password vault.<br>
  自托管单用户加密密码库。
</p>

<p align="center">
  <a href="#screenshots--界面预览">Screenshots</a> · <a href="#中文">中文</a> · <a href="#english">English</a> · <a href="docs/security-design.md">Security Design</a> · <a href="docs/deployment.md">Deployment</a> · <a href="docs/app-roadmap.md">App Roadmap</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-111827?style=flat-square">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-backend-059669?style=flat-square">
  <img alt="Vue" src="https://img.shields.io/badge/Vue%203-vendored-42b883?style=flat-square">
  <img alt="Storage" src="https://img.shields.io/badge/Storage-encrypted%20file-7c3aed?style=flat-square">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-111827?style=flat-square">
</p>

---

## Screenshots / 界面预览

The screenshots below use demo-only data. They do not contain real credentials, real servers, or private deployment details.

以下截图均使用演示数据，不包含真实密码、真实服务器或私人部署信息。

<table>
  <tr>
    <td width="50%">
      <strong>Desktop Overview / 桌面总览</strong><br>
      <img src="docs/assets/screenshots/secretbase-dark-01-overview.png" alt="SecretBase dark theme desktop overview">
    </td>
    <td width="50%">
      <strong>Entry Detail / 条目详情</strong><br>
      <img src="docs/assets/screenshots/secretbase-dark-02-entry-detail.png" alt="SecretBase entry detail with masked fields">
    </td>
  </tr>
  <tr>
    <td width="50%">
      <strong>Tag Browser / 标签浏览</strong><br>
      <img src="docs/assets/screenshots/secretbase-dark-03-tag-browser.png" alt="SecretBase tag browser in dark theme">
    </td>
    <td width="50%">
      <strong>AI Parsing / AI 智能录入</strong><br>
      <img src="docs/assets/screenshots/secretbase-dark-04-ai-parse.png" alt="SecretBase AI parsing modal">
    </td>
  </tr>
  <tr>
    <td width="50%">
      <strong>Backup Settings / 备份设置</strong><br>
      <img src="docs/assets/screenshots/secretbase-dark-05-backup-settings.png" alt="SecretBase backup settings in dark theme">
    </td>
    <td width="50%">
      <strong>Mobile Layout / 移动端布局</strong><br>
      <img src="docs/assets/screenshots/secretbase-dark-06-mobile.png" alt="SecretBase mobile layout in dark theme">
    </td>
  </tr>
</table>

## 中文

SecretBase 是一个面向个人自托管和本机离线场景的单用户加密密码库。项目采用 FastAPI 后端和本地内置的 Vue 3 前端，不依赖数据库或前端构建链，数据以加密 vault 文件形式保存在本地文件系统中。

项目目标是提供一个结构清晰、易于审计、易于备份恢复的密码管理工具，适用于个人服务器、本地局域网或受访问控制保护的私有部署环境。

### 目录

- [项目定位](#项目定位)
- [系统架构](#系统架构)
- [功能概览](#功能概览)
- [安全模型](#安全模型)
- [部署安全要求](#部署安全要求)
- [本地开发](#本地开发)
- [桌面基础模式](#桌面基础模式)
- [配置项](#配置项)
- [AI 解析](#ai-解析)
- [验证命令](#验证命令)
- [生产部署概览](#生产部署概览)
- [项目结构](#项目结构)
- [文档](#文档)

### 项目定位

| 分类 | 说明 |
| --- | --- |
| 使用模型 | 单用户、单 vault、无注册系统。 |
| 数据存储 | 本地加密文件存储，无数据库依赖。 |
| 前端形态 | 本地内置 Vue 3、原生 JavaScript、原生 CSS，运行时不依赖 CDN。 |
| 后端形态 | FastAPI 提供认证、条目、标签、导入导出、工具报告和 AI 解析接口。 |
| 部署方式 | 推荐部署在反向代理、HTTPS 和额外访问控制之后。 |
| 适用场景 | 个人密码管理、服务器凭据管理、API Key 管理、安全笔记和恢复码存档。 |

### 非目标

| 范围外能力 | 说明 |
| --- | --- |
| 多用户协作 | 当前版本不实现组织、团队、共享 vault 或多租户权限模型。 |
| 云同步 | 项目不默认上传、同步或托管用户 vault。 |
| 企业 KMS | 不替代 HSM、KMS、SSO、合规审计或集中化密钥管理系统。 |
| 浏览器插件 | 当前仓库只提供 Web UI 和后端服务。 |

### 系统架构

```text
Browser
  Vendored Vue 3 + JavaScript + CSS
        |
        | X-SecretBase-Token
        v
FastAPI backend on 127.0.0.1:10004
        |
        | PBKDF2-HMAC-SHA256 + AES-256-GCM
        v
Encrypted vault file
  backend/data/secretbase.enc
```

### 功能概览

| 模块 | 功能 |
| --- | --- |
| 认证 | 主密码初始化、解锁、锁定、自动锁定、随机 session token。 |
| 条目管理 | 标题、网址、自定义字段、可复制字段、隐藏字段、备注、星标、标签和密码组。 |
| 搜索与筛选 | 标题、网址、标签、字段名、非敏感字段值、备注、高级筛选、排序和分页。 |
| 字段保护 | 隐藏字段在列表中默认掩码，详情页可按需显示明文；可复制只控制复制入口。 |
| 标签管理 | 标签列表、重命名、删除、合并、按数量和名称排序。 |
| 密码组 | 一个条目可属于多个密码组，密码组有名称和简介，主页可切换到密码组模式并按组查看条目。 |
| 回收站 | 软删除、恢复、永久删除、清空回收站。 |
| 批量操作 | 批量删除、批量星标、批量更新标签。 |
| 备份中心 | 手动/自动备份两列分离、各自分页、固定占位、加载态、可配置自动保留数量、指定备份下载和三步恢复向导。 |
| 数据迁移 | 加密备份导出、明文 JSON 导出、加密/明文导入、导入预览、旧备份兼容。 |
| 工具报告 | 密码健康检查、维护报告、安全配置检查。 |
| AI 辅助 | 可选的自然语言解析，将文本转换为结构化条目；也可为当前筛选条目生成标签和密码组整理建议。 |

### 安全模型

SecretBase 的核心安全边界是本地加密 vault 文件。vault 只有在提供主密码并成功解锁后才会被读取为明文数据。后端在解锁期间维护派生密钥、vault 数据和 session token；锁定、自动锁定或服务重启后，解锁态失效。

| 机制 | 设计 |
| --- | --- |
| 主密码 | 不保存明文主密码。 |
| 密钥派生 | PBKDF2-HMAC-SHA256。 |
| 加密算法 | AES-256-GCM。 |
| Vault 文件 | 默认 `backend/data/secretbase.enc`，必须排除在 Git 之外。 |
| 会话认证 | 解锁后生成随机 token，受保护 API 使用 `X-SecretBase-Token`。 |
| 自动锁定 | 根据空闲时间清理解锁态。 |
| 并发保护 | 文件锁、乐观锁、原子写入和写入前备份。 |
| 日志脱敏 | 对密码、token、API key、authorization 等敏感字段脱敏。 |

完整安全设计见 `docs/security-design.md`。

### 部署安全要求

- 生产环境后端应绑定到 `127.0.0.1`，避免直接暴露到公网。
- 推荐通过 nginx 或其他反向代理统一提供 HTTPS 入口。
- 公网部署应增加 Basic Auth、VPN 或 zero-trust 网关等外层访问控制。
- 生产环境不得使用 `CORS_ORIGINS=*`。
- 不得提交 `backend/.env`、`backend/data/`、`backend/logs/`、`backend/settings.json`、vault 文件或备份文件。
- 主密码不可恢复，部署方应建立独立的主密码保管和恢复策略。
- 备份应定期创建，并通过恢复演练验证可用性。
- 应用内自动备份保存在 `BACKUP_DIR/auto/` 并按设置中的自动备份保留数量轮转，默认 30、范围 5-200；手动备份保存在 `BACKUP_DIR/manual/`，不会被自动轮转删除。
- 恢复备份前，备份中心会展示当前 vault 与备份目标状态的条目数和回收站数量对比；明文 JSON 下载必须显式确认。

### 本地开发

推荐直接使用桌面基础模式。首次运行会自动创建 `.venv/` 并安装固定版本依赖：

Windows：

```powershell
.\start-secretbase.cmd
```

源码启动器兼容 Windows 自带的 PowerShell 5.1 和 PowerShell 7，无需额外安装 `pwsh`。

Linux / macOS：

```bash
./scripts/start-local.sh
```

运行时的 Vue、字体和条目图标均来自本地，不需要连接前端 CDN。AI 服务和用户主动打开的外部网址仍需要网络。

需要分别调试前后端时，可以使用以下手动方式。

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python main.py
```

前端：

```powershell
python -m http.server 8001 -d frontend
```

访问地址：

```text
http://127.0.0.1:8001
```

### 桌面基础模式

`v3.0.0` 已完成由浏览器承载界面的桌面基础模式。`v3.1.0` 在此基础上增加 Windows 独立桌面窗口：使用 PyInstaller one-folder、pywebview 和 Edge WebView2，用户双击 `SecretBase.exe` 即可使用，不需要单独打开浏览器或安装 Python 依赖。

V3.1 Windows 包已通过 Windows 10/11 真机验收并正式发布。GitHub Release 包含：

```text
SecretBase-v3.1.0-windows-x64.zip
SHA256SUMS.txt
```

Windows 独立版默认将 vault、备份、日志、设置和 WebView 数据保存在 `%LOCALAPPDATA%\SecretBase\`。发布包只包含程序资源，构建时会扫描并拒绝 `.env`、vault、备份、日志和本地设置文件。桌面导出使用 Windows 原生“另存为”，外部网址交给系统默认浏览器打开；重复启动会恢复并聚焦已有窗口。

V3.2 正在此基础上增加当前用户免管理员安装器、桌面状态与诊断、目录入口、手动更新检查和可选系统托盘。桌面窗口支持窄屏缩放，关闭时可选择隐藏到托盘、完全退出或取消，并可记住选择。安装版与便携版共用现有数据目录；默认卸载保留数据，只有勾选删除并输入 `DELETE` 才清除整个本地数据目录。V3.2 当前仍处于 CI 与真机验收阶段，不替代已发布的 V3.1 稳定版本。

在 Windows Python 3.11 x64 与 Inno Setup 6.7.1 环境构建测试包：

```powershell
.\scripts\build-desktop-windows.ps1
```

构建脚本会生成 V3.2 安装器、便携 ZIP 和统一 SHA-256，并执行后端、前端及桌面运行时自检；Windows CI 还会安装同一产物，验证默认卸载保留数据和双确认清除策略。详细实现与验收门禁见 `docs/v3.2-windows-productization.md` 和 `docs/manual-qa-checklist-v3.2.md`；V3.1 发布记录仍保留在原文档中。

源码浏览器模式继续保留，由 `desktop/launcher.py` 启动本机后端、分配随机端口，并让后端同源托管 `frontend/` 页面。

默认启动：

```powershell
.\start-secretbase.cmd
```

启动后会自动打开浏览器。控制台会输出本机访问地址、数据目录和日志目录。

只启动服务、不自动打开浏览器：

```bash
./scripts/start-local.sh --no-browser
```

只查看解析后的运行配置，不启动服务：

```bash
./scripts/start-local.sh --dry-run
```

桌面模式默认使用用户本机目录保存 vault、备份、日志和设置；开发或手动测试时建议显式指定临时目录，避免触碰真实数据：

```bash
SECRETBASE_DESKTOP_DATA_ROOT=/tmp/secretbase-v3-manual-test python desktop/launcher.py
```

也可以使用 `--data-root PATH` 显式指定本次运行的数据目录。桌面模式不会读取仓库内的 `backend/.env`，只接受当前回环地址的 Host 和 CORS 来源。AI 接入请在解锁后进入“设置 -> AI”填写 Base URL、API Key 并获取模型列表。

详细设计和验收边界见 `docs/v3-desktop-foundation.md`。

### 配置项

复制 `backend/.env.example` 到 `backend/.env` 后按部署环境调整。

```env
HOST=127.0.0.1
PORT=10004
VAULT_PATH=./data/secretbase.enc
BACKUP_DIR=./data/backups/
SETTINGS_PATH=./data/settings.json
CORS_ORIGINS=https://your-domain.example
```

| 变量 | 说明 |
| --- | --- |
| `HOST` | 后端监听地址，生产建议使用 `127.0.0.1`。 |
| `PORT` | 后端端口，默认 `10004`。 |
| `AI_CHAT_TIMEOUT_SECONDS` | AI 对话请求超时秒数，默认 `120`。 |
| `VAULT_PATH` | 加密 vault 文件路径。 |
| `BACKUP_DIR` | 备份根目录，内部区分 `auto/` 自动备份和 `manual/` 手动备份。 |
| `SETTINGS_PATH` | 非敏感偏好设置文件，推荐放在受限的 `data/` 目录。 |
| `CORS_ORIGINS` | 允许访问 API 的前端来源。 |

### AI 解析与整理

AI 解析是可选功能。用户需要在解锁后进入“设置 -> AI”填写 Base URL、API Key，实时获取模型列表并选择模型。API Key 加密保存在本机 `secure-settings.enc`，不会写入明文 `settings.json` 或进入 vault 备份；修改主密码时，该文件会随 vault 一起重加密。未配置 API Key 时，核心密码管理、搜索、备份和恢复功能不受影响。

示例输入：

```text
示例邮箱 demo@example.com 密码 demo-mail-pass；示例服务器 IP 192.0.2.10 端口 2222 密码 demo-server-pass
```

后端会要求模型返回结构化 JSON，并对常见响应格式差异执行归一化处理。AI 解析结果仍应由用户确认后再保存。AI 整理分为条目标签整理、密码组整理、标签系统管理三类，三类能力分开执行，用户确认后才会应用；整理请求不会向 AI 发送任何字段值。

### 验证命令

推荐使用统一发布检查：

```powershell
python scripts\run-release-checks.py
```

以下命令可用于单独定位问题：

```powershell
python -m compileall backend
python -m compileall desktop scripts
python scripts\test-backup-separation.py
python scripts\test-desktop-foundation.py
python scripts\v1-fake-smoke-test.py
python scripts\test-ai-organize.py
python scripts\test-ai-actions.py
python scripts\test-ai-tag-governance.py
python scripts\test-ai-timeouts.py
python scripts\test-field-hidden-semantics.py
python scripts\test-password-groups.py
python scripts\test-tag-entities.py
python scripts\test-backend-module-split.py
node scripts\test-frontend-auto-theme.js
node scripts\test-frontend-ai-organize.js
node scripts\test-frontend-tag-management.js
node scripts\test-frontend-password-groups.js
node scripts\test-frontend-sidebar-labels.js
node scripts\test-frontend-offline-security.js
node scripts\test-frontend-module-split.js
node scripts\test-frontend-feature-modules.js
node scripts\test-frontend-template-split.js
node scripts\test-frontend-template-loader-runtime.js
node scripts\test-frontend-runtime-setup.js
node scripts\test-frontend-store-runtime.js
node scripts\test-frontend-toast-security.js
node --check frontend\js\app.js
node --check frontend\js\template-loader.js
node --check frontend\js\download-helper.js
Get-ChildItem frontend\js\controllers\*.js | ForEach-Object { node --check $_.FullName }
node --check frontend\js\api.js
node --check frontend\js\store.js
node --check frontend\js\utils.js
node --check frontend\js\pagination.js
node --check frontend\js\toast.js
node --check frontend\js\auto-lock.js
node --check frontend\js\theme-controller.js
node --check frontend\js\filter-controller.js
node --check frontend\js\view-helpers.js
node --check frontend\js\tag-view.js
node --check frontend\js\group-view.js
node --check frontend\js\backup-view.js
node --check frontend\js\ai-view.js
```

`scripts/v1-fake-smoke-test.py` 使用临时 vault，不会读取或修改真实数据。

### 独立接口测试环境

手动测试接口时不要使用真实 vault。启动独立测试后端：

```bash
scripts/dev-test-backend.sh --reset
```

默认地址是 `http://127.0.0.1:10014`，默认测试主密码是 `SecretBase-Test-123456!`。测试 vault、设置、备份、日志和 AI 安全设置都会写入 `/tmp/secretbase-test-runtime`，不会读写仓库内真实运行数据。去掉 `--reset` 可以复用上一次测试 vault。

### 生产部署概览

推荐部署拓扑：

```text
Internet
   |
HTTPS reverse proxy
   |
External access control
  Basic Auth / VPN / zero-trust gateway
   |
Static frontend + /api proxy
   |
FastAPI backend on 127.0.0.1
   |
Encrypted vault + backups
```

辅助脚本：

| 脚本 | 用途 |
| --- | --- |
| `scripts/install.sh` | 通用 Linux 安装脚本。 |
| `scripts/backup.sh` | 备份加密 vault 和配置文件。 |
| `scripts/restore.sh` | 从备份恢复 vault。 |
| `scripts/healthcheck.sh` | 检查服务状态和健康接口。 |
| `scripts/dev-test-backend.sh` | 启动隔离测试后端，用固定测试 vault 做手动接口测试。 |
| `scripts/dev-backend.ps1` | Windows 本地后端启动脚本。 |
| `scripts/dev-frontend.ps1` | Windows 本地前端启动脚本。 |

详细部署说明见 `docs/deployment.md`。

### 项目结构

```text
backend/
  main.py              FastAPI app, middleware, authentication gate
  config.py            environment and path configuration
  crypto.py            vault encryption and key derivation
  storage.py           vault state, locking, persistence, backups
  entry_service.py     entry mutation and single-write batch operations
  import_service.py    plain import conflict and metadata merge logic
  secure_settings.py   local encrypted-settings key derivation and rekeying
  ai_services/         AI prompts, client, parsing, organization and action services
  routes/              thin auth, entries, tags, trash, transfer, tools and AI routers
frontend/
  index.html           轻量入口、资源清单和加载壳
  vendor/vue/          固定版本的本地 Vue 运行时与许可证
  templates/           同源加载的页面与弹窗模板片段
  js/                  组合根、状态、Store 资源域、视图工厂、领域控制器和工具
    controllers/       条目、密码组、标签、AI、备份、导入、回收站、维护、列表控制器
  css/                 基础、工作台、弹窗、表单、AI、管理、响应式和主题样式
desktop/
  app.py               Windows independent desktop window entry
  launcher.py          browser-based local desktop-mode launcher
  runtime.py           shared in-process backend and desktop paths
  SecretBase.spec      PyInstaller one-folder build definition
docs/
  api-specification.md
  app-roadmap.md
  deployment.md
  frontend-design.md
  release-safety-checklist.md
  roadmap.md
  security-design.md
scripts/
  本地一键启动、完整回归、部署和维护脚本
```

### 文档

- `docs/api-specification.md`：API 契约和响应格式。
- `docs/security-design.md`：加密、密钥管理、vault、日志和部署安全设计。
- `docs/frontend-design.md`：前端结构、状态管理和交互说明。
- `docs/deployment.md`：通用生产部署步骤。
- `docs/app-roadmap.md`：桌面和手机 App 长期路线。
- `docs/v3-desktop-foundation.md`：已实现的 V3.0 桌面基础模式、边界和验收。
- `docs/v3.1-windows-desktop-mvp.md`：V3.1 Windows 桌面便携版实现与验收状态。
- `docs/manual-qa-checklist.md`：Windows 桌面真机验收清单。
- `docs/release-assessment-v3.0.0.md`：V3.0.0 完备性、风险和发布结论。
- `docs/release-safety-checklist.md`：发布前安全检查清单。
- `docs/roadmap.md`：路线图。

### License

MIT License. See `LICENSE`.

---

## English

SecretBase is a self-hosted and locally runnable single-user encrypted password vault. It uses a FastAPI backend and a vendored Vue 3 frontend, does not require a database or frontend build chain, and stores vault data as an encrypted file on the local filesystem.

The project is intended to provide a clear, auditable, and backup-friendly password management tool for personal servers, local networks, and private deployments protected by external access controls.

### Contents

- [Positioning](#positioning)
- [Architecture](#architecture)
- [Feature Overview](#feature-overview)
- [Security Model](#security-model)
- [Deployment Security Requirements](#deployment-security-requirements)
- [Local Development](#local-development)
- [Desktop Foundation Mode](#desktop-foundation-mode)
- [Configuration](#configuration)
- [AI Parsing](#ai-parsing)
- [Verification](#verification)
- [Production Deployment Overview](#production-deployment-overview)
- [Repository Layout](#repository-layout)
- [Documentation](#documentation)

### Positioning

| Category | Description |
| --- | --- |
| Usage model | Single user, single vault, no registration system. |
| Storage | Local encrypted file storage, no database dependency. |
| Frontend | Vendored Vue 3, plain JavaScript, plain CSS, with no runtime CDN dependency. |
| Backend | FastAPI APIs for authentication, entries, tags, transfer, reporting, and AI parsing. |
| Deployment | Recommended behind a reverse proxy, HTTPS, and external access control. |
| Use cases | Personal password management, server credentials, API keys, secure notes, and recovery codes. |

### Non-goals

| Out of scope | Description |
| --- | --- |
| Multi-user collaboration | No organizations, teams, shared vaults, or multi-tenant permission model. |
| Cloud sync | SecretBase does not upload, synchronize, or host user vaults by default. |
| Enterprise KMS | It does not replace HSM, KMS, SSO, compliance audit, or centralized key management systems. |
| Browser extension | This repository provides a Web UI and backend service only. |

### Architecture

```text
Browser
  Vendored Vue 3 + JavaScript + CSS
        |
        | X-SecretBase-Token
        v
FastAPI backend on 127.0.0.1:10004
        |
        | PBKDF2-HMAC-SHA256 + AES-256-GCM
        v
Encrypted vault file
  backend/data/secretbase.enc
```

### Feature Overview

| Module | Capabilities |
| --- | --- |
| Authentication | Master-password initialization, unlock, lock, auto-lock, random session token. |
| Entries | Title, URL, custom fields, copyable fields, hidden fields, notes, stars, tags, and password groups. |
| Search and filters | Title, URL, tags, field names, non-sensitive field values, notes, advanced filters, sorting, and pagination. |
| Field protection | Hidden fields are masked in list responses and can be revealed in the detail view; copyable only controls copy actions. |
| Tags | List, rename, delete, merge, and sort by count or name. |
| Password groups | Entries can belong to multiple groups; groups have names and descriptions; the workspace can switch to group mode and then filter by group. |
| Trash | Soft delete, restore, permanent delete, and empty trash. |
| Batch operations | Batch delete, batch star, and batch tag updates. |
| Backup center | Two-column manual/automatic backups, independent pagination, fixed placeholders, loading states, configurable automatic retention, per-backup downloads, and a three-step restore wizard. |
| Data migration | Encrypted backup export, plain JSON export, encrypted/plain imports, import preview, and legacy backup compatibility. |
| Reports | Password health report, maintenance report, and security configuration report. |
| AI assistance | Optional natural-language parsing into structured entries, plus confirmed tag and password-group organization suggestions for the current filter scope. |

### Security Model

The primary security boundary is the local encrypted vault file. The vault is decrypted only after a valid master password is provided. While unlocked, the backend process maintains the derived key, vault data, and session token in memory. Locking, auto-locking, or restarting the service invalidates the unlocked state.

| Mechanism | Design |
| --- | --- |
| Master password | Plaintext master password is not stored. |
| Key derivation | PBKDF2-HMAC-SHA256. |
| Encryption | AES-256-GCM. |
| Vault file | Default path is `backend/data/secretbase.enc`; it must be excluded from Git. |
| Session authentication | Unlock creates a random token; protected APIs use `X-SecretBase-Token`. |
| Auto-lock | Idle timeout clears the unlocked state. |
| Concurrency protection | File locking, optimistic locking, atomic writes, and pre-write backups. |
| Log redaction | Sensitive fields such as passwords, tokens, API keys, and authorization headers are redacted. |

See `docs/security-design.md` for the full design.

### Deployment Security Requirements

- Bind the backend to `127.0.0.1` in production and avoid direct public exposure.
- Serve public traffic through nginx or another HTTPS reverse proxy.
- Add Basic Auth, VPN, or a zero-trust gateway for external access.
- Do not use `CORS_ORIGINS=*` in production.
- Never commit `backend/.env`, `backend/data/`, `backend/logs/`, `backend/settings.json`, vault files, or backup files.
- The master password is not recoverable; operators should maintain an independent password custody process.
- Backups should be created regularly and validated with restore drills.
- In-app automatic backups are stored in `BACKUP_DIR/auto/` and rotated by the automatic backup retention setting, default 30 and range 5-200; manual backups are stored in `BACKUP_DIR/manual/` and are not removed by automatic rotation.
- Before restore, the backup center compares the current vault entry/trash counts with the selected backup target state; plain JSON downloads require explicit confirmation.

### Local Development

The recommended path is the desktop foundation bootstrap. The first run creates `.venv/` and installs pinned dependencies.

Windows:

```powershell
.\start-secretbase.cmd
```

The source bootstrap supports both Windows PowerShell 5.1 and PowerShell 7; installing `pwsh` is optional.

Linux / macOS:

```bash
./scripts/start-local.sh
```

Vue, fonts, and entry icons are local at runtime. AI providers and external URLs opened by the user still require network access.

Use the manual split frontend/backend workflow below only when debugging those layers separately.

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python main.py
```

Frontend:

```powershell
python -m http.server 8001 -d frontend
```

Open:

```text
http://127.0.0.1:8001
```

### Desktop Foundation Mode

`v3.0.0` completes the browser-hosted desktop foundation. `v3.1.0` adds an independent Windows window built with PyInstaller one-folder, pywebview, and Edge WebView2. Users launch `SecretBase.exe` directly without opening a separate browser or installing Python dependencies.

The V3.1 package has passed Windows 10/11 hardware acceptance and is formally released. GitHub Release provides `SecretBase-v3.1.0-windows-x64.zip` plus `SHA256SUMS.txt`.

Desktop data is stored under `%LOCALAPPDATA%\SecretBase\`. Build validation rejects `.env`, vault, backup, log, and local settings files. Native exports use the Windows Save As dialog, external URLs open in the system browser, and a second launch activates the existing window.

V3.2 is adding a per-user installer, desktop diagnostics, fixed directory shortcuts, manual update checks, narrow-window resizing, and an opt-in system tray. Closing the window can prompt to hide, exit, or cancel and can remember the selected action. Installed and portable builds share the existing data directory. Default uninstall preserves all data; full removal requires selecting the purge option and typing `DELETE`. V3.2 remains under CI and hardware acceptance, while V3.1 is the current stable release.

Build on Windows with Python 3.11 x64 and Inno Setup 6.7.1:

```powershell
.\scripts\build-desktop-windows.ps1
```

The build script produces the installer, portable ZIP, and shared SHA-256 file while running packaged backend, frontend, and desktop runtime checks. Windows CI installs the same artifact and verifies both data-preserving uninstall and explicitly confirmed data removal.

The browser-based source mode remains available through `desktop/launcher.py` and the commands below.

Default startup:

```powershell
.\start-secretbase.cmd
```

The launcher opens the browser automatically and prints the local URL, data directory, and log directory.

Start the service without opening a browser:

```bash
./scripts/start-local.sh --no-browser
```

Print resolved runtime configuration without starting the service:

```bash
./scripts/start-local.sh --dry-run
```

Desktop mode stores vault, backups, logs, and settings under the local user data directory by default. For development or manual testing, use a temporary data root to avoid touching real data:

```bash
SECRETBASE_DESKTOP_DATA_ROOT=/tmp/secretbase-v3-manual-test python desktop/launcher.py
```

Use `--data-root PATH` to override the data directory for one launch. Desktop mode does not read `backend/.env` and only accepts the current loopback Host and CORS origin. Configure AI after unlocking from Settings -> AI.

See `docs/v3-desktop-foundation.md` for design details and acceptance boundaries.

### Configuration

Copy `backend/.env.example` to `backend/.env` and adjust it for the target environment.

```env
HOST=127.0.0.1
PORT=10004
VAULT_PATH=./data/secretbase.enc
BACKUP_DIR=./data/backups/
SETTINGS_PATH=./data/settings.json
CORS_ORIGINS=https://your-domain.example
```

| Variable | Description |
| --- | --- |
| `HOST` | Backend bind address. Use `127.0.0.1` in production. |
| `PORT` | Backend port. Default is `10004`. |
| `AI_CHAT_TIMEOUT_SECONDS` | AI chat request timeout in seconds. Default is `120`. |
| `VAULT_PATH` | Encrypted vault file path. |
| `BACKUP_DIR` | Backup root directory containing `auto/` automatic backups and `manual/` manual backups. |
| `SETTINGS_PATH` | Non-sensitive preferences file; keep it inside the restricted `data/` directory. |
| `CORS_ORIGINS` | Allowed frontend origins for API access. |

### AI Parsing

AI parsing is optional. Users configure it after unlocking from Settings -> AI by entering Base URL, API Key, fetching the provider model list, and selecting a model. The API key is encrypted in the local `secure-settings.enc` file, is re-encrypted when the master password changes, and is not written to plaintext `settings.json` or included in vault backups. If no API key is configured, core password management, search, backup, and restore workflows remain available.

Example input:

```text
Demo mail demo@example.com password demo-mail-pass; demo server IP 192.0.2.10 port 2222 password demo-server-pass
```

The backend requests structured JSON from the model and normalizes common response-format variations. AI-generated entries should be reviewed before they are saved.

### Verification

Run the complete cross-platform release checks with:

```powershell
python scripts\run-release-checks.py
```

The individual commands below are useful for isolating a failure:

```powershell
python -m compileall backend
python -m compileall desktop scripts
python scripts\test-backup-separation.py
python scripts\test-desktop-foundation.py
python scripts\v1-fake-smoke-test.py
python scripts\test-ai-organize.py
python scripts\test-ai-actions.py
python scripts\test-ai-tag-governance.py
python scripts\test-ai-timeouts.py
python scripts\test-field-hidden-semantics.py
python scripts\test-password-groups.py
python scripts\test-tag-entities.py
python scripts\test-backend-module-split.py
node scripts\test-frontend-auto-theme.js
node scripts\test-frontend-ai-organize.js
node scripts\test-frontend-tag-management.js
node scripts\test-frontend-password-groups.js
node scripts\test-frontend-sidebar-labels.js
node scripts\test-frontend-offline-security.js
node scripts\test-frontend-module-split.js
node scripts\test-frontend-feature-modules.js
node scripts\test-frontend-template-split.js
node scripts\test-frontend-template-loader-runtime.js
node scripts\test-frontend-runtime-setup.js
node scripts\test-frontend-store-runtime.js
node scripts\test-frontend-toast-security.js
node --check frontend\js\app.js
node --check frontend\js\template-loader.js
node --check frontend\js\download-helper.js
Get-ChildItem frontend\js\controllers\*.js | ForEach-Object { node --check $_.FullName }
node --check frontend\js\api.js
node --check frontend\js\store.js
node --check frontend\js\utils.js
node --check frontend\js\pagination.js
node --check frontend\js\toast.js
node --check frontend\js\auto-lock.js
node --check frontend\js\theme-controller.js
node --check frontend\js\filter-controller.js
node --check frontend\js\view-helpers.js
node --check frontend\js\tag-view.js
node --check frontend\js\group-view.js
node --check frontend\js\backup-view.js
node --check frontend\js\ai-view.js
```

`scripts/v1-fake-smoke-test.py` uses a temporary vault and does not read or modify real data.

### Isolated API Test Environment

For manual API testing, do not use the real vault. Start an isolated test backend:

```bash
scripts/dev-test-backend.sh --reset
```

The default URL is `http://127.0.0.1:10014`, and the default test master password is `SecretBase-Test-123456!`. The test vault, settings, backups, logs, and AI secure settings are written under `/tmp/secretbase-test-runtime`, not the repository runtime data. Omit `--reset` to reuse the previous test vault.

### Production Deployment Overview

Recommended topology:

```text
Internet
   |
HTTPS reverse proxy
   |
External access control
  Basic Auth / VPN / zero-trust gateway
   |
Static frontend + /api proxy
   |
FastAPI backend on 127.0.0.1
   |
Encrypted vault + backups
```

Helper scripts:

| Script | Purpose |
| --- | --- |
| `scripts/install.sh` | Generic Linux installation helper. |
| `scripts/backup.sh` | Back up encrypted vault and configuration files. |
| `scripts/restore.sh` | Restore vault from backup. |
| `scripts/healthcheck.sh` | Check service status and health endpoint. |
| `scripts/dev-test-backend.sh` | Start an isolated test backend with a fixed test vault for manual API testing. |
| `scripts/dev-backend.ps1` | Windows local backend starter. |
| `scripts/dev-frontend.ps1` | Windows local frontend starter. |

See `docs/deployment.md` for detailed deployment instructions.

### Repository Layout

```text
backend/
  main.py              FastAPI app, middleware, authentication gate
  config.py            environment and path configuration
  crypto.py            vault encryption and key derivation
  storage.py           vault state, locking, persistence, backups
  entry_service.py     entry mutation and single-write batch operations
  import_service.py    plain import conflict and metadata merge logic
  secure_settings.py   local encrypted-settings key derivation and rekeying
  ai_services/         AI prompts, client, parsing, organization, and action services
  routes/              thin auth, entries, tags, trash, transfer, tools, and AI routers
frontend/
  index.html           lightweight entry, asset manifest, and loading shell
  vendor/vue/          pinned local Vue runtime and license
  templates/           same-origin page and dialog template fragments
  js/                  composition root, state, Store resource domains, view factories, domain controllers, and utilities
    controllers/       entry, group, tag, AI, backup, transfer, trash, maintenance, list controllers
  css/                 base, workspace, modal, form, AI, management, responsive, and theme styles
desktop/
  app.py               Windows independent desktop window entry
  launcher.py          browser-based local desktop-mode launcher
  runtime.py           shared in-process backend and desktop paths
  SecretBase.spec      PyInstaller one-folder build definition
docs/
  api-specification.md
  app-roadmap.md
  deployment.md
  frontend-design.md
  release-safety-checklist.md
  roadmap.md
  security-design.md
scripts/
  local bootstrap, release checks, deployment, and maintenance helpers
```

### Documentation

- `docs/api-specification.md`: API contract and response shapes.
- `docs/security-design.md`: encryption, key management, vault, logging, and deployment security.
- `docs/frontend-design.md`: frontend structure, state management, and UX notes.
- `docs/deployment.md`: generic production deployment steps.
- `docs/app-roadmap.md`: long-term desktop and mobile app roadmap.
- `docs/v3-desktop-foundation.md`: implemented V3.0 desktop foundation, boundaries, and acceptance checks.
- `docs/v3.1-windows-desktop-mvp.md`: V3.1 Windows desktop implementation and acceptance status.
- `docs/manual-qa-checklist.md`: Windows desktop hardware acceptance checklist.
- `docs/release-assessment-v3.0.0.md`: V3.0.0 completeness, risk, and release assessment.
- `docs/release-safety-checklist.md`: release safety checklist.
- `docs/roadmap.md`: roadmap.

### License

MIT License. See `LICENSE`.
