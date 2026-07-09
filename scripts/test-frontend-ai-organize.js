const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const { readFrontendMarkup, readFrontendCss } = require('./frontend-source');

const indexHtml = readFrontendMarkup();
const appJs = read('frontend/js/app.js');
const stateJs = read('frontend/js/app-state.js');
const featureCompositionJs = read('frontend/js/app-feature-composition.js');
const appUiControllerJs = read('frontend/js/app-ui-controller.js');
const aiControllerJs = read('frontend/js/controllers/ai-controller.js');
const viewHelpersJs = read('frontend/js/view-helpers.js');
const aiViewJs = read('frontend/js/ai-view.js');
const storeJs = read('frontend/js/store.js');
const storeStateJs = read('frontend/js/store-state.js');
const componentsCss = readFrontendCss();

function assertIncludes(content, needle, message) {
    if (!content.includes(needle)) {
        throw new Error(message);
    }
}

function assertMatches(content, pattern, message) {
    if (!pattern.test(content)) {
        throw new Error(message);
    }
}

function assertNotIncludes(content, needle, message) {
    if (content.includes(needle)) {
        throw new Error(message);
    }
}

assertIncludes(indexHtml, '智能录入', 'AI 弹窗必须保留智能录入模式');
assertIncludes(indexHtml, '整理条目', 'AI 弹窗必须新增整理条目模式');
assertIncludes(indexHtml, 'AI 交互', 'AI 弹窗必须提供自然语言操作计划模式');
assertIncludes(indexHtml, '条目标签整理', '整理条目模式必须支持单条目维度的标签整理');
assertIncludes(indexHtml, '密码组整理', '整理条目模式必须支持密码组整理');
assertIncludes(indexHtml, '标签系统管理', 'AI 弹窗必须提供独立标签系统管理模式');
assertIncludes(indexHtml, '本次偏好', '三个 AI 整理子功能必须支持本次偏好提示词');
assertIncludes(indexHtml, 'v-model="currentAiOrganizePrompt"', '整理偏好输入必须绑定当前子模式提示词');
assertIncludes(indexHtml, '生成操作计划', 'AI 交互必须先生成操作计划');
assertIncludes(indexHtml, '应用计划', 'AI 交互必须由用户确认后应用计划');
assertIncludes(indexHtml, '操作计划', 'AI 交互必须展示结构化操作计划');
assertIncludes(indexHtml, '不会发送字段值', 'AI 整理必须提示不会发送字段值');
assertIncludes(indexHtml, '整体摘要', '整理建议必须先展示整体摘要');
assertIncludes(indexHtml, '逐条建议', '整理建议必须支持逐条确认');
assertIncludes(indexHtml, '应用整理', '用户必须手动应用整理结果');
assertIncludes(indexHtml, 'ai-organize-select', '整理建议标题行必须使用专用紧凑选择样式');
assertIncludes(indexHtml, 'ai-organize-mode-tabs', '整理标签和密码组必须使用互斥模式切换');
assertIncludes(indexHtml, "setAiOrganizeMode('tags')", '必须提供整理标签模式入口');
assertIncludes(indexHtml, "setAiOrganizeMode('groups')", '必须提供整理密码组模式入口');
assertIncludes(indexHtml, "setAiOrganizeMode('tag-governance')", '必须提供标签系统管理模式入口');
assertNotIncludes(indexHtml, 'v-model="aiOrganizeOptions.organizeTags"> 整理标签', '整理标签不能再使用可同时勾选的 checkbox');
assertNotIncludes(indexHtml, 'v-model="aiOrganizeOptions.organizeGroups"> 整理密码组', '整理密码组不能再使用可同时勾选的 checkbox');

