const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const ref = value => ({ value });

const context = vm.createContext({
    console,
    Promise,
    AbortController,
    setTimeout,
    clearTimeout,
    window: null
});
context.window = context;
vm.runInContext(read('frontend/js/ai-assistant-request.js'), context, { filename: 'ai-assistant-request.js' });
vm.runInContext(read('frontend/js/controllers/ai-controller.js'), context, { filename: 'ai-controller.js' });

function assert(condition, message) {
    if (!condition) throw new Error(message);
}

const requests = [];
const api = {
    async post(pathname, payload, options = {}) {
        if (pathname !== '/ai/organize/preview') throw new Error(`unexpected AI tools request ${pathname}`);
        return new Promise(resolve => {
            requests.push({ pathname, payload, options, resolve });
        });
    }
};
const state = {
    showAiParse: ref(true),
    aiMode: ref('organize'),
    aiText: ref(''),
    aiResult: ref(null),
    aiParsing: ref(false),
    aiStatus: ref({ configured: true }),
    aiStatusError: ref(''),
    aiFailureMessage: ref(''),
    aiOrganizing: ref(false),
    aiRequestCancelable: ref(false),
    aiOrganizeError: ref(''),
    aiOrganizeResult: ref(null),
    aiOrganizeMode: ref('tags'),
    aiOrganizeOptions: { organizeTags: true, organizeGroups: false },
    currentAiOrganizePrompt: ref('只保留必要标签'),
    aiActionInstruction: ref(''),
    aiActionResult: ref(null),
    aiActionError: ref(''),
    aiCooldownUntil: ref(0),
    aiNow: ref(Date.now()),
    lastAiParseText: ref(''),
    isAiTagGovernanceMode: ref(false),
    canPreviewAiOrganize: ref(true),
    canPreviewAiActions: ref(true),
    canParseAi: ref(true),
    aiCooldownSeconds: ref(0),
    aiMaxInputChars: ref(10000),
    searchQuery: ref(''),
    selectedSearchScopes: ref(['title']),
    sortBy: ref('updated_at'),
    sortOrder: ref('desc'),
    currentPage: ref(1),
    entryForm: { fields: [], tags: [], groups: [] },
    showCreateModal: ref(false)
};
const controller = context.SecretBaseAiController.createAiController({
    api,
    store: { state: { filters: {} } },
    showToast: () => {},
    nextTick: async () => {},
    viewHelpers: {},
    ...state,
    resetEntryForm: () => {},
    loadEntries: async () => true,
    loadTags: async () => true,
    loadGroups: async () => true,
    openSettings: async () => {},
    selectSettingsTab: async () => {}
});

(async () => {
    const firstRequest = controller.previewAiOrganize();
    await Promise.resolve();
    assert(state.aiOrganizing.value && state.aiRequestCancelable.value, '专业 AI 请求开始后必须显示忙碌和取消状态');
    controller.setAiOrganizeMode('groups');
    assert(state.aiOrganizeMode.value === 'tags', '专业 AI 请求期间不得切换整理子模式');

    assert(controller.cancelAiRequest() === true, '专业 AI 请求应提供可用的取消入口');
    assert(!state.aiOrganizing.value && !state.aiRequestCancelable.value, '取消专业 AI 请求后必须立即恢复交互');

    const secondRequest = controller.previewAiOrganize();
    await Promise.resolve();
    assert(requests.length === 2, '取消后重新生成建议必须只创建一个新请求');
    requests[0].resolve({ data: { marker: '迟到旧结果' } });
    requests[1].resolve({ data: { marker: '当前新结果' } });
    await Promise.all([firstRequest, secondRequest]);
    assert(state.aiOrganizeResult.value?.marker === '当前新结果', '迟到的旧 AI 响应不得覆盖新建议');
    assert(!state.aiOrganizing.value && !state.aiRequestCancelable.value, '专业 AI 请求完成后必须清理忙碌状态');

    controller.setAiOrganizeMode('groups');
    assert(state.aiOrganizeMode.value === 'groups' && state.aiOrganizeOptions.organizeGroups && !state.aiOrganizeOptions.organizeTags, '取消后整理子模式必须恢复可切换');
    console.log('PASS frontend AI tools runtime');
})().catch(error => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
});
