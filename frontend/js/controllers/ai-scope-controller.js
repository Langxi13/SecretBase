/**
 * AI 管家分析范围：全部、当前筛选结果与自定义条目选择。
 */
(function () {
    const MAX_SELECTED_ENTRIES = 500;
    const PAGE_SIZE_OPTIONS = [5, 10, 20, 50];

    function createAiScopeController(options) {
        const {
            api,
            store,
            aiAssistantScope,
            aiAssistantScopePicker: picker,
            searchQuery,
            selectedSearchScopes,
            sortBy,
            sortOrder,
            selectedEntryIds,
            resetAiAssistantScope
        } = options;
        let catalogRequestId = 0;

        function currentViewFilters() {
            const filters = {
                ...store.state.filters,
                search: searchQuery.value,
                searchScopes: [...selectedSearchScopes.value],
                sortBy: sortBy.value,
                sortOrder: sortOrder.value
            };
            if (filters.starred !== true) delete filters.starred;
            if (!filters.entryIds?.length) delete filters.entryIds;
            return filters;
        }

        function assistantFiltersForScope(scope = aiAssistantScope.value) {
            if (scope === 'all') return {};
            if (scope === 'selection') {
                return { entryIds: [...picker.selectedIds] };
            }
            return currentViewFilters();
        }

        function selectedIdsForCatalog() {
            return [...new Set([...picker.selectedIds, ...picker.draftSelectedIds])];
        }

        async function refreshAssistantScopeCatalog({ resetPage = false, silent = false } = {}) {
            if (resetPage) picker.page = 1;
            const requestId = ++catalogRequestId;
            picker.loading = true;
            if (!silent) picker.error = '';
            try {
                const result = await api.post('/ai/assistant/scope/catalog', {
                    filters: currentViewFilters(),
                    search: picker.search,
                    tag: picker.tag,
                    group: picker.group,
                    starred: picker.starred === '' ? null : picker.starred === 'true',
                    selected_ids: selectedIdsForCatalog(),
                    page: picker.page,
                    page_size: picker.pageSize
                }, { timeoutMs: 20000 });
                if (requestId !== catalogRequestId) return;
                const data = result.data || {};
                const pagination = data.pagination || {};
                const validIds = new Set(data.valid_selected_ids || []);
                picker.items = data.items || [];
                picker.counts = {
                    all: Number(data.counts?.all || 0),
                    currentView: Number(data.counts?.current_view || 0)
                };
                picker.pagination = {
                    page: Number(pagination.page || 1),
                    pageSize: Number(pagination.page_size || picker.pageSize),
                    total: Number(pagination.total || 0),
                    totalPages: Number(pagination.total_pages || 1)
                };
                picker.page = picker.pagination.page;
                picker.tags = data.tags || [];
                picker.groups = data.groups || [];
                picker.selectedIds = picker.selectedIds.filter(id => validIds.has(id));
                picker.draftSelectedIds = picker.draftSelectedIds.filter(id => validIds.has(id));
                picker.loaded = true;
            } catch (error) {
                if (requestId === catalogRequestId && !silent) {
                    picker.error = error.message || '无法加载条目选择列表';
                }
            } finally {
                if (requestId === catalogRequestId) picker.loading = false;
            }
        }

        async function openAssistantScopePicker() {
            picker.open = true;
            picker.error = '';
            picker.draftScope = aiAssistantScope.value;
            picker.draftSelectedIds = [...picker.selectedIds];
            await refreshAssistantScopeCatalog({ resetPage: true });
        }

        function closeAssistantScopePicker() {
            picker.open = false;
            picker.error = '';
            picker.draftSelectedIds = [...picker.selectedIds];
        }

        function selectAssistantScopeMode(scope) {
            if (!['all', 'current_view', 'selection'].includes(scope)) return;
            picker.draftScope = scope;
            picker.error = '';
        }

        function toggleAssistantScopeEntry(entryId) {
            const selected = new Set(picker.draftSelectedIds);
            if (selected.has(entryId)) {
                selected.delete(entryId);
            } else if (selected.size >= MAX_SELECTED_ENTRIES) {
                picker.error = `单次最多选择 ${MAX_SELECTED_ENTRIES} 个条目`;
                return;
            } else {
                selected.add(entryId);
            }
            picker.draftSelectedIds = [...selected];
            picker.error = '';
        }

        function assistantScopePageFullySelected() {
            return picker.items.length > 0
                && picker.items.every(entry => picker.draftSelectedIds.includes(entry.id));
        }

        function toggleAssistantScopePage() {
            const selected = new Set(picker.draftSelectedIds);
            if (assistantScopePageFullySelected()) {
                picker.items.forEach(entry => selected.delete(entry.id));
            } else {
                for (const entry of picker.items) {
                    if (selected.size >= MAX_SELECTED_ENTRIES) break;
                    selected.add(entry.id);
                }
            }
            picker.draftSelectedIds = [...selected];
        }

        function clearAssistantScopeSelection() {
            picker.draftSelectedIds = [];
            picker.error = '';
        }

        function importCurrentEntrySelection() {
            const selected = new Set(picker.draftSelectedIds);
            selectedEntryIds.value.forEach(id => {
                if (selected.size < MAX_SELECTED_ENTRIES) selected.add(id);
            });
            picker.draftSelectedIds = [...selected];
            picker.draftScope = 'selection';
        }

        async function filterAssistantScopeEntries() {
            await refreshAssistantScopeCatalog({ resetPage: true });
        }

        async function goToAssistantScopePage(page) {
            const totalPages = picker.pagination.totalPages || 1;
            const target = Math.min(Math.max(1, Number(page) || 1), totalPages);
            if (target === picker.page && picker.loaded) return;
            picker.page = target;
            await refreshAssistantScopeCatalog();
        }

        async function changeAssistantScopePageSize(size) {
            const normalized = PAGE_SIZE_OPTIONS.includes(Number(size)) ? Number(size) : 10;
            picker.pageSize = normalized;
            await refreshAssistantScopeCatalog({ resetPage: true });
        }

        function confirmAssistantScopePicker() {
            if (picker.draftScope === 'selection' && picker.draftSelectedIds.length === 0) {
                picker.error = '请至少选择一个条目';
                return;
            }
            if (
                picker.loaded
                && picker.draftScope !== 'selection'
                && assistantScopeCount(picker.draftScope) === 0
            ) {
                picker.error = '当前范围没有可供 AI 分析的条目';
                return;
            }
            aiAssistantScope.value = picker.draftScope;
            picker.selectedIds = picker.draftScope === 'selection'
                ? [...picker.draftSelectedIds]
                : picker.selectedIds;
            picker.open = false;
            picker.error = '';
        }

        function assistantScopeCount(scope = aiAssistantScope.value) {
            if (scope === 'selection') return picker.selectedIds.length;
            if (scope === 'current_view') return picker.counts.currentView;
            return picker.counts.all;
        }

        function assistantScopeLabel(scope = aiAssistantScope.value) {
            if (scope === 'selection') return '自定义选择';
            if (scope === 'current_view') return '当前筛选结果';
            return '全部条目';
        }

        function assistantScopeSummary(scope = aiAssistantScope.value) {
            const label = assistantScopeLabel(scope);
            if (!picker.loaded && scope !== 'selection') return label;
            return `${label} · ${assistantScopeCount(scope)}`;
        }

        function resetAssistantScopeForConversation() {
            resetAiAssistantScope();
        }

        return {
            assistantScopePageSizeOptions: PAGE_SIZE_OPTIONS,
            assistantFiltersForScope,
            assistantScopeCount,
            assistantScopeLabel,
            assistantScopeSummary,
            assistantScopePageFullySelected,
            refreshAssistantScopeCatalog,
            openAssistantScopePicker,
            closeAssistantScopePicker,
            selectAssistantScopeMode,
            toggleAssistantScopeEntry,
            toggleAssistantScopePage,
            clearAssistantScopeSelection,
            importCurrentEntrySelection,
            filterAssistantScopeEntries,
            goToAssistantScopePage,
            changeAssistantScopePageSize,
            confirmAssistantScopePicker,
            resetAssistantScopeForConversation
        };
    }

    window.SecretBaseAiScopeController = {
        createAiScopeController
    };
})();
