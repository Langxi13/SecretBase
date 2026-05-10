<p align="center">
  <strong>SecretBase</strong>
</p>

<p align="center">
  A quiet, local-first vault for secrets you cannot afford to lose.<br>
  一个安静、本地优先、面向单用户的加密密码库。
</p>

<p align="center">
  <a href="#中文">中文</a> · <a href="#english">English</a> · <a href="docs/security-design.md">Security Design</a> · <a href="docs/deployment.md">Deployment</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-111827?style=flat-square">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-backend-059669?style=flat-square">
  <img alt="Vue" src="https://img.shields.io/badge/Vue%203-CDN-42b883?style=flat-square">
  <img alt="Storage" src="https://img.shields.io/badge/Storage-encrypted%20file-7c3aed?style=flat-square">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-111827?style=flat-square">
</p>

---

## 中文

SecretBase 是一个单用户加密密码库。它不需要数据库，不需要账号系统，也不默认连接任何云同步服务。后端用 FastAPI 提供 API，前端使用 Vue 3 CDN、原生 JavaScript 和 CSS，所有密码条目最终保存到一个本地加密 vault 文件里。

它适合这样的使用场景：你想要一个足够透明、可自托管、容易备份、容易审计的私人密码库，而不是一个复杂的多用户平台。

### 项目气质

- 本地优先：数据默认留在你的机器或服务器上。
- 单用户优先：没有注册、团队空间、共享权限和复杂租户模型。
- 可读可改：没有前端构建链，打开文件就能理解大部分界面逻辑。
- 安全克制：主密码解锁、AES-256-GCM 加密、会话 token、自动锁定、备份恢复都围绕单人 vault 设计。
- 生产友好：适合放在 nginx、HTTPS、Basic Auth、VPN 或 zero-trust 网关后面。

### 一眼看懂

```text
Browser
  Vue 3 CDN + plain JS + CSS
        |
        | X-SecretBase-Token
        v
FastAPI backend on 127.0.0.1:10004
        |
        | PBKDF2-HMAC-SHA256 + AES-256-GCM
        v
backend/data/secretbase.enc
```

### 它是什么

| 方向 | 说明 |
| --- | --- |
| 私人密码库 | 管理网站账号、服务器、API Key、安全笔记、恢复码等敏感信息。 |
| 单文件 vault | 数据保存在一个加密文件中，便于备份、迁移和恢复演练。 |
| 自托管 Web UI | 前端静态文件加 FastAPI 后端，可部署在自己的服务器上。 |
| 轻量工具 | 不依赖数据库，不依赖 npm 构建，不绑定云服务。 |

### 它不是什么

| 非目标 | 原因 |
| --- | --- |
| 多用户密码平台 | 当前模型只服务一个 vault owner，避免权限模型复杂化。 |
| 云同步服务 | 默认不上传 vault，不提供中心化同步。 |
| 企业级密钥管理系统 | 不替代 HSM、KMS、SSO、审计合规平台。 |
| 密码生成器套件 | 核心目标是可靠保存、查找、备份和恢复。 |

### 功能亮点

- 主密码初始化、解锁、锁定和自动锁定。
- 随机 session token，前端使用 `sessionStorage` 保存会话状态。
- 条目支持标题、网址、自定义字段、可复制字段、备注、星标和标签。
- 列表搜索、标签筛选、高级筛选、排序、分页。
- 可复制字段在列表中默认掩码，详情页再显示明文。
- 回收站、批量删除、批量加标签、批量星标。
- 标签重命名、删除、合并，以及标签浏览弹窗。
- 加密备份导出、明文 JSON 导出、导入预览和恢复。
- 旧加密备份可通过显式输入备份主密码读取或恢复。
- 安全报告、维护报告、密码健康检查。
- 可选 AI 解析：把自然语言、聊天记录或备忘录拆成结构化条目。
- 轻量前端：Vue 3 CDN、原生 JavaScript、原生 CSS，无 npm 构建步骤。

### 安全模型简述

SecretBase 的安全边界很明确：vault 文件只有在输入主密码后才会被解密，后端进程只在解锁期间缓存派生密钥和明文数据。锁定、自动锁定或服务重启后，会话 token 失效，内存状态被清理。

