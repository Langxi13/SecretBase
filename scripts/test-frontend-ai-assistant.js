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
assertIncludes(markup, '仅发送受限元数据', '普通模式必须明确提示受限元数据边界');
assertIncludes(markup, '应用已选计划', 'AI 写入必须经过逐项计划审核');
assertIncludes(markup, '撤销本次操作', 'AI 写入后必须提供恢复快照撤销入口');
assertIncludes(controller, '/ai/assistant/turns/prepare', '前端必须先准备发送清单');
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
assertIncludes(aiState, "const aiAssistantMode = ref('assistant')", 'AI 管家必须默认使用普通隐私模式');
assertIncludes(settingsController, "id: 'custom'", '厂商列表失败时必须保留自定义接口');
assertNotIncludes(markup, 'Qwen', '内置 AI 厂商列表不应包含 Qwen');

console.log('PASS frontend ai assistant');
