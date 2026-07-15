const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const { readFrontendMarkup, readFrontendCss } = require('./frontend-source');

const indexHtml = readFrontendMarkup();
const appJs = read('frontend/js/app.js');
const stateJs = read('frontend/js/app-state.js');
const featureCompositionJs = read('frontend/js/app-feature-composition.js');
const appUiControllerJs = read('frontend/js/app-ui-controller.js');
const groupControllerJs = read('frontend/js/controllers/group-controller.js');
const listControllerJs = read('frontend/js/controllers/list-controller.js');
const appWatchersJs = read('frontend/js/app-watchers.js');
const entryControllerJs = read('frontend/js/controllers/entry-controller.js');
const viewHelpersJs = read('frontend/js/view-helpers.js');
const storeJs = read('frontend/js/store.js');
const storeStateJs = read('frontend/js/store-state.js');
const storeTaxonomyMethodsJs = read('frontend/js/store-taxonomy-methods.js');
const styleCss = readFrontendCss();
const componentsCss = readFrontendCss();

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

assertIncludes(storeStateJs, 'groups: []', 'Store 必须维护 groups 状态');
assertIncludes(storeStateJs, 'group: null', 'Store filters 必须包含 group');
assertIncludes(storeStateJs, "params.append('group'", 'loadEntries 必须传递 group 筛选参数');
assertIncludes(storeTaxonomyMethodsJs, 'async loadGroups()', 'Store 必须提供 loadGroups');
assertIncludes(storeTaxonomyMethodsJs, 'async assignEntriesToGroup', 'Store 必须封装批量加入密码组接口');
assertIncludes(storeTaxonomyMethodsJs, "/groups/${encodeURIComponent(groupName)}/entries", '批量加入密码组必须调用具体密码组接口');
assertIncludes(storeTaxonomyMethodsJs, 'async updateGroupOrder', 'Store 必须封装密码组自定义排序接口');
assertIncludes(storeTaxonomyMethodsJs, "api.post('/groups/order'", '密码组排序必须调用集合级排序接口');

assertIncludes(stateJs, 'const groups = ref([])', 'Vue 应用必须维护 groups');
assertIncludes(stateJs, 'const activeGroupName = ref', 'Vue 应用必须记录当前密码组筛选');
assertIncludes(featureCompositionJs, 'window.SecretBaseGroupController.createGroupController', '领域装配模块必须装配密码组控制器');
assertIncludes(groupControllerJs, 'async function showGroupMode()', '必须提供密码组模式入口');
assertIncludes(groupControllerJs, 'async function filterByGroup', '必须提供按密码组筛选');
assertIncludes(groupControllerJs, 'function openCreateEntryForActiveGroup', '具体密码组页必须支持新建条目并预填当前密码组');
assertIncludes(groupControllerJs, 'async function openGroupEntryPicker', '具体密码组页必须支持打开选择条目弹窗');
assertIncludes(groupControllerJs, 'async function assignSelectedEntriesToActiveGroup', '具体密码组页必须支持批量加入已选条目');
assertIncludes(groupControllerJs, 'function confirmDeleteGroup', '密码组列表和详情页必须提供受确认保护的删除操作');
assertIncludes(groupControllerJs, 'showConfirmDialog(\'删除密码组\'', '删除密码组必须使用应用内确认对话框');
assertIncludes(groupControllerJs, 'await store.deleteGroup(name)', '确认删除后必须调用 Store 密码组删除接口');
assertIncludes(listControllerJs, "filter.value === 'group'", '清除密码组筛选时必须识别密码组来源上下文');
assertIncludes(listControllerJs, 'await returnToGroupMode()', '密码组详情清除筛选后必须返回密码组模式');
assertIncludes(appWatchersJs, 'watch(state.groups', '密码组数量变化后必须校正分页页码');
assertIncludes(featureCompositionJs, 'availableGroupPickerEntries', '选择条目弹窗必须过滤已属于当前密码组的条目');
assertIncludes(stateJs, 'groupPickerTagFilter', '选择已有条目弹窗必须支持按标签筛选');
assertIncludes(stateJs, 'groupPickerGroupFilter', '选择已有条目弹窗必须支持按密码组筛选');
assertIncludes(stateJs, 'groupPickerPage', '选择已有条目弹窗必须维护分页页码');
assertIncludes(stateJs, 'groupPickerPageSize', '选择已有条目弹窗必须限制每页展示数量');
assertIncludes(featureCompositionJs, 'groupPickerTotalPages', '选择已有条目弹窗必须计算总页数');
assertIncludes(featureCompositionJs, 'paginatedGroupPickerEntries', '选择已有条目弹窗必须只渲染当前页条目');
assertIncludes(groupControllerJs, 'function goToGroupPickerPage', '选择已有条目弹窗必须提供分页跳转方法');
assertIncludes(entryControllerJs, 'function addExistingTag', '编辑器必须支持点选已有标签');
assertIncludes(entryControllerJs, 'function addExistingGroup', '编辑器必须支持点选已有密码组');

