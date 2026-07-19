const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const ref = value => ({ value });

function assert(condition, message) {
    if (!condition) throw new Error(message);
}

const context = vm.createContext({ console, window: null });
context.window = context;
vm.runInContext(read('frontend/js/controllers/tag-controller.js'), context, {
    filename: 'frontend/js/controllers/tag-controller.js'
});

(async () => {
    const storeCalls = [];
    const store = {
        createTag: async payload => {
            storeCalls.push(['create', payload.name]);
            return { name: payload.name };
        },
        updateTag: async (name, payload) => {
            storeCalls.push(['update', name, payload.name]);
            return { old_name: name, new_name: payload.name };
        },
        deleteTag: async name => {
            storeCalls.push(['delete', name]);
            return { affected_count: 1 };
        },
        batchDeleteTags: async names => {
            storeCalls.push(['batch-delete', [...names]]);
            return { deleted_count: names.length };
        },
        setFilter: () => {}
    };
    const selectedManagedTagNames = ref(['旧标签']);
    const tagEditorForm = {
        mode: 'create',
        originalName: '',
        name: '新标签',
        description: '',
        color: '#64748b'
    };
    let confirmation = null;
    let loadTagsCount = 0;
    let loadEntriesCount = 0;
    const showTagManager = ref(true);
    const showTagEditorModal = ref(true);
    const actions = context.SecretBaseTagController.createTagController({
        api: {},
        store,
        showToast: () => {},
        showConfirmDialog: (title, message, callback) => {
            confirmation = { title, message, callback };
        },
        filter: ref('all'),
        activeTagName: ref(''),
        activeGroupName: ref(''),
        listContextNotice: ref(''),
        showTagDropdown: ref(false),
        showTagBrowser: ref(false),
        tagBrowserQuery: ref(''),
        tagBrowserPage: ref(1),
        tagBrowserTotalPages: ref(1),
        loadEntries: async () => { loadEntriesCount += 1; },
        resetAdvancedFilterForm: () => {},
        showTagManager,
        showTagEditorModal,
        tagEditorForm,
        selectedManagedTagNames,
        tagManagerPage: ref(1),
        tagManagerTotalPages: ref(1),
        paginatedManagedTags: ref([]),
        allManagedPageTagsSelected: ref(false),
        tagMergeForm: { sourceTags: '', targetTag: '' },
        tagMergeSourceList: ref([]),
        tagSaving: ref(false),
        tagMerging: ref(false),
        currentPage: ref(2),
        loadTags: async () => { loadTagsCount += 1; }
    });

    actions.deleteTag({ name: '旧标签' });
    assert(storeCalls.length === 0, '确认删除标签前不得调用 Store');
    await confirmation.callback();
    assert(storeCalls[0][0] === 'delete', '确认后必须删除目标标签');
    assert(loadTagsCount === 1 && loadEntriesCount === 1, '删除标签后必须立即刷新标签和条目');
    assert(selectedManagedTagNames.value.length === 0, '删除标签后必须清理失效选择');

    tagEditorForm.mode = 'create';
    tagEditorForm.name = '新标签';
    await actions.createTagFromManager();
    assert(storeCalls.some(call => call[0] === 'create'), '标签管理必须提交新建操作');
    assert(loadTagsCount === 2 && loadEntriesCount === 1, '新建标签后只需刷新标签列表');
    assert(!showTagEditorModal.value, '标签创建成功后必须关闭编辑弹窗');

    tagEditorForm.mode = 'edit';
    tagEditorForm.originalName = '新标签';
    tagEditorForm.name = '重命名标签';
    await actions.saveManagedTag();
    assert(storeCalls.some(call => call[0] === 'update'), '标签管理必须提交编辑操作');
    assert(loadTagsCount === 3 && loadEntriesCount === 2, '编辑标签后必须刷新标签和条目');
    assert(!showTagEditorModal.value, '标签编辑成功后必须关闭编辑弹窗');

    selectedManagedTagNames.value = ['标签 A', '标签 B'];
    await actions.batchDeleteManagedTags();
    await confirmation.callback();
    assert(storeCalls.some(call => call[0] === 'batch-delete'), '标签管理必须提交批量删除');
    assert(loadTagsCount === 4 && loadEntriesCount === 3, '批量删除标签后必须刷新标签和条目');

    console.log('PASS frontend taxonomy refresh runtime');
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