assertIncludes(stateJs, "const aiMode = ref('parse')", 'AI 弹窗必须有 parse/organize 模式状态');
assertIncludes(stateJs, "const aiActionInstruction = ref('')", 'AI 交互必须维护用户自然语言指令');
assertIncludes(stateJs, 'const aiActionResult = ref(null)', 'AI 交互必须维护操作计划结果');
assertIncludes(stateJs, 'const aiOrganizePrompts = reactive', 'AI 整理三个子功能必须维护独立本次偏好');
assertIncludes(stateJs, 'const currentAiOrganizePrompt = computed', '必须根据当前整理子模式读取偏好提示词');
assertIncludes(featureCompositionJs, 'window.SecretBaseAiController.createAiController', '领域装配模块必须装配 AI 控制器');
assertIncludes(aiControllerJs, 'function setAiOrganizeMode', '必须提供互斥整理模式切换方法');
assertIncludes(aiControllerJs, 'async function previewAiOrganize', '必须提供 AI 整理预览方法');
assertIncludes(aiControllerJs, 'async function applyAiOrganize', '必须提供 AI 整理应用方法');
assertIncludes(aiControllerJs, 'async function previewAiActions', 'AI 交互必须提供操作计划预览方法');
assertIncludes(aiControllerJs, 'async function applyAiActions', 'AI 交互必须提供操作计划应用方法');
assertIncludes(aiControllerJs, 'function clearAiActions', 'AI 交互必须支持清空计划');
assertIncludes(appUiControllerJs, 'viewHelpers.aiActionTypeLabel', '模板上下文必须复用 AI 操作类型展示辅助');
assertIncludes(appUiControllerJs, 'viewHelpers.aiActionEntryLabel', '模板上下文必须复用 AI 条目标题展示辅助');
assertIncludes(viewHelpersJs, 'function aiActionTypeLabel', 'AI 交互必须展示可读动作类型');
assertIncludes(viewHelpersJs, 'function aiActionEntryLabel', 'AI 交互必须把条目 id 映射为可读条目标题');
assertIncludes(viewHelpersJs, "update_group: '更新密码组'", 'AI 交互必须展示更新密码组动作类型');
assertIncludes(viewHelpersJs, 'action.group_new', 'AI 交互必须展示密码组改名目标');
assertIncludes(viewHelpersJs, 'action.entry_title || action.entry_id', '更新条目计划标题必须优先展示条目标题而不是唯一代码');
assertIncludes(viewHelpersJs, 'action.source_entry_title || action.source_entry_id', '字段拆分计划标题必须优先展示来源条目标题而不是唯一代码');
assertIncludes(aiControllerJs, '/ai/organize/preview', '前端必须调用整理预览接口');
assertIncludes(aiControllerJs, '/ai/organize/apply', '前端必须调用整理应用接口');
assertIncludes(aiControllerJs, '/ai/tags/preview', '前端标签系统管理必须调用独立预览接口');
assertIncludes(aiControllerJs, '/ai/tags/apply', '前端标签系统管理必须调用独立应用接口');
assertIncludes(aiControllerJs, '/ai/actions/preview', 'AI 交互必须调用操作计划预览接口');
assertIncludes(aiControllerJs, '/ai/actions/apply', 'AI 交互必须调用操作计划应用接口');
assertIncludes(aiControllerJs, 'user_prompt: currentAiOrganizePrompt.value', '整理预览必须把本次偏好传给后端');
assertIncludes(aiControllerJs, 'isAiTagGovernanceMode', '前端必须区分标签系统管理结果，不能和条目整理混用');
assertIncludes(featureCompositionJs, 'window.SecretBaseAiView.createAiView', '领域装配模块必须复用 AI 视图摘要模块');
assertIncludes(aiViewJs, 'const aiOrganizeSummary = computed', 'AI 整理整体摘要必须根据当前勾选和已删除 chip 实时计算');
assertIncludes(aiViewJs, 'uniqueNewGroups', '密码组摘要必须按唯一新建密码组计数，不能把分配次数当成新建数量');
assertIncludes(indexHtml, 'aiOrganizeSummary.add_group_assignments', 'AI 整理摘要必须显示实时加入密码组次数');
assertNotIncludes(indexHtml, 'aiOrganizeResult.summary.add_groups', 'AI 整理摘要不能继续显示后端初始密码组计数');
assertMatches(stateJs, /organizeTags:\s*true[\s\S]*organizeGroups:\s*false/, '默认只能整理标签，不能同时整理标签和密码组');
assertIncludes(storeStateJs, 'filters:', '整理范围应复用当前列表筛选状态');
assertMatches(
    componentsCss,
    /\.ai-organize-entry\s+summary[\s\S]*?display:\s*block[\s\S]*?\.ai-organize-select[\s\S]*?display:\s*grid[\s\S]*?grid-template-columns:\s*16px\s+minmax\(0,\s*1fr\)/,
    '整理建议标题行必须固定勾选框列，避免勾选框和文字换行错位'
);

console.log('PASS frontend ai organize');