| 机制 | 当前设计 |
| --- | --- |
| 主密码 | 不保存明文主密码。 |
| 密钥派生 | PBKDF2-HMAC-SHA256。 |
| 加密算法 | AES-256-GCM。 |
| Vault 文件 | 默认 `backend/data/secretbase.enc`，不应提交到 Git。 |
| 会话认证 | 解锁后生成随机 token，受保护 API 需要携带 `X-SecretBase-Token`。 |
| 自动锁定 | 空闲超时后清理解锁态。 |
| 写入保护 | 文件锁、乐观锁、原子写入和自动备份。 |
| 日志 | 对密码、token、API key 等敏感字段做脱敏。 |

更多细节见 `docs/security-design.md`。

### 公开部署前必须知道

- 不要把后端直接暴露到公网，生产建议只监听 `127.0.0.1`。
- 用 nginx 或其他反向代理提供 HTTPS。
- 公网访问前建议增加 Basic Auth、VPN 或 zero-trust 网关。
- `CORS_ORIGINS` 不要在生产环境使用 `*`。
- `backend/.env`、`backend/data/`、`backend/logs/`、`backend/settings.json`、vault 文件和备份文件都不能提交到 Git。
- 主密码无法找回，丢失主密码通常意味着无法解密 vault。
- 备份不是“有文件就行”，必须定期演练恢复。

### 本地开发

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

打开：

```text
http://127.0.0.1:8001
```

### 常用配置

复制 `backend/.env.example` 到 `backend/.env`，再按需调整。

```env
HOST=127.0.0.1
PORT=10004
VAULT_PATH=./data/secretbase.enc
BACKUP_DIR=./data/backups/
CORS_ORIGINS=https://your-domain.example
DEEPSEEK_API_KEY=
AI_API_URL=https://api.deepseek.com/chat/completions
AI_MODEL=deepseek-v4-flash
```

| 变量 | 说明 |
| --- | --- |
| `HOST` | 后端监听地址，生产建议 `127.0.0.1`。 |
| `PORT` | 后端端口，默认 `10004`。 |
| `VAULT_PATH` | 加密 vault 文件路径。 |
| `BACKUP_DIR` | 自动备份目录。 |
| `CORS_ORIGINS` | 允许访问 API 的前端来源。 |
| `DEEPSEEK_API_KEY` | 可选，留空则禁用 AI 解析。 |
| `AI_API_URL` | DeepSeek 兼容 chat completions 接口。 |
| `AI_MODEL` | AI 解析使用的模型名。 |

### AI 解析

AI 解析是可选增强，不是核心依赖。未配置 API key 时，应用仍可完整手动录入和管理条目。

它的目标是把类似这样的文本：

```text
示例邮箱 demo@example.com 密码 demo-mail-pass；示例服务器 IP 192.0.2.10 端口 2222 密码 demo-server-pass
```

解析成多个结构化条目。后端会要求模型输出严格 JSON，并做字段归一化和输入长度限制。

### 验证

```powershell
python -m compileall backend
$env:DEEPSEEK_API_KEY=''; $env:AI_API_KEY=''; python scripts\v1-fake-smoke-test.py
node --check frontend\js\app.js
node --check frontend\js\api.js
node --check frontend\js\store.js
node --check frontend\js\utils.js
```

`v1-fake-smoke-test.py` 使用临时 vault，不会触碰真实数据。

### 生产部署概览

推荐路径：

```text
Internet
   |
HTTPS reverse proxy
   |
Basic Auth / VPN / zero-trust layer
   |
Static frontend + /api proxy
   |
FastAPI backend on 127.0.0.1
   |
Encrypted vault + backups
```

仓库包含通用脚本：

| 脚本 | 说明 |
| --- | --- |
| `scripts/install.sh` | 通用 Linux 安装脚本。 |
| `scripts/backup.sh` | 备份加密 vault 和配置。 |
| `scripts/restore.sh` | 从备份恢复 vault。 |
| `scripts/healthcheck.sh` | 检查服务和健康接口。 |
| `scripts/dev-backend.ps1` | Windows 本地后端启动脚本。 |
| `scripts/dev-frontend.ps1` | Windows 本地前端启动脚本。 |

更完整的部署说明见 `docs/deployment.md`。

### 项目结构

