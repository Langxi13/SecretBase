const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const lineCount = file => read(file).split('\n').length;

const indexHtml = read('frontend/index.html');
const appJs = read('frontend/js/app.js');
const utilsJs = read('frontend/js/utils.js');
const aiWorkspaceCss = read('frontend/css/ai-workspace.css');
const { cssPaths, readFrontendAssetVersion } = require('./frontend-source');
const assetVersion = readFrontendAssetVersion();

function assertIncludes(content, needle, message) {
    if (!content.includes(needle)) {
        throw new Error(message);
    }
}

function assertNotIncludes(content, needle, message) {
    if (content.includes(needle)) {
        throw new Error(message);
    }
}

function assertLessThan(actual, expected, message) {
    if (!(actual < expected)) {
        throw new Error(`${message}，当前 ${actual}，期望小于 ${expected}`);
    }
}

[
    'css/base.css',
    'css/workspace.css',
    'css/workspace-responsive.css',
    'css/workspace-polish.css',
    'css/modals.css',
    'css/form-controls.css',
    'css/ai-components.css',
    'css/ai-workspace.css',
    'css/ai-scope-picker.css',
    'css/ai-send-review.css',
    'css/management-components.css',
    'css/ai-diagnostics.css',
    'css/component-responsive.css',
    'css/visual-polish.css',
    'css/component-polish.css',
    'css/modal-layout.css'
].forEach(asset => assertIncludes(indexHtml, `${asset}?v=${assetVersion}`, `入口页必须加载 ${asset}`));
assertNotIncludes(indexHtml, 'css/style.css', '入口页不应继续加载巨型 style.css');
assertNotIncludes(indexHtml, 'css/components.css', '入口页不应继续加载巨型 components.css');
assertIncludes(indexHtml, `js/storage.js?v=${assetVersion}`, '安全存储适配必须先于应用模块加载');
assertIncludes(indexHtml, `js/pagination.js?v=${assetVersion}`, '分页偏好工具必须拆到独立 JS 模块');
assertIncludes(indexHtml, `js/toast.js?v=${assetVersion}`, 'Toast 工具必须拆到独立 JS 模块');
assertIncludes(aiWorkspaceCss, `@import url('./ai-entry-inspector.css?v=${assetVersion}')`, 'AI 工作区必须加载独立建议详情样式');
assertIncludes(aiWorkspaceCss, `@import url('./ai-plan-review.css?v=${assetVersion}')`, 'AI 工作区必须加载独立复合计划审核样式');

assertIncludes(appJs, 'window.SecretBasePagination', 'app.js 必须复用分页偏好工具模块');
assertNotIncludes(appJs, 'function normalizeUniversalPageSize', 'app.js 不应继续内联通用分页归一化函数');
assertNotIncludes(utilsJs, 'function showToast', 'utils.js 不应继续承载 Toast DOM 组件逻辑');

assertLessThan(lineCount('frontend/js/app.js'), 140, 'app.js 必须保持为轻量装配入口');
cssPaths.forEach(file => {
    if (!fs.existsSync(path.join(root, file))) {
        throw new Error(`拆分后的样式文件缺失：${file}`);
    }
    assertLessThan(lineCount(file), 900, `${file} 必须保持为可维护体量`);
});
if (fs.existsSync(path.join(root, 'frontend/css/style.css')) || fs.existsSync(path.join(root, 'frontend/css/components.css'))) {
    throw new Error('旧的巨型样式聚合文件应删除，避免后续继续堆叠规则');
}

console.log('PASS frontend module split');
