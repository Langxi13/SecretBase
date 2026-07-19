const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const calls = [];
let resolveEntries;
let resolveTags;
let resolveGroups;

const api = {
    get: async url => {
        calls.push(url);
        if (url.startsWith('/entries?')) {
            return new Promise(resolve => { resolveEntries = resolve; });
        }
        if (url === '/tags') return new Promise(resolve => { resolveTags = resolve; });
        if (url === '/groups') return new Promise(resolve => { resolveGroups = resolve; });
        return { data: {} };
    },
    setToken() {}
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
].forEach(file => vm.runInContext(read(file), context, { filename: file }));

vm.runInContext('globalThis.__store = store;', context);
const store = context.__store;
const assert = (condition, message) => {
    if (!condition) throw new Error(message);
};

(async () => {
    store.state.settings.pageSize = 20;
    store.setState({
        entries: [{ id: 'kept-entry' }],
        tags: [{ name: 'kept-tag' }],
        groups: [{ name: 'kept-group' }]
    });

    const entryRequest = store.loadEntries(2, { shouldCommit: () => false });
    resolveEntries({
        data: {
            items: [{ id: 'late-entry' }],
            pagination: { page: 2, total: 1, total_pages: 1 }
        }
    });
    await entryRequest;
    assert(store.state.entries[0].id === 'kept-entry', '迟到条目响应不得写入 Store');

    const tagRequest = store.loadTags({ shouldCommit: () => false });
    resolveTags({ data: { tags: [{ name: 'late-tag' }] } });
    await tagRequest;
    assert(store.state.tags[0].name === 'kept-tag', '迟到标签响应不得写入 Store');

    const groupRequest = store.loadGroups({ shouldCommit: () => false });
    resolveGroups({ data: { groups: [{ name: 'late-group' }] } });
    await groupRequest;
    assert(store.state.groups[0].name === 'kept-group', '迟到密码组响应不得写入 Store');
    assert(calls.length === 3, '提交守卫测试必须各发起一次读取请求');
    console.log('PASS frontend store commit guard');
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
