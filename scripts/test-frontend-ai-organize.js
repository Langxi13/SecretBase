const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

const indexHtml = read('frontend/index.html');
const appJs = read('frontend/js/app.js');
const storeJs = read('frontend/js/store.js');

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

assertIncludes(indexHtml, '智能录入', 'AI 弹窗必须保留智能录入模式');
assertIncludes(indexHtml, '整理条目', 'AI 弹窗必须新增整理条目模式');
assertIncludes(indexHtml, '整理标签', '整理条目模式必须支持整理标签');
assertIncludes(indexHtml, '整理密码组', '整理条目模式必须支持整理密码组');
assertIncludes(indexHtml, '整体摘要', '整理建议必须先展示整体摘要');
assertIncludes(indexHtml, '逐条建议', '整理建议必须支持逐条确认');
assertIncludes(indexHtml, '应用整理', '用户必须手动应用整理结果');
assertIncludes(indexHtml, '不会发送字段值', 'AI 整理必须提示不会发送字段值');

assertIncludes(appJs, "const aiMode = ref('parse')", 'AI 弹窗必须有 parse/organize 模式状态');
assertIncludes(appJs, 'async function previewAiOrganize', '必须提供 AI 整理预览方法');
assertIncludes(appJs, 'async function applyAiOrganize', '必须提供 AI 整理应用方法');
assertIncludes(appJs, '/ai/organize/preview', '前端必须调用整理预览接口');
assertIncludes(appJs, '/ai/organize/apply', '前端必须调用整理应用接口');
assertMatches(appJs, /organizeTags:\s*true[\s\S]*organizeGroups:\s*true/, '默认同时整理标签和密码组');
assertIncludes(storeJs, 'filters:', '整理范围应复用当前列表筛选状态');

console.log('PASS frontend ai organize');
