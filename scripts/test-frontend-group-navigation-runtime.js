const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const ref = value => ({ value });

function assert(condition, message) {
    if (!condition) throw new Error(message);
}

const context = vm.createContext({
    console,
    URLSearchParams,
    encodeURIComponent,
    window: null
});
context.window = context;
context.scrollTo = () => {};

[
    'frontend/js/controllers/list-controller.js',
    'frontend/js/controllers/group-controller.js'
].forEach(file => vm.runInContext(read(file), context, { filename: file }));

(async () => {
    const filter = ref('group');
    const activeGroupName = ref('工作');
    let returnCount = 0;
    let loadEntriesCount = 0;
    const listActions = context.SecretBaseListController.createListController({
        debounce: callback => callback,
        store: {
            state: { filters: { sortBy: 'updated_at', sortOrder: 'desc' } },
            clearFilters: () => {},
            setFilter: () => {}
        },
        searchQuery: ref(''),
        selectedSearchScopes: ref([]),
        listContextNotice: ref(''),
        filter,
        activeTagName: ref(''),
        activeGroupName,
        sortBy: ref('updated_at'),
        sortOrder: ref('desc'),
        advancedTagList: ref([]),
        advancedFilters: {
            untagged: false,
            createdFrom: '',
            createdTo: '',
            updatedFrom: '',
            updatedTo: '',
            hasUrl: '',
            hasRemarks: ''
        },
        resetAdvancedFilterForm: () => {},
        commitAdvancedTags: () => {},
        resetSearchScopes: () => {},
        clearSelection: () => {},
        loadEntries: async () => { loadEntriesCount += 1; },
        revealedFields: ref([]),
        isSidebarCollapsed: ref(false),
        returnToGroupMode: async () => {
            returnCount += 1;
            filter.value = 'groups';
            activeGroupName.value = '';
        }
    });

    await listActions.clearListState();
    assert(returnCount === 1, '密码组详情清除筛选必须返回密码组模式');
    assert(loadEntriesCount === 0, '返回密码组模式时不应先加载全部条目');
    assert(filter.value === 'groups', '返回后必须恢复密码组视图状态');

    const groups = ref([
        { name: '工作', count: 3 },
        { name: '个人', count: 0 }
    ]);
    const groupFilter = ref('group');
    const selectedGroup = ref('工作');
    let confirmation = null;
    let deletedName = '';
    let loadGroupsCount = 0;
    let groupLoadEntriesCount = 0;
    const store = {
        state: { filters: { sortBy: 'updated_at', sortOrder: 'desc' } },
        clearFilters: () => {},
        setFilter: () => {},
        deleteGroup: async name => {
            deletedName = name;
            return { affected_count: 3 };
        }
    };
    const groupActions = context.SecretBaseGroupController.createGroupController({
        api: {},
        store,
        showToast: () => {},
        showConfirmDialog: (title, message, callback) => {
            confirmation = { title, message, callback };
        },
        groups,
        activeGroupName: selectedGroup,
        filter: groupFilter,
        groupCurrentPage: ref(2),
        groupTotalPages: ref(2),
        searchQuery: ref('搜索条件'),
        resetSearchScopes: () => {},
        resetAdvancedFilterForm: () => {},
        listContextNotice: ref(''),
        activeTagName: ref(''),
        selectedEntryIds: ref(['entry-1']),
        sortBy: ref('updated_at'),
        sortOrder: ref('desc'),
        editingGroupName: ref(''),
        groupForm: { name: '', description: '' },
        groupSaving: ref(false),
        showGroupModal: ref(false),
        loadGroups: async () => { loadGroupsCount += 1; },
        loadEntries: async () => { groupLoadEntriesCount += 1; },
        currentPage: ref(1),
        entryForm: { groups: [] },
        resetEntryForm: () => {},
        showCreateModal: ref(false),
        showGroupEntryPicker: ref(false),
        groupPickerEntries: ref([]),
        groupPickerSelectedIds: ref([]),
        groupPickerTagFilter: ref(''),
        groupPickerGroupFilter: ref(''),
        groupPickerPage: ref(1),
        groupPickerLoading: ref(false),
        groupPickerSaving: ref(false),
        groupPickerTotalPages: ref(1),
        paginatedGroupPickerEntries: ref([]),
        allGroupPickerEntriesSelected: ref(false)
    });

    groupActions.confirmDeleteGroup(groups.value[0]);
    assert(confirmation?.title === '删除密码组', '删除密码组必须先打开应用内确认对话框');
    assert(confirmation.message.includes('不会删除条目'), '确认文案必须明确不会删除条目');
    assert(deletedName === '', '用户确认前不得调用删除接口');

    await confirmation.callback();
    assert(deletedName === '工作', '用户确认后必须删除目标密码组');
    assert(groupFilter.value === 'groups', '删除当前密码组后必须返回密码组模式');
    assert(selectedGroup.value === '', '删除当前密码组后必须清理失效筛选');
    assert(loadGroupsCount === 1, '返回密码组模式时必须刷新密码组列表');
    assert(groupLoadEntriesCount === 0, '删除当前筛选组后不应加载失效的组内列表');

    confirmation = null;
    deletedName = '';
    groupActions.confirmDeleteGroup(groups.value[1]);
    await confirmation.callback();
    assert(deletedName === '个人', '密码组卡片删除必须提交目标名称');
    assert(loadGroupsCount === 2, '密码组卡片删除后必须立即刷新密码组列表');
    assert(groupLoadEntriesCount === 1, '密码组卡片删除后必须同步刷新条目归属关系');

    console.log('PASS frontend group navigation runtime');
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
