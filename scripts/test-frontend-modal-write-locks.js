const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const { readFrontendMarkup } = require('./frontend-source');
const ref = value => ({ value });

function assert(condition, message) {
    if (!condition) throw new Error(message);
}

function deferred() {
    let resolve;
    const promise = new Promise(done => { resolve = done; });
    return { promise, resolve };
}

const markup = readFrontendMarkup();
for (const state of ['entrySaving', 'groupSaving', 'groupPickerSaving', 'tagSaving', 'passwordChanging']) {
    assert(markup.includes(`:inert="${state} ? '' : null"`), `${state} 期间必须冻结弹窗表单`);
}

const context = vm.createContext({ console, window: null, Element: class {} });
context.window = context;
context.scrollTo = () => {};
for (const source of [
    'frontend/js/controllers/entry-controller.js',
    'frontend/js/controllers/group-controller.js',
    'frontend/js/controllers/tag-controller.js'
]) {
    vm.runInContext(read(source), context, { filename: source });
}

(async () => {
    const entryRequest = deferred();
    let entryCalls = 0;
    const entrySaving = ref(false);
    const entryActions = context.SecretBaseEntryController.createEntryController({
        api: {},
        store: {
            createEntry: async () => {
                entryCalls += 1;
                return entryRequest.promise;
            }
        },
        showToast: () => {},
        copyToClipboard: async () => true,
        normalizeFieldForEdit: field => ({ ...field }),
        entries: ref([]),
        currentPage: ref(1),
        totalPages: ref(1),
        selectedEntry: ref(null),
        editingEntry: ref(null),
        entryForm: {
            id: null,
            title: '测试条目',
            url: '',
            starred: false,
            tags: [],
            groups: [],
            fields: [{ name: '账号', value: 'demo', copyable: true, hidden: false }],
            remarks: ''
        },
        entryTemplates: [],
        selectedTemplate: ref(''),
        newTag: ref(''),
        newGroup: ref(''),
        newGroupDescription: ref(''),
        groups: ref([]),
        showCreateModal: ref(true),
        showEditModal: ref(false),
        entrySaving,
        showOnboarding: ref(false),
        importingSamples: ref(false),
        selectedEntryIds: ref([]),
        batchTagName: ref(''),
        allCurrentPageSelected: ref(false),
        copyMenuEntryId: ref(null),
        showTagDropdown: ref(false),
        revealedFields: ref([]),
        resetEntryForm: () => {},
        loadEntries: async () => {},
        loadTags: async () => {},
        loadGroups: async () => {},
        loadAllData: async () => {},
        showConfirmDialog: () => {}
    });
    const entryFirst = entryActions.saveEntry();
    const entrySecond = entryActions.saveEntry();
    await Promise.resolve();
    assert(entryCalls === 1 && entrySaving.value, '条目保存没有阻止重复提交');
    entryRequest.resolve({ id: 'entry-1' });
    await Promise.all([entryFirst, entrySecond]);
    assert(!entrySaving.value, '条目保存完成后没有恢复交互状态');

    const groupRequest = deferred();
    const assignmentRequest = deferred();
    let groupCalls = 0;
    let assignmentCalls = 0;
    const groupSaving = ref(false);
    const groupPickerSaving = ref(false);
    const groupActions = context.SecretBaseGroupController.createGroupController({
        api: {},
        store: {
            state: { filters: { sortBy: 'updated_at', sortOrder: 'desc' } },
            createGroup: async () => {
                groupCalls += 1;
                return groupRequest.promise;
            },
            assignEntriesToGroup: async () => {
                assignmentCalls += 1;
                return assignmentRequest.promise;
            },
            clearFilters: () => {},
            setFilter: () => {}
        },
        showToast: () => {},
        showConfirmDialog: () => {},
        groups: ref([]),
        activeGroupName: ref('工作'),
        filter: ref('groups'),
        groupCurrentPage: ref(1),
        groupTotalPages: ref(1),
        searchQuery: ref(''),
        resetSearchScopes: () => {},
        resetAdvancedFilterForm: () => {},
        listContextNotice: ref(''),
        activeTagName: ref(''),
        selectedEntryIds: ref([]),
        sortBy: ref('updated_at'),
        sortOrder: ref('desc'),
        editingGroupName: ref(''),
        groupForm: { name: '工作', description: '' },
        groupSaving,
        showGroupModal: ref(true),
        loadGroups: async () => {},
        loadEntries: async () => {},
        currentPage: ref(1),
        entryForm: { groups: [] },
        resetEntryForm: () => {},
        showCreateModal: ref(false),
        showGroupEntryPicker: ref(true),
        groupPickerEntries: ref([]),
        groupPickerSelectedIds: ref(['entry-1']),
        groupPickerTagFilter: ref(''),
        groupPickerGroupFilter: ref(''),
        groupPickerPage: ref(1),
        groupPickerLoading: ref(false),
        groupPickerSaving,
        groupPickerTotalPages: ref(1),
        paginatedGroupPickerEntries: ref([]),
        allGroupPickerEntriesSelected: ref(false)
    });
    const groupFirst = groupActions.saveGroup();
    const groupSecond = groupActions.saveGroup();
    await Promise.resolve();
    assert(groupCalls === 1 && groupSaving.value, '密码组保存没有阻止重复提交');
    groupRequest.resolve({ name: '工作' });
    await Promise.all([groupFirst, groupSecond]);
    assert(!groupSaving.value, '密码组保存完成后没有恢复交互状态');

    const assignFirst = groupActions.assignSelectedEntriesToActiveGroup();
    const assignSecond = groupActions.assignSelectedEntriesToActiveGroup();
    await Promise.resolve();
    assert(assignmentCalls === 1 && groupPickerSaving.value, '批量加入密码组没有阻止重复提交');
    assignmentRequest.resolve({ affected_count: 1 });
    await Promise.all([assignFirst, assignSecond]);
    assert(!groupPickerSaving.value, '批量加入密码组完成后没有恢复交互状态');

    const tagRequest = deferred();
    const mergeRequest = deferred();
    let tagCalls = 0;
    let mergeCalls = 0;
    const tagSaving = ref(false);
    const tagMerging = ref(false);
    const tagForm = {
        mode: 'create',
        originalName: '',
        name: '测试',
        description: '',
        color: '#64748b'
    };
    const tagActions = context.SecretBaseTagController.createTagController({
        api: {
            post: async () => {
                mergeCalls += 1;
                return mergeRequest.promise;
            }
        },
        store: {
            createTag: async () => {
                tagCalls += 1;
                return tagRequest.promise;
            },
            setFilter: () => {}
        },
        showToast: () => {},
        showConfirmDialog: () => {},
        filter: ref('all'),
        activeTagName: ref(''),
        activeGroupName: ref(''),
        listContextNotice: ref(''),
        showTagDropdown: ref(false),
        showTagBrowser: ref(false),
        tagBrowserQuery: ref(''),
        tagBrowserPage: ref(1),
        tagBrowserTotalPages: ref(1),
        loadEntries: async () => {},
        resetAdvancedFilterForm: () => {},
        showTagManager: ref(true),
        showTagEditorModal: ref(true),
        tagEditorForm: tagForm,
        selectedManagedTagNames: ref([]),
        tagManagerPage: ref(1),
        tagManagerTotalPages: ref(1),
        paginatedManagedTags: ref([]),
        allManagedPageTagsSelected: ref(false),
        tagMergeForm: { sourceTags: '旧标签', targetTag: '新标签' },
        tagMergeSourceList: ref([]),
        tagSaving,
        tagMerging,
        currentPage: ref(1),
        loadTags: async () => {}
    });
    const tagFirst = tagActions.createTagFromManager();
    const tagSecond = tagActions.createTagFromManager();
    await Promise.resolve();
    assert(tagCalls === 1 && tagSaving.value, '标签保存没有阻止重复提交');
    tagRequest.resolve({ name: '测试' });
    await Promise.all([tagFirst, tagSecond]);
    assert(!tagSaving.value, '标签保存完成后没有恢复交互状态');

    tagForm.name = '测试';
    const mergeFirst = tagActions.mergeTags();
    const mergeSecond = tagActions.mergeTags();
    await Promise.resolve();
    assert(mergeCalls === 1 && tagMerging.value, '标签合并没有阻止重复提交');
    mergeRequest.resolve({ message: '已合并' });
    await Promise.all([mergeFirst, mergeSecond]);
    assert(!tagMerging.value, '标签合并完成后没有恢复交互状态');

    console.log('PASS frontend modal write locks');
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