assertIncludes(indexHtml, '<span class="nav-text">密码组</span>', '侧边栏必须展示密码组入口');
assertIncludes(indexHtml, 'class="group-cards"', '主区必须展示密码组卡片');
assertIncludes(indexHtml, '@click="filterByGroup(group.name)"', '点击密码组卡片必须按组筛选');
assertIncludes(indexHtml, 'role="button"', '密码组卡片改为 div 后必须保留按钮语义');
assertIncludes(indexHtml, '@keydown.enter.prevent="filterByGroup(group.name)"', '密码组卡片必须支持键盘进入筛选');
assertIncludes(indexHtml, '@click.stop="openEditGroupModal(group)"', '密码组卡片必须提供编辑入口且不触发进入筛选');
assertIncludes(indexHtml, '@click.stop="confirmDeleteGroup(group)"', '密码组卡片必须提供删除入口且不误触发进入筛选');
assertIncludes(indexHtml, '@click="openCreateGroupModal"', '密码组模式主按钮必须打开新建密码组');
assertIncludes(indexHtml, '+ 新建密码组', '密码组模式主按钮必须显示新建密码组');
assertIncludes(indexHtml, 'active-group-toolbar', '进入具体密码组后必须展示密码组操作条');
assertNotIncludes(indexHtml, '<button class="btn-primary" @click="openCreateEntryForActiveGroup">+ 新建条目</button>', '具体密码组操作条不应再出现额外的新建条目按钮');
assertIncludes(indexHtml, '@click="openGroupEntryPicker"', '具体密码组页必须提供选择条目操作');
assertIncludes(indexHtml, '选择已有条目', '具体密码组页选择按钮必须明确为选择已有条目');
assertIncludes(indexHtml, '@click="showGroupMode">返回密码组', '具体密码组页必须提供明确返回入口');
assertIncludes(indexHtml, '@click="confirmDeleteGroup(activeGroup)">删除密码组', '具体密码组页必须提供删除入口');
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
assertIncludes(indexHtml, '?v=20260715-sync-v1', '前端资源版本必须随模块拆分更新，避免浏览器继续使用旧 JS');
assertNotIncludes(indexHtml, '?v=20260709-ui-v52', '不能继续引用旧资源版本，否则密码组编辑入口可能不可见');
assertNotIncludes(indexHtml, 'activeGroup?.description', '模板中避免使用可选链，提升 Vue CDN 模板兼容性');
assertNotIncludes(indexHtml, '像相册一样整理密码', '密码组模式说明文案必须保持简短');
assertIncludes(groupControllerJs, 'function openCreateGroupModal', '必须提供新建密码组弹窗入口');
assertIncludes(groupControllerJs, 'function openEditGroupModal', '必须提供编辑密码组弹窗入口');
assertIncludes(groupControllerJs, 'async function moveGroupOrder', '密码组卡片必须支持直接移动排序');
assertIncludes(groupControllerJs, 'async function resetGroupOrder', '密码组模式必须支持恢复默认条目数排序');
assertIncludes(groupControllerJs, 'function groupOrderNamesAfterMove', '前端必须基于当前卡片顺序计算新排序');
assertIncludes(appUiControllerJs, 'groupCardStyle: viewHelpers.groupCardStyle', '模板上下文必须复用密码组卡片颜色辅助');
assertIncludes(viewHelpersJs, 'function groupCardStyle', '密码组卡片必须提供颜色变量计算方法');
assertIncludes(viewHelpersJs, 'function entryCardStyle', '条目卡片必须提供颜色变量计算方法');
assertIncludes(viewHelpersJs, 'function visibleEntryGroups', '条目卡片必须限制密码组 chip 数量并提示剩余数量');
assertIncludes(groupControllerJs, 'async function saveGroup', '必须提供保存密码组方法');
assertIncludes(groupControllerJs, 'editingGroupName', '编辑密码组时必须记录原密码组名称');
assertIncludes(storeTaxonomyMethodsJs, 'async updateGroup', 'Store 必须封装密码组更新接口');
assertIncludes(indexHtml, '编辑密码组', '密码组弹窗必须支持编辑标题');
assertIncludes(indexHtml, "(editingGroupName ? '保存' : '创建')", '密码组弹窗保存按钮必须区分创建和编辑');
assertIncludes(indexHtml, "groupSaving ? '保存中...'", '密码组弹窗保存期间必须提供明确反馈');
assertIncludes(indexHtml, '@click.stop="moveGroupOrder(group.name, -1)"', '密码组卡片必须提供上移操作');
assertIncludes(indexHtml, '@click.stop="moveGroupOrder(group.name, 1)"', '密码组卡片必须提供下移操作');
assertIncludes(indexHtml, '@click="resetGroupOrder"', '密码组模式必须提供恢复默认排序入口');
assertIncludes(indexHtml, 'group-card-action-btn', '密码组卡片操作按钮必须使用专用紧凑样式');
assertIncludes(indexHtml, 'group-card-move-up', '密码组上移按钮必须有独立颜色样式');
assertIncludes(indexHtml, 'group-card-move-down', '密码组下移按钮必须有独立颜色样式');
assertIncludes(indexHtml, 'group-card-edit-action', '密码组编辑按钮必须有独立颜色样式');
assertIncludes(indexHtml, 'group-card-delete-action', '密码组删除按钮必须有独立危险色样式');
assertIncludes(indexHtml, ':style="groupCardStyle(group)"', '密码组卡片必须通过组颜色注入视觉区分变量');
assertIncludes(indexHtml, 'group-card-count-label', '密码组条目数量必须使用更清晰的数字徽章层级');
assertNotIncludes(indexHtml, 'group-sort-modal', '不应为了密码组排序新增独立排序组件');
assertIncludes(indexHtml, '已有标签', '编辑器必须展示已有标签选择区');
assertIncludes(indexHtml, '密码组', '编辑器必须展示密码组选择区');
assertIncludes(indexHtml, 'compact-check-option', '字段可复制/隐藏必须使用紧凑勾选样式');

