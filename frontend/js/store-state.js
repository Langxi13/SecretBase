/**
 * Store 的初始状态、字段映射和条目查询参数构建。
 */
(function () {
    function createDefaultFilters() {
        return {
            search: '',
            entryIds: [],
            tag: null,
            group: null,
            searchScopes: [],
            tags: [],
            untagged: false,
            createdFrom: '',
            createdTo: '',
            updatedFrom: '',
            updatedTo: '',
            hasUrl: '',
            hasRemarks: '',
            starred: false,
            sortBy: 'updated_at',
            sortOrder: 'desc'
        };
    }

    function createInitialStoreState() {
        return {
            initialized: false,
            locked: true,
            entries: [],
            tags: [],
            groups: [],
            trash: [],
            settings: {
                theme: 'system',
                pageSize: 20,
                autoLockMinutes: 5,
                autoBackupRetention: 30,
                closeToTray: false,
                confirmClose: true,
                desktopZoomPercent: 100
            },
            pagination: {
                page: 1,
                pageSize: 20,
                total: 0,
                totalPages: 0
            },
            filters: createDefaultFilters()
        };
    }

    function normalizeSettings(settings = {}) {
        return {
            theme: settings.theme || 'system',
            pageSize: settings.pageSize ?? settings.page_size ?? 20,
            autoLockMinutes: settings.autoLockMinutes ?? settings.auto_lock_minutes ?? 5,
            autoBackupRetention: settings.autoBackupRetention ?? settings.auto_backup_retention ?? 30,
            closeToTray: settings.closeToTray ?? settings.close_to_tray ?? false,
            confirmClose: settings.confirmClose ?? settings.confirm_close ?? true,
            desktopZoomPercent: settings.desktopZoomPercent ?? settings.desktop_zoom_percent ?? 100,
            language: settings.language || 'zh-CN'
        };
    }

    function toBackendSettings(settings = {}) {
        return {
            theme: settings.theme,
            page_size: settings.pageSize ?? settings.page_size,
            auto_lock_minutes: settings.autoLockMinutes ?? settings.auto_lock_minutes,
            auto_backup_retention: settings.autoBackupRetention ?? settings.auto_backup_retention,
            close_to_tray: settings.closeToTray ?? settings.close_to_tray,
            confirm_close: settings.confirmClose ?? settings.confirm_close,
            desktop_zoom_percent: settings.desktopZoomPercent ?? settings.desktop_zoom_percent,
            language: settings.language
        };
    }

    function normalizePagination(pagination = {}) {
        return {
            page: pagination.page ?? 1,
            pageSize: pagination.pageSize ?? pagination.page_size ?? 20,
            total: pagination.total ?? 0,
            totalPages: pagination.totalPages ?? pagination.total_pages ?? 0
        };
    }

    function buildEntrySearchParams({ page, pageSize, filters }) {
        const params = new URLSearchParams({
            page: page.toString(),
            page_size: pageSize.toString()
        });

        if (filters.search) {
            params.append('search', filters.search);
            params.append('search_scopes', (filters.searchScopes || []).join(','));
        }
        if (filters.entryIds?.length) {
            params.append('ids', filters.entryIds.join(','));
        }
        if (filters.tag) {
            params.append('tag', filters.tag);
        }
        if (filters.group) {
            params.append('group', filters.group);
        }
        if (filters.tags?.length) {
            params.append('tags', filters.tags.join(','));
        }
        if (filters.untagged) {
            params.append('untagged', 'true');
        }
        if (filters.createdFrom) {
            params.append('created_from', filters.createdFrom);
        }
        if (filters.createdTo) {
            params.append('created_to', filters.createdTo);
        }
        if (filters.updatedFrom) {
            params.append('updated_from', filters.updatedFrom);
        }
        if (filters.updatedTo) {
            params.append('updated_to', filters.updatedTo);
        }
        if (filters.hasUrl === 'yes') {
            params.append('has_url', 'true');
        } else if (filters.hasUrl === 'no') {
            params.append('has_url', 'false');
        }
        if (filters.hasRemarks === 'yes') {
            params.append('has_remarks', 'true');
        } else if (filters.hasRemarks === 'no') {
            params.append('has_remarks', 'false');
        }
        if (filters.starred) {
            params.append('starred', 'true');
        }
        params.append('sort_by', filters.sortBy || 'updated_at');
        params.append('sort_order', filters.sortOrder || 'desc');
        return params;
    }

    window.SecretBaseStoreState = {
        createDefaultFilters,
        createInitialStoreState,
        normalizeSettings,
        toBackendSettings,
        normalizePagination,
        buildEntrySearchParams
    };
})();
