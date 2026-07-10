const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const { readFrontendMarkup } = require('./frontend-source');

const indexHtml = readFrontendMarkup();
const appJs = read('frontend/js/app.js');
const featureCompositionJs = read('frontend/js/app-feature-composition.js');
const templateContextJs = read('frontend/js/app-template-context.js');
const entryControllerJs = read('frontend/js/controllers/entry-controller.js');

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

assertIncludes(indexHtml, '在此基础上新建', '编辑条目弹窗必须提供基于当前条目新建的入口');
assertIncludes(indexHtml, 'v-if="showEditModal"', '基于当前条目新建入口必须只在编辑模式展示');
assertIncludes(indexHtml, '@click="createEntryFromCurrentEdit"', '基于当前条目新建入口必须调用专用方法');
assertIncludes(indexHtml, '?v=20260710-ui-v70', '前端资源版本必须随模块拆分更新，避免浏览器继续使用旧 JS');
assertMatches(
    indexHtml,
    /<div v-if="!showEditModal" class="form-group">[\s\S]*?<label>条目模板<\/label>/,
    '从编辑切换到新建后必须显示现有模板选择控件'
);

assertIncludes(featureCompositionJs, 'window.SecretBaseEntryController.createEntryController', '领域装配模块必须装配条目控制器');
assertIncludes(entryControllerJs, 'function createEntryFromCurrentEdit', '必须提供从当前编辑表单转为新建条目的方法');
assertMatches(
    entryControllerJs,
    /function createEntryFromCurrentEdit\(\)\s*\{[\s\S]*?entryForm\.id\s*=\s*null[\s\S]*?selectedTemplate\.value\s*=\s*''[\s\S]*?showEditModal\.value\s*=\s*false[\s\S]*?showCreateModal\.value\s*=\s*true[\s\S]*?\}/,
    '从编辑转为新建时必须清空 id、清空模板选择并切换到创建模式'
);
assertIncludes(
    entryControllerJs,
    'showEditModal.value && entryForm.id',
    '保存逻辑必须继续只在编辑模式且存在 id 时更新旧条目，否则创建新条目'
);
assertIncludes(templateContextJs, 'actions', '领域操作必须通过模板上下文暴露给 Vue 模板使用');

console.log('PASS frontend entry duplicate');
