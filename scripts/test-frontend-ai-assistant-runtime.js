const vm = require('vm');
const { readProjectFile } = require('./frontend-source');

const ref = value => ({ value });
const calls = [];
let releaseSubmit;
const submitGate = new Promise(resolve => {
    releaseSubmit = resolve;
});

const api = {
    async get(path) {
        calls.push({ method: 'GET', path });
        if (path === '/ai/status') {
            return { data: { configured: true, provider_name: '测试接口', model: 'test-model' } };
        }
        if (path === '/ai/assistant/conversations') return { data: { conversations: [] } };
        if (path.startsWith('/ai/assistant/conversations/')) return { data: { messages: [] } };
        throw new Error(`未处理 GET ${path}`);
    },
    async post(path, data) {
        calls.push({ method: 'POST', path, data });
        if (path === '/ai/assistant/turns/preview') {
            return {
                data: {
                    preview_token: 'preview-token-12345678901234567890',
                    source_revision: 4,
                    manifest: {
                        provider_name: '测试接口',
                        target_host: 'api.example.test',
                        model: 'test-model',
                        entry_count: 1,
                        includes_field_values: false,
                        data_types: ['本轮提示词', '标题'],
                        warnings: []
                    }
                }
            };
        }
        if (path === '/ai/assistant/turns/prepare') {
            return {
                data: {
                    conversation_id: 'conversation-1',
                    turn_token: 'turn-token-1234567890123456789012'
                }
            };
        }
        if (path === '/ai/assistant/turns/submit') {
            await submitGate;
            return {
                data: {
                    conversation_id: 'conversation-1',
                    message: '已生成建议',
                    actions: [],
                    warnings: ['计划类型已自动纠正'],
                    privacy_note: '本轮未发送字段值。'
                }
            };
        }
        if (path === '/ai/assistant/plans/apply') {
            return {
                message: '已应用 2 项 AI 操作',
                data: {
                    undo_token: 'undo-token',
                    revision: 5,
                    domains: ['groups', 'tags']
                }
            };
        }
        if (path === '/ai/assistant/conversations') {
            return { data: { id: 'conversation-1' } };
        }
        throw new Error(`未处理 POST ${path}`);
    },
    async delete() {
        return { data: null };
    }
};

const sandbox = {
    console,
    Promise,
    Uint32Array,
    encodeURIComponent,
    setTimeout,
    clearTimeout
};
sandbox.document = { querySelector: () => null };
sandbox.window = {
    confirm: () => true,
    setTimeout,
    crypto: require('crypto').webcrypto
};
const context = vm.createContext(sandbox);
vm.runInContext(readProjectFile('frontend/js/controllers/ai-assistant-inspector-controller.js'), context, {
    filename: 'ai-assistant-inspector-controller.js'
});
vm.runInContext(readProjectFile('frontend/js/controllers/ai-assistant-controller.js'), context, {
    filename: 'ai-assistant-controller.js'
});

const showAiAssistant = ref(true);
const showAiParse = ref(false);
const aiAssistantInput = ref('请整理密码组，内部提示词 XYZ');
const aiAssistantBusy = ref(false);
const aiAssistantPrepared = ref(null);
const aiAssistantMessages = ref([]);
const aiAssistantPlan = ref(null);
const aiAssistantLastResult = ref(null);
const aiAssistantInspector = {
    open: false,
    loading: false,
    error: '',
    actionTitle: '',
    actionReason: '',
    targets: [],
    page: 1,
    pageSize: 8,
    activeEntryId: '',
    entry: null
};
let settingsOpened = 0;
const store = {
    state: { filters: {} },
    async getEntry(id) {
        return {
            id,
            title: '生产控制台',
            tags: ['开发'],
            groups: ['服务器'],
            fields: [{ name: '登录密码', value: 'local-only', hidden: true, copyable: true }]
        };
    }
};
const resetAiAssistantInspector = () => Object.assign(aiAssistantInspector, {
    open: false,
    loading: false,
    error: '',
    actionTitle: '',
    actionReason: '',
    targets: [],
    page: 1,
    pageSize: 8,
    activeEntryId: '',
    entry: null
});
const inspectorController = context.window.SecretBaseAiAssistantInspectorController.createAiAssistantInspectorController({
    store,
    showToast() {},
    async copyToClipboard() {},
    aiAssistantInspector,
    resetAiAssistantInspector
});

