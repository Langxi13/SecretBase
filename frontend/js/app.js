/**
 * SecretBase Vue 应用
 */
const { createApp, ref, reactive, computed, watch, onMounted, nextTick } = Vue;

const app = createApp({
    setup() {
        // 状态
        const loading = ref(true);
        const initialized = ref(false);
        const locked = ref(true);
        const password = ref('');
        const confirmPassword = ref('');
        const passwordError = ref('');
        const unlockError = ref('');
        const submitting = ref(false);

        // 主界面状态
        const entries = ref([]);
        const tags = ref([]);
        const currentPage = ref(1);
        const totalPages = ref(0);
        const totalEntries = ref(0);
        const searchQuery = ref('');
        const searchScopeOptions = [
            { key: 'title', label: '标题' },
            { key: 'url', label: '网址' },
            { key: 'tags', label: '标签' },
            { key: 'field_names', label: '字段名' },
            { key: 'field_values', label: '非可复制字段值' },
            { key: 'remarks', label: '备注' }
        ];
        const defaultSearchScopes = [];
        const selectedSearchScopes = ref([...defaultSearchScopes]);
        const sortBy = ref('updated_at');
        const sortOrder = ref('desc');
        const filter = ref('all');
        const activeTagName = ref('');
        const listContextNotice = ref('');
        const showTagDropdown = ref(false);
        const tagBrowserQuery = ref('');
        const tagBrowserSort = ref('count_desc');
        const advancedTagDraft = ref('');
        const advancedTagList = ref([]);

        // 弹窗状态
        const showCreateModal = ref(false);
        const showEditModal = ref(false);
        const showAiParse = ref(false);
        const showSettings = ref(false);
        const showChangePassword = ref(false);
        const showTrash = ref(false);
        const showTagManager = ref(false);
        const showTagBrowser = ref(false);
        const showConfirm = ref(false);
        const showTools = ref(false);
        const showBackupCenter = ref(false);
        const showAdvancedFilters = ref(false);
        const selectedEntry = ref(null);
        const editingEntry = ref(null);
        const copyMenuEntryId = ref(null);
        const selectedEntryIds = ref([]);
        const batchTagName = ref('');
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
        const backupPageSize = 3;
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

        // 表单
        const entryForm = reactive({
            id: null,
            title: '',
            url: '',
            starred: false,
            tags: [],
            fields: [],
            remarks: ''
        });
        const newTag = ref('');
        const tagInput = ref(null);
        const selectedTemplate = ref('');
        const entryTemplates = [
            { id: 'website', name: '网站账号', fields: [{ name: '账号', value: '', copyable: true }, { name: '密码', value: '', copyable: true }, { name: '邮箱', value: '', copyable: true }] },
            { id: 'server', name: '服务器', fields: [{ name: 'IP', value: '', copyable: true }, { name: '端口', value: '22', copyable: false }, { name: '用户名', value: '', copyable: true }, { name: '密码/密钥', value: '', copyable: true }] },
            { id: 'api', name: 'API Key', fields: [{ name: 'API Key', value: '', copyable: true }, { name: 'Secret', value: '', copyable: true }, { name: '环境', value: '', copyable: false }] },
            { id: 'note', name: '安全笔记', fields: [{ name: '内容', value: '', copyable: false }] },
            { id: 'card', name: '银行卡/证件', fields: [{ name: '号码', value: '', copyable: true }, { name: '姓名', value: '', copyable: false }, { name: '有效期', value: '', copyable: false }] }
        ];

        // AI 解析
        const aiText = ref('');
        const aiResult = ref(null);
        const aiParsing = ref(false);
        const aiStatus = ref(null);
        const aiStatusError = ref('');
        const aiFailureMessage = ref('');
        const aiCooldownUntil = ref(0);
        const aiNow = ref(Date.now());
        const lastAiParseText = ref('');

        // 设置
        const settingsForm = reactive({
            theme: 'system',
            pageSize: 20,
            autoLockMinutes: 5,
            autoBackupRetention: 30
        });
        const activeSettingsTab = ref('general');
        const settingsTabs = [
            { key: 'general', label: '通用' },
            { key: 'security', label: '安全' },
            { key: 'ai', label: 'AI' },
            { key: 'data', label: '数据' }
        ];
        const aiSettingsForm = reactive({
            baseUrl: '',
            apiKey: '',
            model: ''
        });
        const aiSettingsStatus = ref(null);
        const aiSettingsEditing = ref(false);
        const aiModels = ref([]);
        const aiModelsLoading = ref(false);
        const aiSettingsSaving = ref(false);
        const aiSettingsError = ref('');
        const aiSettingsMessage = ref('');
        const aiConfiguredBaseUrl = computed(() => aiSettingsStatus.value?.base_url || aiSettingsStatus.value?.baseUrl || '');
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

        // 修改密码
        const passwordForm = reactive({
            oldPassword: '',
            newPassword: '',
            confirmPassword: '',
            error: ''
        });

        // 回收站
        const trashItems = ref([]);
        const trashPage = ref(1);
        const trashTotalPages = ref(0);
        const trashTotal = ref(0);

        // 确认弹窗
        const confirmTitle = ref('');
        const confirmMessage = ref('');
        let confirmCallback = null;
        let autoLockTimer = null;
        let entriesRequestSeq = 0;

        // 主题
        const currentTheme = ref('system');
        const themeIcon = computed(() => {
            switch (currentTheme.value) {
                case 'dark': return '🌙';
                case 'light': return '☀️';
                default: return '💻';
            }
        });

        const aiCooldownSeconds = computed(() => Math.max(0, Math.ceil((aiCooldownUntil.value - aiNow.value) / 1000)));
        const aiSoftInputChars = 3000;
        const aiMaxInputChars = 6000;
        const aiTextLength = computed(() => aiText.value.length);
        const aiInputWarning = computed(() => {
            const text = aiText.value.trim();
            if (aiText.value.length > aiMaxInputChars) return `内容过长，请分批解析，单次最多 ${aiMaxInputChars} 字符。`;
            if (text.split(/\n+/).filter(Boolean).length > 60) return '内容行数较多，建议按系统或账号分批解析，避免 AI 合并或误分条目。';
            if (aiText.value.length > aiSoftInputChars) return '内容较长，建议分批解析并逐条检查结果。';
            return '';
        });
        const canParseAi = computed(() => {
            const text = aiText.value.trim();
            return Boolean(text)
                && Boolean(aiStatus.value?.configured)
                && aiText.value.length <= aiMaxInputChars
                && !aiParsing.value
                && aiCooldownSeconds.value === 0
                && text !== lastAiParseText.value;
        });

        const selectedAiEntryCount = computed(() => {
            return aiResult.value?.entries?.filter(entry => entry.selected).length || 0;
        });

        const selectedImportPreviewCount = computed(() => importPreviewSelectedIds.value.length);

        const selectedImportConflictCount = computed(() => {
            return (importPreview.value?.entries || []).filter(entry => entry.is_conflict && isImportPreviewSelected(entry.id)).length;
        });

        const selectedSearchScopeLabels = computed(() => {
            return searchScopeOptions
                .filter(scope => selectedSearchScopes.value.includes(scope.key))
                .map(scope => scope.label);
        });

        const sidebarTagLimit = 6;
        const tagNameCollator = new Intl.Collator('zh-CN', { numeric: true, sensitivity: 'base' });
        const tagBrowserSortOptions = [
            { value: 'count_desc', label: '条目数量多到少' },
            { value: 'count_asc', label: '条目数量少到多' },
            { value: 'name_asc', label: '名称 A-Z / 中文升序' },
            { value: 'name_desc', label: '名称 Z-A / 中文降序' }
        ];

        const sortedTagBrowserTags = computed(() => {
            const sorted = [...tags.value];
            sorted.sort((left, right) => {
                const nameCompare = tagNameCollator.compare(left.name || '', right.name || '');
                if (tagBrowserSort.value === 'count_asc') {
                    return (left.count || 0) - (right.count || 0) || nameCompare;
                }
                if (tagBrowserSort.value === 'name_asc') {
                    return nameCompare || (right.count || 0) - (left.count || 0);
                }
                if (tagBrowserSort.value === 'name_desc') {
                    return -nameCompare || (right.count || 0) - (left.count || 0);
                }
                return (right.count || 0) - (left.count || 0) || nameCompare;
            });
            return sorted;
        });

        const visibleSidebarTags = computed(() => {
            if (tags.value.length <= sidebarTagLimit) return tags.value;
            const activeTag = tags.value.find(tag => tag.name === activeTagName.value);
            const baseTags = tags.value
                .filter(tag => tag.name !== activeTagName.value)
                .slice(0, activeTag ? sidebarTagLimit - 1 : sidebarTagLimit);
            return activeTag ? [activeTag, ...baseTags] : baseTags;
        });

        const hiddenSidebarTagCount = computed(() => Math.max(0, tags.value.length - visibleSidebarTags.value.length));

        const filteredTagBrowserTags = computed(() => {
            const query = tagBrowserQuery.value.trim().toLowerCase();
            if (!query) return sortedTagBrowserTags.value;
            return sortedTagBrowserTags.value.filter(tag => String(tag.name || '').toLowerCase().includes(query));
        });

        const activeAdvancedFilterChips = computed(() => {
            const chips = advancedTagList.value.map(tag => ({
                key: `tag:${tag}`,
                label: `标签：${tag}`,
                type: 'tag',
                value: tag
            }));
            if (advancedFilters.untagged) chips.push({ key: 'untagged', label: '只看无标签', type: 'untagged' });
            if (advancedFilters.createdFrom) chips.push({ key: 'createdFrom', label: `创建起：${advancedFilters.createdFrom}`, type: 'createdFrom' });
            if (advancedFilters.createdTo) chips.push({ key: 'createdTo', label: `创建止：${advancedFilters.createdTo}`, type: 'createdTo' });
            if (advancedFilters.hasUrl === 'yes') chips.push({ key: 'hasUrlYes', label: '有网址', type: 'hasUrl' });
            if (advancedFilters.hasUrl === 'no') chips.push({ key: 'hasUrlNo', label: '无网址', type: 'hasUrl' });
            if (advancedFilters.hasRemarks === 'yes') chips.push({ key: 'hasRemarksYes', label: '有备注', type: 'hasRemarks' });
            if (advancedFilters.hasRemarks === 'no') chips.push({ key: 'hasRemarksNo', label: '无备注', type: 'hasRemarks' });
            return chips;
        });

        const activeListStateItems = computed(() => {
            const items = [];
            if (listContextNotice.value) items.push(listContextNotice.value);
            if (searchQuery.value.trim()) {
                const scopes = selectedSearchScopeLabels.value.length > 0 ? selectedSearchScopeLabels.value.join('、') : '未选择范围';
                items.push(`搜索：${searchQuery.value.trim()}（${scopes}）`);
            }
            if (filter.value === 'starred') items.push('仅星标');
            if (filter.value === 'tag' && activeTagName.value) items.push(`标签：${activeTagName.value}`);
            activeAdvancedFilterChips.value.forEach(chip => items.push(chip.label));
            if (sortBy.value !== 'updated_at' || sortOrder.value !== 'desc') {
                const sortLabel = sortBy.value === 'title' ? '标题' : sortBy.value === 'created_at' ? '创建时间' : '更新时间';
                items.push(`排序：${sortLabel}${sortOrder.value === 'asc' ? '升序' : '降序'}`);
            }
            return items;
        });

        const hasActiveListState = computed(() => activeListStateItems.value.length > 0);

        const allCurrentPageSelected = computed(() => {
            return entries.value.length > 0 && entries.value.every(entry => selectedEntryIds.value.includes(entry.id));
        });

        const backupBusy = computed(() => (
            backupListLoading.value ||
            creatingBackup.value ||
            Boolean(restoringBackupFilename.value) ||
            Boolean(downloadingBackupFilename.value)
        ));
        const sortedBackups = computed(() => {
            return [...backups.value].sort((a, b) => new Date(b.modified_at || 0) - new Date(a.modified_at || 0));
        });
        const backupSummary = computed(() => {
            const manualCount = backups.value.filter(backup => backup.type === 'manual').length;
            const autoCount = backups.value.filter(backup => backup.type === 'auto').length;
            const recent = sortedBackups.value[0] || null;
            return {
                manualCount,
                autoCount,
                retention: settingsForm.autoBackupRetention,
                recent
            };
        });
        const backupGroups = computed(() => {
            const definitions = [
                {
                    type: 'manual',
                    title: '手动备份',
                    hint: '由你主动创建，不会被自动备份轮转清理。'
                },
                {
                    type: 'auto',
                    title: '自动备份',
                    hint: '写入或恢复前自动创建，会按保留数量清理旧文件。'
                },
                {
                    type: 'legacy',
                    title: '旧版备份',
                    hint: '旧目录中的兼容备份。刷新后通常会迁移到自动备份。'
                }
            ];
            return definitions
                .map(group => ({
                    ...group,
                    items: backups.value.filter(backup => (backup.type || 'legacy') === group.type)
                }))
                .filter(group => group.type !== 'legacy' || group.items.length > 0)
                .map(group => {
                    const totalPages = Math.max(1, Math.ceil(group.items.length / backupPageSize));
                    const current = Math.min(backupPages[group.type] || 1, totalPages);
                    const start = (current - 1) * backupPageSize;
                    const pagedItems = group.items.slice(start, start + backupPageSize);
                    return {
                        ...group,
                        page: current,
                        totalPages,
                        pagedItems,
                        emptySlots: Math.max(0, backupPageSize - pagedItems.length)
                    };
                });
        });

        // 分页
        const visiblePages = computed(() => {
            const pages = [];
            const total = totalPages.value;
            const current = currentPage.value;

            if (total <= 7) {
                for (let i = 1; i <= total; i++) pages.push(i);
            } else {
                pages.push(1);
                if (current > 3) pages.push('...');
                for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
                    pages.push(i);
                }
                if (current < total - 2) pages.push('...');
                pages.push(total);
            }

            return pages;
        });

        // 初始化
        onMounted(async () => {
            try {
                const authStatus = await store.checkAuth();
                initialized.value = authStatus.initialized;
                window.addEventListener('secretbase:unauthorized', handleUnauthorizedLock);

                const hasSessionToken = Boolean(api.getToken());
                locked.value = authStatus.locked || (authStatus.initialized && !hasSessionToken);
                if (locked.value) {
                    api.setToken(null);
                    store.setState({ locked: true });
                }

                const settings = locked.value
                    ? {
                        ...store.state.settings,
                        autoLockMinutes: authStatus.auto_lock_minutes ?? store.state.settings.autoLockMinutes
                    }
                    : await store.loadSettings();
                applySettings(settings);
                applyTheme(currentTheme.value);
                loadSavedAdvancedFilters();
                bindActivityListeners();
                setInterval(() => {
                    aiNow.value = Date.now();
                }, 1000);

                if (!locked.value) {
                    await loadAllData();
                    startAutoLockTimer();
                }
            } catch (error) {
                console.error('初始化失败:', error);
            } finally {
                loading.value = false;
            }
        });

        // 加载所有数据
        async function loadAllData() {
            await Promise.all([
                loadEntries(),
                loadTags()
            ]);
        }

        function applySettings(settings) {
            currentTheme.value = settings.theme;
            applyTheme(settings.theme);
            settingsForm.theme = settings.theme;
            settingsForm.pageSize = settings.pageSize;
            settingsForm.autoLockMinutes = settings.autoLockMinutes;
            settingsForm.autoBackupRetention = settings.autoBackupRetention;
        }

        async function openSettings() {
            showSettings.value = true;
            activeSettingsTab.value = 'general';
            if (aiSettingsStatus.value === null) {
                await loadAiSettingsStatus();
            }
        }

        async function selectSettingsTab(tabKey) {
            activeSettingsTab.value = tabKey;
            if (tabKey === 'ai') {
                await loadAiSettingsStatus();
            }
        }

        async function loadAiSettingsStatus() {
            aiSettingsError.value = '';
            try {
                const result = await api.get('/ai/status');
                const status = result.data || {};
                status.base_url = status.base_url || status.baseUrl || '';
                aiSettingsStatus.value = status;
                aiSettingsForm.baseUrl = status.base_url || '';
                aiSettingsForm.model = status.model || '';
                aiSettingsForm.apiKey = '';
                aiModels.value = status.model ? [status.model] : [];
                aiSettingsEditing.value = !status.configured;
            } catch (error) {
                aiSettingsStatus.value = null;
                aiSettingsEditing.value = true;
                aiSettingsError.value = error.message || '无法加载 AI 配置状态';
            }
        }

        // 加载条目
        async function loadEntries(page = 1) {
            const requestSeq = ++entriesRequestSeq;
            const result = await store.loadEntries(page);
            if (requestSeq !== entriesRequestSeq) {
                return;
            }
            entries.value = result.items;
            totalPages.value = result.pagination.totalPages;
            totalEntries.value = result.pagination.total;
            currentPage.value = result.pagination.page || page;
        }

        function reportItemIds(items = []) {
            return Array.from(new Set(items.map(item => item.id).filter(Boolean)));
        }

        function duplicateGroupIds(groups = []) {
            return reportItemIds(groups.flatMap(group => group));
        }

        async function focusReportItems(items, label) {
            const ids = reportItemIds(items);
            if (ids.length === 0) {
                showToast('没有可定位的条目', 'warning');
                return;
            }
            store.clearFilters();
            resetAdvancedFilterForm();
            searchQuery.value = '';
            filter.value = 'all';
            activeTagName.value = '';
            listContextNotice.value = `工具定位：${label || '条目'}（${ids.length} 条）`;
            store.setFilter('entryIds', ids);
            showTools.value = false;
            await loadEntries(1);
            showToast(`已定位 ${ids.length} 条${label || '条目'}`, 'success');
        }

        async function focusReportGroups(groups, label) {
            await focusReportItems(groups.flatMap(group => group), label);
        }

        async function focusUntaggedItems() {
            showTools.value = false;
            await clearAdvancedFilters();
            advancedFilters.untagged = true;
            showAdvancedFilters.value = true;
            listContextNotice.value = '维护工具：无标签条目';
            await applyAdvancedFilters();
        }

        async function addTagToUntaggedItems() {
            const items = maintenanceReport.value?.untagged_items || [];
            const ids = reportItemIds(items);
            if (ids.length === 0) return;
            const tagName = window.prompt('给无标签条目添加标签', '待整理');
            if (!tagName || !tagName.trim()) return;
            const result = await store.batchUpdateTags(ids, [tagName.trim()], []);
            if (result) {
                await Promise.all([loadEntries(1), loadTags(), loadMaintenanceReport()]);
            }
        }

        // 加载标签
        async function loadTags() {
            tags.value = await store.loadTags();
        }

        // 初始化密码
        async function initPassword() {
            if (password.value !== confirmPassword.value) {
                passwordError.value = '两次输入的密码不一致';
                return;
            }
            if (password.value.length < 8) {
                passwordError.value = '密码至少 8 位';
                return;
            }

            submitting.value = true;
            passwordError.value = '';

            try {
                await store.initPassword(password.value);
                initialized.value = true;
                locked.value = false;
                password.value = '';
                confirmPassword.value = '';
                applySettings(await store.loadSettings());
                await loadAllData();
                startAutoLockTimer();
                showOnboarding.value = true;
                showToast('欢迎使用 SecretBase', 'success');
            } catch (error) {
                passwordError.value = error.message || '设置失败';
            } finally {
                submitting.value = false;
            }
        }

        // 解锁
        async function unlock() {
            if (!password.value) {
                unlockError.value = '请输入密码';
                return;
            }

            submitting.value = true;
            unlockError.value = '';

            try {
                await store.unlock(password.value);
                locked.value = false;
                password.value = '';
                applySettings(await store.loadSettings());
                await loadAllData();
                startAutoLockTimer();
            } catch (error) {
                unlockError.value = error.message || '解锁失败';
            } finally {
                submitting.value = false;
            }
        }

        // 锁定
        async function lock() {
            try {
                await store.lock();
            } finally {
                applyLockedState();
            }
        }

        function applyLockedState() {
            api.setToken(null);
            locked.value = true;
            entries.value = [];
            tags.value = [];
            selectedEntry.value = null;
            selectedEntryIds.value = [];
            showCreateModal.value = false;
            showEditModal.value = false;
            showAiParse.value = false;
            showSettings.value = false;
            showTrash.value = false;
            showTagManager.value = false;
            showTagBrowser.value = false;
            showTools.value = false;
            showImportPreview.value = false;
            showImportConflicts.value = false;
            showImportReport.value = false;
            clearAutoLockTimer();
        }

        // 搜索防抖
        const debounceSearch = debounce(async () => {
            store.setFilter('entryIds', []);
            listContextNotice.value = '';
            store.setFilter('search', searchQuery.value);
            store.setFilter('searchScopes', selectedSearchScopes.value);
            await loadEntries(1);
        }, 300);

        async function toggleSearchScope(scopeKey) {
            selectedSearchScopes.value = selectedSearchScopes.value.includes(scopeKey)
                ? selectedSearchScopes.value.filter(key => key !== scopeKey)
                : [...selectedSearchScopes.value, scopeKey];
            store.setFilter('searchScopes', selectedSearchScopes.value);
            if (searchQuery.value.trim()) {
                store.setFilter('entryIds', []);
                listContextNotice.value = '';
                await loadEntries(1);
            }
        }

        function resetSearchScopes() {
            selectedSearchScopes.value = [...defaultSearchScopes];
            store.setFilter('searchScopes', selectedSearchScopes.value);
        }

        // 按标签筛选
        async function filterByTag(tagName) {
            store.setFilter('entryIds', []);
            listContextNotice.value = '';
            store.setFilter('tag', tagName);
            store.setFilter('starred', false);
            filter.value = 'tag';
            activeTagName.value = tagName;
            showTagDropdown.value = false;
            showTagBrowser.value = false;
            await loadEntries(1);
        }

        function openTagBrowser() {
            tagBrowserQuery.value = '';
            showTagBrowser.value = true;
        }

        function closeTagBrowser() {
            showTagBrowser.value = false;
        }

        async function showAllEntries() {
            filter.value = 'all';
            activeTagName.value = '';
            listContextNotice.value = '';
            searchQuery.value = '';
            resetSearchScopes();
            store.clearFilters();
            resetAdvancedFilterForm();
            sortBy.value = store.state.filters.sortBy;
            sortOrder.value = store.state.filters.sortOrder;
            await loadEntries(1);
        }

        async function showStarredEntries() {
            filter.value = 'starred';
            activeTagName.value = '';
            listContextNotice.value = '';
            store.setFilter('entryIds', []);
            store.setFilter('tag', null);
            store.setFilter('starred', true);
            await loadEntries(1);
        }

        // 切换主题
        function toggleTheme() {
            const themes = ['system', 'light', 'dark'];
            const currentIndex = themes.indexOf(currentTheme.value);
            currentTheme.value = themes[(currentIndex + 1) % themes.length];
            settingsForm.theme = currentTheme.value;
            applyTheme(currentTheme.value);
            store.updateSettings({ theme: currentTheme.value });
        }

        // 应用主题
        function applyTheme(theme) {
            const root = document.documentElement;
            if (theme === 'system') {
                root.removeAttribute('data-theme');
            } else {
                root.setAttribute('data-theme', theme);
            }
        }

        // 获取 favicon
        function getFavicon(url) {
            return getFaviconUrl(url);
        }

        // 获取标签颜色
        function getTagColor(tagName) {
            return window.getTagColor(tagName);
        }

        // 格式化日期
        function formatDate(dateString) {
            return window.formatDate ? window.formatDate(dateString) : dateString;
        }

        // 切换星标
        async function toggleStar(entry) {
            await store.toggleStar(entry);
            await loadEntries(currentPage.value);
        }

        // 查看条目
        async function viewEntry(entry) {
            selectedEntry.value = await store.getEntry(entry.id);
            revealedFields.value = [];
        }

        function closeEntryDetail() {
            selectedEntry.value = null;
        }

        // 打开创建弹窗
        function openCreateModal() {
            resetEntryForm();
            showCreateModal.value = true;
        }

        function applyEntryTemplate() {
            const template = entryTemplates.find(item => item.id === selectedTemplate.value);
            if (!template) return;
            entryForm.fields = template.fields.map(field => ({ ...field }));
            if (!entryForm.title) {
                entryForm.title = template.name;
            }
        }

        function skipOnboarding() {
            showOnboarding.value = false;
        }

        async function importSampleData() {
            importingSamples.value = true;
            try {
                const samples = [
                    {
                        title: '示例：云服务器控制台',
                        url: 'https://example.invalid/cloud',
                        starred: true,
                        tags: ['示例', '云服务'],
                        fields: [
                            { name: '账号', value: 'demo-cloud-user', copyable: true },
                            { name: '密码', value: 'Demo-Password-123!', copyable: true }
                        ],
                        remarks: '这是示例数据，可删除。用于体验字段复制、星标和标签筛选。'
                    },
                    {
                        title: '示例：测试邮箱',
                        url: 'https://example.invalid/mail',
                        starred: false,
                        tags: ['示例', '邮箱'],
                        fields: [
                            { name: '邮箱', value: 'demo@example.invalid', copyable: true },
                            { name: '恢复码', value: 'DEMO-CODE-0000', copyable: true }
                        ],
                        remarks: '这是示例数据，可删除。这里不包含任何真实账号。'
                    },
                    {
                        title: '示例：本地开发密钥',
                        url: '',
                        starred: false,
                        tags: ['示例', '开发'],
                        fields: [
                            { name: 'API Key', value: 'demo_api_key_not_real', copyable: true },
                            { name: '环境', value: 'local-demo', copyable: false }
                        ],
                        remarks: '这是示例数据，可删除。用于体验备注和自定义字段。'
                    }
                ];

                for (const sample of samples) {
                    await api.post('/entries', sample);
                }

                showOnboarding.value = false;
                await loadAllData();
                showToast('示例数据已导入', 'success');
            } catch (error) {
                showToast(error.message || '示例数据导入失败', 'error');
            } finally {
                importingSamples.value = false;
            }
        }

        // 编辑条目
        async function editEntry(entry) {
            const fullEntry = await store.getEntry(entry.id);
            if (fullEntry) {
                editingEntry.value = fullEntry;
                entryForm.id = fullEntry.id;
                entryForm.title = fullEntry.title;
                entryForm.url = fullEntry.url || '';
                entryForm.starred = fullEntry.starred;
                entryForm.tags = [...fullEntry.tags];
                entryForm.fields = fullEntry.fields.map(f => ({ ...f }));
                entryForm.remarks = fullEntry.remarks || '';
                showEditModal.value = true;
            }
        }

        // 重置表单
        function resetEntryForm() {
            entryForm.id = null;
            entryForm.title = '';
            entryForm.url = '';
            entryForm.starred = false;
            entryForm.tags = [];
            entryForm.fields = [];
            entryForm.remarks = '';
            newTag.value = '';
            selectedTemplate.value = '';
        }

        // 关闭弹窗
        function closeEntryModal() {
            showCreateModal.value = false;
            showEditModal.value = false;
            resetEntryForm();
        }

        // 添加标签
        function addTag() {
            const tag = newTag.value.trim();
            if (tag && !entryForm.tags.includes(tag)) {
                entryForm.tags.push(tag);
            }
            newTag.value = '';
        }

        // 移除标签
        function removeTag(index) {
            entryForm.tags.splice(index, 1);
        }

        // 添加字段
        function addField() {
            entryForm.fields.push({ name: '', value: '', copyable: true });
        }

        // 移除字段
        function removeField(index) {
            entryForm.fields.splice(index, 1);
        }

        // 保存条目
        async function saveEntry() {
            if (!entryForm.title) {
                showToast('请输入标题', 'error');
                return;
            }

            const data = {
                title: entryForm.title,
                url: entryForm.url || '',
                starred: entryForm.starred,
                tags: entryForm.tags,
                fields: entryForm.fields.filter(f => f.name),
                remarks: entryForm.remarks
            };

            let result;
            if (showEditModal.value && entryForm.id) {
                result = await store.updateEntry(entryForm.id, data);
            } else {
                result = await store.createEntry(data);
            }

            if (result) {
                closeEntryModal();
                await loadEntries(currentPage.value);
                await loadTags();
            }
        }

        function confirmDeleteEntry(entry) {
            showConfirmDialog('删除条目', `确认将「${entry.title}」移至回收站？`, async () => {
                const success = await store.deleteEntry(entry.id);
                if (success) {
                    selectedEntry.value = null;
                    selectedEntryIds.value = selectedEntryIds.value.filter(id => id !== entry.id);
                    await loadEntries(currentPage.value);
                    await loadTags();
                }
            });
        }

        function toggleEntrySelection(entryId) {
            if (selectedEntryIds.value.includes(entryId)) {
                selectedEntryIds.value = selectedEntryIds.value.filter(id => id !== entryId);
            } else {
                selectedEntryIds.value = [...selectedEntryIds.value, entryId];
            }
        }

        function isEntrySelected(entryId) {
            return selectedEntryIds.value.includes(entryId);
        }

        function clearSelection() {
            selectedEntryIds.value = [];
            batchTagName.value = '';
        }

        function toggleCurrentPageSelection() {
            const pageIds = entries.value.map(entry => entry.id);
            if (pageIds.length === 0) return;
            if (allCurrentPageSelected.value) {
                selectedEntryIds.value = selectedEntryIds.value.filter(id => !pageIds.includes(id));
            } else {
                selectedEntryIds.value = Array.from(new Set([...selectedEntryIds.value, ...pageIds]));
            }
        }

        function batchDeleteSelected() {
            if (selectedEntryIds.value.length === 0) return;
            showConfirmDialog('批量删除', `确认将已选 ${selectedEntryIds.value.length} 个条目移至回收站？此操作不会彻底删除，可从回收站恢复。`, async () => {
                await store.batchDelete(selectedEntryIds.value);
                clearSelection();
                await loadEntries(1);
                await loadTags();
            });
        }

        async function batchStarSelected(starred) {
            if (selectedEntryIds.value.length === 0) return;
            await store.batchStar(selectedEntryIds.value, starred);
            clearSelection();
            await loadEntries(currentPage.value);
        }

        async function batchAddTagSelected() {
            const tag = batchTagName.value.trim();
            if (selectedEntryIds.value.length === 0 || !tag) return;
            showConfirmDialog('批量加标签', `确认给已选 ${selectedEntryIds.value.length} 个条目添加标签「${tag}」？`, async () => {
                await store.batchUpdateTags(selectedEntryIds.value, [tag], []);
                batchTagName.value = '';
                await loadEntries(currentPage.value);
                await loadTags();
            });
        }

        async function batchRemoveTagSelected() {
            const tag = batchTagName.value.trim();
            if (selectedEntryIds.value.length === 0 || !tag) return;
            showConfirmDialog('批量移除标签', `确认从已选 ${selectedEntryIds.value.length} 个条目移除标签「${tag}」？`, async () => {
                await store.batchUpdateTags(selectedEntryIds.value, [], [tag]);
                batchTagName.value = '';
                await loadEntries(currentPage.value);
                await loadTags();
            });
        }

        // 打开链接
        function openUrl(url) {
            window.open(url, '_blank');
        }

        // 切换复制菜单
        function toggleCopyMenu(entryId) {
            copyMenuEntryId.value = copyMenuEntryId.value === entryId ? null : entryId;
        }

        // 复制单个字段
        async function copyField(entryId, field) {
            try {
                // 获取条目详情（包含明文）
                const entryDetail = await store.getEntry(entryId);
                if (entryDetail) {
                    const targetField = entryDetail.fields.find(f => f.name === field.name);
                    if (targetField) {
                        const copied = await copyToClipboard(targetField.value);
                        showToast(copied ? `已复制 ${field.name}` : '复制失败，请手动复制', copied ? 'success' : 'error');
                    }
                }
            } catch (error) {
                showToast('复制失败', 'error');
            }
            copyMenuEntryId.value = null;
        }

        // 复制全部字段
        async function copyAllFields(entryId) {
            try {
                const entryDetail = await store.getEntry(entryId);
                if (entryDetail) {
                    const text = entryDetail.fields
                        .filter(f => f.copyable)
                        .map(f => `${f.name}: ${f.value}`)
                        .join('\n');
                    const copied = await copyToClipboard(text);
                    showToast(copied ? '已复制全部字段' : '复制失败，请手动复制', copied ? 'success' : 'error');
                }
            } catch (error) {
                showToast('复制失败', 'error');
            }
            copyMenuEntryId.value = null;
        }

        // 点击其他区域关闭复制菜单
        document.addEventListener('click', () => {
            copyMenuEntryId.value = null;
        });

        document.addEventListener('click', (event) => {
            if (!event.target.closest?.('.tag-filter')) {
                showTagDropdown.value = false;
            }
        });

        // 跳转页面
        async function goToPage(page) {
            if (page < 1 || page > totalPages.value) return;
            await loadEntries(page);
        }

        async function applySort() {
            if (!['updated_at', 'created_at', 'title'].includes(sortBy.value)) {
                sortBy.value = 'updated_at';
            }
            if (!['asc', 'desc'].includes(sortOrder.value)) {
                sortOrder.value = 'desc';
            }
            store.setFilter('entryIds', []);
            listContextNotice.value = '';
            store.setFilter('sortBy', sortBy.value);
            store.setFilter('sortOrder', sortOrder.value);
            await loadEntries(1);
        }

        async function applyAdvancedFilters() {
            commitAdvancedTags();
            store.setFilter('entryIds', []);
            if (!listContextNotice.value.startsWith('维护工具')) {
                listContextNotice.value = '';
            }
            store.setFilter('tags', advancedTagList.value);
            store.setFilter('untagged', advancedFilters.untagged);
            store.setFilter('createdFrom', advancedFilters.createdFrom);
            store.setFilter('createdTo', advancedFilters.createdTo);
            advancedFilters.updatedFrom = '';
            advancedFilters.updatedTo = '';
            store.setFilter('updatedFrom', '');
            store.setFilter('updatedTo', '');
            store.setFilter('hasUrl', advancedFilters.hasUrl);
            store.setFilter('hasRemarks', advancedFilters.hasRemarks);
            await loadEntries(1);
        }

        function resetAdvancedFilterForm() {
            advancedTagDraft.value = '';
            advancedTagList.value = [];
            advancedFilters.untagged = false;
            advancedFilters.createdFrom = '';
            advancedFilters.createdTo = '';
            advancedFilters.updatedFrom = '';
            advancedFilters.updatedTo = '';
            advancedFilters.hasUrl = '';
            advancedFilters.hasRemarks = '';
        }

        async function clearAdvancedFilters() {
            resetAdvancedFilterForm();
            store.setFilter('tags', []);
            store.setFilter('entryIds', []);
            listContextNotice.value = '';
            store.setFilter('untagged', false);
            store.setFilter('createdFrom', '');
            store.setFilter('createdTo', '');
            store.setFilter('updatedFrom', '');
            store.setFilter('updatedTo', '');
            store.setFilter('hasUrl', '');
            store.setFilter('hasRemarks', '');
            await loadEntries(1);
        }

        async function clearListState() {
            listContextNotice.value = '';
            activeTagName.value = '';
            searchQuery.value = '';
            resetSearchScopes();
            filter.value = 'all';
            resetAdvancedFilterForm();
            store.clearFilters();
            sortBy.value = store.state.filters.sortBy;
            sortOrder.value = store.state.filters.sortOrder;
            clearSelection();
            await loadEntries(1);
        }

        async function removeAdvancedFilterChip(chip) {
            if (chip.type === 'tag') {
                advancedTagList.value = advancedTagList.value.filter(tag => tag !== chip.value);
            } else if (chip.type === 'untagged') {
                advancedFilters.untagged = false;
            } else if (chip.type === 'createdFrom') {
                advancedFilters.createdFrom = '';
            } else if (chip.type === 'createdTo') {
                advancedFilters.createdTo = '';
            } else if (chip.type === 'hasUrl') {
                advancedFilters.hasUrl = '';
            } else if (chip.type === 'hasRemarks') {
                advancedFilters.hasRemarks = '';
            }
            await applyAdvancedFilters();
        }

        function loadSavedAdvancedFilters() {
            try {
                const raw = localStorage.getItem('secretbase.savedAdvancedFilters');
                const parsed = raw ? JSON.parse(raw) : [];
                savedAdvancedFilters.value = Array.isArray(parsed) ? parsed : [];
            } catch (error) {
                savedAdvancedFilters.value = [];
            }
        }

        function persistSavedAdvancedFilters() {
            localStorage.setItem('secretbase.savedAdvancedFilters', JSON.stringify(savedAdvancedFilters.value));
        }

        function getAdvancedFilterSnapshot(name) {
            return {
                id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
                name,
                tags: [...advancedTagList.value],
                untagged: advancedFilters.untagged,
                createdFrom: advancedFilters.createdFrom,
                createdTo: advancedFilters.createdTo,
                hasUrl: advancedFilters.hasUrl,
                hasRemarks: advancedFilters.hasRemarks
            };
        }

        function saveCurrentAdvancedFilter() {
            if (activeAdvancedFilterChips.value.length === 0) {
                showToast('请先设置筛选条件', 'warning');
                return;
            }
            const defaultName = activeAdvancedFilterChips.value.map(chip => chip.label).join(' + ').slice(0, 40);
            const name = window.prompt('保存筛选名称', defaultName);
            if (!name || !name.trim()) return;
            savedAdvancedFilters.value = [
                getAdvancedFilterSnapshot(name.trim()),
                ...savedAdvancedFilters.value.filter(item => item.name !== name.trim())
            ].slice(0, 12);
            persistSavedAdvancedFilters();
            showToast('已保存筛选', 'success');
        }

        async function applySavedAdvancedFilter(savedFilter) {
            advancedTagDraft.value = '';
            advancedTagList.value = Array.isArray(savedFilter.tags) ? [...savedFilter.tags] : [];
            advancedFilters.untagged = Boolean(savedFilter.untagged);
            advancedFilters.createdFrom = savedFilter.createdFrom || '';
            advancedFilters.createdTo = savedFilter.createdTo || '';
            advancedFilters.updatedFrom = '';
            advancedFilters.updatedTo = '';
            advancedFilters.hasUrl = savedFilter.hasUrl || '';
            advancedFilters.hasRemarks = savedFilter.hasRemarks || '';
            await applyAdvancedFilters();
        }

        function deleteSavedAdvancedFilter(savedFilter) {
            savedAdvancedFilters.value = savedAdvancedFilters.value.filter(item => item.id !== savedFilter.id);
            persistSavedAdvancedFilters();
        }

        function addAdvancedTags(input) {
            const tagsToAdd = String(input || '')
                .split(/[,，]/)
                .map(tag => tag.trim())
                .filter(Boolean);
            if (tagsToAdd.length === 0) return;
            advancedTagList.value = Array.from(new Set([...advancedTagList.value, ...tagsToAdd]));
            advancedTagDraft.value = '';
        }

        function commitAdvancedTags() {
            addAdvancedTags(advancedTagDraft.value);
        }

        async function removeAdvancedTag(tag) {
            advancedTagList.value = advancedTagList.value.filter(item => item !== tag);
            await applyAdvancedFilters();
        }

        async function commitAndApplyAdvancedTags() {
            commitAdvancedTags();
            await applyAdvancedFilters();
        }

        async function handleAdvancedTagKey(event) {
            if (event.isComposing) return;
            if ((event.key === 'Backspace' || event.key === 'Delete') && !advancedTagDraft.value && advancedTagList.value.length > 0) {
                event.preventDefault();
                advancedTagList.value = advancedTagList.value.slice(0, -1);
                await applyAdvancedFilters();
                return;
            }
            if (event.key === ',' || event.key === '，') {
                event.preventDefault();
                await commitAndApplyAdvancedTags();
            }
        }

        async function handleAdvancedTagInput() {
            if (/[,，]/.test(advancedTagDraft.value)) {
                commitAdvancedTags();
                await applyAdvancedFilters();
            }
        }

        function isFieldRevealed(fieldName) {
            return revealedFields.value.includes(fieldName);
        }

        function toggleFieldReveal(fieldName) {
            if (isFieldRevealed(fieldName)) {
                revealedFields.value = revealedFields.value.filter(name => name !== fieldName);
            } else {
                revealedFields.value = [...revealedFields.value, fieldName];
            }
        }

        // AI 解析
        async function openAiParse() {
            showAiParse.value = true;
            aiStatus.value = null;
            aiStatusError.value = '';
            aiFailureMessage.value = '';
            try {
                const result = await api.get('/ai/status');
                aiStatus.value = result.data;
            } catch (error) {
                aiStatusError.value = error.message || '无法获取 AI 配置状态，可继续手动录入';
            }
        }

        async function manualEntryFromAi(showMessage = true) {
            resetEntryForm();
            entryForm.remarks = aiText.value;
            aiResult.value = null;
            showAiParse.value = false;
            await nextTick();
            showCreateModal.value = true;
            if (showMessage) {
                showToast('已将原文转入备注，可继续手动录入', 'warning');
            }
        }

        function clearAiParse() {
            aiText.value = '';
            aiResult.value = null;
            aiFailureMessage.value = '';
            lastAiParseText.value = '';
            aiCooldownUntil.value = 0;
            aiNow.value = Date.now();
        }

        async function openAiSettingsFromParse() {
            showAiParse.value = false;
            await openSettings();
            selectSettingsTab('ai');
        }

        async function parseAiText() {
            const text = aiText.value.trim();
            if (!text) return;
            if (!aiStatus.value?.configured) {
                aiFailureMessage.value = 'AI 未配置，请先到设置页填写 Base URL、API Key 并选择模型后再使用智能解析。';
                showToast(aiFailureMessage.value, 'warning');
                return;
            }
            if (aiText.value.length > aiMaxInputChars) {
                aiFailureMessage.value = `内容过长，请分批解析，单次最多 ${aiMaxInputChars} 字符。原文仍保留，可转为手动录入。`;
                showToast(aiFailureMessage.value, 'warning');
                return;
            }
            if (!canParseAi.value) {
                if (aiCooldownSeconds.value > 0) {
                    showToast(`请等待 ${aiCooldownSeconds.value} 秒后再解析`, 'warning');
                } else if (text === lastAiParseText.value) {
                    showToast('内容未变化，不能重复智能解析', 'warning');
                } else if (!aiStatus.value?.configured) {
                    showToast('请先配置 AI 接入信息后再解析', 'warning');
                }
                return;
            }

            aiParsing.value = true;
            aiResult.value = null;
            aiFailureMessage.value = '';
            try {
                const result = await api.post('/ai/parse', { text });
                const parsedEntries = normalizeAiParsedEntries(result.data);
                aiResult.value = {
                    entries: parsedEntries,
                    entryCount: parsedEntries.length,
                    warnings: normalizeAiWarnings(result.data, parsedEntries)
                };
                lastAiParseText.value = text;
                aiNow.value = Date.now();
                aiCooldownUntil.value = aiNow.value + 5000;
            } catch (error) {
                if (error.status === 429) {
                    aiFailureMessage.value = error.message || '请求过于频繁，请等待冷却结束后再试。你也可以直接转为手动录入。';
                    showToast(aiFailureMessage.value, 'warning');
                } else {
                    aiFailureMessage.value = formatAiFailureMessage(error);
                    showToast(aiFailureMessage.value, 'warning');
                }
            } finally {
                aiParsing.value = false;
            }
        }

        function formatAiFailureMessage(error = {}) {
            if (error.status === 401) return '当前 vault 已锁定，请重新解锁后再使用 AI。原文仍保留，可转为手动录入。';
            if (error.status === 502) return 'AI 未配置、网络/API 不可用，或模型返回格式异常。原文仍保留，可转为手动录入。';
            if (error.status >= 500) return 'AI 服务暂时不可用。原文仍保留，可转为手动录入。';
            if (error.status === 413) return '输入内容过长，请分批解析。原文仍保留，可转为手动录入。';
            if (error.status === 422) return '输入内容无法解析为有效请求。请调整文本，或转为手动录入。';
            return `${error.message || 'AI 解析失败'}。原文仍保留，可转为手动录入。`;
        }

        // 应用 AI 结果
        async function applyAiResult() {
            const entriesToApply = (aiResult.value?.entries || [])
                .filter(entry => entry.selected)
                .map(normalizeEditableAiEntry)
                .filter(entry => entry.title);
            if (entriesToApply.length === 0) return;

            if (entriesToApply.length === 1) {
                const entry = entriesToApply[0];
                resetEntryForm();
                entryForm.title = entry.title;
                entryForm.url = entry.url || '';
                entryForm.fields = entry.fields || [];
                entryForm.tags = entry.tags || [];
                entryForm.remarks = buildAiRemarks(entry.remarks);
                showAiParse.value = false;
                showCreateModal.value = true;
                aiResult.value = null;
                aiText.value = '';
                return;
            }

            try {
                for (const entry of entriesToApply) {
                    await api.post('/entries', {
                        title: entry.title,
                        url: entry.url || '',
                        starred: false,
                        tags: entry.tags || [],
                        fields: entry.fields || [],
                        remarks: buildAiRemarks(entry.remarks)
                    });
                }
                showToast(`已创建 ${entriesToApply.length} 条 AI 解析条目`, 'success');
                showAiParse.value = false;
                aiResult.value = null;
                aiText.value = '';
                await loadEntries(1);
                await loadTags();
            } catch (error) {
                showToast(error.message || 'AI 多条目创建失败，请检查解析结果', 'error');
            }
        }

        function normalizeEditableAiEntry(entry = {}) {
            const tags = String(entry.tagsText || '')
                .split(/[,，]/)
                .map(tag => tag.trim())
                .filter(Boolean);
            const fields = Array.isArray(entry.fields)
                ? entry.fields
                    .map(field => ({
                        name: String(field.name || '').trim(),
                        value: String(field.value || ''),
                        copyable: Boolean(field.copyable)
                    }))
                    .filter(field => field.name)
                : [];
            return {
                title: String(entry.title || '').trim(),
                url: String(entry.url || '').trim(),
                fields,
                tags: Array.from(new Set(tags)),
                remarks: String(entry.remarks || '').trim()
            };
        }

        function toggleAiEntrySelection(entry) {
            entry.selected = !entry.selected;
        }

        function addAiEntryField(entry) {
            if (!Array.isArray(entry.fields)) entry.fields = [];
            entry.fields.push({ name: '', value: '', copyable: true });
        }

        function removeAiEntryField(entry, index) {
            if (!Array.isArray(entry.fields)) return;
            entry.fields.splice(index, 1);
        }

        function normalizeAiParsedEntries(data = {}) {
            const rawEntries = Array.isArray(data.parsed_entries)
                ? data.parsed_entries
                : data.parsed
                    ? [data.parsed]
                    : [];
            return rawEntries.map((entry, index) => ({
                aiKey: `${Date.now()}-${index}-${Math.random().toString(16).slice(2)}`,
                selected: true,
                title: String(entry?.title || `AI 解析条目 ${index + 1}`).trim(),
                url: String(entry?.url || '').trim(),
                fields: Array.isArray(entry?.fields) ? entry.fields : [],
                tags: Array.isArray(entry?.tags) ? entry.tags : [],
                tagsText: Array.isArray(entry?.tags) ? entry.tags.join(', ') : '',
                remarks: String(entry?.remarks || '').trim()
            }));
        }

        function normalizeAiWarnings(data = {}, entries = []) {
            const warnings = Array.isArray(data.warnings) ? data.warnings.map(item => String(item || '').trim()).filter(Boolean) : [];
            if (entries.length > 8) warnings.push('解析结果条目较多，建议逐条确认标题、字段和标签后再创建。');
            if (entries.some(entry => !entry.fields || entry.fields.length === 0)) warnings.push('部分条目没有字段，可能需要手动补充账号、密码或备注。');
            return Array.from(new Set(warnings));
        }

        function buildAiRemarks(entryRemarks = '') {
            const parts = [];
            if (entryRemarks) parts.push(entryRemarks);
            if (aiText.value) parts.push(`AI 原文：\n${aiText.value}`);
            return parts.join('\n\n');
        }

        // 保存设置
        async function saveSettings() {
            settingsForm.autoBackupRetention = Math.min(200, Math.max(5, Number(settingsForm.autoBackupRetention || 30)));
            const previousPageSize = settingsForm.pageSize;
            await store.updateSettings({
                theme: settingsForm.theme,
                pageSize: settingsForm.pageSize,
                autoLockMinutes: settingsForm.autoLockMinutes,
                autoBackupRetention: settingsForm.autoBackupRetention
            });
            currentTheme.value = settingsForm.theme;
            applyTheme(settingsForm.theme);
            startAutoLockTimer();
            if (previousPageSize !== store.state.settings.pageSize || !locked.value) {
                await loadEntries(1);
            }
        }

        async function fetchAiModels() {
            aiSettingsError.value = '';
            aiSettingsMessage.value = '';
            const baseUrl = aiSettingsForm.baseUrl.trim();
            const apiKey = aiSettingsForm.apiKey.trim();
            if (!baseUrl || !apiKey) {
                if (!(aiSettingsStatus.value?.configured && baseUrl === aiSettingsStatus.value.base_url)) {
                    aiSettingsError.value = '请先填写 Base URL 和 API Key';
                    return;
                }
            }
            if (!baseUrl) {
                aiSettingsError.value = '请先填写 Base URL';
                return;
            }

            aiModelsLoading.value = true;
            try {
                const result = await api.post('/ai/models', { baseUrl, apiKey });
                aiModels.value = result.data?.models || [];
                if (!aiModels.value.includes(aiSettingsForm.model)) {
                    aiSettingsForm.model = aiModels.value[0] || '';
                }
                aiSettingsMessage.value = aiModels.value.length > 0
                    ? `已获取 ${aiModels.value.length} 个模型`
                    : '服务商未返回可用模型';
            } catch (error) {
                aiModels.value = [];
                aiSettingsForm.model = '';
                aiSettingsError.value = error.message || '获取模型列表失败';
            } finally {
                aiModelsLoading.value = false;
            }
        }

        async function saveAiConfiguration() {
            aiSettingsError.value = '';
            aiSettingsMessage.value = '';
            const baseUrl = aiSettingsForm.baseUrl.trim();
            const apiKey = aiSettingsForm.apiKey.trim();
            const model = aiSettingsForm.model;
            if (!baseUrl || !model) {
                aiSettingsError.value = '请填写 Base URL，并从模型列表中选择模型';
                return;
            }
            if (!apiKey && !(aiSettingsStatus.value?.configured && baseUrl === aiSettingsStatus.value.base_url)) {
                aiSettingsError.value = '请填写 API Key';
                return;
            }

            aiSettingsSaving.value = true;
            try {
                const result = await api.put('/ai/settings', { baseUrl, apiKey, model });
                aiSettingsStatus.value = result.data;
                aiSettingsForm.apiKey = '';
                aiModels.value = result.data?.model ? [result.data.model] : [];
                aiSettingsEditing.value = false;
                aiSettingsMessage.value = 'AI 连通测试通过，设置已保存';
                showToast('AI 设置已保存', 'success');
            } catch (error) {
                aiSettingsError.value = error.message || 'AI 连通测试失败，设置未保存';
            } finally {
                aiSettingsSaving.value = false;
            }
        }

        async function clearAiConfiguration() {
            aiSettingsError.value = '';
            aiSettingsMessage.value = '';
            try {
                const result = await api.delete('/ai/settings');
                aiSettingsStatus.value = result.data;
                aiSettingsForm.baseUrl = '';
                aiSettingsForm.apiKey = '';
                aiSettingsForm.model = '';
                aiModels.value = [];
                aiSettingsEditing.value = true;
                aiSettingsMessage.value = 'AI 设置已清除';
                showToast('AI 设置已清除', 'success');
            } catch (error) {
                aiSettingsError.value = error.message || '清除 AI 设置失败';
            }
        }

        function editAiConfiguration() {
            aiSettingsEditing.value = true;
            aiSettingsError.value = '';
            aiSettingsMessage.value = '';
            aiSettingsForm.baseUrl = aiSettingsStatus.value?.base_url || '';
            aiSettingsForm.model = aiSettingsStatus.value?.model || '';
            aiSettingsForm.apiKey = '';
            aiModels.value = aiSettingsStatus.value?.model ? [aiSettingsStatus.value.model] : [];
        }

        function cancelAiConfigurationEdit() {
            aiSettingsEditing.value = false;
            aiSettingsError.value = '';
            aiSettingsMessage.value = '';
            aiSettingsForm.baseUrl = aiSettingsStatus.value?.base_url || '';
            aiSettingsForm.model = aiSettingsStatus.value?.model || '';
            aiSettingsForm.apiKey = '';
            aiModels.value = aiSettingsStatus.value?.model ? [aiSettingsStatus.value.model] : [];
        }

        function startAutoLockTimer() {
            clearAutoLockTimer();
            const minutes = Number(settingsForm.autoLockMinutes || 0);
            if (locked.value || minutes <= 0) return;

            autoLockTimer = setTimeout(async () => {
                showToast('已因长时间无操作自动锁定', 'warning');
                try {
                    await store.lock();
                } catch (error) {
                    // 即使网络请求失败，也必须立即清除前端解锁态。
                } finally {
                    applyLockedState();
                }
            }, minutes * 60 * 1000);
        }

        function clearAutoLockTimer() {
            if (autoLockTimer) {
                clearTimeout(autoLockTimer);
                autoLockTimer = null;
            }
        }

        function resetAutoLockTimer() {
            if (!locked.value) {
                startAutoLockTimer();
            }
        }

        function bindActivityListeners() {
            ['click', 'keydown', 'mousemove', 'touchstart'].forEach(eventName => {
                window.addEventListener(eventName, resetAutoLockTimer, { passive: true });
            });
        }

        function handleUnauthorizedLock(event) {
            if (locked.value) return;
            showToast(event.detail?.message || '已锁定，请重新解锁', 'warning');
            applyLockedState();
        }

        // 修改密码
        async function changePassword() {
            passwordForm.error = '';

            if (!passwordForm.oldPassword) {
                passwordForm.error = '请输入旧密码';
                return;
            }
            if (passwordForm.newPassword.length < 8) {
                passwordForm.error = '新密码至少 8 位';
                return;
            }
            if (passwordForm.newPassword !== passwordForm.confirmPassword) {
                passwordForm.error = '两次输入的密码不一致';
                return;
            }

            try {
                await api.post('/auth/change-password', {
                    old_password: passwordForm.oldPassword,
                    new_password: passwordForm.newPassword
                });
                showToast('主密码已更新', 'success');
                showChangePassword.value = false;
                passwordForm.oldPassword = '';
                passwordForm.newPassword = '';
                passwordForm.confirmPassword = '';
            } catch (error) {
                passwordForm.error = error.message || '修改失败';
            }
        }

        // 加载回收站
        async function loadTrash(page = 1) {
            try {
                const result = await api.get(`/trash?page=${page}&page_size=${settingsForm.pageSize}`);
                trashItems.value = result.data.items;
                trashPage.value = result.data.pagination.page;
                trashTotalPages.value = result.data.pagination.total_pages;
                trashTotal.value = result.data.pagination.total;
            } catch (error) {
                console.error('加载回收站失败:', error);
            }
        }

        async function goToTrashPage(page) {
            if (page < 1 || page > trashTotalPages.value) return;
            await loadTrash(page);
        }

        // 恢复回收站条目
        async function restoreTrashItem(id) {
            try {
                await api.post(`/trash/${id}/restore`);
                showToast('条目已恢复', 'success');
                await loadTrash();
                await loadEntries();
            } catch (error) {
                showToast('恢复失败', 'error');
            }
        }

        // 彻底删除
        async function deleteTrashItem(id) {
            showConfirmDialog('彻底删除', '此操作不可恢复，确认删除？', async () => {
                try {
                    await api.delete(`/trash/${id}`);
                    showToast('已彻底删除', 'success');
                    await loadTrash();
                } catch (error) {
                    showToast('删除失败', 'error');
                }
            });
        }

        // 清空回收站
        function emptyTrashConfirm() {
            showConfirmDialog('清空回收站', '此操作不可恢复，确认清空？', async () => {
                try {
                    await api.post('/trash/empty');
                    showToast('回收站已清空', 'success');
                    await loadTrash();
                } catch (error) {
                    showToast('清空失败', 'error');
                }
            });
        }

        // 重命名标签
        function renameTag(tag) {
            const newName = prompt('请输入新标签名:', tag.name);
            if (newName && newName !== tag.name) {
                api.put(`/tags/${encodeURIComponent(tag.name)}`, { new_name: newName }).then(async () => {
                    showToast('标签已重命名', 'success');
                    await loadTags();
                    await loadEntries();
                }).catch(error => {
                    showToast('重命名失败: ' + (error.message || ''), 'error');
                });
            }
        }

        // 删除标签
        function deleteTag(tag) {
            showConfirmDialog('删除标签', `确认删除标签 "${tag.name}"？`, async () => {
                try {
                    await api.delete(`/tags/${encodeURIComponent(tag.name)}`);
                    showToast('标签已删除', 'success');
                    await loadTags();
                    await loadEntries();
                } catch (error) {
                    showToast('删除失败', 'error');
                }
            });
        }

        function parseTagMergeSourceText(text) {
            return text
                .split(/[，,]/)
                .map(tag => tag.trim())
                .filter(Boolean);
        }

        function commitTagMergeSourceTags() {
            const nextTags = parseTagMergeSourceText(tagMergeForm.sourceTags);
            if (nextTags.length === 0) return;
            const existing = new Set(tagMergeSourceList.value);
            nextTags.forEach(tag => {
                if (!existing.has(tag)) {
                    tagMergeSourceList.value.push(tag);
                    existing.add(tag);
                }
            });
            tagMergeForm.sourceTags = '';
        }

        function removeTagMergeSourceTag(tagName) {
            tagMergeSourceList.value = tagMergeSourceList.value.filter(tag => tag !== tagName);
        }

        function handleTagMergeSourceKey(event) {
            if (event.key === ',' || event.key === '，') {
                event.preventDefault();
                commitTagMergeSourceTags();
            }
        }

        function handleTagMergeSourceInput() {
            if (/[，,]/.test(tagMergeForm.sourceTags)) {
                commitTagMergeSourceTags();
            }
        }

        async function mergeTags() {
            commitTagMergeSourceTags();
            const sourceTags = [...tagMergeSourceList.value];
            const targetTag = tagMergeForm.targetTag.trim();

            if (sourceTags.length === 0 || !targetTag) {
                showToast('请输入源标签和目标标签', 'error');
                return;
            }

            try {
                const result = await api.post('/tags/merge', {
                    source_tags: sourceTags,
                    target_tag: targetTag
                });
                tagMergeForm.sourceTags = '';
                tagMergeForm.targetTag = '';
                tagMergeSourceList.value = [];
                showToast(result.message || '标签已合并', 'success');
                await loadTags();
                await loadEntries(currentPage.value);
            } catch (error) {
                showToast(error.message || '标签合并失败', 'error');
            }
        }

        function formatBytes(size) {
            if (size < 1024) return `${size} B`;
            if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
            return `${(size / 1024 / 1024).toFixed(1)} MB`;
        }

        function backupTypeLabel(type) {
            if (type === 'manual') return '手动备份';
            if (type === 'auto') return '自动备份';
            return '旧版备份';
        }

        function friendlyApiMessage(error, fallback) {
            if (!error) return fallback;
            if (error.status === 401) return '当前会话已失效，请重新解锁后再操作。';
            if (error.status === 409) return '数据文件已被其他进程修改，请重新解锁或刷新后再操作。';
            if (error.status === 413) return '请求或文件过大，请减小内容后重试。';
            if (error.status === 422) return error.message || '请求内容无效，请检查输入后重试。';
            if (error.status === 423 || error.code === 'VAULT_LOCKED') return '数据文件正在被其他进程使用。请确认没有旧的 SecretBase 进程仍在运行后重试。';
            if (error.status >= 500) return '服务器内部错误，请稍后重试或检查后端日志。';
            return error.message || fallback;
        }

        async function loadBackups() {
            if (backupListLoading.value) return;
            backupListLoading.value = true;
            try {
                const result = await api.get('/backups');
                backups.value = result.data.items || [];
            } catch (error) {
                showToast(error.message || '备份列表加载失败', 'error');
            } finally {
                backupListLoading.value = false;
            }
        }

        function openBackupCenter() {
            showBackupCenter.value = true;
        }

        function setBackupPage(type, page) {
            backupPages[type] = Math.max(1, page);
        }

        async function createManualBackup() {
            if (creatingBackup.value) return;
            creatingBackup.value = true;
            try {
                const result = await api.post('/backups', {});
                highlightedBackupFilename.value = result.data?.filename || '';
                showToast(result.message || '已创建手动备份', 'success');
                await loadBackups();
            } catch (error) {
                showToast(friendlyApiMessage(error, '创建备份失败'), 'error');
            } finally {
                creatingBackup.value = false;
            }
        }

        function backupDisplayName(backup) {
            return backup.display_name || backup.filename;
        }

        async function downloadBackupFile(backup, kind) {
            if (downloadingBackupFilename.value) return;
            if (kind === 'encrypted') {
                downloadingBackupFilename.value = backup.filename;
                try {
                    await downloadBackup(
                        `/backups/${encodeURIComponent(backup.filename)}/download/encrypted`,
                        null,
                        backup.download_name_encrypted || backup.filename,
                        'GET'
                    );
                } catch (error) {
                    showToast(friendlyApiMessage(error, '备份下载失败'), 'error');
                } finally {
                    downloadingBackupFilename.value = '';
                }
                return;
            }

            showConfirmDialog('下载明文 JSON', `明文 JSON 会包含这个备份里的所有密码和密钥。\n\n备份：${backupDisplayName(backup)}\n\n确认下载？`, async () => {
                downloadingBackupFilename.value = backup.filename;
                try {
                    try {
                        await downloadBackup(
                            `/backups/${encodeURIComponent(backup.filename)}/download/plain`,
                            { confirm: true },
                            backup.download_name_plain || backup.filename.replace(/\.bak$/, '.json'),
                            'POST',
                            true
                        );
                    } catch (error) {
                        if (error.data?.needs_password) {
                            const password = window.prompt('该备份需要对应的主密码才能下载明文 JSON。') || '';
                            if (!password) return;
                            try {
                                await downloadBackup(
                                    `/backups/${encodeURIComponent(backup.filename)}/download/plain`,
                                    { confirm: true, password },
                                    backup.download_name_plain || backup.filename.replace(/\.bak$/, '.json'),
                                    'POST',
                                    true
                                );
                            } catch (passwordError) {
                                showToast(friendlyApiMessage(passwordError, '明文 JSON 下载失败'), 'error');
                            }
                        } else {
                            showToast(friendlyApiMessage(error, '明文 JSON 下载失败'), 'error');
                        }
                    }
                } finally {
                    downloadingBackupFilename.value = '';
                }
            });
        }

        function openRestoreWizard(backup) {
            restoreWizard.visible = true;
            restoreWizard.step = 1;
            restoreWizard.backup = backup;
            restoreWizard.summary = null;
            restoreWizard.password = '';
            restoreWizard.needsPassword = false;
            restoreWizard.confirmation = '';
            restoreWizard.loadingSummary = false;
            restoreWizard.restoring = false;
            restoreWizard.error = '';
            loadRestoreSummary();
        }

        function closeRestoreWizard() {
            if (restoreWizard.restoring) return;
            restoreWizard.visible = false;
            restoreWizard.backup = null;
        }

        async function loadRestoreSummary() {
            if (!restoreWizard.backup || restoreWizard.loadingSummary) return;
            restoreWizard.loadingSummary = true;
            restoreWizard.error = '';
            try {
                const path = `/backups/${encodeURIComponent(restoreWizard.backup.filename)}/summary`;
                const result = restoreWizard.password
                    ? await api.post(path, { password: restoreWizard.password })
                    : await api.get(path);
                restoreWizard.summary = result.data;
                restoreWizard.needsPassword = false;
                restoreWizard.error = '';
            } catch (error) {
                if (error.data?.needs_password) {
                    restoreWizard.needsPassword = true;
                    restoreWizard.error = '该备份需要输入对应的主密码后才能读取概况。';
                } else {
                    restoreWizard.error = friendlyApiMessage(error, '备份概况读取失败');
                }
            } finally {
                restoreWizard.loadingSummary = false;
            }
        }

        function restoreWizardNext() {
            if (restoreWizard.step === 1 && !restoreWizard.summary) {
                showToast('请先读取备份概况', 'warning');
                return;
            }
            restoreWizard.step = Math.min(3, restoreWizard.step + 1);
        }

        function restoreWizardBack() {
            restoreWizard.step = Math.max(1, restoreWizard.step - 1);
        }

        async function restoreBackup(backup) {
            openRestoreWizard(backup);
        }

        async function confirmRestoreBackup() {
            if (!restoreWizard.backup || restoreWizard.confirmation !== 'RESTORE') {
                showToast('请输入 RESTORE 后再恢复', 'warning');
                return;
            }
            restoreWizard.restoring = true;
            restoringBackupFilename.value = restoreWizard.backup.filename;
            try {
                const body = restoreWizard.password ? { password: restoreWizard.password } : {};
                const result = await api.post(`/backups/${encodeURIComponent(restoreWizard.backup.filename)}/restore`, body);
                showToast(result.message || '备份已恢复', 'success');
                restoreWizard.visible = false;
                restoreWizard.backup = null;
                await loadAllData();
                await loadBackups();
            } catch (error) {
                restoreWizard.error = friendlyApiMessage(error, '备份恢复失败');
                showToast(restoreWizard.error, 'error');
            } finally {
                restoreWizard.restoring = false;
                restoringBackupFilename.value = '';
            }
        }

        function showImportResultReport(resultData = {}, fallbackConflictCount = 0) {
            importReport.value = {
                importedCount: resultData.imported_count ?? 0,
                createdCount: resultData.created_count ?? 0,
                overwrittenCount: resultData.overwritten_count ?? 0,
                skippedCount: resultData.skipped_count ?? 0,
                conflictCount: resultData.conflicts?.length ?? fallbackConflictCount,
                selectedCount: lastImportSelectedIds.value.length
            };
            showImportReport.value = true;
        }

        async function openToolsModal() {
            showTools.value = true;
            await Promise.all([loadHealthReport(), loadMaintenanceReport(), loadSecurityReport()]);
        }

        async function loadHealthReport() {
            try {
                const result = await api.get('/tools/health-report');
                healthReport.value = result.data;
            } catch (error) {
                showToast(error.message || '健康报告加载失败', 'error');
            }
        }

        async function loadMaintenanceReport() {
            try {
                const result = await api.get('/tools/maintenance-report');
                maintenanceReport.value = result.data;
            } catch (error) {
                showToast(error.message || '维护报告加载失败', 'error');
            }
        }

        async function loadSecurityReport() {
            try {
                const result = await api.get('/tools/security-report');
                securityReport.value = result.data;
            } catch (error) {
                showToast(friendlyApiMessage(error, '安全自检加载失败'), 'error');
            }
        }

        function deleteSampleEntries() {
            const ids = (maintenanceReport.value?.sample_items || []).map(item => item.id);
            if (ids.length === 0) return;
            showConfirmDialog('删除示例数据', `确认删除 ${ids.length} 条示例数据？`, async () => {
                await store.batchDelete(ids);
                await loadAllData();
                await loadMaintenanceReport();
                showToast('示例数据已移至回收站', 'success');
            });
        }

        // 导出加密备份
        async function exportEncrypted() {
            await downloadBackup('/export/encrypted', {}, `secretbase-backup-${new Date().toISOString().slice(0, 10)}.enc`);
        }

        // 导出明文
        function exportPlain() {
            showConfirmDialog('导出明文', '明文包含所有密码，是否继续？', async () => {
                await downloadBackup('/export/plain', { confirm: true }, `secretbase-backup-${new Date().toISOString().slice(0, 10)}.json`);
            });
        }

        async function downloadBackup(path, body, filename, method = 'POST', throwOnError = false) {
            try {
                const headers = {
                    'X-SecretBase-Token': api.getToken()
                };
                const options = {
                    method,
                    headers,
                    credentials: 'same-origin'
                };
                if (method !== 'GET') {
                    headers['Content-Type'] = 'application/json';
                    options.body = JSON.stringify(body || {});
                }
                const response = await fetch(`${api.baseUrl}${path}`, {
                    ...options
                });

                if (!response.ok) {
                    const error = await response.json().catch(() => ({}));
                    throw new ApiError(error.error, error.message || '导出失败', response.status, error.data || error.details);
                }

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                a.click();
                URL.revokeObjectURL(url);
                showToast('备份已下载', 'success');
            } catch (error) {
                if (!throwOnError) showToast(error.message || '导出失败', 'error');
                if (throwOnError) throw error;
            }
        }

        async function importEncryptedFile(event) {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (!file) return;

            showConfirmDialog('导入加密备份', '导入会替换当前数据文件，系统会先自动备份当前数据。确认继续？', async () => {
                try {
                    let result;
                    try {
                        result = await api.upload('/import/encrypted', file);
                    } catch (error) {
                        if (error.data?.needs_password) {
                            const password = window.prompt('该加密备份可能是旧备份或主密码不匹配。请输入该备份对应的主密码。') || '';
                            if (!password) throw error;
                            result = await api.upload('/import/encrypted', file, { password });
                        } else {
                            throw error;
                        }
                    }
                    if (!result.success) throw new Error(result.message || '导入失败');
                    showToast(result.message || '导入成功', 'success');
                    await loadAllData();
                } catch (error) {
                    showToast(friendlyApiMessage(error, '导入失败'), 'error');
                }
            });
        }

        async function importPlainFile(event) {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (!file) return;
            lastImportPlainFile.value = file;

            try {
                const preview = await api.upload('/import/plain/preview', file);
                importPreview.value = preview.data;
                importPreviewSelectedIds.value = (preview.data.entries || []).map(entry => entry.id);
                importConflictResolutions.value = Object.fromEntries(
                    (preview.data.entries || [])
                        .filter(entry => entry.is_conflict)
                        .map(entry => [entry.id, importConflictStrategy.value === 'ask' ? 'skip' : importConflictStrategy.value])
                );
                showImportPreview.value = true;
            } catch (error) {
                showToast(error.message || '导入失败', 'error');
            }
        }

        async function confirmImportPlain() {
            if (!lastImportPlainFile.value) return;
            if (importPreview.value?.entries?.length && importPreviewSelectedIds.value.length === 0) {
                showToast('请至少选择一个要导入的条目', 'warning');
                return;
            }
            const selectedIds = [...importPreviewSelectedIds.value];
            lastImportSelectedIds.value = selectedIds;
            const conflictResolutions = Object.fromEntries(
                Object.entries(importConflictResolutions.value)
                    .filter(([id]) => selectedIds.includes(id))
            );
            const selectedConflictCount = (importPreview.value?.entries || [])
                .filter(entry => entry.is_conflict && selectedIds.includes(entry.id))
                .length;
            lastImportConflictResolutions.value = conflictResolutions;
            closeImportPreview();
            try {
                const result = await api.upload('/import/plain', lastImportPlainFile.value, {
                    conflict_strategy: importConflictStrategy.value,
                    selected_entry_ids: JSON.stringify(selectedIds),
                    conflict_resolutions: JSON.stringify(conflictResolutions)
                });
                if (!result.success) throw new Error(result.message || '导入失败');
                importConflictMessage.value = '';
                showToast(result.message || '导入成功', 'success');
                showImportResultReport(result.data, selectedConflictCount);
                await loadAllData();
            } catch (error) {
                const conflicts = error.data?.conflicts || [];
                if (conflicts.length > 0) {
                    importConflictMessage.value = `发现 ${conflicts.length} 个冲突：${conflicts.slice(0, 3).map(c => c.import_title).join('、')}`;
                    importConflicts.value = conflicts;
                    showImportConflicts.value = true;
                }
                showToast(error.message || '导入失败', 'error');
            }
        }

        async function retryImportPlain(strategy) {
            if (!lastImportPlainFile.value) {
                showToast('请重新选择导入文件', 'error');
                closeImportConflicts();
                return;
            }

            try {
                const unresolvedConflictCount = importConflicts.value.length;
                const result = await api.upload('/import/plain', lastImportPlainFile.value, {
                    conflict_strategy: strategy,
                    selected_entry_ids: JSON.stringify(lastImportSelectedIds.value),
                    conflict_resolutions: JSON.stringify(lastImportConflictResolutions.value)
                });
                if (!result.success) throw new Error(result.message || '导入失败');
                importConflictStrategy.value = strategy;
                importConflictMessage.value = '';
                closeImportConflicts();
                showToast(result.message || '导入成功', 'success');
                showImportResultReport(result.data, unresolvedConflictCount);
                await loadAllData();
            } catch (error) {
                showToast(error.message || '导入失败', 'error');
            }
        }

        function closeImportConflicts() {
            showImportConflicts.value = false;
            importConflicts.value = [];
        }

        function closeImportPreview() {
            showImportPreview.value = false;
            importPreview.value = null;
            importPreviewSelectedIds.value = [];
            importConflictResolutions.value = {};
        }

        function isImportPreviewSelected(id) {
            return importPreviewSelectedIds.value.includes(id);
        }

        function toggleImportPreviewSelection(id) {
            if (isImportPreviewSelected(id)) {
                importPreviewSelectedIds.value = importPreviewSelectedIds.value.filter(item => item !== id);
            } else {
                importPreviewSelectedIds.value = [...importPreviewSelectedIds.value, id];
            }
        }

        function selectAllImportPreviewEntries() {
            importPreviewSelectedIds.value = (importPreview.value?.entries || []).map(entry => entry.id);
        }

        function clearImportPreviewSelection() {
            importPreviewSelectedIds.value = [];
        }

        function setImportConflictResolution(id, strategy) {
            importConflictResolutions.value = {
                ...importConflictResolutions.value,
                [id]: strategy
            };
        }

        // 显示确认弹窗
        function showConfirmDialog(title, message, callback) {
            confirmTitle.value = title;
            confirmMessage.value = message;
            confirmCallback = callback;
            showConfirm.value = true;
        }

        // 确认操作
        async function confirmAction() {
            if (confirmCallback) {
                await confirmCallback();
            }
            showConfirm.value = false;
            confirmCallback = null;
        }

        // 监听回收站弹窗
        watch(showTrash, (val) => {
            if (val) loadTrash();
        });

        watch(showBackupCenter, (val) => {
            if (val) loadBackups();
        });

        return {
            // 状态
            loading,
            initialized,
            locked,
            password,
            confirmPassword,
            passwordError,
            unlockError,
            submitting,
            entries,
            tags,
            currentPage,
            totalPages,
            totalEntries,
            searchQuery,
            searchScopeOptions,
            selectedSearchScopes,
            advancedTagDraft,
            advancedTagList,
            sortBy,
            sortOrder,
            filter,
            activeTagName,
            listContextNotice,
            showTagDropdown,
            showTagBrowser,
            tagBrowserQuery,
            tagBrowserSort,
            tagBrowserSortOptions,
            showCreateModal,
            showEditModal,
            showAiParse,
            showSettings,
            showChangePassword,
            showTrash,
            showTagManager,
            showConfirm,
            showTools,
            showBackupCenter,
            showAdvancedFilters,
            selectedEntry,
            editingEntry,
            copyMenuEntryId,
            selectedEntryIds,
            batchTagName,
            importConflictMessage,
            showOnboarding,
            importingSamples,
            showImportConflicts,
            importConflicts,
            showImportReport,
            importReport,
            showImportPreview,
            importPreview,
            importPreviewSelectedIds,
            importConflictResolutions,
            backups,
            highlightedBackupFilename,
            backupListLoading,
            creatingBackup,
            restoringBackupFilename,
            downloadingBackupFilename,
            backupPages,
            restoreWizard,
            healthReport,
            maintenanceReport,
            securityReport,
            savedAdvancedFilters,
            entryForm,
            newTag,
            tagInput,
            selectedTemplate,
            entryTemplates,
            aiText,
            aiResult,
            aiParsing,
            aiStatus,
            aiStatusError,
            aiFailureMessage,
            aiSoftInputChars,
            aiMaxInputChars,
            aiTextLength,
            aiInputWarning,
            aiCooldownSeconds,
            canParseAi,
            selectedAiEntryCount,
            lastAiParseText,
            settingsForm,
            activeSettingsTab,
            settingsTabs,
            aiSettingsForm,
            aiSettingsStatus,
            aiSettingsEditing,
            aiConfiguredBaseUrl,
            aiModels,
            aiModelsLoading,
            aiSettingsSaving,
            aiSettingsError,
            aiSettingsMessage,
            importConflictStrategy,
            advancedFilters,
            defaultTimeRange,
            tagMergeForm,
            tagMergeSourceList,
            passwordForm,
            trashItems,
            trashPage,
            trashTotalPages,
            trashTotal,
            confirmTitle,
            confirmMessage,
            currentTheme,
            themeIcon,
            visiblePages,
            selectedImportPreviewCount,
            selectedImportConflictCount,
            visibleSidebarTags,
            hiddenSidebarTagCount,
            filteredTagBrowserTags,
            activeAdvancedFilterChips,
            activeListStateItems,
            hasActiveListState,
            allCurrentPageSelected,
            backupBusy,
            backupSummary,
            backupGroups,

            // 方法
            initPassword,
            unlock,
            lock,
            loadEntries,
            debounceSearch,
            toggleSearchScope,
            filterByTag,
            openTagBrowser,
            closeTagBrowser,
            showAllEntries,
            showStarredEntries,
            toggleTheme,
            openSettings,
            selectSettingsTab,
            getFavicon,
            getTagColor,
            formatDate,
            toggleStar,
            viewEntry,
            closeEntryDetail,
            openCreateModal,
            editEntry,
            closeEntryModal,
            skipOnboarding,
            importSampleData,
            applyEntryTemplate,
            addTag,
            removeTag,
            addField,
            removeField,
            saveEntry,
            confirmDeleteEntry,
            toggleEntrySelection,
            isEntrySelected,
            clearSelection,
            toggleCurrentPageSelection,
            batchDeleteSelected,
            batchStarSelected,
            batchAddTagSelected,
            batchRemoveTagSelected,
            openUrl,
            toggleCopyMenu,
            copyField,
            copyAllFields,
            goToPage,
            applySort,
            clearListState,
            applyAdvancedFilters,
            clearAdvancedFilters,
            commitAdvancedTags,
            commitAndApplyAdvancedTags,
            removeAdvancedTag,
            removeAdvancedFilterChip,
            saveCurrentAdvancedFilter,
            applySavedAdvancedFilter,
            deleteSavedAdvancedFilter,
            handleAdvancedTagKey,
            handleAdvancedTagInput,
            isFieldRevealed,
            toggleFieldReveal,
            openAiParse,
            manualEntryFromAi,
            clearAiParse,
            openAiSettingsFromParse,
            parseAiText,
            applyAiResult,
            toggleAiEntrySelection,
            addAiEntryField,
            removeAiEntryField,
            saveSettings,
            fetchAiModels,
            saveAiConfiguration,
            clearAiConfiguration,
            editAiConfiguration,
            cancelAiConfigurationEdit,
            changePassword,
            restoreTrashItem,
            deleteTrashItem,
            emptyTrashConfirm,
            loadTrash,
            goToTrashPage,
            renameTag,
            deleteTag,
            mergeTags,
            commitTagMergeSourceTags,
            removeTagMergeSourceTag,
            handleTagMergeSourceKey,
            handleTagMergeSourceInput,
            formatBytes,
            backupTypeLabel,
            loadBackups,
            openBackupCenter,
            setBackupPage,
            createManualBackup,
            backupDisplayName,
            downloadBackupFile,
            restoreBackup,
            closeRestoreWizard,
            loadRestoreSummary,
            restoreWizardNext,
            restoreWizardBack,
            confirmRestoreBackup,
            openToolsModal,
            loadHealthReport,
            loadMaintenanceReport,
            loadSecurityReport,
            focusReportItems,
            focusReportGroups,
            focusUntaggedItems,
            addTagToUntaggedItems,
            deleteSampleEntries,
            exportEncrypted,
            exportPlain,
            importEncryptedFile,
            importPlainFile,
            confirmImportPlain,
            retryImportPlain,
            closeImportConflicts,
            closeImportPreview,
            isImportPreviewSelected,
            toggleImportPreviewSelection,
            selectAllImportPreviewEntries,
            clearImportPreviewSelection,
            setImportConflictResolution,
            confirmAction
        };
    }
});

app.mount('#app');
