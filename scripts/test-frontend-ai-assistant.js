const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const { readFrontendMarkup } = require('./frontend-source');

const markup = readFrontendMarkup();
const controller = read('frontend/js/controllers/ai-assistant-controller.js');
const scopeController = read('frontend/js/controllers/ai-scope-controller.js');
const composition = read('frontend/js/ai-feature-composition.js');
const settingsController = read('frontend/js/controllers/ai-settings-controller.js');
const aiState = read('frontend/js/ai-state.js');
const sessionController = read('frontend/js/app-session-controller.js');
const aiWorkspaceCss = read('frontend/css/ai-workspace.css');
const aiScopeCss = read('frontend/css/ai-scope-picker.css');
const aiReviewCss = read('frontend/css/ai-send-review.css');
const aiComponentsCss = read('frontend/css/ai-components.css');
const diagnosticsCss = read('frontend/css/ai-diagnostics.css');

function assertIncludes(content, needle, message) {
    if (!content.includes(needle)) throw new Error(message);
}

function assertNotIncludes(content, needle, message) {
    if (content.includes(needle)) throw new Error(message);
}

function assertMatches(content, pattern, message) {
    if (!pattern.test(content)) throw new Error(message);
}

assertIncludes(markup, 'AI 管家', '默认 AI 工作区必须提供对话式管家');
assertIncludes(markup, 'AI 新建', 'AI 工作区必须提供需要二次确认的 AI 新建模式');
assertIncludes(markup, '尚未发送', '确认页必须明确提示数据尚未发送');
assertIncludes(markup, '本轮提示词', '确认页必须展示本轮提示词');
assertIncludes(markup, '范围内条目', '确认页必须展示本轮分析范围的条目标题摘要');
assertIncludes(markup, "class=\"modal-overlay\" :class=\"{ 'ai-subpanel-overlay': showAiAssistant }\"", '专业工具和服务设置必须在 AI 管家上层打开');
assertIncludes(markup, 'class="ai-composer-surface"', 'AI 输入器必须使用独立的居中输入表面');
assertIncludes(markup, 'class="ai-composer-footer"', '模式、范围和发送操作必须收敛到输入器控制栏');
assertIncludes(markup, '选择 AI 分析范围', 'AI 管家必须提供交互式分析范围弹窗');
assertIncludes(markup, '当前筛选结果', 'AI 范围必须明确表示覆盖全部筛选结果而非当前页');
assertIncludes(markup, '自定义选择', 'AI 范围必须支持跨页自定义选择条目');
assertIncludes(markup, '按标题或域名搜索', '自定义范围必须提供元数据搜索');
assertIncludes(markup, '不包含已有字段值', '范围选择弹窗必须明确隐私边界');
assertIncludes(markup, 'class="btn-primary inline ai-send-button"', 'AI 发送按钮必须使用行内按钮语义');
assertIncludes(markup, 'class="ai-quick-command-bar"', '常用 AI 整理指令必须固定显示在输入框上方');
assertIncludes(markup, '>分类</button>', '快捷整理栏必须提供分类体检入口');
assertIncludes(markup, '>标签清理</button>', '快捷整理栏必须提供标签清理入口');
assertIncludes(markup, '>字段名</button>', '快捷整理栏必须提供字段规范入口');
assertIncludes(markup, "'计划已降级'", '不可执行计划必须在审核栏明确标记为已降级');
assertNotIncludes(markup, 'class="ai-starter-row"', '快捷指令不应只在空会话中央显示一次');
assertIncludes(markup, 'message.meta?.warnings?.length', '计划降级警告必须跟随 AI 回复显示在聊天区');
assertIncludes(markup, 'class="btn-secondary ai-review-back"', '发送确认页必须提供不换行的返回修改操作');
assertIncludes(markup, '确认运行真实模型诊断', '真实模型诊断必须先展示数据与额度确认');
assertIncludes(markup, 'aiDiagnosticsPreview.includes_field_values', '诊断确认必须明确字段值发送状态');
assertIncludes(markup, 'class="ai-diagnostics-details"', '诊断明细必须默认折叠，避免设置页过长');
assertIncludes(markup, 'class="ai-history-rail"', '对话历史收起后必须保留清晰的侧栏展开入口');
assertIncludes(markup, 'class="btn-icon compact ai-history-collapse"', '对话历史侧栏必须提供内嵌收起操作');
assertNotIncludes(markup, ':class="{ active: aiAssistantHistoryOpen }"', '顶部不应继续保留不直观的历史切换小按钮');
assertIncludes(markup, '应用已选计划', 'AI 写入必须经过逐项计划审核');
assertIncludes(markup, '撤销本次操作', 'AI 写入后必须提供恢复快照撤销入口');
assertIncludes(controller, '/ai/assistant/turns/preview', '前端必须先请求不含提示词的发送清单');
assertIncludes(scopeController, '/ai/assistant/scope/catalog', '范围选择器必须使用元数据专用目录接口');
assertIncludes(scopeController, "if (filters.starred !== true) delete filters.starred", '未启用收藏筛选时不得误排除收藏条目');
assertIncludes(scopeController, "return { entryIds: [...picker.selectedIds] }", '自定义选择不得叠加主页筛选条件');
assertIncludes(controller, '/ai/assistant/turns/prepare', '用户确认后才能绑定本轮提示词');
assertIncludes(controller, '/ai/assistant/turns/submit', '前端必须通过待处理令牌提交模型请求');
assertIncludes(controller, '/ai/assistant/plans/apply', '前端必须通过计划令牌应用操作');
assertIncludes(controller, '/ai/assistant/plans/undo', '前端必须支持撤销 AI 操作');
assertIncludes(composition, 'window.SecretBaseAiAssistantController.createAiAssistantController', 'AI 领域装配必须接入对话管家控制器');
assertIncludes(composition, 'window.SecretBaseAiScopeController.createAiScopeController', 'AI 领域装配必须接入范围选择控制器');
assertIncludes(composition, 'window.SecretBaseAiSettingsController.createAiSettingsController', 'AI 领域装配必须接入厂商设置控制器');
assertMatches(
    controller,
    /finally\s*\{\s*aiAssistantBusy\.value\s*=\s*false;\s*aiAssistantStage\.value\s*=\s*'';/,
    '本地回复或请求失败后必须无条件结束处理中状态'
);
assertIncludes(controller, 'const limit = Math.floor(0x100000000 / alphabet.length)', '本地密码生成必须使用无取模偏差的拒绝采样');
assertIncludes(controller, "if (!prepared?.previewToken || aiAssistantBusy.value) return", '确认操作必须防止重复并发提交');
assertIncludes(controller, 'const warnings = Array.isArray(data.warnings)', '前端必须保留服务端计划纠正与降级警告');
assertNotIncludes(controller, 'requires_confirmation', '前端不得根据服务端条件跳过用户发送确认');
assertMatches(
    aiWorkspaceCss,
    /\.modal-overlay\.ai-subpanel-overlay\s*\{[\s\S]*?z-index:\s*6000/,
    'AI 子面板层级必须高于 AI 管家工作区'
);
assertMatches(
    aiWorkspaceCss,
    /\.ai-composer-inner\s*\{[\s\S]*?width:\s*min\(920px,\s*100%\)[\s\S]*?margin:\s*0\s+auto/,
    'AI 输入器必须居中限宽，避免宽屏输入行过长'
);
assertMatches(
    aiWorkspaceCss,
    /\.ai-send-button\s*\{[\s\S]*?width:\s*auto;[\s\S]*?flex:\s*0\s+0\s+auto/,
    'AI 发送按钮必须覆盖全局全宽按钮规则，避免挤压输入器工具栏'
);
assertNotIncludes(aiWorkspaceCss, '.ai-composer-input', '旧的分离式输入栏样式必须删除');
assertNotIncludes(aiWorkspaceCss, '.ai-starter-row', '旧的空会话快捷按钮样式必须删除');
assertMatches(
    aiScopeCss,
    /\.ai-scope-mode-tabs\s*\{[\s\S]*?grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/,
    '桌面范围模式必须使用稳定的三段布局'
);
assertMatches(
    aiScopeCss,
    /\.ai-scope-entry-row\s*\{[\s\S]*?grid-template-columns:/,
    '自定义条目列表必须使用稳定行布局，避免内容导致尺寸跳动'
);
assertMatches(
    aiReviewCss,
    /\.ai-send-review-actions \.ai-review-back,[\s\S]*?white-space:\s*nowrap/,
    '发送确认按钮必须保持单行并覆盖全宽按钮规则'
);
assertMatches(
    aiComponentsCss,
    /@media \(min-width: 768px\)[\s\S]*?\.ai-assistant-modal \.modal-footer \.btn-primary[\s\S]*?white-space:\s*nowrap/,
    '桌面专业 AI 工具底部操作必须保持紧凑单行'
);
assertIncludes(aiState, "const aiAssistantMode = ref('assistant')", 'AI 管家必须默认使用普通隐私模式');
assertIncludes(aiState, "const aiAssistantScope = ref('all')", 'AI 管家必须默认分析全部条目');
assertIncludes(aiState, "!window.matchMedia('(max-width: 820px)').matches", '桌面端对话历史必须默认展开，窄屏默认收起');
assertIncludes(sessionController, 'state.showAiAssistant.value = false', '锁定密码库时必须关闭 AI 管家');
assertIncludes(sessionController, 'state.resetAiAssistantSession()', '锁定密码库时必须清除 AI 管家敏感状态');
assertIncludes(aiState, "aiAssistantInput.value = ''", 'AI 会话重置必须清除页面内待确认提示词');
assertIncludes(settingsController, "id: 'custom'", '厂商列表失败时必须保留自定义接口');
assertIncludes(settingsController, '/ai/assistant/diagnostics/preview', '诊断必须先获取合成测试发送清单');
assertIncludes(settingsController, 'acknowledge_cost: true', '真实模型诊断必须携带用户额度确认');
assertIncludes(settingsController, '/ai/assistant/diagnostics/status', '诊断运行期间必须支持进度轮询');
assertMatches(
    diagnosticsCss,
    /\.ai-diagnostics-case-list\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    '桌面诊断明细应使用紧凑双栏布局'
);
assertNotIncludes(markup, 'Qwen', '内置 AI 厂商列表不应包含 Qwen');

console.log('PASS frontend ai assistant');
