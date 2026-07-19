/**
 * AI 视图、专业工具控制器与对话管家控制器的依赖装配。
 */
(function () {
    function createAiFeatureComposition({
        computed,
        nextTick,
        api,
        store,
        showToast,
        copyToClipboard,
        state,
        data,
        ui,
        viewHelpers,
        settingsActions,
        openEntryDetail = () => false
    }) {
        const views = window.SecretBaseAiView.createAiView({
            computed,
            aiText: state.aiText,
            aiParsing: state.aiParsing,
            aiStatus: state.aiStatus,
            aiCooldownUntil: state.aiCooldownUntil,
            aiNow: state.aiNow,
            lastAiParseText: state.lastAiParseText,
            aiResult: state.aiResult,
            aiOrganizing: state.aiOrganizing,
            aiOrganizeOptions: state.aiOrganizeOptions,
            aiActionInstruction: state.aiActionInstruction,
            aiOrganizeResult: state.aiOrganizeResult,
            isAiTagGovernanceMode: state.isAiTagGovernanceMode,
            groups: state.groups,
            aiActionResult: state.aiActionResult
        });

        const providerActions = window.SecretBaseAiSettingsController.createAiSettingsController({
            api,
            showToast,
            showConfirmDialog: ui.showConfirmDialog,
            aiSettingsForm: state.aiSettingsForm,
            aiProviders: state.aiProviders,
            aiManualModel: state.aiManualModel,
            aiSettingsStatus: state.aiSettingsStatus,
            aiSettingsEditing: state.aiSettingsEditing,
            aiModels: state.aiModels,
            aiModelsLoading: state.aiModelsLoading,
            aiSettingsSaving: state.aiSettingsSaving,
            aiSettingsError: state.aiSettingsError,
            aiSettingsMessage: state.aiSettingsMessage,
            aiDiagnosticsPreview: state.aiDiagnosticsPreview,
            aiDiagnosticsReport: state.aiDiagnosticsReport,
            aiDiagnosticsBusy: state.aiDiagnosticsBusy,
            aiDiagnosticsError: state.aiDiagnosticsError
        });

        const professionalActions = window.SecretBaseAiController.createAiController({
            api,
            store,
            showToast,
            nextTick,
            viewHelpers,
            showAiParse: state.showAiParse,
            aiMode: state.aiMode,
            aiText: state.aiText,
            aiResult: state.aiResult,
            aiParsing: state.aiParsing,
            aiStatus: state.aiStatus,
            aiStatusError: state.aiStatusError,
            aiFailureMessage: state.aiFailureMessage,
            aiOrganizing: state.aiOrganizing,
            aiRequestCancelable: state.aiRequestCancelable,
            aiOrganizeError: state.aiOrganizeError,
            aiOrganizeResult: state.aiOrganizeResult,
            aiOrganizeMode: state.aiOrganizeMode,
            aiOrganizeOptions: state.aiOrganizeOptions,
            currentAiOrganizePrompt: state.currentAiOrganizePrompt,
            aiActionInstruction: state.aiActionInstruction,
            aiActionResult: state.aiActionResult,
            aiActionError: state.aiActionError,
            aiCooldownUntil: state.aiCooldownUntil,
            aiNow: state.aiNow,
            lastAiParseText: state.lastAiParseText,
            isAiTagGovernanceMode: state.isAiTagGovernanceMode,
            canPreviewAiOrganize: views.canPreviewAiOrganize,
            canPreviewAiActions: views.canPreviewAiActions,
            canParseAi: views.canParseAi,
            aiCooldownSeconds: views.aiCooldownSeconds,
            aiMaxInputChars: views.aiMaxInputChars,
            searchQuery: state.searchQuery,
            selectedSearchScopes: state.selectedSearchScopes,
            sortBy: state.sortBy,
            sortOrder: state.sortOrder,
            currentPage: state.currentPage,
            entryForm: state.entryForm,
            showCreateModal: state.showCreateModal,
            resetEntryForm: ui.resetEntryForm,
            loadEntries: data.loadEntries,
            loadTags: data.loadTags,
            loadGroups: data.loadGroups,
            openSettings: (...args) => settingsActions.openSettings(...args),
            selectSettingsTab: (...args) => settingsActions.selectSettingsTab(...args)
        });

        const scopeActions = window.SecretBaseAiScopeController.createAiScopeController({
            api,
            store,
            aiAssistantScope: state.aiAssistantScope,
            aiAssistantScopePicker: state.aiAssistantScopePicker,
            searchQuery: state.searchQuery,
            selectedSearchScopes: state.selectedSearchScopes,
            sortBy: state.sortBy,
            sortOrder: state.sortOrder,
            selectedEntryIds: state.selectedEntryIds,
            resetAiAssistantScope: state.resetAiAssistantScope
        });

        const inspectorActions = window.SecretBaseAiAssistantInspectorController.createAiAssistantInspectorController({
            store,
            showToast,
            copyToClipboard,
            aiAssistantInspector: state.aiAssistantInspector,
            resetAiAssistantInspector: state.resetAiAssistantInspector
        });

        const assistantActions = window.SecretBaseAiAssistantController.createAiAssistantController({
            nextTick,
            api,
            store,
            showToast,
            showConfirmDialog: ui.showConfirmDialog,
            copyToClipboard,
            showAiAssistant: state.showAiAssistant,
            showAiParse: state.showAiParse,
            aiStatus: state.aiStatus,
            aiAssistantMode: state.aiAssistantMode,
            aiAssistantScope: state.aiAssistantScope,
            aiAssistantInput: state.aiAssistantInput,
            aiAssistantBusy: state.aiAssistantBusy,
            aiAssistantStage: state.aiAssistantStage,
            aiAssistantError: state.aiAssistantError,
            aiAssistantConversations: state.aiAssistantConversations,
            aiAssistantConversationId: state.aiAssistantConversationId,
            aiAssistantMessages: state.aiAssistantMessages,
            aiAssistantPrepared: state.aiAssistantPrepared,
            aiAssistantPlan: state.aiAssistantPlan,
            aiAssistantLastResult: state.aiAssistantLastResult,
            aiAssistantHistoryOpen: state.aiAssistantHistoryOpen,
            selectedEntry: state.selectedEntry,
            currentPage: state.currentPage,
            assistantFiltersForScope: scopeActions.assistantFiltersForScope,
            assistantScopeCount: scopeActions.assistantScopeCount,
            refreshAssistantScopeCatalog: scopeActions.refreshAssistantScopeCatalog,
            closeAssistantScopePicker: scopeActions.closeAssistantScopePicker,
            resetAssistantScopeForConversation: scopeActions.resetAssistantScopeForConversation,
            loadEntries: data.loadEntries,
            loadTags: data.loadTags,
            loadGroups: data.loadGroups,
            openSettings: (...args) => settingsActions.openSettings(...args),
            selectSettingsTab: (...args) => settingsActions.selectSettingsTab(...args),
            openEntryDetail,
            normalizeAssistantActionTargets: inspectorActions.normalizeAssistantActionTargets,
            resetAssistantInspector: inspectorActions.resetAssistantInspector,
            assistantPlanHasSelectedConflicts: inspectorActions.assistantPlanHasSelectedConflicts
        });

        return {
            views,
            actions: {
                ...providerActions,
                ...professionalActions,
                ...scopeActions,
                ...inspectorActions,
                ...assistantActions
            }
        };
    }

    window.SecretBaseAiFeatureComposition = {
        createAiFeatureComposition
    };
})();
