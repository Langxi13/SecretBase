/**
 * 根应用的跨模块响应式监听。
 */
(function () {
    function registerAppWatchers({
        watch,
        state,
        views,
        actions,
        savePageSizePreference,
        normalizeUniversalPageSize = (value, fallback = 12) => {
            const numeric = Number(value);
            return Number.isFinite(numeric) && numeric >= 1 && numeric <= 500
                ? Math.round(numeric)
                : fallback;
        }
    }) {
        function normalizePageSize(target, key, fallback) {
            const normalized = normalizeUniversalPageSize(target.value, fallback);
            if (target.value !== normalized) target.value = normalized;
            savePageSizePreference(key, normalized);
            return normalized;
        }

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
            // 筛选只改变当前可见页；跨筛选条件的已选条目必须继续保留，提交时一次性加入密码组。
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
            normalizePageSize(state.tagBrowserPageSize, 'secretbase.tagBrowserPageSize', 5);
            state.tagBrowserPage.value = 1;
        });

        watch(state.tagManagerPageSize, () => {
            normalizePageSize(state.tagManagerPageSize, 'secretbase.tagManagerPageSize', 5);
            state.tagManagerPage.value = 1;
        });

        watch(state.groupPageSize, () => {
            normalizePageSize(state.groupPageSize, 'secretbase.groupPageSize', 12);
            state.groupCurrentPage.value = 1;
        });

        watch(state.groupPickerPageSize, () => {
            normalizePageSize(state.groupPickerPageSize, 'secretbase.groupPickerPageSize', 10);
            state.groupPickerPage.value = 1;
        });

        watch(state.backupPageSize, () => {
            normalizePageSize(state.backupPageSize, 'secretbase.backupPageSize', 3);
            state.backupPages.manual = 1;
            state.backupPages.auto = 1;
            state.backupPages.legacy = 1;
        });

        watch(state.trashPageSize, () => {
            normalizePageSize(state.trashPageSize, 'secretbase.trashPageSize', 10);
            state.trashPage.value = 1;
            if (state.showTrash.value) actions.loadTrash(1);
        });
    }

    window.SecretBaseAppWatchers = {
        registerAppWatchers
    };
})();
