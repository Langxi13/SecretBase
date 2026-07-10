/**
 * 根应用中不属于某个业务领域的轻量交互。
 */
(function () {
    function createAppUiController({ state, store, viewHelpers }) {
        let confirmCallback = null;

        function resetSearchScopes() {
            state.selectedSearchScopes.value = [...state.defaultSearchScopes];
            store.setFilter('searchScopes', state.selectedSearchScopes.value);
        }

        function resetEntryForm() {
            state.entryForm.id = null;
            state.entryForm.title = '';
            state.entryForm.url = '';
            state.entryForm.starred = false;
            state.entryForm.tags = [];
            state.entryForm.groups = [];
            state.entryForm.fields = [];
            state.entryForm.remarks = '';
            state.newTag.value = '';
            state.newGroup.value = '';
            state.newGroupDescription.value = '';
            state.selectedTemplate.value = '';
        }

        function showConfirmDialog(title, message, callback) {
            state.confirmTitle.value = title;
            state.confirmMessage.value = message;
            confirmCallback = callback;
            state.showConfirm.value = true;
        }

        async function confirmAction() {
            try {
                if (confirmCallback) {
                    await confirmCallback();
                }
            } finally {
                state.showConfirm.value = false;
                confirmCallback = null;
            }
        }

        return {
            resetSearchScopes,
            resetEntryForm,
            showConfirmDialog,
            confirmAction,
            getEntryIconText: viewHelpers.getEntryIconText,
            getTagColor: viewHelpers.getTagColor,
            groupCardStyle: viewHelpers.groupCardStyle,
            entryCardStyle: viewHelpers.entryCardStyle,
            visibleEntryGroups: viewHelpers.visibleEntryGroups,
            remainingEntryGroupsCount: viewHelpers.remainingEntryGroupsCount,
            groupChipStyle: viewHelpers.groupChipStyle,
            formatDate: viewHelpers.formatDate,
            formatBytes: viewHelpers.formatBytes,
            aiTagActionLabel: viewHelpers.aiTagActionLabel,
            aiTagActionTitle: viewHelpers.aiTagActionTitle,
            aiActionTypeLabel: viewHelpers.aiActionTypeLabel,
            aiActionEntryLabel: viewHelpers.aiActionEntryLabel,
            aiActionTitle: viewHelpers.aiActionTitle
        };
    }

    window.SecretBaseAppUiController = {
        createAppUiController
    };
})();
