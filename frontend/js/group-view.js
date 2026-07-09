/**
 * Password group list and existing-entry picker computed state.
 */
(function () {
    function visiblePageWindow(current, total) {
        const pages = [];
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
    }

    function createGroupView(options) {
        const {
            computed,
            groups,
            totalEntries,
            activeGroupName,
            groupPickerEntries,
            groupPickerTagFilter,
            groupPickerGroupFilter,
            groupPickerPage,
            groupPickerPageSize,
            groupPickerSelectedIds,
            groupCurrentPage,
            groupPageSize
        } = options;

        const activeGroup = computed(() => {
            if (!activeGroupName.value) return null;
            return groups.value.find(group => group.name === activeGroupName.value) || {
                name: activeGroupName.value,
                description: '',
                count: totalEntries.value
            };
        });

        const availableGroupPickerEntries = computed(() => {
            const groupName = activeGroupName.value;
            const tagFilter = groupPickerTagFilter.value;
            const groupFilter = groupPickerGroupFilter.value;
            return groupPickerEntries.value.filter(entry => {
                if (!groupName || (entry.groups || []).includes(groupName)) {
                    return false;
                }
                if (tagFilter && !(entry.tags || []).includes(tagFilter)) {
                    return false;
                }
                if (groupFilter && !(entry.groups || []).includes(groupFilter)) {
                    return false;
                }
                return true;
            });
        });

        const groupPickerTotalPages = computed(() => Math.max(1, Math.ceil(availableGroupPickerEntries.value.length / groupPickerPageSize.value)));

        const paginatedGroupPickerEntries = computed(() => {
            const start = (groupPickerPage.value - 1) * groupPickerPageSize.value;
            return availableGroupPickerEntries.value.slice(start, start + groupPickerPageSize.value);
        });

        const selectableGroupPickerGroups = computed(() => {
            return groups.value.filter(group => group.name !== activeGroupName.value);
        });

        const allGroupPickerEntriesSelected = computed(() => {
            const ids = paginatedGroupPickerEntries.value.map(entry => entry.id);
            return ids.length > 0 && ids.every(id => groupPickerSelectedIds.value.includes(id));
        });

        const paginatedGroups = computed(() => {
            const start = (groupCurrentPage.value - 1) * groupPageSize.value;
            return groups.value.slice(start, start + groupPageSize.value);
        });

        const groupTotalPages = computed(() => {
            return Math.ceil((groups.value?.length || 0) / groupPageSize.value) || 1;
        });

        const visibleGroupPages = computed(() => visiblePageWindow(groupCurrentPage.value, groupTotalPages.value));

        return {
            activeGroup,
            availableGroupPickerEntries,
            groupPickerTotalPages,
            paginatedGroupPickerEntries,
            selectableGroupPickerGroups,
            allGroupPickerEntriesSelected,
            paginatedGroups,
            groupTotalPages,
            visibleGroupPages
        };
    }

    window.SecretBaseGroupView = {
        createGroupView,
        visiblePageWindow
    };
})();
