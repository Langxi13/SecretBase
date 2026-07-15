/**
 * 领域视图工厂与控制器的依赖装配。
 *
 * 此文件是应用的 composition root：只传递显式依赖，不承载领域实现。
 */
(function () {
    function createFeatureComposition({
        computed,
        nextTick,
        debounce,
        copyToClipboard,
        openExternalUrl,
        api,
        store,
        showToast,
        state,
        data,
        ui,
        viewHelpers,
        settingsActions,
        pagination
    }) {
        const listActions = {};
        const aiFeature = window.SecretBaseAiFeatureComposition.createAiFeatureComposition({
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
            settingsActions
        });

        const selectedSearchScopeLabels = computed(() => {
            return state.searchScopeOptions
                .filter(scope => state.selectedSearchScopes.value.includes(scope.key))
                .map(scope => scope.label);
        });

        const {
            tagBrowserSortOptions,
            sortedTagBrowserTags,
            visibleSidebarTags,
            hiddenSidebarTagCount,
            filteredTagBrowserTags,
            tagBrowserTotalPages,
            paginatedTagBrowserTags,
            tagManagerTotalPages,
            paginatedManagedTags,
            allManagedPageTagsSelected
        } = window.SecretBaseTagView.createTagView({
            computed,
            tags: state.tags,
            activeTagName: state.activeTagName,
            tagBrowserSort: state.tagBrowserSort,
            tagBrowserQuery: state.tagBrowserQuery,
            tagBrowserPage: state.tagBrowserPage,
            tagBrowserPageSize: state.tagBrowserPageSize,
            tagManagerPage: state.tagManagerPage,
            tagManagerPageSize: state.tagManagerPageSize,
            selectedManagedTagNames: state.selectedManagedTagNames
        });

        const {
            activeAdvancedFilterChips,
            activeListStateItems,
            hasActiveListState,
            resetAdvancedFilterForm,
            removeAdvancedFilterChip,
            loadSavedAdvancedFilters,
            persistSavedAdvancedFilters,
            getAdvancedFilterSnapshot,
            saveCurrentAdvancedFilter,
            applySavedAdvancedFilter,
            deleteSavedAdvancedFilter,
            addAdvancedTags,
            commitAdvancedTags,
            removeAdvancedTag,
            commitAndApplyAdvancedTags,
            handleAdvancedTagKey,
            handleAdvancedTagInput
        } = window.SecretBaseFilterController.createAdvancedFilterController({
            computed,
            advancedTagDraft: state.advancedTagDraft,
            advancedTagList: state.advancedTagList,
            advancedFilters: state.advancedFilters,
            savedAdvancedFilters: state.savedAdvancedFilters,
            listContextNotice: state.listContextNotice,
            searchQuery: state.searchQuery,
            selectedSearchScopeLabels,
            filter: state.filter,
            activeTagName: state.activeTagName,
            activeGroupName: state.activeGroupName,
            sortBy: state.sortBy,
            sortOrder: state.sortOrder,
            applyAdvancedFilters: (...args) => listActions.applyAdvancedFilters(...args),
            clearAdvancedFilters: (...args) => listActions.clearAdvancedFilters(...args)
        });

        const allCurrentPageSelected = computed(() => {
            return state.entries.value.length > 0
                && state.entries.value.every(entry => state.selectedEntryIds.value.includes(entry.id));
        });

        const {
            activeGroup,
            availableGroupPickerEntries,
            groupPickerTotalPages,
            paginatedGroupPickerEntries,
            selectableGroupPickerGroups,
            allGroupPickerEntriesSelected,
            paginatedGroups,
            groupTotalPages,
            visibleGroupPages
        } = window.SecretBaseGroupView.createGroupView({
            computed,
            groups: state.groups,
            totalEntries: state.totalEntries,
            activeGroupName: state.activeGroupName,
            groupPickerEntries: state.groupPickerEntries,
            groupPickerTagFilter: state.groupPickerTagFilter,
            groupPickerGroupFilter: state.groupPickerGroupFilter,
            groupPickerPage: state.groupPickerPage,
            groupPickerPageSize: state.groupPickerPageSize,
            groupPickerSelectedIds: state.groupPickerSelectedIds,
            groupCurrentPage: state.groupCurrentPage,
            groupPageSize: state.groupPageSize
        });

        const {
            backupBusy,
            sortedBackups,
            backupSummary,
            backupGroups
        } = window.SecretBaseBackupView.createBackupView({
            computed,
            backups: state.backups,
            backupPages: state.backupPages,
            backupPageSize: state.backupPageSize,
            settingsForm: state.settingsForm,
            backupListLoading: state.backupListLoading,
            creatingBackup: state.creatingBackup,
            restoringBackupFilename: state.restoringBackupFilename,
            downloadingBackupFilename: state.downloadingBackupFilename
        });

        const visiblePages = computed(() => {
            return pagination.createVisiblePages(state.currentPage.value, state.totalPages.value);
        });

        const tagActions = window.SecretBaseTagController.createTagController({
            api,
            store,
            showToast,
            showConfirmDialog: ui.showConfirmDialog,
            filter: state.filter,
            activeTagName: state.activeTagName,
            activeGroupName: state.activeGroupName,
            listContextNotice: state.listContextNotice,
            showTagDropdown: state.showTagDropdown,
            showTagBrowser: state.showTagBrowser,
            tagBrowserQuery: state.tagBrowserQuery,
            tagBrowserPage: state.tagBrowserPage,
            tagBrowserTotalPages,
            loadEntries: data.loadEntries,
            resetAdvancedFilterForm,
            showTagManager: state.showTagManager,
            showTagEditorModal: state.showTagEditorModal,
            tagEditorForm: state.tagEditorForm,
            selectedManagedTagNames: state.selectedManagedTagNames,
            tagManagerPage: state.tagManagerPage,
            tagManagerTotalPages,
            paginatedManagedTags,
            allManagedPageTagsSelected,
            tagMergeForm: state.tagMergeForm,
            tagMergeSourceList: state.tagMergeSourceList,
            currentPage: state.currentPage,
            loadTags: data.loadTags
        });

        const backupActions = window.SecretBaseBackupController.createBackupController({
            api,
            showToast,
            showConfirmDialog: ui.showConfirmDialog,
            friendlyApiMessage: viewHelpers.friendlyApiMessage,
            downloadProtectedFile: window.SecretBaseDownload.downloadProtectedFile,
            backups: state.backups,
            highlightedBackupFilename: state.highlightedBackupFilename,
            backupListLoading: state.backupListLoading,
            showBackupCenter: state.showBackupCenter,
            backupPages: state.backupPages,
            creatingBackup: state.creatingBackup,
            restoringBackupFilename: state.restoringBackupFilename,
            downloadingBackupFilename: state.downloadingBackupFilename,
            restoreWizard: state.restoreWizard,
            loadAllData: data.loadAllData
        });

        const trashActions = window.SecretBaseTrashController.createTrashController({
            api,
            showToast,
            showConfirmDialog: ui.showConfirmDialog,
            trashItems: state.trashItems,
            trashPage: state.trashPage,
            trashTotalPages: state.trashTotalPages,
            trashTotal: state.trashTotal,
            trashPageSize: state.trashPageSize,
            loadEntries: data.loadEntries
        });

        const transferActions = window.SecretBaseTransferController.createTransferController({
            api,
            showToast,
            showConfirmDialog: ui.showConfirmDialog,
            friendlyApiMessage: viewHelpers.friendlyApiMessage,
            downloadProtectedFile: window.SecretBaseDownload.downloadProtectedFile,
            loadAllData: data.loadAllData,
            importConflictStrategy: state.importConflictStrategy,
            importConflictMessage: state.importConflictMessage,
            showImportConflicts: state.showImportConflicts,
            importConflicts: state.importConflicts,
            showImportReport: state.showImportReport,
            importReport: state.importReport,
            showImportPreview: state.showImportPreview,
            importPreview: state.importPreview,
            lastImportPlainFile: state.lastImportPlainFile,
            importPreviewSelectedIds: state.importPreviewSelectedIds,
            lastImportSelectedIds: state.lastImportSelectedIds,
            importConflictResolutions: state.importConflictResolutions,
            lastImportConflictResolutions: state.lastImportConflictResolutions
        });

        const entryActions = window.SecretBaseEntryController.createEntryController({
            api,
            store,
            showToast,
            copyToClipboard,
            normalizeFieldForEdit: viewHelpers.normalizeFieldForEdit,
            entries: state.entries,
            currentPage: state.currentPage,
            totalPages: state.totalPages,
            selectedEntry: state.selectedEntry,
            editingEntry: state.editingEntry,
            entryForm: state.entryForm,
            entryTemplates: state.entryTemplates,
            selectedTemplate: state.selectedTemplate,
            newTag: state.newTag,
            newGroup: state.newGroup,
            newGroupDescription: state.newGroupDescription,
            groups: state.groups,
            showCreateModal: state.showCreateModal,
            showEditModal: state.showEditModal,
            showOnboarding: state.showOnboarding,
            importingSamples: state.importingSamples,
            selectedEntryIds: state.selectedEntryIds,
            batchTagName: state.batchTagName,
            allCurrentPageSelected,
            copyMenuEntryId: state.copyMenuEntryId,
            showTagDropdown: state.showTagDropdown,
            revealedFields: state.revealedFields,
            resetEntryForm: ui.resetEntryForm,
            loadEntries: data.loadEntries,
            loadTags: data.loadTags,
            loadGroups: data.loadGroups,
            loadAllData: data.loadAllData,
            showConfirmDialog: ui.showConfirmDialog
        });

        const listControllerActions = window.SecretBaseListController.createListController({
            debounce,
            store,
            searchQuery: state.searchQuery,
            selectedSearchScopes: state.selectedSearchScopes,
            listContextNotice: state.listContextNotice,
            filter: state.filter,
            activeTagName: state.activeTagName,
            activeGroupName: state.activeGroupName,
            sortBy: state.sortBy,
            sortOrder: state.sortOrder,
            advancedTagList: state.advancedTagList,
            advancedFilters: state.advancedFilters,
            resetAdvancedFilterForm,
            commitAdvancedTags,
            resetSearchScopes: ui.resetSearchScopes,
            clearSelection: entryActions.clearSelection,
            loadEntries: data.loadEntries,
            revealedFields: state.revealedFields,
            isSidebarCollapsed: state.isSidebarCollapsed,
            returnToGroupMode: (...args) => listActions.returnToGroupMode(...args)
        });
        Object.assign(listActions, {
            applyAdvancedFilters: listControllerActions.applyAdvancedFilters,
            clearAdvancedFilters: listControllerActions.clearAdvancedFilters
        });

        const maintenanceActions = window.SecretBaseMaintenanceController.createMaintenanceController({
            api,
            store,
            showToast,
            showConfirmDialog: ui.showConfirmDialog,
            friendlyApiMessage: viewHelpers.friendlyApiMessage,
            showTools: state.showTools,
            healthReport: state.healthReport,
            maintenanceReport: state.maintenanceReport,
            securityReport: state.securityReport,
            searchQuery: state.searchQuery,
            filter: state.filter,
            activeTagName: state.activeTagName,
            activeGroupName: state.activeGroupName,
            listContextNotice: state.listContextNotice,
            advancedFilters: state.advancedFilters,
            showAdvancedFilters: state.showAdvancedFilters,
            resetAdvancedFilterForm,
            clearAdvancedFilters: listControllerActions.clearAdvancedFilters,
            applyAdvancedFilters: listControllerActions.applyAdvancedFilters,
            loadEntries: data.loadEntries,
            loadTags: data.loadTags,
            loadAllData: data.loadAllData
        });

        const desktop = window.SecretBaseDesktopController.createDesktopController({
            computed,
            copyToClipboard,
            openExternalUrl,
            store,
            showToast,
            state
        });

        const groupActions = window.SecretBaseGroupController.createGroupController({
            api,
            store,
            showToast,
            showConfirmDialog: ui.showConfirmDialog,
            groups: state.groups,
            activeGroupName: state.activeGroupName,
            filter: state.filter,
            groupCurrentPage: state.groupCurrentPage,
            groupTotalPages,
            searchQuery: state.searchQuery,
            resetSearchScopes: ui.resetSearchScopes,
            resetAdvancedFilterForm,
            listContextNotice: state.listContextNotice,
            activeTagName: state.activeTagName,
            selectedEntryIds: state.selectedEntryIds,
            sortBy: state.sortBy,
            sortOrder: state.sortOrder,
            editingGroupName: state.editingGroupName,
            groupForm: state.groupForm,
            showGroupModal: state.showGroupModal,
            loadGroups: data.loadGroups,
            loadEntries: data.loadEntries,
            currentPage: state.currentPage,
            entryForm: state.entryForm,
            resetEntryForm: ui.resetEntryForm,
            showCreateModal: state.showCreateModal,
            showGroupEntryPicker: state.showGroupEntryPicker,
            groupPickerEntries: state.groupPickerEntries,
            groupPickerSelectedIds: state.groupPickerSelectedIds,
            groupPickerTagFilter: state.groupPickerTagFilter,
            groupPickerGroupFilter: state.groupPickerGroupFilter,
            groupPickerPage: state.groupPickerPage,
            groupPickerLoading: state.groupPickerLoading,
            groupPickerTotalPages,
            paginatedGroupPickerEntries,
            allGroupPickerEntriesSelected
        });
        Object.assign(listActions, {
            returnToGroupMode: groupActions.showGroupMode
        });

        const selectedImportPreviewCount = computed(() => state.importPreviewSelectedIds.value.length);
        const selectedImportConflictCount = computed(() => {
            return (state.importPreview.value?.entries || []).filter(entry => {
                return entry.is_conflict && transferActions.isImportPreviewSelected(entry.id);
            }).length;
        });

        return {
            views: {
                ...aiFeature.views,
                selectedSearchScopeLabels,
                tagBrowserSortOptions,
                sortedTagBrowserTags,
                visibleSidebarTags,
                hiddenSidebarTagCount,
                filteredTagBrowserTags,
                tagBrowserTotalPages,
                paginatedTagBrowserTags,
                tagManagerTotalPages,
                paginatedManagedTags,
                allManagedPageTagsSelected,
                activeAdvancedFilterChips,
                activeListStateItems,
                hasActiveListState,
                activeGroup,
                availableGroupPickerEntries,
                groupPickerTotalPages,
                paginatedGroupPickerEntries,
                selectableGroupPickerGroups,
                allGroupPickerEntriesSelected,
                paginatedGroups,
                groupTotalPages,
                visibleGroupPages,
                backupBusy,
                sortedBackups,
                backupSummary,
                backupGroups,
                visiblePages,
                allCurrentPageSelected,
                selectedImportPreviewCount,
                selectedImportConflictCount,
                ...desktop.views
            },
            actions: {
                ...aiFeature.actions,
                ...tagActions,
                ...backupActions,
                ...trashActions,
                ...transferActions,
                ...entryActions,
                ...listControllerActions,
                ...maintenanceActions,
                ...groupActions,
                ...desktop.actions,
                resetAdvancedFilterForm,
                removeAdvancedFilterChip,
                loadSavedAdvancedFilters,
                persistSavedAdvancedFilters,
                getAdvancedFilterSnapshot,
                saveCurrentAdvancedFilter,
                applySavedAdvancedFilter,
                deleteSavedAdvancedFilter,
                addAdvancedTags,
                commitAdvancedTags,
                removeAdvancedTag,
                commitAndApplyAdvancedTags,
                handleAdvancedTagKey,
                handleAdvancedTagInput
            }
        };
    }

    window.SecretBaseFeatureComposition = {
        createFeatureComposition
    };
})();
