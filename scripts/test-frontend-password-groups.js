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
assertIncludes(storeJs, 'async assignEntriesToGroup', 'Store 必须封装批量加入密码组接口');
assertIncludes(storeJs, "/groups/${encodeURIComponent(groupName)}/entries", '批量加入密码组必须调用具体密码组接口');

assertIncludes(appJs, 'const groups = ref([])', 'Vue 应用必须维护 groups');
assertIncludes(appJs, 'const activeGroupName = ref', 'Vue 应用必须记录当前密码组筛选');
assertIncludes(appJs, 'function showGroupMode()', '必须提供密码组模式入口');
assertIncludes(appJs, 'async function filterByGroup', '必须提供按密码组筛选');
assertIncludes(appJs, 'function openCreateEntryForActiveGroup', '具体密码组页必须支持新建条目并预填当前密码组');
assertIncludes(appJs, 'async function openGroupEntryPicker', '具体密码组页必须支持打开选择条目弹窗');
assertIncludes(appJs, 'async function assignSelectedEntriesToActiveGroup', '具体密码组页必须支持批量加入已选条目');
assertIncludes(appJs, 'availableGroupPickerEntries', '选择条目弹窗必须过滤已属于当前密码组的条目');
assertIncludes(appJs, 'groupPickerTagFilter', '选择已有条目弹窗必须支持按标签筛选');
assertIncludes(appJs, 'groupPickerGroupFilter', '选择已有条目弹窗必须支持按密码组筛选');
assertIncludes(appJs, 'groupPickerPage', '选择已有条目弹窗必须维护分页页码');
assertIncludes(appJs, 'groupPickerPageSize', '选择已有条目弹窗必须限制每页展示数量');
assertIncludes(appJs, 'groupPickerTotalPages', '选择已有条目弹窗必须计算总页数');
assertIncludes(appJs, 'paginatedGroupPickerEntries', '选择已有条目弹窗必须只渲染当前页条目');
assertIncludes(appJs, 'function goToGroupPickerPage', '选择已有条目弹窗必须提供分页跳转方法');
assertIncludes(appJs, 'function addExistingTag', '编辑器必须支持点选已有标签');
assertIncludes(appJs, 'function addExistingGroup', '编辑器必须支持点选已有密码组');

assertIncludes(indexHtml, '密码组模式', '侧边栏必须展示密码组模式');
assertIncludes(indexHtml, 'class="group-cards"', '主区必须展示密码组卡片');
assertIncludes(indexHtml, '@click="filterByGroup(group.name)"', '点击密码组卡片必须按组筛选');
assertIncludes(indexHtml, '@click="openCreateGroupModal"', '密码组模式主按钮必须打开新建密码组');
assertIncludes(indexHtml, '+ 新建密码组', '密码组模式主按钮必须显示新建密码组');
assertIncludes(indexHtml, 'active-group-toolbar', '进入具体密码组后必须展示密码组操作条');
assertNotIncludes(indexHtml, '<button class="btn-primary" @click="openCreateEntryForActiveGroup">+ 新建条目</button>', '具体密码组操作条不应再出现额外的新建条目按钮');
assertIncludes(indexHtml, '@click="openGroupEntryPicker"', '具体密码组页必须提供选择条目操作');
assertIncludes(indexHtml, '选择已有条目', '具体密码组页选择按钮必须明确为选择已有条目');
assertIncludes(indexHtml, 'showGroupEntryPicker', '必须提供选择条目加入密码组弹窗');
assertIncludes(indexHtml, '加入当前密码组', '选择条目弹窗必须明确加入当前密码组');
assertIncludes(indexHtml, 'groupPickerTagFilter', '选择已有条目弹窗必须提供标签筛选控件');
assertIncludes(indexHtml, 'groupPickerGroupFilter', '选择已有条目弹窗必须提供密码组筛选控件');
assertIncludes(indexHtml, 'paginatedGroupPickerEntries', '选择已有条目弹窗必须渲染分页后的条目');
assertIncludes(indexHtml, 'group-entry-picker-pagination', '选择已有条目弹窗必须展示分页控件');
assertIncludes(indexHtml, '全部标签', '选择已有条目弹窗标签筛选必须提供全部标签选项');
assertIncludes(indexHtml, '全部密码组', '选择已有条目弹窗密码组筛选必须提供全部密码组选项');
assertIncludes(indexHtml, '上一页', '选择已有条目弹窗分页必须提供上一页');
assertIncludes(indexHtml, '下一页', '选择已有条目弹窗分页必须提供下一页');
assertNotIncludes(indexHtml, 'v-model="groupPickerQuery"', '选择已有条目弹窗不应继续提供搜索框');
assertNotIncludes(indexHtml, '搜索标题、网址、标签或已有密码组', '选择已有条目弹窗不再支持搜索，避免和筛选重复');
assertIncludes(indexHtml, '?v=20260708-ui-v49', '前端资源版本必须随选择已有条目弹窗更新，避免浏览器继续使用旧 JS');
assertNotIncludes(indexHtml, '?v=20260708-ui-v48', '不能继续引用旧资源版本，否则选择已有条目弹窗可能继续显示旧 UI');
assertNotIncludes(indexHtml, 'activeGroup?.description', '模板中避免使用可选链，提升 Vue CDN 模板兼容性');
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
