/**
 * 首次使用引导与假示例数据导入。
 */
(function () {
    function createEntryOnboardingController({
        api,
        showToast,
        showOnboarding,
        importingSamples,
        loadAllData
    }) {
        function skipOnboarding() {
            showOnboarding.value = false;
        }

        async function importSampleData() {
            if (importingSamples.value) return;
            importingSamples.value = true;
            try {
                const samples = [
                    {
                        title: '示例：云服务器控制台',
                        url: 'https://example.invalid/cloud',
                        starred: true,
                        tags: ['示例', '云服务'],
                        fields: [
                            { name: '账号', value: 'demo-cloud-user', copyable: true, hidden: false },
                            { name: '密码', value: 'Demo-Password-123!', copyable: true, hidden: true }
                        ],
                        remarks: '这是示例数据，可删除。用于体验字段复制、星标和标签筛选。'
                    },
                    {
                        title: '示例：测试邮箱',
                        url: 'https://example.invalid/mail',
                        starred: false,
                        tags: ['示例', '邮箱'],
                        fields: [
                            { name: '邮箱', value: 'demo@example.invalid', copyable: true, hidden: false },
                            { name: '恢复码', value: 'DEMO-CODE-0000', copyable: true, hidden: true }
                        ],
                        remarks: '这是示例数据，可删除。这里不包含任何真实账号。'
                    },
                    {
                        title: '示例：本地开发密钥',
                        url: '',
                        starred: false,
                        tags: ['示例', '开发'],
                        fields: [
                            { name: 'API Key', value: 'demo_api_key_not_real', copyable: true, hidden: true },
                            { name: '环境', value: 'local-demo', copyable: false, hidden: false }
                        ],
                        remarks: '这是示例数据，可删除。用于体验备注和自定义字段。'
                    }
                ];

                for (const sample of samples) await api.post('/entries', sample);
                showOnboarding.value = false;
                const refreshed = await loadAllData();
                showToast(
                    refreshed === false
                        ? '示例数据已导入，但列表刷新不完整，请稍后重试。'
                        : '示例数据已导入',
                    refreshed === false ? 'warning' : 'success'
                );
            } catch (error) {
                showToast(error.message || '示例数据导入失败', 'error');
            } finally {
                importingSamples.value = false;
            }
        }

        return { skipOnboarding, importSampleData };
    }

    window.SecretBaseEntryOnboardingController = { createEntryOnboardingController };
})();
