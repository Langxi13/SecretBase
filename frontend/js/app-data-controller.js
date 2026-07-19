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
        let tagsRequestSeq = 0;
        let groupsRequestSeq = 0;
        let dataRequestEpoch = 0;
        let requestId = 0;
        const activeDataRequests = new Set();
        const loadErrors = new Map();

        function beginDataRequest() {
            const id = ++requestId;
            activeDataRequests.add(id);
            state.dataLoading.value = true;
            return id;
        }

        function endDataRequest(id) {
            activeDataRequests.delete(id);
            state.dataLoading.value = activeDataRequests.size > 0;
        }

        function refreshLoadError() {
            state.dataLoadError.value = Array.from(loadErrors.values()).join('；');
        }

        function reportLoadError(key, error, fallback) {
            loadErrors.set(key, error?.message || fallback);
            refreshLoadError();
            return false;
        }

        function clearLoadError(key) {
            if (!loadErrors.delete(key)) return;
            refreshLoadError();
        }

        function clearLoadErrors() {
            loadErrors.clear();
            refreshLoadError();
        }

        function hasLoadError(key) {
            return loadErrors.has(key);
        }

        function normalizeEntryPagination(result, requestedPage) {
            const pagination = result?.pagination || {};
            const total = Math.max(0, Number(pagination.total || 0));
            const totalPages = Math.max(1, Number(pagination.totalPages ?? pagination.total_pages ?? 0));
            const reportedPage = Math.max(1, Number(pagination.page || requestedPage || 1));
            return {
                total,
                totalPages,
                page: Math.min(reportedPage, totalPages)
            };
        }

        function invalidateRequests() {
            dataRequestEpoch += 1;
            entriesRequestSeq += 1;
            tagsRequestSeq += 1;
            groupsRequestSeq += 1;
            activeDataRequests.clear();
            state.dataLoading.value = false;
        }

        async function loadEntries(page = 1) {
            const requestSeq = ++entriesRequestSeq;
            const requestEpoch = dataRequestEpoch;
            const requestId = beginDataRequest();
            const shouldCommit = () => (
                requestSeq === entriesRequestSeq && requestEpoch === dataRequestEpoch
            );
            try {
                const result = await store.loadEntries(page, { shouldCommit });
                if (!shouldCommit()) return false;
                const pagination = normalizeEntryPagination(result, page);
                // 删除最后一页的最后一条后，后端可能返回空的越界页；自动回到新的末页。
                if (pagination.total > 0 && page > pagination.totalPages) {
                    return await loadEntries(pagination.totalPages);
                }
                state.entries.value = result.items;
                state.totalPages.value = pagination.totalPages;
                state.totalEntries.value = pagination.total;
                state.currentPage.value = pagination.page;
                clearLoadError('entries');
                return true;
            } catch (error) {
                if (requestSeq !== entriesRequestSeq || requestEpoch !== dataRequestEpoch) return false;
                return reportLoadError('entries', error, '条目加载失败，请重试。');
            } finally {
                endDataRequest(requestId);
            }
        }

        async function loadTags() {
            const requestSeq = ++tagsRequestSeq;
            const requestEpoch = dataRequestEpoch;
            const requestId = beginDataRequest();
            const shouldCommit = () => (
                requestSeq === tagsRequestSeq && requestEpoch === dataRequestEpoch
            );
            try {
                const tags = await store.loadTags({ shouldCommit });
                if (!shouldCommit()) return false;
                state.tags.value = tags;
                clearLoadError('tags');
                return true;
            } catch (error) {
                if (requestSeq !== tagsRequestSeq || requestEpoch !== dataRequestEpoch) return false;
                return reportLoadError('tags', error, '标签加载失败，请重试。');
            } finally {
                endDataRequest(requestId);
            }
        }

        async function loadGroups() {
            const requestSeq = ++groupsRequestSeq;
            const requestEpoch = dataRequestEpoch;
            const requestId = beginDataRequest();
            const shouldCommit = () => (
                requestSeq === groupsRequestSeq && requestEpoch === dataRequestEpoch
            );
            try {
                const groups = await store.loadGroups({ shouldCommit });
                if (!shouldCommit()) return false;
                state.groups.value = groups;
                const groupTotalPages = getGroupTotalPages();
                if (state.groupCurrentPage.value > groupTotalPages && groupTotalPages > 0) {
                    state.groupCurrentPage.value = groupTotalPages;
                }
                clearLoadError('groups');
                return true;
            } catch (error) {
                if (requestSeq !== groupsRequestSeq || requestEpoch !== dataRequestEpoch) return false;
                return reportLoadError('groups', error, '密码组加载失败，请重试。');
            } finally {
                endDataRequest(requestId);
            }
        }

        async function loadAllData() {
            ['entries', 'tags', 'groups'].forEach(clearLoadError);
            const results = await Promise.all([
                loadEntries(),
                loadTags(),
                loadGroups()
            ]);
            return results.every(Boolean);
        }

        async function retryDataLoad() {
            return loadAllData();
        }

        async function updateEntryPageSize(value) {
            const size = normalizeUniversalPageSize(value, 20);
            state.settingsForm.pageSize = size;
            savePageSizePreference('secretbase.entryPageSize', size);
            if (api.getToken()) {
                try {
                    await store.updateSettings({ pageSize: size });
                    clearLoadError('settings');
                    return await loadEntries(1);
                } catch (error) {
                    return reportLoadError('settings', error, '分页设置保存失败，请重试。');
                }
            }
            return true;
        }

        async function applySettings(settings, { currentTheme, applyTheme }) {
            currentTheme.value = settings.theme;
            applyTheme(settings.theme);
            state.settingsForm.theme = settings.theme;
            const savedEntryPageSize = loadPageSizePreference('secretbase.entryPageSize', settings.pageSize || 20);
            state.settingsForm.pageSize = savedEntryPageSize;
            if (savedEntryPageSize !== settings.pageSize && api.getToken()) {
                try {
                    await store.updateSettings({ pageSize: savedEntryPageSize });
                    clearLoadError('settings');
                } catch (error) {
                    reportLoadError('settings', error, '分页偏好同步失败，已保留本机设置。');
                }
            } else {
                clearLoadError('settings');
            }
            state.settingsForm.autoLockMinutes = settings.autoLockMinutes;
            state.settingsForm.autoBackupRetention = settings.autoBackupRetention;
            state.settingsForm.closeToTray = Boolean(settings.closeToTray);
            state.settingsForm.confirmClose = settings.confirmClose !== false;
            state.settingsForm.desktopZoomPercent = settings.desktopZoomPercent || 100;
        }

        return {
            loadEntries,
            loadTags,
            loadGroups,
            loadAllData,
            retryDataLoad,
            clearLoadErrors,
            hasLoadError,
            invalidateRequests,
            updateEntryPageSize,
            applySettings
        };
    }

    window.SecretBaseAppDataController = {
        createAppDataController
    };
})();
