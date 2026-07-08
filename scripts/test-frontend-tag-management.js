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

assertIncludes(indexHtml, '新建标签', '标签管理弹窗必须支持新建空标签');
assertIncludes(indexHtml, '标签简介', '标签管理弹窗必须展示和编辑标签简介');
assertIncludes(indexHtml, '标签颜色', '标签管理弹窗必须展示和编辑标签颜色');
assertIncludes(indexHtml, 'tagEditorForm', '标签管理必须有独立标签编辑表单状态');
assertIncludes(indexHtml, 'createTagFromManager', '标签管理必须调用新建标签方法');
assertIncludes(indexHtml, 'saveManagedTag', '标签管理必须调用保存标签方法');
assertIncludes(appJs, 'function startEditManagedTag', '前端必须支持进入标签实体编辑');
assertIncludes(appJs, 'async function createTagFromManager', '前端必须支持创建空标签实体');
assertIncludes(appJs, 'async function saveManagedTag', '前端必须支持保存标签实体元数据');
assertIncludes(storeJs, 'async createTag', 'Store 必须封装创建标签接口');
assertIncludes(storeJs, 'async updateTag', 'Store 必须封装更新标签接口');
assertIncludes(storeJs, 'async deleteTag', 'Store 必须封装删除标签接口');
assertMatches(
    componentsCss,
    /\.tag-edit-grid[\s\S]*grid-template-columns:\s*minmax\(120px,\s*1fr\)\s+minmax\(160px,\s*2fr\)\s+minmax\(96px,\s*auto\)/,
    '标签编辑表单应使用稳定网格，避免名称、简介和颜色挤在一起'
);

console.log('PASS frontend tag management');
