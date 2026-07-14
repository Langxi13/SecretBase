/**
 * AI 厂商、模型与加密接入设置。
 */
(function () {
    function createAiSettingsController({
        api,
        showToast,
        aiSettingsForm,
        aiProviders,
        aiManualModel,
        aiSettingsStatus,
        aiSettingsEditing,
        aiModels,
        aiModelsLoading,
        aiSettingsSaving,
        aiSettingsError,
        aiSettingsMessage,
        aiDiagnosticsPreview,
        aiDiagnosticsReport,
        aiDiagnosticsBusy,
        aiDiagnosticsError
    }) {
        let diagnosticsPollTimer = null;

        function stopDiagnosticsPolling() {
            if (diagnosticsPollTimer) {
                clearTimeout(diagnosticsPollTimer);
                diagnosticsPollTimer = null;
            }
        }

        function resetAiDiagnosticsState() {
            stopDiagnosticsPolling();
            aiDiagnosticsPreview.value = null;
            aiDiagnosticsReport.value = null;
            aiDiagnosticsBusy.value = false;
            aiDiagnosticsError.value = '';
        }

        function scheduleDiagnosticsPolling() {
            stopDiagnosticsPolling();
            diagnosticsPollTimer = setTimeout(() => {
                refreshAiDiagnosticsStatus(true);
            }, 1500);
        }

        async function refreshAiDiagnosticsStatus(keepPolling = false) {
            try {
                const result = await api.get('/ai/assistant/diagnostics/status');
                const report = result.data || null;
                aiDiagnosticsReport.value = report;
                aiDiagnosticsBusy.value = report?.status === 'running';
                if (keepPolling && aiDiagnosticsBusy.value) {
                    scheduleDiagnosticsPolling();
                } else {
                    stopDiagnosticsPolling();
                }
            } catch (error) {
                stopDiagnosticsPolling();
                aiDiagnosticsBusy.value = false;
                aiDiagnosticsError.value = error.message || '无法读取 AI 诊断状态';
            }
        }

        async function previewAiDiagnostics() {
            aiDiagnosticsError.value = '';
            try {
                const result = await api.get('/ai/assistant/diagnostics/preview');
                aiDiagnosticsPreview.value = result.data || null;
            } catch (error) {
                aiDiagnosticsPreview.value = null;
                aiDiagnosticsError.value = error.message || '无法准备 AI 兼容性诊断';
            }
        }

        function cancelAiDiagnosticsPreview() {
            aiDiagnosticsPreview.value = null;
        }

        async function runAiDiagnostics() {
            if (!aiDiagnosticsPreview.value || aiDiagnosticsBusy.value) return;
            aiDiagnosticsError.value = '';
            aiDiagnosticsBusy.value = true;
            try {
                const result = await api.post('/ai/assistant/diagnostics/run', {
                    acknowledge_cost: true
                }, { timeoutMs: 20000 });
                aiDiagnosticsPreview.value = null;
                aiDiagnosticsReport.value = result.data || null;
                scheduleDiagnosticsPolling();
                showToast('AI 兼容性诊断已开始', 'success');
            } catch (error) {
                aiDiagnosticsBusy.value = false;
                aiDiagnosticsError.value = error.message || 'AI 兼容性诊断启动失败';
            }
        }

        async function loadAiProviders() {
            try {
                const result = await api.get('/ai/providers');
                aiProviders.value = result.data?.providers || [];
            } catch (error) {
                aiProviders.value = [{
                    id: 'custom',
                    name: '自定义 OpenAI 兼容接口',
                    base_url: ''
                }];
            }
        }

        async function loadAiSettingsStatus() {
            aiSettingsError.value = '';
            try {
                if (aiProviders.value.length === 0) {
                    await loadAiProviders();
                }
                const result = await api.get('/ai/status');
                const status = result.data || {};
                status.base_url = status.base_url || status.baseUrl || '';
                aiSettingsStatus.value = status;
                aiSettingsForm.providerId = status.provider_id || 'custom';
                aiSettingsForm.baseUrl = status.base_url || '';
                aiSettingsForm.model = status.model || '';
                aiSettingsForm.apiKey = '';
                aiModels.value = status.model ? [status.model] : [];
                aiManualModel.value = false;
                aiSettingsEditing.value = !status.configured;
                if (status.configured) {
                    refreshAiDiagnosticsStatus(true);
                }
            } catch (error) {
                aiSettingsStatus.value = null;
                aiSettingsEditing.value = true;
                aiSettingsError.value = error.message || '无法加载 AI 配置状态';
            }
        }

        function selectAiProvider() {
            const provider = aiProviders.value.find(item => item.id === aiSettingsForm.providerId);
            const nextUrl = provider?.base_url || '';
            if (nextUrl !== aiSettingsForm.baseUrl) {
                aiSettingsForm.baseUrl = nextUrl;
                aiSettingsForm.apiKey = '';
                aiSettingsForm.model = '';
                aiModels.value = [];
            }
            aiManualModel.value = false;
            aiSettingsError.value = '';
            aiSettingsMessage.value = provider?.category === 'aggregator'
                ? '聚合服务会把请求转发给所选模型供应方，请确认其隐私政策。'
                : '';
        }

        function resetAiProviderUrl() {
            const provider = aiProviders.value.find(item => item.id === aiSettingsForm.providerId);
            if (!provider?.base_url) return;
            aiSettingsForm.baseUrl = provider.base_url;
            aiSettingsMessage.value = '已恢复该厂商的官方 Base URL';
        }

        function enableAiManualModel() {
            aiManualModel.value = true;
            aiModels.value = [];
            aiSettingsMessage.value = '可以直接填写厂商控制台中的模型 ID';
        }

        async function fetchAiModels() {
            aiSettingsError.value = '';
            aiSettingsMessage.value = '';
            const baseUrl = aiSettingsForm.baseUrl.trim();
            const apiKey = aiSettingsForm.apiKey.trim();
            if (!baseUrl || !apiKey) {
                if (!(aiSettingsStatus.value?.configured && baseUrl === aiSettingsStatus.value.base_url)) {
                    aiSettingsError.value = '请先填写 Base URL 和 API Key';
                    return;
                }
            }
            if (!baseUrl) {
                aiSettingsError.value = '请先填写 Base URL';
                return;
            }

            aiModelsLoading.value = true;
            try {
                const result = await api.post('/ai/models', {
                    providerId: aiSettingsForm.providerId,
                    baseUrl,
                    apiKey
                });
                aiModels.value = result.data?.models || [];
                if (!aiModels.value.includes(aiSettingsForm.model)) {
                    aiSettingsForm.model = aiModels.value[0] || '';
                }
                aiSettingsMessage.value = aiModels.value.length > 0
                    ? `已获取 ${aiModels.value.length} 个模型`
                    : '服务商未返回可用模型';
                aiManualModel.value = aiModels.value.length === 0;
            } catch (error) {
                aiModels.value = [];
                aiManualModel.value = true;
                aiSettingsError.value = `${error.message || '获取模型列表失败'}，可以手动填写模型 ID。`;
            } finally {
                aiModelsLoading.value = false;
            }
        }

        async function saveAiConfiguration() {
            aiSettingsError.value = '';
            aiSettingsMessage.value = '';
            const baseUrl = aiSettingsForm.baseUrl.trim();
            const apiKey = aiSettingsForm.apiKey.trim();
            const model = aiSettingsForm.model;
            if (!baseUrl || !model) {
                aiSettingsError.value = '请填写 Base URL，并从模型列表中选择模型';
                return;
            }
            if (!apiKey && !(aiSettingsStatus.value?.configured && baseUrl === aiSettingsStatus.value.base_url)) {
                aiSettingsError.value = '请填写 API Key';
                return;
            }

            aiSettingsSaving.value = true;
            try {
                const result = await api.put('/ai/settings', {
                    providerId: aiSettingsForm.providerId,
                    baseUrl,
                    apiKey,
                    model
                });
                aiSettingsStatus.value = result.data;
                aiSettingsForm.providerId = result.data?.provider_id || aiSettingsForm.providerId;
                aiSettingsForm.apiKey = '';
                aiModels.value = result.data?.model ? [result.data.model] : [];
                aiSettingsEditing.value = false;
                resetAiDiagnosticsState();
                aiSettingsMessage.value = 'AI 连通测试通过，设置已保存';
                showToast('AI 设置已保存', 'success');
            } catch (error) {
                aiSettingsError.value = error.message || 'AI 连通测试失败，设置未保存';
            } finally {
                aiSettingsSaving.value = false;
            }
        }

        async function clearAiConfiguration() {
            aiSettingsError.value = '';
            aiSettingsMessage.value = '';
            try {
                const result = await api.delete('/ai/settings');
                aiSettingsStatus.value = result.data;
                aiSettingsForm.baseUrl = '';
                aiSettingsForm.providerId = 'deepseek';
                aiSettingsForm.apiKey = '';
                aiSettingsForm.model = '';
                aiModels.value = [];
                aiManualModel.value = false;
                aiSettingsEditing.value = true;
                resetAiDiagnosticsState();
                aiSettingsMessage.value = 'AI 设置已清除';
                showToast('AI 设置已清除', 'success');
            } catch (error) {
                aiSettingsError.value = error.message || '清除 AI 设置失败';
            }
        }

        function resetConfigurationForm(editing) {
            aiSettingsEditing.value = editing;
            aiSettingsError.value = '';
            aiSettingsMessage.value = '';
            aiSettingsForm.baseUrl = aiSettingsStatus.value?.base_url || '';
            aiSettingsForm.providerId = aiSettingsStatus.value?.provider_id || 'custom';
            aiSettingsForm.model = aiSettingsStatus.value?.model || '';
            aiSettingsForm.apiKey = '';
            aiModels.value = aiSettingsStatus.value?.model ? [aiSettingsStatus.value.model] : [];
            aiManualModel.value = false;
        }

        return {
            loadAiSettingsStatus,
            loadAiProviders,
            selectAiProvider,
            resetAiProviderUrl,
            enableAiManualModel,
            fetchAiModels,
            saveAiConfiguration,
            clearAiConfiguration,
            editAiConfiguration: () => resetConfigurationForm(true),
            cancelAiConfigurationEdit: () => resetConfigurationForm(false),
            previewAiDiagnostics,
            cancelAiDiagnosticsPreview,
            runAiDiagnostics,
            refreshAiDiagnosticsStatus
        };
    }

    window.SecretBaseAiSettingsController = {
        createAiSettingsController
    };
})();
