const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const lineCount = file => read(file).split('\n').length;

const indexHtml = read('frontend/index.html');
const appJs = read('frontend/js/app.js');

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
    'js/view-helpers.js?v=20260710-ui-v65',
    'js/tag-view.js?v=20260710-ui-v65',
    'js/backup-view.js?v=20260710-ui-v65',
    'js/ai-view.js?v=20260710-ui-v65',
    'js/app.js?v=20260710-ui-v65'
].forEach(asset => {
    assertIncludes(indexHtml, asset, `index.html 必须加载 ${asset}`);
});

assertIncludes(appJs, 'window.SecretBaseViewHelpers', 'app.js 必须复用视图辅助模块');
assertIncludes(appJs, 'window.SecretBaseTagView.createTagView', 'app.js 必须复用标签视图模块');
assertIncludes(appJs, 'window.SecretBaseBackupView.createBackupView', 'app.js 必须复用备份视图模块');
assertIncludes(appJs, 'window.SecretBaseAiView.createAiView', 'app.js 必须复用 AI 视图模块');

assertNotIncludes(appJs, 'function entryAccentColor', '条目强调色逻辑不应继续内联在 app.js');
assertNotIncludes(appJs, 'function normalizeFieldForEdit', '字段编辑归一化不应继续内联在 app.js');
assertNotIncludes(appJs, 'const sortedTagBrowserTags = computed', '标签排序视图不应继续内联在 app.js');
assertNotIncludes(appJs, 'const backupGroups = computed', '备份分组视图不应继续内联在 app.js');
assertNotIncludes(appJs, 'const aiOrganizeSummary = computed', 'AI 整理摘要不应继续内联在 app.js');

assertLessThan(lineCount('frontend/js/app.js'), 3100, 'app.js 必须继续拆分到可维护体量');

console.log('PASS frontend feature modules');
