const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

const indexHtml = read('frontend/index.html');
const appJs = read('frontend/js/app.js');
const tagViewJs = read('frontend/js/tag-view.js');
const storeJs = read('frontend/js/store.js');
const componentsCss = [
    read('frontend/css/components.css'),
    read('frontend/css/component-polish.css')
].join('\n');

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
assertIncludes(indexHtml, 'showTagEditorModal', '标签新建/编辑必须使用独立弹窗，避免默认占用标签管理顶部空间');
assertIncludes(indexHtml, 'openCreateTagModal', '标签管理应通过按钮打开新建标签弹窗');
assertIncludes(indexHtml, 'tag-manager-toolbar', '标签管理列表顶部应有简洁工具栏');
assertIncludes(indexHtml, 'tag-manager-list', '标签管理应有独立列表容器');
assertIncludes(indexHtml, 'selectedManagedTagNames', '标签管理必须支持批量选择');
assertIncludes(indexHtml, 'batchDeleteManagedTags', '标签管理必须支持批量删除');
assertIncludes(indexHtml, 'paginatedManagedTags', '标签管理列表必须使用分页数据');
assertIncludes(indexHtml, 'tag-manager-pagination', '标签分页控件必须放在标签列表下方');
assertIncludes(indexHtml, 'tag-manager-segmented', '标签管理应使用分段切换减少弹窗内长距离滚动');
assertIncludes(indexHtml, 'tagManagerPanel', '标签管理应区分列表和合并面板');
assertIncludes(indexHtml, 'paginatedTagBrowserTags', '更多标签弹窗必须分页展示，避免长列表滚动');
assertIncludes(indexHtml, 'tag-browser-pagination', '更多标签分页控件必须固定在底部区域');
assertIncludes(indexHtml, 'tagBrowserPageSize', '更多标签必须允许选择每页标签数量');
assertIncludes(indexHtml, 'tagManagerPageSize', '标签管理必须允许选择每页标签数量');
assertIncludes(indexHtml, 'tag-page-size-control', '每页数量选择应使用统一的紧凑控件样式');
assertIncludes(indexHtml, 'v-for="size in tagPageSizeOptions"', '每页数量下拉框必须复用 5/10/20/50 选项');
assertMatches(
    indexHtml,
    /<div class="tag-manager-toolbar"[\s\S]*openCreateTagModal[\s\S]*<div v-if="tags\.length === 0"/,
    '标签管理主弹窗顶部应是工具栏，而不是默认展开的新建表单'
);
assertIncludes(appJs, 'function startEditManagedTag', '前端必须支持进入标签实体编辑');
assertIncludes(appJs, 'const showTagEditorModal', '前端必须有标签编辑弹窗状态');
assertIncludes(appJs, 'const tagManagerPage', '前端必须有标签管理分页状态');
assertIncludes(appJs, 'const tagManagerPageSize = ref', '标签管理每页数量必须是可变状态');
assertIncludes(appJs, 'const tagManagerPanel', '前端必须有标签管理分段面板状态');
assertIncludes(appJs, 'window.SecretBaseTagView.createTagView', 'app.js 必须复用标签视图模块');
assertIncludes(tagViewJs, 'const paginatedManagedTags', '前端必须计算当前页标签');
assertIncludes(appJs, 'const tagBrowserPage', '前端必须有更多标签分页状态');
assertIncludes(appJs, 'const tagBrowserPageSize = ref', '更多标签每页数量必须是可变状态');
assertIncludes(tagViewJs, 'const paginatedTagBrowserTags', '前端必须计算更多标签当前页数据');
assertIncludes(appJs, 'const tagPageSizeOptions = [5, 10, 20, 50]', '每页数量选项必须固定为 5、10、20、50');
assertIncludes(appJs, 'secretbase.tagBrowserPageSize', '更多标签每页数量必须保存到本地偏好');
assertIncludes(appJs, 'secretbase.tagManagerPageSize', '标签管理每页数量必须保存到本地偏好');
assertIncludes(appJs, 'loadPageSizePreference', '前端必须从统一分页偏好工具恢复标签每页数量');
assertIncludes(appJs, 'savePageSizePreference', '前端必须在用户切换每页数量时暂存偏好');
assertMatches(
    appJs,
    /watch\(tagBrowserPageSize[\s\S]*savePageSizePreference\('secretbase\.tagBrowserPageSize'/,
    '更多标签每页数量变化后必须写入本地偏好'
);
assertMatches(
    appJs,
    /watch\(tagManagerPageSize[\s\S]*savePageSizePreference\('secretbase\.tagManagerPageSize'/,
    '标签管理每页数量变化后必须写入本地偏好'
);
assertIncludes(appJs, 'async function batchDeleteManagedTags', '前端必须支持批量删除标签');
assertIncludes(appJs, 'function openCreateTagModal', '前端必须通过按钮打开新建标签弹窗');
assertIncludes(appJs, 'async function createTagFromManager', '前端必须支持创建空标签实体');
assertIncludes(appJs, 'async function saveManagedTag', '前端必须支持保存标签实体元数据');
assertIncludes(storeJs, 'async createTag', 'Store 必须封装创建标签接口');
assertIncludes(storeJs, 'async updateTag', 'Store 必须封装更新标签接口');
assertIncludes(storeJs, 'async deleteTag', 'Store 必须封装删除标签接口');
assertIncludes(storeJs, 'async batchDeleteTags', 'Store 必须封装批量删除标签接口');
assertMatches(
    componentsCss,
    /\.tag-edit-grid[\s\S]*grid-template-columns:\s*minmax\(120px,\s*1fr\)\s+minmax\(160px,\s*2fr\)\s+minmax\(96px,\s*auto\)/,
    '标签编辑表单应使用稳定网格，避免名称、简介和颜色挤在一起'
);
assertMatches(
    componentsCss,
    /\.tag-manager-pagination[\s\S]*justify-content:\s*center/,
    '标签分页控件应在列表下方居中'
);
assertMatches(
    componentsCss,
    /\.tag-manager-list\s*\{[^}]*overflow-y:\s*auto/,
    '标签管理选择 20/50 每页时，列表区域必须可滚动访问全部标签，不能隐藏超出项'
);
assertMatches(
    componentsCss,
    /\.tag-browser-pagination[\s\S]*justify-content:\s*center/,
    '更多标签分页控件应在底部居中'
);
assertMatches(
    componentsCss,
    /\.tag-browser-list\s*\{[^}]*overflow-y:\s*auto/,
    '更多标签选择 20/50 每页时，列表区域必须可滚动访问全部标签，不能隐藏超出项'
);
assertMatches(
    componentsCss,
    /\.tag-page-size-control[\s\S]*display:\s*inline-flex/,
    '每页数量选择控件应紧凑横向排列'
);

console.log('PASS frontend tag management');
