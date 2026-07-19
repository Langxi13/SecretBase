const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const ref = value => ({ value });

const uiSandbox = { window: {} };
uiSandbox.window.window = uiSandbox.window;
vm.runInContext(read('frontend/js/app-ui-controller.js'), vm.createContext(uiSandbox));

const uiState = {
    selectedSearchScopes: ref([]),
    defaultSearchScopes: [],
    entryForm: { fields: [] },
    newTag: ref(''),
    newGroup: ref(''),
    newGroupDescription: ref(''),
    selectedTemplate: ref(''),
    confirmTitle: ref(''),
    confirmMessage: ref(''),
    confirmSubmitting: ref(false),
    confirmError: ref(''),
    showConfirm: ref(false)
};
const ui = uiSandbox.window.SecretBaseAppUiController.createAppUiController({
    state: uiState,
    store: { setFilter() {} },
    viewHelpers: {}
});

const dataSandbox = { window: {} };
dataSandbox.window.window = dataSandbox.window;
vm.runInContext(read('frontend/js/app-data-controller.js'), vm.createContext(dataSandbox));

let resolveTags;
let rejectTags;
let tagCalls = 0;
const dataState = {
    dataLoading: ref(false),
    dataLoadError: ref(''),
    entries: ref([{ id: 'old-entry' }]),
    tags: ref([{ name: 'old-tag' }]),
    groups: ref([{ name: 'old-group' }]),
    groupCurrentPage: ref(1),
    totalPages: ref(1),
    totalEntries: ref(1),
    currentPage: ref(1),
    settingsForm: { pageSize: 20 },
    settings: {}
};
const store = {
    state: { settings: { pageSize: 20 } },
    async loadTags() {
        tagCalls += 1;
        if (tagCalls === 1) {
            return new Promise((resolve, reject) => {
                resolveTags = resolve;
                rejectTags = reject;
            });
        }
        if (tagCalls === 2) {
            return new Promise((resolve, reject) => {
                rejectTags = reject;
            });
        }
        return [{ name: 'new-tag' }];
    },
    async loadGroups() {
        return [{ name: 'new-group' }];
    },
    async loadEntries() {
        return { items: [{ id: 'new-entry' }], pagination: { totalPages: 1, total: 1, page: 1 } };
    },
    async updateSettings() {}
};
const data = dataSandbox.window.SecretBaseAppDataController.createAppDataController({
    api: { getToken: () => null },
    store,
    state: dataState,
    normalizeUniversalPageSize: value => Number(value) || 20,
    loadPageSizePreference: (_key, fallback) => fallback,
    savePageSizePreference() {},
    getGroupTotalPages: () => 1
});

(async () => {
    ui.showConfirmDialog('失败操作', '确认？', async () => false);
    await ui.confirmAction();
    if (!uiState.showConfirm.value || !uiState.confirmError.value) {
        throw new Error('确认回调失败后应保留弹窗并显示可重试提示');
    }

    ui.showConfirmDialog('成功操作', '确认？', async () => true);
    await ui.confirmAction();
    if (uiState.showConfirm.value) throw new Error('确认回调成功后没有关闭弹窗');

    const pendingTags = data.loadTags();
    data.invalidateRequests();
    resolveTags([{ name: 'stale-tag' }]);
    await pendingTags;
    if (dataState.tags.value[0].name !== 'old-tag') {
        throw new Error('锁定后迟到的标签响应不应覆盖已清理的界面');
    }

    const failed = data.loadTags();
    rejectTags(new Error('标签服务不可用'));
    await failed;
    if (!dataState.dataLoadError.value.includes('标签服务不可用')) {
        throw new Error('标签加载失败应保留可见错误提示');
    }
    await data.loadTags();
    if (dataState.dataLoadError.value) throw new Error('标签重试成功后错误提示未清除');
    console.log('PASS frontend data interaction runtime');
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
