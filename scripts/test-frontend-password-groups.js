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

assertIncludes(storeJs, 'groups: []', 'Store 必须维护 groups 状态');
assertIncludes(storeJs, 'group: null', 'Store filters 必须包含 group');
assertIncludes(storeJs, "params.append('group'", 'loadEntries 必须传递 group 筛选参数');
assertIncludes(storeJs, 'async loadGroups()', 'Store 必须提供 loadGroups');

assertIncludes(appJs, 'const groups = ref([])', 'Vue 应用必须维护 groups');
assertIncludes(appJs, 'const activeGroupName = ref', 'Vue 应用必须记录当前密码组筛选');
assertIncludes(appJs, 'function showGroupMode()', '必须提供密码组模式入口');
assertIncludes(appJs, 'async function filterByGroup', '必须提供按密码组筛选');
assertIncludes(appJs, 'function addExistingTag', '编辑器必须支持点选已有标签');
assertIncludes(appJs, 'function addExistingGroup', '编辑器必须支持点选已有密码组');

assertIncludes(indexHtml, '密码组模式', '侧边栏必须展示密码组模式');
assertIncludes(indexHtml, 'class="group-cards"', '主区必须展示密码组卡片');
assertIncludes(indexHtml, '@click="filterByGroup(group.name)"', '点击密码组卡片必须按组筛选');
assertIncludes(indexHtml, '@click="openCreateGroupModal"', '密码组模式主按钮必须打开新建密码组');
assertIncludes(indexHtml, '+ 新建密码组', '密码组模式主按钮必须显示新建密码组');
assertNotIncludes(indexHtml, '像相册一样整理密码', '密码组模式说明文案必须保持简短');
assertIncludes(appJs, 'function openCreateGroupModal', '必须提供新建密码组弹窗入口');
assertIncludes(appJs, 'async function saveGroup', '必须提供保存密码组方法');
assertIncludes(indexHtml, '已有标签', '编辑器必须展示已有标签选择区');
assertIncludes(indexHtml, '密码组', '编辑器必须展示密码组选择区');
assertIncludes(indexHtml, 'compact-check-option', '字段可复制/隐藏必须使用紧凑勾选样式');

assertMatches(
    componentsCss,
    /\.compact-check-option\s+input\[type="checkbox"\][\s\S]*?width:\s*14px[\s\S]*?height:\s*14px/,
    '紧凑勾选框必须限制为 14px'
);

assertMatches(
    componentsCss,
    /\.fields-editor\s+\.field-item\s+\.compact-check-option[\s\S]*?height:\s*26px[\s\S]*?padding:\s*0\s+8px[\s\S]*?font-size:\s*var\(--font-size-xs\)/,
    '编辑器字段的可复制/隐藏选项必须使用 26px 紧凑高度'
);

console.log('PASS frontend password groups');
