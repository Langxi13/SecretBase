# SecretBase V3.0 桌面基础层规划

本文档记录 V3.0 的需求和设计边界。V3.0 的目标不是发布正式桌面安装包，而是先让 SecretBase 具备稳定的桌面本地运行基础，为 V3.1 Windows 桌面 MVP 做准备。

## 1. 版本目标

V3.0 只解决一件事：在不破坏现有自托管 Web 部署的前提下，新增一个桌面本地运行入口。

成功后的状态应是：

- 服务器模式继续按现有方式运行，默认行为不变。
- 桌面模式可以通过独立启动器运行。
- 桌面模式使用用户本机目录保存 vault、备份、日志和设置。
- 桌面模式使用本机随机端口，不依赖固定 `127.0.0.1:10004`。
- 前端能访问桌面启动器分配的 API 地址。
- 桌面模式不会读写仓库内的真实运行数据目录。

V3.0 不追求正式桌面应用外观，也不引入安装器、签名、托盘或自动更新。

## 2. 用户体验原则

V3.0 对普通用户应尽量“基本无感”：

- 不新增桌面首页。
- 不调整主界面布局。
- 不把桌面化包装成新产品形态。
- 不增加复杂首次启动向导。
- 通过控制台输出清晰提示，方便开发者和用户手动验证。

如果启动失败，V3.0 只要求控制台提示清楚：

- 当前运行模式。
- 数据目录。
- 日志路径。
- 后端访问地址。
- 失败原因或下一步检查方向。

窗口级错误页、系统托盘提示和桌面通知留到后续版本。

## 3. 运行模式

V3.0 增加 `server` 和 `desktop` 两种运行模式。

### server 模式

`server` 模式是现有自托管 Web 部署模式：

- 继续通过 `python backend/main.py` 或现有 systemd/nginx 方式运行。
- 继续读取 `backend/.env`。
- 继续使用当前默认端口 `10004`。
- 继续支持反向代理 `/api/`。
- 不因为 V3.0 桌面基础层改变默认行为。

### desktop 模式

`desktop` 模式通过独立桌面启动器进入：

```bash
python desktop/launcher.py
```

桌面启动器负责组装运行环境，而不是让 `backend/main.py` 承担桌面启动职责。

桌面模式应设置：

- `SECRETBASE_MODE=desktop`
- `HOST=127.0.0.1`
- `PORT=<动态分配端口>`
- `DATA_DIR=<桌面数据根目录>/data`
- `VAULT_PATH=<桌面数据根目录>/data/secretbase.enc`
- `BACKUP_DIR=<桌面数据根目录>/data/backups`
- `LOG_DIR=<桌面数据根目录>/logs`
- `SETTINGS_PATH=<桌面数据根目录>/settings.json`

这些关键路径和端口由启动器强制覆盖，避免误读服务器部署配置。

## 4. 数据目录

Windows 桌面模式默认数据根目录为：

```text
%LOCALAPPDATA%\SecretBase
```

选择 `%LOCALAPPDATA%` 的原因是密码库数据默认应留在本机，不应参与 Windows Roaming Profile 漫游同步。

默认目录结构为：

```text
%LOCALAPPDATA%\SecretBase\
├── data\
│   ├── secretbase.enc
│   └── backups\
│       ├── auto\
│       └── manual\
├── logs\
│   └── secretbase.log
└── settings.json
```

Linux 和 macOS 在 V3.0 只提供开发兜底目录，用于本仓库环境测试，不作为正式桌面产品承诺。

允许通过环境变量覆盖桌面数据根目录：

```bash
SECRETBASE_DESKTOP_DATA_ROOT=/tmp/secretbase-desktop-dev python desktop/launcher.py
```

该覆盖能力主要用于测试、开发和高级用户排查，不作为普通用户首选路径。

## 5. 数据迁移策略

V3.0 不做自动迁移。

具体原则：

- 桌面模式首次启动时创建独立空 vault。
- 不自动复制仓库内 `backend/data/secretbase.enc`。
- 不自动复制服务器部署中的 vault。
- 不扫描用户机器上的旧 vault。
- 不把明文 JSON 作为推荐迁移方式。

如果用户需要把服务器或开发环境数据迁移到桌面模式，应使用现有加密备份流程：

1. 在原环境创建或下载加密备份。
2. 在桌面模式中初始化或解锁 vault。
3. 通过数据迁移/导入导出入口导入加密备份。

