const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const calls = [];

const api = {
    get: async url => {
        calls.push(['get', url]);
        if (url.startsWith('/entries?')) {
            return {
                data: {
                    items: [{ id: 'entry-1', title: '示例' }],
                    pagination: { page: 3, page_size: 50, total: 11, total_pages: 1 }
                }
            };
        }
        if (url === '/groups') return { data: { groups: [{ name: '工作' }] } };
        if (url === '/tags') return { data: { tags: [{ name: '重要' }] } };
        if (url === '/settings') return { data: { page_size: 50, theme: 'dark' } };
        return { data: {} };
    },
    post: async (url, body) => {
        calls.push(['post', url, body]);
        if (url === '/groups/order') return { data: { groups: [{ name: '工作' }] } };
        return { data: {}, message: '完成' };
    },
    put: async (url, body) => {
        calls.push(['put', url, body]);
        if (url === '/settings') return { data: body };
        return { data: {}, message: '完成' };
    },
    delete: async url => {
        calls.push(['delete', url]);
        return { data: {}, message: '完成' };
    },
    setToken: token => calls.push(['token', token])
};

const context = vm.createContext({
    console,
    URLSearchParams,
    encodeURIComponent,
    Promise,
    Object,
    Array,
    Error,
    api,
    showToast: () => {},
    window: null
});
context.window = context;

[
    'frontend/js/store-state.js',
    'frontend/js/store-auth-settings.js',
    'frontend/js/store-entry-methods.js',
    'frontend/js/store-taxonomy-methods.js',
    'frontend/js/store-trash-methods.js',
    'frontend/js/store.js'
].forEach(file => {
    vm.runInContext(read(file), context, { filename: file });
});
vm.runInContext('globalThis.__store = store;', context);

const store = context.__store;

function assert(condition, message) {
    if (!condition) throw new Error(message);
}

(async () => {
    const entryMethodsSource = read('frontend/js/store-entry-methods.js');
    const taxonomyMethodsSource = read('frontend/js/store-taxonomy-methods.js');
    assert(!entryMethodsSource.includes('await this.loadEntries'), '条目 Store 写操作不得隐式刷新页面数据');
    assert(!taxonomyMethodsSource.includes('await this.load'), '分类 Store 写操作不得隐式刷新页面数据');

    [
        'checkAuth', 'initPassword', 'unlock', 'lock', 'loadSettings', 'updateSettings',
        'loadEntries', 'getEntry', 'createEntry', 'updateEntry', 'deleteEntry', 'batchDelete',
        'batchStar', 'batchUpdateTags', 'toggleStar', 'loadTags', 'createTag', 'updateTag',
        'deleteTag', 'batchDeleteTags', 'loadGroups', 'createGroup', 'updateGroup',
        'updateGroupOrder', 'deleteGroup', 'assignEntriesToGroup', 'loadTrash', 'restoreEntry',
        'permanentlyDelete', 'emptyTrash'
    ].forEach(name => assert(typeof store[name] === 'function', `store 缺少 ${name} 方法`));

    store.state.settings.pageSize = 50;
    store.state.filters = {
        ...store.state.filters,
        search: 'cloud',
        searchScopes: ['title', 'tags'],
        entryIds: ['a', 'b'],
        tag: '重要',
        group: '工作',
        tags: ['云', '生产'],
        untagged: true,
        createdFrom: '2026-01-01',
        createdTo: '2026-01-31',
        hasUrl: 'yes',
        hasRemarks: 'no',
        starred: true,
        sortBy: 'title',
        sortOrder: 'asc'
    };
    const entries = await store.loadEntries(3);
    const entryRequest = calls.find(call => call[0] === 'get' && call[1].startsWith('/entries?'))[1];
    [
        'page=3', 'page_size=50', 'search=cloud', 'search_scopes=title%2Ctags', 'ids=a%2Cb',
        'tag=%E9%87%8D%E8%A6%81', 'group=%E5%B7%A5%E4%BD%9C', 'tags=%E4%BA%91%2C%E7%94%9F%E4%BA%A7',
        'untagged=true', 'created_from=2026-01-01', 'created_to=2026-01-31', 'has_url=true',
        'has_remarks=false', 'starred=true', 'sort_by=title', 'sort_order=asc'
    ].forEach(part => assert(entryRequest.includes(part), `条目筛选参数缺少 ${part}`));
    assert(entries.pagination.pageSize === 50, '分页 page_size 必须映射为 pageSize');
    assert(store.state.entries.length === 1, '加载条目必须同步 Store 状态');

    await store.updateSettings({
        theme: 'light',
        pageSize: 30,
        autoLockMinutes: 10,
        autoBackupRetention: 60
    });
    const settingsCall = calls.find(call => call[0] === 'put' && call[1] === '/settings');
    assert(settingsCall[2].page_size === 30, '设置更新必须转换 pageSize');
    assert(settingsCall[2].auto_lock_minutes === 10, '设置更新必须转换 autoLockMinutes');
    assert(store.state.settings.pageSize === 30, '设置响应必须映射回 pageSize');

    await store.loadGroups();
    const groupMutationStart = calls.length;
    await store.assignEntriesToGroup('工作', ['entry-1']);
    const groupMutationCalls = calls.slice(groupMutationStart);
    assert(groupMutationCalls.some(call => call[0] === 'post' && call[1] === '/groups/%E5%B7%A5%E4%BD%9C/entries'), '批量加入密码组必须调用正确接口');
    assert(!groupMutationCalls.some(call => call[0] === 'get'), 'Store 写操作不应隐式重复加载页面数据');
    assert(store.state.groups[0].name === '工作', '加载密码组必须同步 Store 状态');

    store.clearFilters();
    assert(store.state.filters.group === null, '清除筛选必须恢复密码组筛选默认值');
    assert(store.state.filters.searchScopes.includes('title'), '默认搜索范围必须支持直接搜索标题');
    assert(store.state.filters.searchScopes.includes('field_names'), '默认搜索范围必须包含字段名');
    assert(!store.state.filters.searchScopes.includes('field_values'), '字段值搜索必须由用户主动选择');

    console.log('PASS frontend store runtime');
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
