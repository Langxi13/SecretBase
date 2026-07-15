/**
 * 根应用的跨模块响应式监听。
 */
(function () {
    function registerAppWatchers({
        watch,
        state,
        views,
        actions,
        savePageSizePreference
    }) {
        watch(state.showTrash, value => {
            if (value) actions.loadTrash();
        });

        watch(state.showBackupCenter, value => {
            if (value) actions.loadBackups();
        });

        watch(state.tags, () => {
            if (state.tagManagerPage.value > views.tagManagerTotalPages.value) {
                state.tagManagerPage.value = views.tagManagerTotalPages.value;
            }
            if (state.tagBrowserPage.value > views.tagBrowserTotalPages.value) {
                state.tagBrowserPage.value = views.tagBrowserTotalPages.value;
            }
            const validNames = new Set(state.tags.value.map(tag => tag.name));
            state.selectedManagedTagNames.value = state.selectedManagedTagNames.value.filter(name => validNames.has(name));
        });

        watch([state.tagBrowserQuery, state.tagBrowserSort], () => {
            state.tagBrowserPage.value = 1;
        });

        watch([state.groupPickerTagFilter, state.groupPickerGroupFilter], () => {
            state.groupPickerPage.value = 1;
            const visibleIds = new Set(views.availableGroupPickerEntries.value.map(entry => entry.id));
            state.groupPickerSelectedIds.value = state.groupPickerSelectedIds.value.filter(id => visibleIds.has(id));
        });

        watch(state.groups, () => {
            if (state.groupCurrentPage.value > views.groupTotalPages.value) {
                state.groupCurrentPage.value = views.groupTotalPages.value;
            }
        });

        watch(views.availableGroupPickerEntries, () => {
            if (state.groupPickerPage.value > views.groupPickerTotalPages.value) {
                state.groupPickerPage.value = views.groupPickerTotalPages.value;
            }
        });

        watch(state.tagBrowserPageSize, () => {
            savePageSizePreference('secretbase.tagBrowserPageSize', state.tagBrowserPageSize.value);
            state.tagBrowserPage.value = 1;
        });

        watch(state.tagManagerPageSize, () => {
            savePageSizePreference('secretbase.tagManagerPageSize', state.tagManagerPageSize.value);
            state.tagManagerPage.value = 1;
        });

        watch(state.groupPageSize, () => {
            savePageSizePreference('secretbase.groupPageSize', state.groupPageSize.value);
            state.groupCurrentPage.value = 1;
        });

        watch(state.groupPickerPageSize, () => {
            savePageSizePreference('secretbase.groupPickerPageSize', state.groupPickerPageSize.value);
            state.groupPickerPage.value = 1;
        });

        watch(state.backupPageSize, () => {
            savePageSizePreference('secretbase.backupPageSize', state.backupPageSize.value);
        });

        watch(state.trashPageSize, () => {
            savePageSizePreference('secretbase.trashPageSize', state.trashPageSize.value);
            actions.goToTrashPage(1);
        });
    }

    window.SecretBaseAppWatchers = {
        registerAppWatchers
    };
})();
