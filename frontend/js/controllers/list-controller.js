/**
 * 条目列表的搜索、筛选、排序、视图状态与字段显示切换。
 */
(function () {
    function createListController(options) {
        const {
            debounce,
            store,
            searchQuery,
            selectedSearchScopes,
            listContextNotice,
            filter,
            activeTagName,
            activeGroupName,
            sortBy,
            sortOrder,
            advancedTagList,
            advancedFilters,
            resetAdvancedFilterForm,
            commitAdvancedTags,
            resetSearchScopes,
            clearSelection,
            loadEntries,
            revealedFields,
            isSidebarCollapsed,
            returnToGroupMode
        } = options;

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

        async function showAllEntries() {
            filter.value = 'all';
            activeTagName.value = '';
            activeGroupName.value = '';
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
            activeGroupName.value = '';
            listContextNotice.value = '';
            store.setFilter('entryIds', []);
            store.setFilter('tag', null);
            store.setFilter('group', null);
            store.setFilter('starred', true);
            await loadEntries(1);
        }

        function toggleSidebar() {
            isSidebarCollapsed.value = !isSidebarCollapsed.value;
            try {
                localStorage.setItem('secretbase.sidebarCollapsed', String(isSidebarCollapsed.value));
            } catch (error) {
                // 本地存储不可用时仍保留本次会话内的状态切换。
            }
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
            if (
                filter.value === 'group'
                && activeGroupName.value
                && typeof returnToGroupMode === 'function'
            ) {
                await returnToGroupMode();
                return;
            }
            listContextNotice.value = '';
            activeTagName.value = '';
            activeGroupName.value = '';
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

        return {
            debounceSearch,
            toggleSearchScope,
            showAllEntries,
            showStarredEntries,
            toggleSidebar,
            applySort,
            applyAdvancedFilters,
            clearAdvancedFilters,
            clearListState,
            isFieldRevealed,
            toggleFieldReveal
        };
    }

    window.SecretBaseListController = {
        createListController
    };
})();
