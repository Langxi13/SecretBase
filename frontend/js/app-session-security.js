/**
 * Locked-session cleanup and desktop lock bridge.
 *
 * Keeping this boundary separate makes it easier to audit every sensitive
 * value that is removed when the vault is locked.
 */
(function () {
    function createSessionSecurityController({
        api,
        store,
        state,
        desktopLockCover,
        pauseSync = () => {},
        pauseDesktopUpdates = () => {},
        invalidateDataRequests = () => {},
        clearDataLoadErrors = () => {},
        clearPendingDialogs = () => {},
        pauseAi = () => {},
        disposeAiAssistant = () => {},
        disposeAiTools = () => {},
        disposeMaintenance = () => {},
        disposeEntryRequests = () => {},
        invalidateAuthOperations = () => {},
        clearAutoLockTimer = () => {}
    }) {
        function setRef(name, value) {
            const target = state[name];
            if (target && typeof target === 'object' && 'value' in target) {
                target.value = value;
            }
        }

        function setReactive(name, values) {
            const target = state[name];
            if (target && typeof target === 'object') Object.assign(target, values);
        }

        function setRefs(names, value) {
            names.forEach(name => {
                const nextValue = Array.isArray(value)
                    ? []
                    : value && typeof value === 'object'
                        ? { ...value }
                        : value;
                setRef(name, nextValue);
            });
        }

        function clearSensitiveState() {
            invalidateAuthOperations();
            clearPendingDialogs();
            pauseSync();
            pauseDesktopUpdates();
            pauseAi();
            disposeAiAssistant();
            disposeAiTools();
            disposeMaintenance();
            disposeEntryRequests();
            if (typeof api.invalidateSession === 'function') api.invalidateSession();
            invalidateDataRequests();
            clearDataLoadErrors();

            setRefs([
                'startupError', 'dataLoadError', 'restoringBackupFilename', 'downloadingBackupFilename',
                'desktopDiagnosticsError', 'desktopUpdateError', 'trashError', 'backupError',
                'importConflictMessage', 'transferError', 'batchTagName', 'groupPickerTagFilter', 'groupPickerGroupFilter',
                'groupPickerError',
                'searchQuery', 'tagBrowserQuery', 'advancedTagDraft', 'newTag', 'newGroup',
                'newGroupDescription', 'selectedTemplate'
            ], '');
            setRefs([
                'entries', 'tags', 'groups', 'trashItems', 'backups', 'groupPickerEntries',
                'importConflicts', 'importPreviewSelectedIds', 'lastImportSelectedIds',
                'selectedEntryIds', 'groupPickerSelectedIds', 'revealedFields', 'advancedTagList',
                'selectedManagedTagNames', 'tagMergeSourceList'
            ], []);
            setRefs([
                'healthReport', 'maintenanceReport', 'securityReport', 'desktopDiagnostics',
                'desktopUpdateResult', 'importPreview', 'importReport', 'lastImportPlainFile',
                'selectedEntry', 'editingEntry'
            ], null);
            setRef('showEntryDetail', false);
            setRefs(['entryDetailTargetId', 'entryDetailError', 'entryEditTargetId', 'entryEditError'], '');
            setRefs(['entryDetailLoading', 'entryEditLoading'], false);
            setRefs(['importConflictResolutions', 'lastImportConflictResolutions'], {});
            setRefs([
                'dataLoading', 'trashLoading', 'groupPickerLoading', 'backupListLoading', 'syncConflictsLoading',
                'desktopDiagnosticsLoading', 'desktopUpdateChecking'
            ], false);
            setRefs(['loading', 'startupRetrying', 'importingSamples'], false);
            setRef('creatingBackup', false);
            setRef('currentPage', 1);
            setRef('totalPages', 0);
            setRef('totalEntries', 0);
            setRef('selectedSearchScopes', [...(state.defaultSearchScopes || [])]);
            setRef('sortBy', 'updated_at');
            setRef('sortOrder', 'desc');
            setRef('tagBrowserSort', 'count_desc');
            setRef('showAdvancedFilters', false);
            setRef('highlightedBackupFilename', '');
            setRef('tagInput', null);
            setRef('activeSettingsTab', 'general');
            setRef('editingGroupName', '');
            setRef('trashTotal', 0);
            setRef('trashPage', 1);
            setRef('trashTotalPages', 0);
            setRef('transferBusy', false);
            setRef('filter', 'all');
            setRefs(['activeTagName', 'activeGroupName', 'listContextNotice'], '');
            setRefs(['tagManagerPage', 'tagBrowserPage', 'groupCurrentPage', 'groupPickerPage'], 1);
            setRef('copyMenuEntryId', null);
            setRef('showTagDropdown', false);
            setRefs([
                'showCreateModal', 'showEditModal', 'showAiParse', 'showSettings', 'showDesktopStatus',
                'showDesktopCloseConfirm', 'showTrash', 'showTagManager', 'showTagEditorModal',
                'showGroupModal', 'showTagBrowser', 'showGroupEntryPicker', 'showChangePassword',
                'showBackupCenter', 'showConfirm', 'showPrompt', 'showTools', 'showImportPreview',
                'showImportConflicts', 'showImportReport', 'showOnboarding'
            ], false);
            setRef('showAiAssistant', false);

            setRefs([
                'submitting', 'promptSubmitting', 'passwordChanging', 'entrySaving', 'batchBusy', 'groupSaving',
                'groupOrdering', 'tagSaving', 'tagMerging', 'groupPickerSaving', 'settingsSaving',
                'confirmSubmitting', 'trashEmptying'
            ], false);
            setRefs(['entryActionIds', 'trashActionIds'], []);
            setRefs([
                'settingsError', 'confirmError', 'promptError', 'syncConflictsError',
                'syncSetupError', 'syncSetupMessage'
            ], '');
            setRef('syncSetupTestPassed', false);

            setRefs(['password', 'confirmPassword', 'passwordError', 'unlockError', 'aiText',
                'aiFailureMessage', 'aiStatusError', 'aiOrganizeError', 'aiActionError',
                'lastAiParseText', 'aiActionInstruction', 'aiSettingsError', 'aiSettingsMessage'], '');
            setRef('aiCooldownUntil', 0);
            setRefs(['aiOrganizeResult', 'aiActionResult', 'aiResult', 'aiStatus', 'aiSettingsStatus',
                'aiDiagnosticsPreview', 'aiDiagnosticsReport'], null);
            setRefs(['aiModels', 'aiProviders', 'aiAssistantConversations', 'aiAssistantMessages'], []);
            setRefs(['aiManualModel', 'aiModelsLoading', 'aiSettingsSaving', 'aiParsing', 'aiOrganizing',
                'aiAssistantBusy', 'aiDiagnosticsBusy', 'aiAssistantHistoryOpen'], false);
            setRef('aiRequestCancelable', false);
            setRef('aiDiagnosticsError', '');
            setRef('aiAssistantConversationId', '');
            setRefs(['promptValue', 'promptTitle', 'promptMessage', 'promptPlaceholder'], '');
            setRef('promptType', 'text');
            setRef('promptConfirmLabel', '确定');
            setRef('promptMaxLength', 200);
            setRef('promptRequired', true);
            setRef('promptObscured', true);

            setReactive('passwordForm', { oldPassword: '', newPassword: '', confirmPassword: '', error: '' });
            setReactive('tagMergeForm', { sourceTags: '', targetTag: '' });
            setRef('tagMergeSourceList', []);
            setReactive('tagEditorForm', { name: '', description: '' });
            setReactive('groupForm', { name: '', description: '' });
            setReactive('advancedFilters', {
                untagged: false,
                createdFrom: '',
                createdTo: '',
                updatedFrom: '',
                updatedTo: '',
                hasUrl: '',
                hasRemarks: ''
            });
            setReactive('aiSettingsForm', {
                providerId: 'deepseek',
                baseUrl: '',
                apiKey: '',
                model: ''
            });
            setReactive('aiOrganizePrompts', { tags: '', groups: '', 'tag-governance': '' });
            setReactive('restoreWizard', {
                visible: false,
                step: 1,
                backup: null,
                summary: null,
                password: '',
                confirmation: '',
                needsPassword: false,
                loadingSummary: false,
                restoring: false,
                error: ''
            });
            setRef('desktopCloseRemember', false);
            setRef('desktopCloseSubmitting', false);
            setRef('desktopCloseError', '');
            setRef('desktopCloseSettingsSaving', false);
            setRef('confirmTitle', '');
            setRef('confirmMessage', '');

            if (typeof state.resetAiAssistantSession === 'function') state.resetAiAssistantSession();
            setReactive('entryForm', {
                id: null,
                title: '',
                url: '',
                starred: false,
                tags: [],
                groups: [],
                fields: [],
                remarks: ''
            });

            api.setToken(null);
            const storeReset = {
                locked: true,
                entries: [],
                tags: [],
                groups: [],
                trash: [],
                pagination: { page: 1, pageSize: 20, total: 0, totalPages: 0 }
            };
            if (typeof window.SecretBaseStoreState?.createDefaultFilters === 'function') {
                storeReset.filters = window.SecretBaseStoreState.createDefaultFilters();
            }
            store.setState(storeReset);
            setRef('locked', true);
            clearAutoLockTimer();
        }

        function handleDesktopLockRequest() {
            clearSensitiveState();
            desktopLockCover?.scheduleRelease?.();
        }

        return {
            applyLockedState: clearSensitiveState,
            handleDesktopLockRequest
        };
    }

    window.SecretBaseSessionSecurity = { createSessionSecurityController };
})();