```text
backend/
  main.py              FastAPI app, middleware, auth gate
  config.py            environment and path configuration
  crypto.py            vault encryption and key derivation
  storage.py           vault state, locking, persistence, backups
  routes/              auth, entries, tags, trash, transfer, tools, AI
frontend/
  index.html           Vue CDN application shell
  js/                  API client, app logic, store, utilities
  css/                 layout, components, themes
docs/
  api-specification.md
  deployment.md
  frontend-design.md
  release-safety-checklist.md
  roadmap.md
  security-design.md
scripts/
  local development, smoke test, deployment and maintenance helpers
```

### 文档入口

- `docs/api-specification.md`：API 契约和响应格式。
- `docs/security-design.md`：加密、密钥、vault、日志和部署安全设计。
- `docs/frontend-design.md`：前端结构、状态和交互说明。
- `docs/deployment.md`：通用生产部署步骤。
- `docs/release-safety-checklist.md`：发布前安全检查清单。
- `docs/roadmap.md`：后续路线图。

### 许可证

MIT License. See `LICENSE`.

---

## English

SecretBase is a single-user encrypted password vault. It does not require a database, an account system, or any built-in cloud sync. The backend is powered by FastAPI, the frontend uses Vue 3 from CDN with plain JavaScript and CSS, and all vault data is stored in one local encrypted file.

It is designed for people who want a transparent, self-hostable, easy-to-backup private vault instead of a large multi-user password platform.

### Design Character

- Local-first: data stays on your machine or your server by default.
- Single-user-first: no registration, teams, shared permissions, or tenant model.
- Easy to inspect: no frontend build chain is required.
- Security-focused but restrained: master password, AES-256-GCM, session token, auto-lock, backups, and restore flows are built around one vault owner.
- Production-friendly: intended to run behind nginx, HTTPS, Basic Auth, VPN, or a zero-trust gateway.

### Quick Mental Model

```text
Browser
  Vue 3 CDN + plain JS + CSS
        |
        | X-SecretBase-Token
        v
FastAPI backend on 127.0.0.1:10004
        |
        | PBKDF2-HMAC-SHA256 + AES-256-GCM
        v
backend/data/secretbase.enc
```

### What It Is

| Area | Description |
| --- | --- |
| Private password vault | Store website accounts, servers, API keys, secure notes, recovery codes, and other sensitive records. |
| Single-file vault | Data lives in one encrypted file, making backup, migration, and restore drills straightforward. |
| Self-hosted Web UI | Static frontend plus FastAPI backend, deployable on your own server. |
| Lightweight tool | No database, no npm build step, no cloud lock-in. |

### What It Is Not

| Non-goal | Reason |
| --- | --- |
| Multi-user password platform | The current model serves one vault owner and avoids a complex permission model. |
| Cloud sync service | SecretBase does not upload or synchronize your vault by default. |
| Enterprise KMS | It does not replace HSM, KMS, SSO, or compliance audit systems. |
| Password generator suite | The core product is reliable storage, lookup, backup, and restore. |

### Highlights

- Master-password setup, unlock, lock, and auto-lock.
- Random session token stored in frontend `sessionStorage`.
- Entries with title, URL, custom fields, copyable fields, notes, stars, and tags.
- Search, tag filtering, advanced filters, sorting, and pagination.
- Copyable fields are masked in list views and revealed only in detail views.
- Trash, batch delete, batch tagging, and batch starring.
- Tag rename, delete, merge, and tag browser.
- Encrypted backup export, plain JSON export, import preview, and restore.
- Legacy encrypted backup support with explicit backup password input.
- Security report, maintenance report, and password health report.
- Optional AI parsing for natural language notes or pasted chat records.
- Lightweight frontend: Vue 3 CDN, plain JavaScript, plain CSS, no npm build step.

### Security Model

SecretBase has a narrow security boundary: the vault file is decrypted only after the master password is provided. While unlocked, the backend process keeps the derived key and plaintext data in memory. Locking, auto-locking, or restarting the service invalidates the session token and clears the unlocked state.

| Mechanism | Design |
| --- | --- |
| Master password | Plaintext master password is not stored. |
| Key derivation | PBKDF2-HMAC-SHA256. |
| Encryption | AES-256-GCM. |
| Vault file | Default path is `backend/data/secretbase.enc`; never commit it. |
| Session auth | Unlock creates a random token; protected APIs require `X-SecretBase-Token`. |
| Auto-lock | Idle timeout clears the unlocked state. |
| Write safety | File locking, optimistic locking, atomic writes, and automatic backups. |
| Logging | Sensitive fields such as passwords, tokens, and API keys are redacted. |

