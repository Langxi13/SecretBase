/**
 * Vue 根应用的共享响应式状态。
 *
 * 这里仅创建状态和不含副作用的派生值；领域行为仍由各控制器负责。
 */
(function () {
    function createAppState({ ref, reactive, computed, loadPageSizePreference }) {
        const loading = ref(true);
        const initialized = ref(false);
        const locked = ref(true);
        const password = ref('');
        const confirmPassword = ref('');
        const passwordError = ref('');
        const unlockError = ref('');
        const submitting = ref(false);
        const passwordChanging = ref(false);
        const isSidebarCollapsed = ref(localStorage.getItem('secretbase.sidebarCollapsed') === 'true');
        const runtimeConfig = window.SECRETBASE_RUNTIME_CONFIG || {};
        const isDesktopMode = runtimeConfig.mode === 'desktop';
        const desktopVersion = runtimeConfig.version || '未知';
        const desktopPlatform = runtimeConfig.desktopPlatform || '';
        const desktopArchitecture = runtimeConfig.desktopArchitecture || '';
        const desktopRuntimeCapabilities = reactive({
            single_instance: false,
            directory_open: false,
            close_confirmation: false,
            tray: false,
            zoom_controls: false,
            native_zoom_feedback: false,
            ...(runtimeConfig.desktopCapabilities || {})
        });

        const entries = ref([]);
        const tags = ref([]);
        const groups = ref([]);
        const entryPageSizeOptions = [6, 12, 20, 30, 50, 100];
        const groupPageSizeOptions = [3, 6, 9, 12, 15, 24, 50, 100];

        const groupCurrentPage = ref(1);
        const groupPageSize = ref(loadPageSizePreference('secretbase.groupPageSize', 12));
        const currentPage = ref(1);
        const totalPages = ref(0);
        const totalEntries = ref(0);
        const searchQuery = ref('');
        const searchScopeOptions = [
            { key: 'title', label: '标题' },
            { key: 'url', label: '网址' },
            { key: 'tags', label: '标签' },
            { key: 'field_names', label: '字段名' },
            { key: 'field_values', label: '非隐藏字段值' },
            { key: 'remarks', label: '备注' }
        ];
        const defaultSearchScopes = [];
        const selectedSearchScopes = ref([...defaultSearchScopes]);
        const sortBy = ref('updated_at');
        const sortOrder = ref('desc');
        const filter = ref('all');
        const activeTagName = ref('');
        const activeGroupName = ref('');
        const listContextNotice = ref('');
        const showTagDropdown = ref(false);
        const tagBrowserQuery = ref('');
        const tagBrowserSort = ref('count_desc');
        const tagBrowserPage = ref(1);
        const tagPageSizeOptions = [5, 10, 20, 50];
        const tagBrowserPageSize = ref(loadPageSizePreference('secretbase.tagBrowserPageSize', 5));
        const advancedTagDraft = ref('');
        const advancedTagList = ref([]);

        const showCreateModal = ref(false);
        const showEditModal = ref(false);
        const showAiParse = ref(false);
        const showAiAssistant = ref(false);
        const showSettings = ref(false);
        const showChangePassword = ref(false);
        const showTrash = ref(false);
        const showTagManager = ref(false);
        const showTagEditorModal = ref(false);
        const showGroupModal = ref(false);
        const showTagBrowser = ref(false);
        const showGroupEntryPicker = ref(false);
        const entrySaving = ref(false);
        const groupSaving = ref(false);
        const tagSaving = ref(false);
        const tagMerging = ref(false);
        const groupPickerSaving = ref(false);
        const showConfirm = ref(false);
        const confirmSubmitting = ref(false);
        const showTools = ref(false);
        const showBackupCenter = ref(false);
        const showAdvancedFilters = ref(false);
        const showDesktopStatus = ref(false);
        const showDesktopCloseConfirm = ref(false);
        const desktopCloseRemember = ref(false);
        const desktopCloseSubmitting = ref(false);
        const desktopCloseError = ref('');
        const desktopCloseSettingsSaving = ref(false);
        const selectedEntry = ref(null);
        const editingEntry = ref(null);
        const copyMenuEntryId = ref(null);
        const selectedEntryIds = ref([]);
        const batchTagName = ref('');
        const groupPickerEntries = ref([]);
        const groupPickerSelectedIds = ref([]);
        const groupPickerTagFilter = ref('');
        const groupPickerGroupFilter = ref('');
        const groupPickerPage = ref(1);
        const groupPickerPageSize = ref(loadPageSizePreference('secretbase.groupPickerPageSize', 10));
        const groupPickerPageSizeOptions = [5, 10, 20, 50, 100];
        const groupPickerLoading = ref(false);
        const importConflictMessage = ref('');
        const showOnboarding = ref(false);
        const importingSamples = ref(false);
        const showImportConflicts = ref(false);
        const importConflicts = ref([]);
        const showImportReport = ref(false);
        const importReport = ref(null);
        const showImportPreview = ref(false);
        const importPreview = ref(null);
        const lastImportPlainFile = ref(null);
        const importPreviewSelectedIds = ref([]);
        const lastImportSelectedIds = ref([]);
        const importConflictResolutions = ref({});
        const lastImportConflictResolutions = ref({});
        const revealedFields = ref([]);
        const backups = ref([]);
        const highlightedBackupFilename = ref('');
        const backupListLoading = ref(false);
        const creatingBackup = ref(false);
        const restoringBackupFilename = ref('');
        const downloadingBackupFilename = ref('');
        const backupPages = reactive({
            manual: 1,
            auto: 1,
            legacy: 1
        });
        const backupPageSize = ref(loadPageSizePreference('secretbase.backupPageSize', 3));
        const backupPageSizeOptions = [3, 6, 10, 20, 50, 100];
        const restoreWizard = reactive({
            visible: false,
            step: 1,
            backup: null,
            summary: null,
            password: '',
            needsPassword: false,
            confirmation: '',
            loadingSummary: false,
            restoring: false,
            error: ''
        });
        const healthReport = ref(null);
        const maintenanceReport = ref(null);
        const securityReport = ref(null);
        const savedAdvancedFilters = ref([]);
        const desktopDiagnostics = ref(null);
        const desktopDiagnosticsLoading = ref(false);
        const desktopDiagnosticsError = ref('');
        const desktopUpdateChecking = ref(false);
        const desktopUpdateResult = ref(null);
        const desktopUpdateError = ref('');

        const entryForm = reactive({
            id: null,
            title: '',
            url: '',
            starred: false,
            tags: [],
            groups: [],
            fields: [],
            remarks: ''
        });
        const newTag = ref('');
        const newGroup = ref('');
        const newGroupDescription = ref('');
        const tagInput = ref(null);
        const selectedTemplate = ref('');
        const entryTemplates = [
            { id: 'website', name: '网站账号', fields: [{ name: '账号', value: '', copyable: true, hidden: false }, { name: '密码', value: '', copyable: true, hidden: true }, { name: '邮箱', value: '', copyable: true, hidden: false }] },
            { id: 'server', name: '服务器', fields: [{ name: 'IP', value: '', copyable: true, hidden: false }, { name: '端口', value: '22', copyable: false, hidden: false }, { name: '用户名', value: '', copyable: true, hidden: false }, { name: '密码/密钥', value: '', copyable: true, hidden: true }] },
            { id: 'api', name: 'API Key', fields: [{ name: 'API Key', value: '', copyable: true, hidden: true }, { name: 'Secret', value: '', copyable: true, hidden: true }, { name: '环境', value: '', copyable: false, hidden: false }] },
            { id: 'note', name: '安全笔记', fields: [{ name: '内容', value: '', copyable: false, hidden: false }] },
            { id: 'card', name: '银行卡/证件', fields: [{ name: '号码', value: '', copyable: true, hidden: true }, { name: '姓名', value: '', copyable: false, hidden: false }, { name: '有效期', value: '', copyable: false, hidden: false }] }
        ];

        const settingsForm = reactive({
            theme: 'system',
            pageSize: 20,
            autoLockMinutes: 5,
            autoBackupRetention: 30,
            closeToTray: false,
            confirmClose: true,
            desktopZoomPercent: 100,
            desktopUpdateAutoCheck: true,
            desktopUpdateAutoDownload: true
        });
        const activeSettingsTab = ref('general');
        const settingsTabs = [
            { key: 'general', label: '通用' },
            { key: 'security', label: '安全' },
            { key: 'ai', label: 'AI' },
            { key: 'data', label: '数据' },
            ...(isDesktopMode ? [{ key: 'desktop', label: '桌面' }] : [])
        ];
        const aiState = window.SecretBaseAiState.createAiState({ ref, reactive, computed });
        const importConflictStrategy = ref('skip');
        const advancedFilters = reactive({
            untagged: false,
            createdFrom: '',
            createdTo: '',
            updatedFrom: '',
            updatedTo: '',
            hasUrl: '',
            hasRemarks: ''
        });
        const defaultTimeRange = {
            from: '1970-01-01',
            to: '9999-12-31'
        };
        const tagMergeForm = reactive({
            sourceTags: '',
            targetTag: ''
        });
        const tagMergeSourceList = ref([]);
        const tagManagerPanel = ref('list');
        const tagManagerPage = ref(1);
        const tagManagerPageSize = ref(loadPageSizePreference('secretbase.tagManagerPageSize', 5));
        const selectedManagedTagNames = ref([]);
        const tagEditorForm = reactive({
            mode: 'create',
            originalName: '',
            name: '',
            description: '',
            color: '#64748b'
        });
        const editingGroupName = ref('');
        const groupForm = reactive({
            name: '',
            description: ''
        });

        const passwordForm = reactive({
            oldPassword: '',
            newPassword: '',
            confirmPassword: '',
            error: ''
        });

        const trashItems = ref([]);
        const trashPage = ref(1);
        const trashTotalPages = ref(0);
        const trashTotal = ref(0);
        const trashPageSize = ref(loadPageSizePreference('secretbase.trashPageSize', 10));
        const trashPageSizeOptions = [5, 10, 20, 50, 100];

        const confirmTitle = ref('');
        const confirmMessage = ref('');

        return {
            loading,
            initialized,
            locked,
            password,
            confirmPassword,
            passwordError,
            unlockError,
            submitting,
            passwordChanging,
            isSidebarCollapsed,
            isDesktopMode,
            desktopVersion,
            desktopPlatform,
            desktopArchitecture,
            desktopRuntimeCapabilities,
            entries,
            tags,
            groups,
            entryPageSizeOptions,
            groupPageSizeOptions,
            groupCurrentPage,
            groupPageSize,
            currentPage,
            totalPages,
            totalEntries,
            searchQuery,
            searchScopeOptions,
            defaultSearchScopes,
            selectedSearchScopes,
            sortBy,
            sortOrder,
            filter,
            activeTagName,
            activeGroupName,
            listContextNotice,
            showTagDropdown,
            tagBrowserQuery,
            tagBrowserSort,
            tagBrowserPage,
            tagPageSizeOptions,
            tagBrowserPageSize,
            advancedTagDraft,
            advancedTagList,
            showCreateModal,
            showEditModal,
            showAiParse,
            showAiAssistant,
            showSettings,
            showChangePassword,
            showTrash,
            showTagManager,
            showTagEditorModal,
            showGroupModal,
            showTagBrowser,
            showGroupEntryPicker,
            entrySaving,
            groupSaving,
            tagSaving,
            tagMerging,
            groupPickerSaving,
            showConfirm,
            confirmSubmitting,
            showTools,
            showBackupCenter,
            showAdvancedFilters,
            showDesktopStatus,
            showDesktopCloseConfirm,
            desktopCloseRemember,
            desktopCloseSubmitting,
            desktopCloseError,
            desktopCloseSettingsSaving,
            selectedEntry,
            editingEntry,
            copyMenuEntryId,
            selectedEntryIds,
            batchTagName,
            groupPickerEntries,
            groupPickerSelectedIds,
            groupPickerTagFilter,
            groupPickerGroupFilter,
            groupPickerPage,
            groupPickerPageSize,
            groupPickerPageSizeOptions,
            groupPickerLoading,
            importConflictMessage,
            showOnboarding,
            importingSamples,
            showImportConflicts,
            importConflicts,
            showImportReport,
            importReport,
            showImportPreview,
            importPreview,
            lastImportPlainFile,
            importPreviewSelectedIds,
            lastImportSelectedIds,
            importConflictResolutions,
            lastImportConflictResolutions,
            revealedFields,
            backups,
            highlightedBackupFilename,
            backupListLoading,
            creatingBackup,
            restoringBackupFilename,
            downloadingBackupFilename,
            backupPages,
            backupPageSize,
            backupPageSizeOptions,
            restoreWizard,
            healthReport,
            maintenanceReport,
            securityReport,
            savedAdvancedFilters,
            desktopDiagnostics,
            desktopDiagnosticsLoading,
            desktopDiagnosticsError,
            desktopUpdateChecking,
            desktopUpdateResult,
            desktopUpdateError,
            entryForm,
            newTag,
            newGroup,
            newGroupDescription,
            tagInput,
            selectedTemplate,
            entryTemplates,
            ...aiState,
            settingsForm,
            activeSettingsTab,
            settingsTabs,
            importConflictStrategy,
            advancedFilters,
            defaultTimeRange,
            tagMergeForm,
            tagMergeSourceList,
            tagManagerPanel,
            tagManagerPage,
            tagManagerPageSize,
            selectedManagedTagNames,
            tagEditorForm,
            editingGroupName,
            groupForm,
            passwordForm,
            trashItems,
            trashPage,
            trashTotalPages,
            trashTotal,
            trashPageSize,
            trashPageSizeOptions,
            confirmTitle,
            confirmMessage
        };
    }

    window.SecretBaseAppState = {
        createAppState
    };
})();
