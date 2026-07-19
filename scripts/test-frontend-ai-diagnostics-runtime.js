const vm = require('vm');
const { readProjectFile } = require('./frontend-source');

const ref = value => ({ value });
const calls = [];
let timerId = 0;
let confirmCallback = null;
let releaseModels;

const api = {
    async get(path) {
        calls.push({ method: 'GET', path });
        if (path === '/ai/assistant/diagnostics/preview') {
            return {
                data: {
                    case_count: 16,
                    estimated_max_tokens: 100000,
                    includes_real_vault_data: false,
                    includes_field_values: false
                }
            };
        }
        if (path === '/ai/assistant/diagnostics/status') {
            return {
                data: {
                    status: 'completed',
                    progress: 16,
                    total: 16,
                    results: [],
                    summary: { passed: 16, degraded: 0, blocked: 0, failed: 0 }
                }
            };
        }
        throw new Error(`未处理 GET ${path}`);
    },
    async post(path, data) {
        calls.push({ method: 'POST', path, data });
        if (path === '/ai/assistant/diagnostics/run') {
            return {
                data: {
                    status: 'running',
                    progress: 0,
                    total: 16,
                    results: []
                }
            };
        }
        if (path === '/ai/models') {
            return new Promise(resolve => { releaseModels = resolve; });
        }
        throw new Error(`未处理 POST ${path}`);
    },
    async put(path, data) {
        calls.push({ method: 'PUT', path, data });
        if (path === '/ai/settings') {
            return { data: { configured: true, provider_id: 'deepseek', base_url: data.baseUrl, model: data.model } };
        }
        throw new Error(`未处理 PUT ${path}`);
    },
    async delete(path) {
        calls.push({ method: 'DELETE', path });
        if (path === '/ai/settings') return { data: { configured: false } };
        throw new Error(`未处理 DELETE ${path}`);
    }
};

const sandbox = {
    console,
    setTimeout() { timerId += 1; return timerId; },
    clearTimeout() {}
};
sandbox.window = {};
const context = vm.createContext(sandbox);
vm.runInContext(readProjectFile('frontend/js/controllers/ai-settings-controller.js'), context, {
    filename: 'ai-settings-controller.js'
});

const aiDiagnosticsPreview = ref(null);
const aiDiagnosticsReport = ref(null);
const aiDiagnosticsBusy = ref(false);
const aiDiagnosticsError = ref('');
const aiSettingsSaving = ref(false);
const aiModelsLoading = ref(false);
const aiSettingsError = ref('');
const aiSettingsMessage = ref('');
const aiSettingsStatus = ref({ configured: true, base_url: 'https://api.example.invalid', model: 'old-model' });
const aiSettingsForm = { providerId: 'deepseek', baseUrl: 'https://api.example.invalid', apiKey: 'new-key', model: 'new-model' };

const controller = context.window.SecretBaseAiSettingsController.createAiSettingsController({
    api,
    showToast() {},
    showConfirmDialog: (_title, _message, callback) => { confirmCallback = callback; },
    aiSettingsForm,
    aiProviders: ref([]),
    aiManualModel: ref(false),
    aiSettingsStatus,
    aiSettingsEditing: ref(true),
    aiModels: ref([]),
    aiModelsLoading,
    aiSettingsSaving,
    aiSettingsError,
    aiSettingsMessage,
    aiDiagnosticsPreview,
    aiDiagnosticsReport,
    aiDiagnosticsBusy,
    aiDiagnosticsError
});

(async () => {
    await controller.previewAiDiagnostics();
    if (!aiDiagnosticsPreview.value || aiDiagnosticsPreview.value.case_count !== 16) {
        throw new Error('诊断必须先加载合成测试与预算预览');
    }
    if (calls.some(call => call.path === '/ai/assistant/diagnostics/run')) {
        throw new Error('用户确认前不得启动真实模型诊断');
    }

    await controller.runAiDiagnostics();
    const runCall = calls.find(call => call.path === '/ai/assistant/diagnostics/run');
    if (!runCall || runCall.data.acknowledge_cost !== true) {
        throw new Error('运行诊断必须提交明确的额度确认');
    }
    if (!aiDiagnosticsBusy.value || aiDiagnosticsReport.value?.status !== 'running') {
        throw new Error('诊断启动后必须显示运行状态');
    }

    await controller.refreshAiDiagnosticsStatus(false);
    if (aiDiagnosticsBusy.value || aiDiagnosticsReport.value?.status !== 'completed') {
        throw new Error('诊断完成后必须停止忙碌状态并保留报告');
    }
    if (aiDiagnosticsError.value) throw new Error('正常诊断流程不应产生错误');

    await controller.saveAiConfiguration();
    if (aiSettingsSaving.value) throw new Error('AI 设置保存成功后不得永久停留在保存中');
    if (!calls.some(call => call.method === 'PUT' && call.path === '/ai/settings')) {
        throw new Error('AI 设置保存必须调用保存接口');
    }

    controller.clearAiConfiguration();
    if (typeof confirmCallback !== 'function') throw new Error('清除 AI 配置必须先请求确认');
    await confirmCallback();
    if (aiSettingsSaving.value) throw new Error('AI 设置清除成功后不得永久停留在保存中');
    if (!calls.some(call => call.method === 'DELETE' && call.path === '/ai/settings')) {
        throw new Error('清除 AI 配置必须调用删除接口');
    }

    aiSettingsForm.baseUrl = 'https://api.example.invalid';
    aiSettingsForm.apiKey = 'temporary-key';
    aiSettingsForm.model = '';
    const loadingModels = controller.fetchAiModels();
    await Promise.resolve();
    if (!aiModelsLoading.value) throw new Error('获取模型列表开始后必须显示加载状态');
    controller.disposeAiSettings();
    if (aiModelsLoading.value) throw new Error('关闭设置后必须立即释放模型列表加载锁');
    releaseModels({ data: { models: ['late-model'] } });
    await loadingModels;
    if (aiModelsLoading.value) throw new Error('迟到的模型响应不得重新锁定设置页');

    console.log('PASS frontend ai diagnostics runtime');
})().catch(error => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
});
