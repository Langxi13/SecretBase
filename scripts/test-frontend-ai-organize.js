const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

const indexHtml = read('frontend/index.html');
const appJs = read('frontend/js/app.js');
const storeJs = read('frontend/js/store.js');
const componentsCss = read('frontend/css/components.css');

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
assertIncludes(indexHtml, '条目标签整理', '整理条目模式必须支持单条目维度的标签整理');
assertIncludes(indexHtml, '密码组整理', '整理条目模式必须支持密码组整理');
assertIncludes(indexHtml, '标签系统管理', 'AI 弹窗必须提供独立标签系统管理模式');
assertIncludes(indexHtml, '整体摘要', '整理建议必须先展示整体摘要');
assertIncludes(indexHtml, '逐条建议', '整理建议必须支持逐条确认');
assertIncludes(indexHtml, '应用整理', '用户必须手动应用整理结果');
assertIncludes(indexHtml, '不会发送字段值', 'AI 整理必须提示不会发送字段值');
assertIncludes(indexHtml, 'ai-organize-select', '整理建议标题行必须使用专用紧凑选择样式');
assertIncludes(indexHtml, 'ai-organize-mode-tabs', '整理标签和密码组必须使用互斥模式切换');
assertIncludes(indexHtml, "setAiOrganizeMode('tags')", '必须提供整理标签模式入口');
assertIncludes(indexHtml, "setAiOrganizeMode('groups')", '必须提供整理密码组模式入口');
assertIncludes(indexHtml, "setAiOrganizeMode('tag-governance')", '必须提供标签系统管理模式入口');
assertNotIncludes(indexHtml, 'v-model="aiOrganizeOptions.organizeTags"> 整理标签', '整理标签不能再使用可同时勾选的 checkbox');
assertNotIncludes(indexHtml, 'v-model="aiOrganizeOptions.organizeGroups"> 整理密码组', '整理密码组不能再使用可同时勾选的 checkbox');

assertIncludes(appJs, "const aiMode = ref('parse')", 'AI 弹窗必须有 parse/organize 模式状态');
assertIncludes(appJs, 'function setAiOrganizeMode', '必须提供互斥整理模式切换方法');
assertIncludes(appJs, 'async function previewAiOrganize', '必须提供 AI 整理预览方法');
assertIncludes(appJs, 'async function applyAiOrganize', '必须提供 AI 整理应用方法');
assertIncludes(appJs, '/ai/organize/preview', '前端必须调用整理预览接口');
assertIncludes(appJs, '/ai/organize/apply', '前端必须调用整理应用接口');
assertIncludes(appJs, '/ai/tags/preview', '前端标签系统管理必须调用独立预览接口');
assertIncludes(appJs, '/ai/tags/apply', '前端标签系统管理必须调用独立应用接口');
assertIncludes(appJs, 'isAiTagGovernanceMode', '前端必须区分标签系统管理结果，不能和条目整理混用');
assertMatches(appJs, /organizeTags:\s*true[\s\S]*organizeGroups:\s*false/, '默认只能整理标签，不能同时整理标签和密码组');
assertIncludes(storeJs, 'filters:', '整理范围应复用当前列表筛选状态');
assertMatches(
    componentsCss,
    /\.ai-organize-entry\s+summary[\s\S]*?display:\s*block[\s\S]*?\.ai-organize-select[\s\S]*?display:\s*grid[\s\S]*?grid-template-columns:\s*16px\s+minmax\(0,\s*1fr\)/,
    '整理建议标题行必须固定勾选框列，避免勾选框和文字换行错位'
);

console.log('PASS frontend ai organize');