这样可以保持迁移动作显式、可审计，也避免桌面模式误复制真实敏感数据。

## 6. 启动器设计

V3.0 新增桌面启动器，建议入口为：

```bash
python desktop/launcher.py
```

启动器职责：

- 解析桌面数据根目录。
- 创建必要目录。
- 分配空闲本机端口。
- 强制设置桌面模式关键环境变量。
- 启动 FastAPI 后端子进程。
- 等待 `/health` 返回可用。
- 打开默认浏览器访问本地桌面入口。
- 在控制台持续输出运行状态。
- 用户按 `Ctrl+C` 时停止后端子进程。

V3.0 不要求检测浏览器窗口关闭，也不要求自动退出后台服务。

建议支持两个辅助参数：

```bash
python desktop/launcher.py --no-browser
python desktop/launcher.py --dry-run
```

`--no-browser` 用于只启动本地服务，不自动打开浏览器。

`--dry-run` 用于输出解析后的运行配置，不启动后端、不打开浏览器，便于测试和排查。

## 7. 前端访问方式

桌面模式应尽量使用同源访问，减少 CORS 复杂度。

建议由 FastAPI 在桌面模式下托管 `frontend/` 静态文件：

- 浏览器访问 `http://127.0.0.1:<动态端口>/`。
- API 继续在同一个 origin 下访问。
- 前端通过运行时配置获得 API base URL。

现有 `frontend/js/api.js` 已支持 `window.SECRETBASE_API_BASE_URL`。V3.0 可以继续利用这个能力，但需要明确桌面模式如何注入它。

服务器部署中的 nginx `/api/` 代理方式保持不变。

## 8. AI 功能策略

桌面离线核心能力不依赖 AI。

V3.0 桌面模式下，AI 解析保持可选：

- 未配置 API Key 时，AI 解析继续显示为未配置或不可用。
- 用户主动配置 `DEEPSEEK_API_KEY` 或 `AI_API_KEY` 后，可以继续使用 AI 解析。
- 文档必须说明：AI 解析不是离线能力，使用时会访问外部模型服务。

V3.0 不新增桌面专用 AI 配置界面。

## 9. 实施设计暂定方案

本节记录当前已暂定的工程方案。后续如果讨论结果变化，应同步更新本节。

### 9.1 后端配置模块

后端配置采用“集中配置对象 + 现有常量兼容”的方式演进。

暂定原则：

- 新增集中配置对象，统一表达运行模式、端口、路径、CORS、日志和 AI 配置。
- 保留现有 `from config import VAULT_PATH`、`BACKUP_DIR`、`SETTINGS_PATH` 等常量，避免 V3.0 一次性改动所有调用方。
- 配置模块导入时只解析配置，不创建目录。
- 新增显式初始化函数，例如 `ensure_runtime_dirs()`，由后端启动流程或桌面启动器明确调用。
- `server` 模式继续读取 `backend/.env`，系统环境变量优先于 `.env`，保证现有部署不受影响。
- `desktop` 模式不读取仓库内 `backend/.env`。
- `desktop` 模式由启动器在后端导入配置前设置关键环境变量。
- 关键运行参数以桌面启动器为准，包括 `HOST`、`PORT`、`DATA_DIR`、`VAULT_PATH`、`BACKUP_DIR`、`LOG_DIR`、`SETTINGS_PATH`。
- AI 相关变量继续允许从环境读取，但不作为桌面离线核心能力。

这个方案比“彻底依赖注入”改造面小，也比“完全沿用环境变量常量”更容易测试和审计。

配置职责边界已经暂定为：配置对象负责解析和暴露配置值；目录创建、权限检查和运行时准备放到显式初始化函数中。这样可以避免仅仅导入模块就创建真实目录，也方便测试验证桌面模式不会误碰仓库内数据目录。

### 9.2 前端和 API 路径

桌面模式采用后端同源托管前端。

暂定原则：

- FastAPI 在 `desktop` 模式下托管 `frontend/` 静态文件。
- 浏览器访问 `http://127.0.0.1:<动态端口>/`。
- 桌面模式不新增 `/api` 路由别名。
- 前端在桌面模式下使用空 API base URL，直接请求现有顶层接口，例如 `/auth/status`、`/entries`、`/backups`。
- 服务器模式继续由 nginx 负责 `/api/` 代理，不改变现有生产部署。
- 静态托管采用根路径兜底策略：API 顶层路由优先，`/` 和未匹配前端路径返回前端资源或 `index.html`。

