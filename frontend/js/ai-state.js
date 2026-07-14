/**
 * AI 专业工具、对话管家和厂商设置的响应式状态。
 */
(function () {
    function createAiState({ ref, reactive, computed }) {
        const aiMode = ref('parse');
        const aiText = ref('');
        const aiResult = ref(null);
        const aiParsing = ref(false);
        const aiStatus = ref(null);
        const aiStatusError = ref('');
        const aiFailureMessage = ref('');
        const aiOrganizing = ref(false);
        const aiOrganizeError = ref('');
        const aiOrganizeResult = ref(null);
        const aiOrganizeMode = ref('tags');
        const aiOrganizeOptions = reactive({
            organizeTags: true,
            organizeGroups: false
        });
        const aiOrganizePrompts = reactive({
            tags: '',
            groups: '',
            'tag-governance': ''
        });
        const aiActionInstruction = ref('');
        const aiActionResult = ref(null);
        const aiActionError = ref('');
        const aiCooldownUntil = ref(0);
        const aiNow = ref(Date.now());
        const lastAiParseText = ref('');
        const isAiTagGovernanceMode = computed(() => aiOrganizeMode.value === 'tag-governance');
        const currentAiOrganizePrompt = computed({
            get() {
                return aiOrganizePrompts[aiOrganizeMode.value] || '';
            },
            set(value) {
                aiOrganizePrompts[aiOrganizeMode.value] = value;
            }
        });

        const aiAssistantMode = ref('assistant');
        const aiAssistantScope = ref('all');
        const aiAssistantScopePicker = reactive({
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
        });
        const aiAssistantInput = ref('');
        const aiAssistantBusy = ref(false);
        const aiAssistantStage = ref('');
        const aiAssistantError = ref('');
        const aiAssistantConversations = ref([]);
        const aiAssistantConversationId = ref('');
        const aiAssistantMessages = ref([]);
        const aiAssistantPrepared = ref(null);
        const aiAssistantPlan = ref(null);
        const aiAssistantLastResult = ref(null);
        const aiAssistantHistoryOpen = ref(
            typeof window === 'undefined'
            || typeof window.matchMedia !== 'function'
            || !window.matchMedia('(max-width: 820px)').matches
        );

        function resetAiAssistantScope() {
            aiAssistantScope.value = 'all';
            Object.assign(aiAssistantScopePicker, {
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
            });
        }

        function resetAiAssistantSession() {
            aiAssistantInput.value = '';
            aiAssistantPrepared.value = null;
            aiAssistantPlan.value = null;
            aiAssistantLastResult.value = null;
            aiAssistantMessages.value = [];
            aiAssistantConversationId.value = '';
            aiAssistantBusy.value = false;
            aiAssistantStage.value = '';
            aiAssistantError.value = '';
            resetAiAssistantScope();
        }

        const aiSettingsForm = reactive({
            providerId: 'deepseek',
            baseUrl: '',
            apiKey: '',
            model: ''
        });
        const aiProviders = ref([]);
        const aiManualModel = ref(false);
        const aiSettingsStatus = ref(null);
        const aiSettingsEditing = ref(false);
        const aiModels = ref([]);
        const aiModelsLoading = ref(false);
        const aiSettingsSaving = ref(false);
        const aiSettingsError = ref('');
        const aiSettingsMessage = ref('');
        const aiDiagnosticsPreview = ref(null);
        const aiDiagnosticsReport = ref(null);
        const aiDiagnosticsBusy = ref(false);
        const aiDiagnosticsError = ref('');
        const aiConfiguredBaseUrl = computed(
            () => aiSettingsStatus.value?.base_url || aiSettingsStatus.value?.baseUrl || ''
        );

        return {
            aiMode,
            aiText,
            aiResult,
            aiParsing,
            aiStatus,
            aiStatusError,
            aiFailureMessage,
            aiOrganizing,
            aiOrganizeError,
            aiOrganizeResult,
            aiOrganizeMode,
            aiOrganizeOptions,
            aiOrganizePrompts,
            aiActionInstruction,
            aiActionResult,
            aiActionError,
            aiCooldownUntil,
            aiNow,
            lastAiParseText,
            isAiTagGovernanceMode,
            currentAiOrganizePrompt,
            aiAssistantMode,
            aiAssistantScope,
            aiAssistantScopePicker,
            aiAssistantInput,
            aiAssistantBusy,
            aiAssistantStage,
            aiAssistantError,
            aiAssistantConversations,
            aiAssistantConversationId,
            aiAssistantMessages,
            aiAssistantPrepared,
            aiAssistantPlan,
            aiAssistantLastResult,
            aiAssistantHistoryOpen,
            resetAiAssistantScope,
            resetAiAssistantSession,
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
            aiDiagnosticsError,
            aiConfiguredBaseUrl
        };
    }

    window.SecretBaseAiState = {
        createAiState
    };
})();
