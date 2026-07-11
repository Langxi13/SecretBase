/**
 * 根应用的跨领域数据加载与条目分页偏好。
 */
(function () {
    function createAppDataController({
        api,
        store,
        state,
        normalizeUniversalPageSize,
        loadPageSizePreference,
        savePageSizePreference,
        getGroupTotalPages
    }) {
        let entriesRequestSeq = 0;

        async function loadEntries(page = 1) {
            const requestSeq = ++entriesRequestSeq;
            const result = await store.loadEntries(page);
            if (requestSeq !== entriesRequestSeq) {
                return;
            }
            state.entries.value = result.items;
            state.totalPages.value = result.pagination.totalPages;
            state.totalEntries.value = result.pagination.total;
            state.currentPage.value = result.pagination.page || page;
        }

        async function loadTags() {
            state.tags.value = await store.loadTags();
        }

        async function loadGroups() {
            state.groups.value = await store.loadGroups();
            const groupTotalPages = getGroupTotalPages();
            if (state.groupCurrentPage.value > groupTotalPages && groupTotalPages > 0) {
                state.groupCurrentPage.value = groupTotalPages;
            }
        }

        async function loadAllData() {
            await Promise.all([
                loadEntries(),
                loadTags(),
                loadGroups()
            ]);
        }

        async function updateEntryPageSize(value) {
            const size = normalizeUniversalPageSize(value, 20);
            state.settingsForm.pageSize = size;
            savePageSizePreference('secretbase.entryPageSize', size);
            if (api.getToken()) {
                await store.updateSettings({ pageSize: size });
                await loadEntries(1);
            }
        }

        async function applySettings(settings, { currentTheme, applyTheme }) {
            currentTheme.value = settings.theme;
            applyTheme(settings.theme);
            state.settingsForm.theme = settings.theme;
            const savedEntryPageSize = loadPageSizePreference('secretbase.entryPageSize', settings.pageSize || 20);
            state.settingsForm.pageSize = savedEntryPageSize;
            if (savedEntryPageSize !== settings.pageSize && api.getToken()) {
                await store.updateSettings({ pageSize: savedEntryPageSize });
            }
            state.settingsForm.autoLockMinutes = settings.autoLockMinutes;
            state.settingsForm.autoBackupRetention = settings.autoBackupRetention;
            state.settingsForm.closeToTray = Boolean(settings.closeToTray);
            state.settingsForm.confirmClose = settings.confirmClose !== false;
        }

        return {
            loadEntries,
            loadTags,
            loadGroups,
            loadAllData,
            updateEntryPageSize,
            applySettings
        };
    }

    window.SecretBaseAppDataController = {
        createAppDataController
    };
})();
