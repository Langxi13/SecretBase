const vm = require('vm');
const { readProjectFile } = require('./frontend-source');

const ref = value => ({ value });
const calls = [];
let timerId = 0;

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
        throw new Error(`未处理 POST ${path}`);
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

const controller = context.window.SecretBaseAiSettingsController.createAiSettingsController({
    api,
    showToast() {},
    aiSettingsForm: { providerId: 'deepseek', baseUrl: '', apiKey: '', model: '' },
    aiProviders: ref([]),
    aiManualModel: ref(false),
    aiSettingsStatus: ref({ configured: true }),
    aiSettingsEditing: ref(false),
    aiModels: ref([]),
    aiModelsLoading: ref(false),
    aiSettingsSaving: ref(false),
    aiSettingsError: ref(''),
    aiSettingsMessage: ref(''),
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

    console.log('PASS frontend ai diagnostics runtime');
})().catch(error => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
});
