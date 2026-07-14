/**
 * AI 建议关联条目的本地详情查看状态。
 */
(function () {
    function createAiAssistantInspectorState({ reactive, computed }) {
        const aiAssistantInspector = reactive({
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
        const aiAssistantInspectorTotalPages = computed(() => Math.max(
            1,
            Math.ceil(aiAssistantInspector.targets.length / aiAssistantInspector.pageSize)
        ));
        const aiAssistantInspectorPageTargets = computed(() => {
            const start = (aiAssistantInspector.page - 1) * aiAssistantInspector.pageSize;
            return aiAssistantInspector.targets.slice(start, start + aiAssistantInspector.pageSize);
        });

        function resetAiAssistantInspector() {
            Object.assign(aiAssistantInspector, {
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
        }

        return {
            aiAssistantInspector,
            aiAssistantInspectorTotalPages,
            aiAssistantInspectorPageTargets,
            resetAiAssistantInspector
        };
    }

    window.SecretBaseAiAssistantInspectorState = {
        createAiAssistantInspectorState
    };
})();
