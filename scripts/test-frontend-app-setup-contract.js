const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const appJs = fs.readFileSync(path.join(root, 'frontend/js/app.js'), 'utf8');
const stateJs = fs.readFileSync(path.join(root, 'frontend/js/app-state.js'), 'utf8');
const dataControllerJs = fs.readFileSync(path.join(root, 'frontend/js/app-data-controller.js'), 'utf8');
const sessionControllerJs = fs.readFileSync(path.join(root, 'frontend/js/app-session-controller.js'), 'utf8');
const contextJs = fs.readFileSync(path.join(root, 'frontend/js/app-template-context.js'), 'utf8');
const { readFrontendMarkup } = require('./frontend-source');
const indexHtml = readFrontendMarkup();

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

assertIncludes(indexHtml, 'entryPageSizeOptions', '条目分页下拉框必须使用 setup 暴露的选项');
assertIncludes(stateJs, 'entryPageSizeOptions,', '共享状态必须暴露条目分页选项');
assertMatches(
    stateJs,
    /const\s+entryPageSizeOptions\s*=\s*\[6,\s*12,\s*20,\s*30,\s*50,\s*100\]/,
    'entryPageSizeOptions 必须在状态工厂中声明，否则 Vue 初始化会 ReferenceError'
);
assertIncludes(dataControllerJs, 'if (api.getToken())', '条目分页自定义必须用 api token 判断解锁状态，不能读取不存在的 store.state.token');
assertMatches(
    dataControllerJs,
    /async function updateEntryPageSize\(value\)\s*\{[\s\S]*?await store\.updateSettings\(\{ pageSize: size \}\)[\s\S]*?await loadEntries\(1\)/,
    '条目分页自定义保存后必须通过 loadEntries(1) 刷新 Vue 列表状态'
);
assertMatches(
    dataControllerJs,
    /async function applySettings\(settings, \{ currentTheme, applyTheme \}\)[\s\S]*?await store\.updateSettings\(\{ pageSize: savedEntryPageSize \}\)/,
    '启动或解锁恢复条目分页偏好时必须等待设置同步完成，避免首次加载仍用旧分页'
);
assertMatches(
    sessionControllerJs,
    /await data\.applySettings\(settings, theme\)/,
    '初始化流程必须等待分页偏好应用后再加载条目'
);
assertMatches(
    sessionControllerJs,
    /await data\.applySettings\(await store\.loadSettings\(\), theme\)/,
    '初始化和解锁流程必须等待分页偏好应用后再加载条目'
);
assertIncludes(indexHtml, 'updateEntryPageSize(settingsForm.pageSize)', '全部条目分页控件必须继续支持自定义每页数量');
assertIncludes(indexHtml, 'entryPageSizeOptions', '全部条目分页控件必须继续支持常用每页数量下拉');
if (/<div class="setting-item">\s*<label>每页条目数<\/label>/.test(indexHtml)) {
    throw new Error('系统设置通用页不应再保留“每页条目数”，分页数量应在各分页区自定义');
}

assertIncludes(appJs, 'window.SecretBaseTemplateContext.createTemplateContext', '根入口必须通过模板上下文集中暴露绑定');
assertIncludes(contextJs, 'state,', '模板上下文必须包含共享状态');
assertIncludes(contextJs, 'views,', '模板上下文必须包含派生视图');
assertIncludes(contextJs, 'actions', '模板上下文必须包含领域操作');

console.log('PASS frontend app setup contract');
