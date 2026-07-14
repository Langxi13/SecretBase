const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const { readFrontendMarkup } = require('./frontend-source');

const markup = readFrontendMarkup();
const controller = read('frontend/js/controllers/ai-assistant-controller.js');
const composition = read('frontend/js/ai-feature-composition.js');
const settingsController = read('frontend/js/controllers/ai-settings-controller.js');
const aiState = read('frontend/js/ai-state.js');
const sessionController = read('frontend/js/app-session-controller.js');
const aiWorkspaceCss = read('frontend/css/ai-workspace.css');

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
assertIncludes(markup, "class=\"modal-overlay\" :class=\"{ 'ai-subpanel-overlay': showAiAssistant }\"", '专业工具和服务设置必须在 AI 管家上层打开');
assertIncludes(markup, 'class="ai-composer-surface"', 'AI 输入器必须使用独立的居中输入表面');
assertIncludes(markup, 'class="ai-composer-footer"', '模式、范围和发送操作必须收敛到输入器控制栏');
assertIncludes(markup, '应用已选计划', 'AI 写入必须经过逐项计划审核');
assertIncludes(markup, '撤销本次操作', 'AI 写入后必须提供恢复快照撤销入口');
assertIncludes(controller, '/ai/assistant/turns/preview', '前端必须先请求不含提示词的发送清单');
assertIncludes(controller, '/ai/assistant/turns/prepare', '用户确认后才能绑定本轮提示词');
assertIncludes(controller, '/ai/assistant/turns/submit', '前端必须通过待处理令牌提交模型请求');
assertIncludes(controller, '/ai/assistant/plans/apply', '前端必须通过计划令牌应用操作');
assertIncludes(controller, '/ai/assistant/plans/undo', '前端必须支持撤销 AI 操作');
assertIncludes(composition, 'window.SecretBaseAiAssistantController.createAiAssistantController', 'AI 领域装配必须接入对话管家控制器');
assertIncludes(composition, 'window.SecretBaseAiSettingsController.createAiSettingsController', 'AI 领域装配必须接入厂商设置控制器');
assertMatches(
    controller,
    /finally\s*\{\s*aiAssistantBusy\.value\s*=\s*false;\s*aiAssistantStage\.value\s*=\s*'';/,
    '本地回复或请求失败后必须无条件结束处理中状态'
);
assertIncludes(controller, 'const limit = Math.floor(0x100000000 / alphabet.length)', '本地密码生成必须使用无取模偏差的拒绝采样');
assertIncludes(controller, "if (!prepared?.previewToken || aiAssistantBusy.value) return", '确认操作必须防止重复并发提交');
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
assertNotIncludes(aiWorkspaceCss, '.ai-composer-input', '旧的分离式输入栏样式必须删除');
assertIncludes(aiState, "const aiAssistantMode = ref('assistant')", 'AI 管家必须默认使用普通隐私模式');
assertIncludes(sessionController, 'state.showAiAssistant.value = false', '锁定密码库时必须关闭 AI 管家');
assertIncludes(sessionController, 'state.resetAiAssistantSession()', '锁定密码库时必须清除 AI 管家敏感状态');
assertIncludes(aiState, "aiAssistantInput.value = ''", 'AI 会话重置必须清除页面内待确认提示词');
assertIncludes(settingsController, "id: 'custom'", '厂商列表失败时必须保留自定义接口');
assertNotIncludes(markup, 'Qwen', '内置 AI 厂商列表不应包含 Qwen');

console.log('PASS frontend ai assistant');