See `docs/security-design.md` for details.

### Before Public Deployment

- Do not expose the backend directly to the public internet.
- Bind the backend to `127.0.0.1` in production.
- Put HTTPS, nginx or another reverse proxy in front of it.
- Add Basic Auth, VPN, or a zero-trust gateway before public access.
- Do not use `CORS_ORIGINS=*` in production.
- Never commit `backend/.env`, `backend/data/`, `backend/logs/`, `backend/settings.json`, vault files, or backups.
- The master password cannot be recovered.
- Backups should be tested with restore drills, not just created.

### Local Development

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

### Configuration

Copy `backend/.env.example` to `backend/.env` and adjust values as needed.

```env
HOST=127.0.0.1
PORT=10004
VAULT_PATH=./data/secretbase.enc
BACKUP_DIR=./data/backups/
CORS_ORIGINS=https://your-domain.example
DEEPSEEK_API_KEY=
AI_API_URL=https://api.deepseek.com/chat/completions
AI_MODEL=deepseek-v4-flash
```

| Variable | Description |
| --- | --- |
| `HOST` | Backend bind address. Use `127.0.0.1` in production. |
| `PORT` | Backend port. Default is `10004`. |
| `VAULT_PATH` | Encrypted vault file path. |
| `BACKUP_DIR` | Automatic backup directory. |
| `CORS_ORIGINS` | Allowed frontend origins for API access. |
| `DEEPSEEK_API_KEY` | Optional. Leave empty to disable AI parsing. |
| `AI_API_URL` | DeepSeek-compatible chat completions endpoint. |
| `AI_MODEL` | Model name used for AI parsing. |

### AI Parsing

AI parsing is optional. If no API key is configured, the app still supports the full manual workflow.

It can turn text like this:

```text
Demo mail demo@example.com password demo-mail-pass; demo server IP 192.0.2.10 port 2222 password demo-server-pass
```

into structured entries. The backend asks the model for strict JSON and normalizes common response variations.

### Verification

```powershell
python -m compileall backend
$env:DEEPSEEK_API_KEY=''; $env:AI_API_KEY=''; python scripts\v1-fake-smoke-test.py
node --check frontend\js\app.js
node --check frontend\js\api.js
node --check frontend\js\store.js
node --check frontend\js\utils.js
```

The fake smoke test uses a temporary vault and does not touch real data.

### Production Overview

Recommended shape:

```text
Internet
   |
HTTPS reverse proxy
   |
Basic Auth / VPN / zero-trust layer
   |
Static frontend + /api proxy
   |
FastAPI backend on 127.0.0.1
   |
Encrypted vault + backups
```

Included helper scripts:

| Script | Purpose |
| --- | --- |
| `scripts/install.sh` | Generic Linux installation helper. |
| `scripts/backup.sh` | Back up encrypted vault and config. |
| `scripts/restore.sh` | Restore vault from backup. |
| `scripts/healthcheck.sh` | Check service and health endpoint. |
| `scripts/dev-backend.ps1` | Windows local backend starter. |
| `scripts/dev-frontend.ps1` | Windows local frontend starter. |

See `docs/deployment.md` for the full deployment guide.

### Repository Layout

```text
backend/
  main.py              FastAPI app, middleware, auth gate
  config.py            environment and path configuration
  crypto.py            vault encryption and key derivation
  storage.py           vault state, locking, persistence, backups
  routes/              auth, entries, tags, trash, transfer, tools, AI
frontend/
  index.html           Vue CDN application shell
  js/                  API client, app logic, store, utilities
  css/                 layout, components, themes
docs/
  api-specification.md
  deployment.md
  frontend-design.md
  release-safety-checklist.md
  roadmap.md
  security-design.md
scripts/
  local development, smoke test, deployment and maintenance helpers
```

### Documentation

- `docs/api-specification.md`: API contract and response shapes.
- `docs/security-design.md`: encryption, key handling, vault, logging, and deployment security.
- `docs/frontend-design.md`: frontend structure, state, and UX notes.
- `docs/deployment.md`: generic production deployment steps.
- `docs/release-safety-checklist.md`: release safety checklist.
- `docs/roadmap.md`: roadmap.

### License

MIT License. See `LICENSE`.