assertMatches(
    styleCss,
    /\.group-mode-actions[\s\S]*?flex-wrap:\s*nowrap[\s\S]*?white-space:\s*nowrap/,
    '恢复默认排序和新建密码组必须保持同一行且文字不换行'
);

assertMatches(
    styleCss,
    /\.group-card-action-btn[\s\S]*?height:\s*26px[\s\S]*?font-size:\s*12px[\s\S]*?white-space:\s*nowrap/,
    '密码组卡片操作按钮必须保持紧凑且不换行'
);

assertMatches(
    styleCss,
    /\.group-card-date[\s\S]*?position:\s*relative[\s\S]*?border-top:\s*0/,
    '密码组日期行不能再用整行 border-top，否则会和右侧操作按钮重叠'
);

assertMatches(
    styleCss,
    /\.group-card-date::before[\s\S]*?right:\s*210px[\s\S]*?border-top:\s*1px dashed color-mix\(in srgb, var\(--border-color\) 70%, transparent\)/,
    '密码组日期虚线必须避开右侧操作区'
);

assertMatches(
    styleCss,
    /\.group-card-delete-action[\s\S]*?var\(--color-error\)/,
    '密码组删除操作必须使用危险色并保持与其他操作区分'
);

assertMatches(
    styleCss,
    /\.group-card[\s\S]*?--group-accent[\s\S]*?background:[\s\S]*?color-mix\(in srgb, var\(--group-accent\) 10%, var\(--bg-card\)\)/,
    '密码组卡片必须使用组色轻量 tint 背景提升区分度'
);

assertMatches(
    styleCss,
    /\.group-card-meta[\s\S]*?border:[\s\S]*?var\(--group-accent\)[\s\S]*?background:[\s\S]*?var\(--group-accent\)/,
    '密码组数量徽章必须继承组色，形成清晰信息层级'
);

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
