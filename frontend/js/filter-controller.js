/**
 * Advanced filter chip state, saved filters, and tag input helpers.
 */
(function () {
    function createAdvancedFilterController(options) {
        const {
            computed,
            advancedTagDraft,
            advancedTagList,
            advancedFilters,
            savedAdvancedFilters,
            listContextNotice,
            searchQuery,
            selectedSearchScopeLabels,
            filter,
            activeTagName,
            activeGroupName,
            sortBy,
            sortOrder,
            applyAdvancedFilters,
            clearAdvancedFilters
        } = options;

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
            if (filter.value === 'group' && activeGroupName.value) items.push(`密码组：${activeGroupName.value}`);
            activeAdvancedFilterChips.value.forEach(chip => items.push(chip.label));
            if (sortBy.value !== 'updated_at' || sortOrder.value !== 'desc') {
                const sortLabel = sortBy.value === 'title' ? '标题' : sortBy.value === 'created_at' ? '创建时间' : '更新时间';
                items.push(`排序：${sortLabel}${sortOrder.value === 'asc' ? '升序' : '降序'}`);
            }
            return items;
        });

        const hasActiveListState = computed(() => activeListStateItems.value.length > 0);

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
            if (activeAdvancedFilterChips.value.length === 0) {
                await clearAdvancedFilters();
            } else {
                await applyAdvancedFilters();
            }
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

        return {
            activeAdvancedFilterChips,
            activeListStateItems,
            hasActiveListState,
            resetAdvancedFilterForm,
            removeAdvancedFilterChip,
            loadSavedAdvancedFilters,
            persistSavedAdvancedFilters,
            getAdvancedFilterSnapshot,
            saveCurrentAdvancedFilter,
            applySavedAdvancedFilter,
            deleteSavedAdvancedFilter,
            addAdvancedTags,
            commitAdvancedTags,
            removeAdvancedTag,
            commitAndApplyAdvancedTags,
            handleAdvancedTagKey,
            handleAdvancedTagInput
        };
    }

    window.SecretBaseFilterController = {
        createAdvancedFilterController
    };
})();