const controller = context.window.SecretBaseAiAssistantController.createAiAssistantController({
    nextTick: async () => {},
    api,
    store,
    showToast() {},
    async copyToClipboard() {},
    showAiAssistant,
    showAiParse,
    aiStatus: ref({ configured: true, provider_name: '测试接口', model: 'test-model' }),
    aiAssistantMode: ref('assistant'),
    aiAssistantScope: ref('all'),
    aiAssistantInput,
    aiAssistantBusy,
    aiAssistantStage: ref(''),
    aiAssistantError: ref(''),
    aiAssistantConversations: ref([]),
    aiAssistantConversationId: ref('conversation-1'),
    aiAssistantMessages,
    aiAssistantPrepared,
    aiAssistantPlan,
    aiAssistantLastResult,
    aiAssistantHistoryOpen: ref(false),
    selectedEntry: ref(null),
    currentPage: ref(1),
    assistantFiltersForScope: () => ({}),
    assistantScopeCount: () => 1,
    async refreshAssistantScopeCatalog() {},
    closeAssistantScopePicker() {},
    resetAssistantScopeForConversation() {},
    async loadEntries() {},
    async loadTags() {},
    async loadGroups() {},
    async openSettings() { settingsOpened += 1; },
    async selectSettingsTab() {},
    normalizeAssistantActionTargets: inspectorController.normalizeAssistantActionTargets,
    resetAssistantInspector: inspectorController.resetAssistantInspector,
    assistantPlanHasSelectedConflicts: inspectorController.assistantPlanHasSelectedConflicts
});