这个方案可以减少 CORS 和双端口复杂度，也避免复制一套 API 路由。

### 9.3 运行时配置注入

前端运行时配置采用 JavaScript 端点注入。

暂定原则：

- 新增 `/secretbase-runtime-config.js`。
- `server` 和 `desktop` 两种模式都提供该端点，前端加载方式保持统一。
- 该端点设置 `window.SECRETBASE_RUNTIME_CONFIG`，并兼容现有 `window.SECRETBASE_API_BASE_URL`。
- `desktop` 模式 API base 为空字符串，表示同源顶层 API。
- `server` 模式继续保持现有 API base 解析策略，不破坏当前生产部署。

选择运行时 JS 端点，是为了避免启动器改写 HTML 文件，也为后续 V3.1 桌面窗口壳注入版本、平台、运行模式等信息保留空间。

### 9.4 启动器健康检查和退出行为

桌面启动器的基础生命周期策略已经暂定。

暂定原则：

- 启动后端后，最多等待 15 秒检查 `/health`。
- 健康检查失败时，控制台显示最近 50 行后端输出，并显示完整日志路径。
- 用户按 `Ctrl+C` 后，先向后端子进程发送优雅退出信号。
- 优雅退出等待 5 秒；仍未退出则强制结束子进程。
- V3.0 不检测浏览器关闭，不根据浏览器窗口生命周期自动退出后端。

这个策略兼顾排错体验和避免残留进程，也避免 V3.0 引入桌面窗口生命周期管理。

### 9.5 测试策略

V3.0 采用“自动化优先，手动冒烟兜底”的测试策略。

自动化测试优先覆盖：

- 配置对象在 `server` 和 `desktop` 模式下的解析结果。
- `server` 模式读取 `backend/.env` 且系统环境变量优先。
- `desktop` 模式不读取仓库内 `backend/.env`。
- 单纯导入配置模块不会创建运行目录。
- `ensure_runtime_dirs()` 会显式创建需要的运行目录。
- 桌面路径是否被正确隔离。
- `--dry-run` 是否输出预期配置。
- `--no-browser` 是否能启动后端并通过 `/health`。
- 桌面模式是否不会读写仓库内 `backend/data/`、`backend/logs/`、`backend/settings.json`。

测试脚本暂定新增：

```bash
scripts/test-desktop-foundation.py
```

该脚本专门覆盖桌面配置、启动器 dry-run、路径隔离和基础健康检查，不并入 `scripts/v1-fake-smoke-test.py`，避免职责混杂。

手动冒烟只使用测试目录，不使用真实 vault。手动检查范围包括初始化、解锁、条目创建、手动备份、备份中心和加密备份导入。

### 9.6 UI 策略

V3.0 不在主界面显示“桌面模式”标识。

暂定原则：

- 不新增顶部状态标识。
- 不新增设置页运行模式展示。
- 不新增桌面模式首页。
- 运行状态主要通过启动器控制台和文档说明。

如果后续发现手动测试需要确认运行模式，可以优先考虑增强控制台输出，而不是改主界面。

## 10. Git 管理策略

V3.0 相关工作按“文档基线进入本地 `main`，实现进入独立 worktree 分支”的方式管理。

### 10.1 文档基线

当前长期规划和 V3.0 文档应先作为本地基线提交到 `main`，暂不推送远端。

这样做的目的：

- 让后续实现分支从已确认的文档基线开始。
- 避免未提交文档在主目录和 worktree 之间反复牵连。
- 保持远端 `main` 暂时停留在已稳定版本。

### 10.2 实现分支

V3.0 实现分支命名为：

```text
feature/v3-desktop-foundation
```

实现阶段使用项目内 worktree：

```text
.worktrees/v3-desktop-foundation
```

创建 worktree 前需要先把 `.worktrees/` 加入 `.gitignore` 并本地提交，避免 worktree 目录被 Git 跟踪。

### 10.3 提交粒度

V3.0 实现采用阶段性小提交，不做单一大提交，也不做过碎的每步提交。

建议提交顺序：

1. 配置模块改造。
2. 桌面模式静态前端托管。
3. 桌面启动器。
4. 测试和路径隔离。
5. 文档更新。

每个阶段性提交都应能说明独立目的，并尽量配套对应验证。

### 10.4 推送策略

V3.0 实现完成并通过验收前不推送远端。

