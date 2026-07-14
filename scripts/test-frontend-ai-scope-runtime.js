const vm = require('vm');
const { readProjectFile } = require('./frontend-source');

const ref = value => ({ value });
const calls = [];
const api = {
    async post(path, body) {
        calls.push({ path, body });
        if (path !== '/ai/assistant/scope/catalog') throw new Error(`未处理 ${path}`);
        return {
            data: {
                counts: { all: 4, current_view: 4 },
                items: [
                    { id: 'entry-1', title: 'Alpha', hostname: 'alpha.test', starred: true, tags: ['开发'], groups: [] },
                    { id: 'entry-2', title: 'Beta', hostname: 'beta.test', starred: false, tags: [], groups: ['工作'] }
                ],
                pagination: { page: body.page, page_size: body.page_size, total: 4, total_pages: 2 },
                tags: ['开发'],
                groups: ['工作'],
                valid_selected_ids: body.selected_ids
            }
        };
    }
};

const context = vm.createContext({ console, window: {} });
vm.runInContext(readProjectFile('frontend/js/controllers/ai-scope-controller.js'), context, {
    filename: 'ai-scope-controller.js'
});

const aiAssistantScope = ref('all');
const picker = {
    open: false,
    loaded: false,
    loading: false,
    error: '',
    draftScope: 'all',
    selectedIds: [],
    draftSelectedIds: [],
    search: '',
    tag: '',
    group: '',
    starred: '',
    page: 1,
    pageSize: 10,
    items: [],
    pagination: { page: 1, pageSize: 10, total: 0, totalPages: 1 },
    counts: { all: 0, currentView: 0 },
    tags: [],
    groups: []
};
let resetCount = 0;
const controller = context.window.SecretBaseAiScopeController.createAiScopeController({
    api,
    store: {
        state: {
            filters: {
                starred: false,
                tag: null,
                entryIds: [],
                search: ''
            }
        }
    },
    aiAssistantScope,
    aiAssistantScopePicker: picker,
    searchQuery: ref(''),
    selectedSearchScopes: ref([]),
    sortBy: ref('updated_at'),
    sortOrder: ref('desc'),
    selectedEntryIds: ref(['entry-2']),
    resetAiAssistantScope() { resetCount += 1; }
});

(async () => {
    await controller.openAssistantScopePicker();
    if (!picker.open || picker.counts.all !== 4 || picker.counts.currentView !== 4) {
        throw new Error('打开范围弹窗后必须加载全部与当前筛选数量');
    }
    if (Object.prototype.hasOwnProperty.call(calls[0].body.filters, 'starred')) {
        throw new Error('主页未启用收藏筛选时不得把 starred=false 解释为仅未收藏');
    }

    controller.selectAssistantScopeMode('selection');
    controller.toggleAssistantScopeEntry('entry-1');
    controller.importCurrentEntrySelection();
    controller.confirmAssistantScopePicker();
    if (aiAssistantScope.value !== 'selection') throw new Error('确认后必须切换到自定义选择范围');
    const selectedFilters = controller.assistantFiltersForScope();
    if (selectedFilters.entryIds.join(',') !== 'entry-1,entry-2') {
        throw new Error('自定义选择必须只提交用户勾选的条目 ID');
    }
    if (selectedFilters.starred !== undefined || selectedFilters.tag !== undefined) {
        throw new Error('自定义选择不得继续叠加主页筛选条件');
    }

    await controller.changeAssistantScopePageSize(20);
    if (calls.at(-1).body.page_size !== 20 || calls.at(-1).body.page !== 1) {
        throw new Error('切换每页条数后必须回到第一页重新加载');
    }
    if (controller.assistantScopeSummary() !== '自定义选择 · 2') {
        throw new Error('输入器必须显示明确的自定义范围摘要');
    }

    await controller.openAssistantScopePicker();
    controller.toggleAssistantScopeEntry('entry-1');
    await controller.filterAssistantScopeEntries();
    controller.closeAssistantScopePicker();
    if (controller.assistantFiltersForScope().entryIds.join(',') !== 'entry-1,entry-2') {
        throw new Error('关闭范围弹窗必须丢弃未确认的选择修改');
    }

    controller.resetAssistantScopeForConversation();
    if (resetCount !== 1) throw new Error('切换 AI 会话时必须重置分析范围');

    console.log('PASS frontend ai scope runtime');
})().catch(error => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
});