(async () => {
    await controller.sendAssistantMessage();

    const previewCalls = calls.filter(call => call.path === '/ai/assistant/turns/preview');
    if (previewCalls.length !== 1) throw new Error('点击预览必须只请求一次发送清单');
    if (JSON.stringify(previewCalls[0].data).includes('内部提示词 XYZ')) {
        throw new Error('用户确认前，发送清单请求不得携带提示词');
    }
    if (calls.some(call => call.path === '/ai/assistant/turns/prepare' || call.path === '/ai/assistant/turns/submit')) {
        throw new Error('用户确认前不得准备或提交 AI 请求');
    }
    if (aiAssistantPrepared.value.originalMessage !== '请整理密码组，内部提示词 XYZ') {
        throw new Error('发送确认页必须在浏览器本地保留提示词预览');
    }

    const firstSubmit = controller.submitPreparedTurn();
    await Promise.resolve();
    await Promise.resolve();
    const duplicateSubmit = controller.submitPreparedTurn();
    await duplicateSubmit;

    const prepareCalls = calls.filter(call => call.path === '/ai/assistant/turns/prepare');
    const submitCalls = calls.filter(call => call.path === '/ai/assistant/turns/submit');
    if (prepareCalls.length !== 1 || submitCalls.length !== 1) {
        throw new Error('重复点击确认不得产生并发 AI 请求');
    }
    if (prepareCalls[0].data.message !== '请整理密码组，内部提示词 XYZ') {
        throw new Error('只有确认后的准备请求才能携带提示词');
    }
    if (submitCalls[0].data.acknowledge_risk !== true) {
        throw new Error('模型请求必须携带本轮用户确认标记');
    }
    if (!aiAssistantBusy.value || !aiAssistantMessages.value.some(message => message.pending)) {
        throw new Error('确认发送后必须进入明确的处理中状态');
    }

    await controller.openProfessionalAiTools();
    if (!showAiAssistant.value || !showAiParse.value) {
        throw new Error('发送过程中仍必须能打开专业工具，且 AI 管家保留在下层');
    }

    await controller.openAssistantSettings();
    if (!showAiAssistant.value || settingsOpened !== 1) {
        throw new Error('发送过程中仍必须能打开服务设置，且 AI 管家保留在下层');
    }
    if (calls.filter(call => call.path === '/ai/assistant/turns/submit').length !== 1) {
        throw new Error('打开子面板不得取消或重发正在进行的 AI 请求');
    }

    releaseSubmit();
    await firstSubmit;
    if (aiAssistantBusy.value) throw new Error('请求完成后必须解除忙碌状态');
    if (aiAssistantMessages.value.some(message => message.pending)) {
        throw new Error('请求完成后必须移除临时用户消息');
    }
    if (aiAssistantLastResult.value?.warnings?.[0] !== '计划类型已自动纠正') {
        throw new Error('无可执行计划时仍必须保留 AI 回复及计划纠正警告');
    }
    if (aiAssistantLastResult.value?.privacyNote !== '本轮未发送字段值。') {
        throw new Error('无可执行计划时仍必须保留本轮隐私说明');
    }

    aiAssistantPlan.value = context.window.SecretBaseAiAssistantPlanHelpers.normalizeAssistantPlan({
        message: '将创建测试密码组和测试标签',
        plan_token: 'first-plan-token',
        source_revision: 4,
        actions: [
            { id: 'assistant-1', type: 'create_group', domain: 'groups', title: '新建密码组「测试」' },
            { id: 'assistant-2', type: 'create_tag', domain: 'tags', title: '新建标签「测试」' }
        ],
        conflicts: []
    }, { scope: 'all', scopeEntryCount: 1 }, 'all', inspectorController.normalizeAssistantActionTargets);
    if (aiAssistantPlan.value.actionGroups.length !== 2 || !aiAssistantPlan.value.actions.every(action => action.selected)) {
        throw new Error('复合计划必须按领域分组，并默认选择普通操作');
    }
    aiAssistantInput.value = '确认执行';
    const submitCountBeforeConfirmation = calls.filter(call => call.path === '/ai/assistant/turns/submit').length;
    await controller.sendAssistantMessage();
    if (calls.filter(call => call.path === '/ai/assistant/plans/apply').length !== 1) {
        throw new Error('确认执行必须直接应用当前本地计划');
    }
    if (calls.filter(call => call.path === '/ai/assistant/turns/submit').length !== submitCountBeforeConfirmation) {
        throw new Error('确认执行不得再次发送给模型');
    }
    const applyCall = calls.find(call => call.path === '/ai/assistant/plans/apply');
    if (JSON.stringify(applyCall.data.selected_ids) !== JSON.stringify(['assistant-1', 'assistant-2'])) {
        throw new Error('复合计划必须通过一个令牌一次提交全部选中领域操作');
    }
    if (aiAssistantPlan.value !== null || aiAssistantLastResult.value?.undoToken !== 'undo-token') {
        throw new Error('复合计划应用后必须只保留一个统一撤销入口');
    }

    const conflictPlan = context.window.SecretBaseAiAssistantPlanHelpers.normalizeAssistantPlan({
        actions: [
            { id: 'rename-tag', type: 'update_tag', domain: 'tags', title: '重命名标签' },
            { id: 'assign-tag', type: 'assign_tags', domain: 'tags', title: '分配新标签' }
        ],
        conflicts: [{ id: 'conflict-1', action_ids: ['rename-tag', 'assign-tag'], message: '标签目标冲突' }]
    }, {}, 'all', inspectorController.normalizeAssistantActionTargets);
    if (!inspectorController.assistantPlanHasSelectedConflicts(conflictPlan)) {
        throw new Error('同时选中冲突操作时必须阻止复合计划提交');
    }
    inspectorController.toggleAssistantPlanGroup(conflictPlan.actionGroups[0], false);
    if (inspectorController.assistantPlanHasSelectedConflicts(conflictPlan)) {
        throw new Error('取消冲突分组后必须解除提交阻止状态');
    }

    await inspectorController.openAssistantActionEntries({
        title: '重命名生产控制台',
        reason: '统一名称',
        entryTargets: [{ id: 'entry-1', title: '生产控制台' }]
    });
    if (!aiAssistantInspector.open || aiAssistantInspector.entry?.fields?.[0]?.revealed !== false) {
        throw new Error('建议详情必须从本机加载完整条目，隐藏字段默认保持遮罩');
    }

    console.log('PASS frontend ai assistant runtime');
})().catch(error => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
});