暂定策略：

- 文档基线本地提交，不推送。
- 实现分支本地开发，不推送。
- 完成 V3.0 验收后，再决定是否合并到 `main` 并推送。

## 11. 明确不做

V3.0 不包含以下内容：

- PyInstaller 打包。
- pywebview 桌面窗口。
- Windows 安装器。
- 代码签名。
- 自动更新。
- 系统托盘。
- 开机启动。
- 浏览器插件或自动填充。
- 云同步。
- 手机 App。
- 共享 vault 核心重写。
- 保存或自动填充主密码。

这些能力分别放到 V3.1 或后续版本讨论。

## 12. 验证要求

V3.0 实现前应把以下验证作为验收标准：

### 配置和路径

- 桌面模式默认使用 `%LOCALAPPDATA%\SecretBase`。
- 测试环境可通过 `SECRETBASE_DESKTOP_DATA_ROOT` 覆盖数据根目录。
- 桌面模式不读写仓库内 `backend/data/`。
- 桌面模式不读写仓库内 `backend/logs/`。
- 桌面模式不读写仓库内 `backend/settings.json`。
- 服务器模式默认行为不变。

### 启动器

- `--dry-run` 能输出模式、端口、数据目录、vault 路径、备份目录和日志目录。
- `--no-browser` 能启动后端并通过 `/health`。
- 默认启动能打开浏览器访问本地页面。
- 端口冲突时能自动换端口。
- 后端启动失败时控制台能显示日志路径、失败原因和最近 50 行后端输出。
- `/health` 15 秒内不可用时判定启动失败。
- `Ctrl+C` 后先优雅停止后端子进程，5 秒后仍未退出则强制结束。

### 核心功能

- 桌面模式可以初始化主密码。
- 桌面模式可以解锁。
- 桌面模式可以创建、编辑、删除条目。
- 桌面模式可以使用标签和回收站。
- 桌面模式可以创建手动备份。
- 桌面模式可以查看备份中心。
- 桌面模式可以通过加密备份导入数据。

### 回归命令

```bash
python -m compileall backend
node --check frontend/js/app.js frontend/js/api.js frontend/js/store.js frontend/js/utils.js
venv/bin/python scripts/test-desktop-foundation.py
venv/bin/python scripts/test-backup-separation.py
env DEEPSEEK_API_KEY= AI_API_KEY= AI_MODEL=deepseek-v4-flash venv/bin/python scripts/v1-fake-smoke-test.py
```

## 13. 仍需继续讨论的问题

下一轮可以继续拆 V3.0 的实施设计，但仍建议先讨论清楚再写代码。当前已经确认配置边界、静态托管方向、运行时配置注入、启动器健康检查和测试脚本组织，剩余需要确认的问题如下。

### 13.1 文档基线和 Git 操作时机

需要确认是否先完成当前文档基线本地提交，再继续写 V3.0 实施计划。

倾向方案：先把当前 README、长期 App 化规划、V3.0 基础层规划本地提交到 `main`，暂不推送；然后再创建实现分支和 worktree。

### 13.2 `.worktrees/` 忽略规则

需要确认 `.worktrees/` 是否在下一次准备提交中加入 `.gitignore`。

倾向方案：在创建 worktree 前单独提交 `.gitignore` 更新，避免项目内 worktree 目录被 Git 误跟踪。

### 13.3 实施计划拆分

需要确认 V3.0 实施计划是否按以下阶段拆分：

1. 配置对象和显式运行目录初始化。
2. 桌面模式同源静态托管和运行时配置端点。
3. 桌面启动器和子进程生命周期。
4. 桌面基础层自动化测试。
5. 文档和开发命令更新。

倾向方案：按这 5 个阶段拆分，每个阶段都能独立验证并形成阶段性小提交。

### 13.4 手动冒烟测试数据

需要确认 V3.0 手动冒烟使用什么测试数据和测试目录命名。

倾向方案：使用 `/tmp/secretbase-v3-desktop-smoke` 作为 Linux 开发环境测试目录；只创建示例条目和示例加密备份，不读取真实 vault。

### 13.5 V3.0 与 V3.1 的交接边界

需要确认 V3.0 完成后，哪些内容明确留给 V3.1。

倾向方案：V3.0 到此为止只证明“本地桌面运行基础层可用”；PyInstaller、pywebview、安装器、桌面窗口错误页、托盘和正式 Windows 验收全部进入 V3.1。
