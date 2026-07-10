# 变更记录

## 3.1.0 - 未发布

### 新增

- 新增基于 pywebview 与 Edge WebView2 的 Windows 独立桌面窗口。
- 新增单实例运行，重复启动时恢复并聚焦已有窗口。
- 新增 Windows 原生“另存为”导出桥，桌面导出不再依赖浏览器下载行为。
- 新增 PyInstaller one-folder 构建、自检、敏感文件扫描和 SHA-256 校验流程。

### 兼容性

- 保留现有服务端部署、源码启动器和 vault 文件格式。
- Windows 桌面包使用独立本地数据目录，不在发布目录写入用户数据。

## 3.0.2 - 2026-07-10

### 修复

- 修复 Windows PowerShell 5.1 将无 BOM UTF-8 启动脚本按系统代码页读取，导致中文乱码和脚本解析失败的问题。
- 修复英文 Windows 等非中文系统在包含 Unicode 字符的解压路径中安装依赖时，Python/pip 输出编码失败的问题。

### 兼容性

- Windows 源码启动同时验证系统自带 PowerShell 5.1 与 PowerShell 7。
- CI 从模拟发布压缩包执行真实 CMD 入口，并覆盖包含中文和空格的解压路径。
- 增加 PowerShell、CMD 和 Shell 脚本的编码与换行规则检查。

### 隐私

- 将组织专属示例、作者标识和部署绝对路径替换为保留域名及通用占位符。

## 3.0.1 - 2026-07-10

### 修复

- 修复 Windows 默认 locale 无法格式化含中文字符的备份展示名称问题。
- 修复 Windows 启动器退出时可能遗留后端进程并占用日志文件的问题。
- 增加 locale 无关的备份名称回归测试，恢复 Windows 发布检查。
- 发布测试在清理临时目录前统一关闭日志文件，兼容 Windows 文件锁语义。
- Vue vendored 完整性校验统一换行后计算哈希，兼容 Windows CRLF checkout。
- CI 与 Release 工作流升级到基于新 Node 运行时的官方 Actions 主版本。

## 3.0.0 - 2026-07-10

### 新增

- 桌面基础模式：隔离本地数据路径并使用随机回环端口。
- Windows、Linux 和 macOS 源码环境的一键本地启动。
- 本地 vendored Vue 运行时，支持前端离线启动。
- Linux/Windows CI 和由 Git 标签触发的 GitHub Release 自动化。
- 密码组、完整标签管理、AI 整理和需确认的 AI 操作计划。

### 安全

- 桌面 CORS 和 Host 只接受当前本地应用来源。
- 防止认证表单退化为携带凭据的 GET 请求。
- 移除 vault 页面中的第三方 favicon 和字体请求。
- 增加浏览器安全头，以及外部链接的 opener/referrer 隔离。

### 调整

- API 和桌面运行信息统一使用 `3.0.0` 版本常量。
- 固定 Python 直接依赖版本，提高本地启动可复现性。
- 服务端偏好设置默认保存在可写数据目录，并补充旧版 `backend/settings.json` 的升级说明。
- V3.0 文档从待实施规划更新为已完成的桌面基础模式说明。

### 兼容性

- Vault 文件格式保持 `1.0` 不变。
- 现有服务器部署和加密 vault 文件继续兼容。
