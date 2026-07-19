const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const ref = value => ({ value });

const sandbox = { console, window: {} };
sandbox.window.window = sandbox.window;
const context = vm.createContext(sandbox);
vm.runInContext(read('frontend/js/controllers/entry-controller.js'), context);
vm.runInContext(read('frontend/js/controllers/trash-controller.js'), context);

function createEntryOptions(overrides = {}) {
    const state = {
        entries: ref([]),
        currentPage: ref(1),
        totalPages: ref(1),
        selectedEntry: ref({ id: 'entry-1', title: '测试条目' }),
        showEntryDetail: ref(true),
        entryDetailTargetId: ref('entry-1'),
        entryDetailLoading: ref(false),
        entryDetailError: ref(''),
        editingEntry: ref(null),
        entryEditLoading: ref(false),
        entryEditTargetId: ref(''),
        entryEditError: ref(''),
        entryForm: {
            id: null,
            title: '测试条目',
            url: '',
            starred: false,
            tags: [],
            groups: [],
            fields: [],
            remarks: ''
        },
        entryTemplates: [],
        selectedTemplate: ref(''),
        newTag: ref(''),
        newGroup: ref('新组'),
        newGroupDescription: ref(''),
        groups: ref([]),
        showCreateModal: ref(false),
        showEditModal: ref(false),
        entrySaving: ref(false),
        entryActionIds: ref([]),
        selectedEntryIds: ref(['entry-1']),
        batchTagName: ref(''),
        batchBusy: ref(false),
        allCurrentPageSelected: ref(false),
        copyMenuEntryId: ref(null),
        showTagDropdown: ref(false),
        revealedFields: ref([])
    };
    const toasts = [];
    let confirmCallback = null;
    const options = {
        store: {
            async getEntry() { return state.selectedEntry.value; },
            async deleteEntry() { return true; },
            async createGroup() { return { name: '新组' }; },
            async batchStar() { return { updated: 1 }; }
        },
        showToast: (...args) => toasts.push(args),
        copyToClipboard: async () => true,
        openExternalUrl: async url => url,
        normalizeFieldForEdit: field => ({ ...field }),
        ...state,
        resetEntryForm: () => {},
        loadEntries: async () => true,
        loadTags: async () => true,
        loadGroups: async () => true,
        showConfirmDialog: (_title, _message, callback) => { confirmCallback = callback; }
    };
    Object.assign(options, overrides);
    return { options, state, toasts, getConfirmCallback: () => confirmCallback };
}

(async () => {
    const opened = createEntryOptions();
    const entryActions = context.window.SecretBaseEntryController.createEntryController(opened.options);
    if (await entryActions.openUrl('https://example.invalid') !== 'https://example.invalid') {
        throw new Error('条目详情网址必须使用注入的外部链接能力');
    }

    entryActions.confirmDeleteEntry({ id: 'entry-1', title: '测试条目' });
    await opened.getConfirmCallback()();
    if (opened.state.showEntryDetail.value || opened.state.selectedEntry.value !== null) {
        throw new Error('删除条目成功后必须关闭详情弹窗并清理当前条目');
    }

    const groupFailure = createEntryOptions({
        loadGroups: async () => { throw new Error('密码组服务不可用'); }
    });
    const groupActions = context.window.SecretBaseEntryController.createEntryController(groupFailure.options);
    if (await groupActions.addGroup() !== false) throw new Error('密码组加载失败时应中止添加');
    if (groupFailure.state.entryForm.groups.includes('新组')) throw new Error('密码组添加失败后不得残留未确认的归属');
    if (!groupFailure.toasts.some(item => String(item[0]).includes('密码组服务不可用'))) {
        throw new Error('密码组添加失败必须显示可操作错误');
    }

    const starFailure = createEntryOptions({
        store: {
            async batchStar() { throw new Error('批量星标服务不可用'); }
        }
    });
    const starActions = context.window.SecretBaseEntryController.createEntryController(starFailure.options);
    await starActions.batchStarSelected(true);
    if (starFailure.state.batchBusy.value) throw new Error('批量星标失败后必须恢复交互状态');
    if (!starFailure.toasts.some(item => String(item[0]).includes('批量星标服务不可用'))) {
        throw new Error('批量星标失败必须显示可操作错误');
    }

    const trashVisible = ref(true);
    const trashActions = context.window.SecretBaseTrashController.createTrashController({
        api: {},
        showToast: () => {},
        showConfirmDialog: () => {},
        trashItems: ref([]),
        trashPage: ref(1),
        trashTotalPages: ref(1),
        trashTotal: ref(0),
        trashPageSize: ref(10),
        trashActionIds: ref([]),
        trashEmptying: ref(false),
        showTrash: trashVisible,
        loadEntries: async () => true,
        trashLoading: ref(false),
        trashError: ref(''),
        locked: ref(false)
    });
    trashActions.closeTrash();
    if (trashVisible.value) throw new Error('回收站关闭操作必须真正隐藏弹窗');

    console.log('PASS frontend interaction gaps');
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
