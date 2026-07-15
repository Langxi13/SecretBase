/**
 * 密码组模式、密码组编辑和“选择已有条目”对话框行为。
 *
 * 该控制器只接收 setup 中创建的响应式引用和明确的回调，
 * 不读取 Vue 全局实例或其他控制器的私有状态。
 */
(function () {
    function createGroupController(options) {
        const {
            api,
            store,
            showToast,
            showConfirmDialog,
            groups,
            activeGroupName,
            filter,
            groupCurrentPage,
            groupTotalPages,
            searchQuery,
            resetSearchScopes,
            resetAdvancedFilterForm,
            listContextNotice,
            activeTagName,
            selectedEntryIds,
            sortBy,
            sortOrder,
            editingGroupName,
            groupForm,
            showGroupModal,
            loadGroups,
            loadEntries,
            currentPage,
            entryForm,
            resetEntryForm,
            showCreateModal,
            showGroupEntryPicker,
            groupPickerEntries,
            groupPickerSelectedIds,
            groupPickerTagFilter,
            groupPickerGroupFilter,
            groupPickerPage,
            groupPickerLoading,
            groupPickerTotalPages,
            paginatedGroupPickerEntries,
            allGroupPickerEntriesSelected
        } = options;

        function goToGroupPage(page) {
            if (page < 1 || page > groupTotalPages.value) return;
            groupCurrentPage.value = page;
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        async function showGroupMode() {
            filter.value = 'groups';
            groupCurrentPage.value = 1;
            activeTagName.value = '';
            activeGroupName.value = '';
            listContextNotice.value = '';
            searchQuery.value = '';
            resetSearchScopes();
            store.clearFilters();
            resetAdvancedFilterForm();
            selectedEntryIds.value = [];
            await loadGroups();
        }

        function openCreateGroupModal() {
            editingGroupName.value = '';
            groupForm.name = '';
            groupForm.description = '';
            showGroupModal.value = true;
        }

        function openEditGroupModal(group) {
            const name = String(group?.name || '').trim();
            if (!name) return;
            editingGroupName.value = name;
            groupForm.name = name;
            groupForm.description = String(group?.description || '');
            showGroupModal.value = true;
        }

        function closeGroupModal() {
            showGroupModal.value = false;
            editingGroupName.value = '';
            groupForm.name = '';
            groupForm.description = '';
        }

        function groupOrderNamesAfterMove(groupName, direction) {
            const names = groups.value.map(group => group.name);
            const index = names.indexOf(groupName);
            const nextIndex = index + direction;
            if (index < 0 || nextIndex < 0 || nextIndex >= names.length) {
                return names;
            }
            const [name] = names.splice(index, 1);
            names.splice(nextIndex, 0, name);
            return names;
        }

        async function moveGroupOrder(groupName, direction) {
            const nextNames = groupOrderNamesAfterMove(groupName, direction);
            if (nextNames.join('\n') === groups.value.map(group => group.name).join('\n')) {
                return;
            }
            const updatedGroups = await store.updateGroupOrder(nextNames);
            if (updatedGroups) {
                groups.value = updatedGroups;
            }
        }

        async function resetGroupOrder() {
            const updatedGroups = await store.updateGroupOrder([]);
            if (updatedGroups) {
                groups.value = updatedGroups;
            }
        }

        async function saveGroup() {
            const name = groupForm.name.trim();
            if (!name) {
                showToast('请输入密码组名称', 'error');
                return;
            }
            const oldName = editingGroupName.value;
            const payload = {
                name,
                description: groupForm.description.trim()
            };
            const result = oldName
                ? await store.updateGroup(oldName, payload)
                : await store.createGroup(payload);
            if (result) {
                closeGroupModal();
                await loadGroups();
                if (oldName && activeGroupName.value === oldName) {
                    await filterByGroup(result.new_name || name);
                } else if (oldName) {
                    await loadEntries(currentPage.value);
                }
            }
        }

        function confirmDeleteGroup(groupOrName) {
            const name = String(
                typeof groupOrName === 'string' ? groupOrName : groupOrName?.name || ''
            ).trim();
            if (!name) return;
            const group = groups.value.find(item => item.name === name);
            const count = Math.max(0, Number(group?.count || 0));
            const relationNotice = count > 0
                ? `该密码组当前关联 ${count} 个条目。删除后只会解除这些条目的密码组归属，不会删除条目。`
                : '该操作只会删除密码组，不会删除任何条目。';
            showConfirmDialog('删除密码组', `确认删除密码组「${name}」？\n\n${relationNotice}`, async () => {
                const result = await store.deleteGroup(name);
                if (!result) return;
                if (filter.value === 'group' && activeGroupName.value === name) {
                    await showGroupMode();
                    return;
                }
                await Promise.all([loadGroups(), loadEntries(currentPage.value)]);
            });
        }

        async function filterByGroup(groupName) {
            const normalized = String(groupName || '').trim();
            if (!normalized) return;
            searchQuery.value = '';
            resetSearchScopes();
            resetAdvancedFilterForm();
            store.clearFilters();
            listContextNotice.value = '';
            store.setFilter('group', normalized);
            store.setFilter('starred', false);
            sortBy.value = store.state.filters.sortBy;
            sortOrder.value = store.state.filters.sortOrder;
            filter.value = 'group';
            activeTagName.value = '';
            activeGroupName.value = normalized;
            selectedEntryIds.value = [];
            await loadEntries(1);
        }

        function openCreateEntryForActiveGroup() {
            if (!activeGroupName.value) return;
            resetEntryForm();
            entryForm.groups = [activeGroupName.value];
            showCreateModal.value = true;
        }

        async function openGroupEntryPicker() {
            if (!activeGroupName.value) return;
            showGroupEntryPicker.value = true;
            groupPickerTagFilter.value = '';
            groupPickerGroupFilter.value = '';
            groupPickerPage.value = 1;
            groupPickerSelectedIds.value = [];
            groupPickerLoading.value = true;
            try {
                const params = new URLSearchParams({
                    page: '1',
                    page_size: '1000',
                    sort_by: 'title',
                    sort_order: 'asc'
                });
                const result = await api.get(`/entries?${params}`);
                groupPickerEntries.value = result.data?.items || [];
            } catch (error) {
                groupPickerEntries.value = [];
                showToast(error.message || '加载可选条目失败', 'error');
            } finally {
                groupPickerLoading.value = false;
            }
        }

        function closeGroupEntryPicker() {
            showGroupEntryPicker.value = false;
            groupPickerEntries.value = [];
            groupPickerSelectedIds.value = [];
            groupPickerTagFilter.value = '';
            groupPickerGroupFilter.value = '';
            groupPickerPage.value = 1;
        }

        function goToGroupPickerPage(page) {
            const target = Math.min(Math.max(Number(page) || 1, 1), groupPickerTotalPages.value);
            groupPickerPage.value = target;
        }

        function toggleGroupPickerEntry(entryId) {
            if (groupPickerSelectedIds.value.includes(entryId)) {
                groupPickerSelectedIds.value = groupPickerSelectedIds.value.filter(id => id !== entryId);
            } else {
                groupPickerSelectedIds.value = [...groupPickerSelectedIds.value, entryId];
            }
        }

        function toggleAllGroupPickerEntries() {
            const ids = paginatedGroupPickerEntries.value.map(entry => entry.id);
            if (ids.length === 0) return;
            if (allGroupPickerEntriesSelected.value) {
                groupPickerSelectedIds.value = groupPickerSelectedIds.value.filter(id => !ids.includes(id));
            } else {
                groupPickerSelectedIds.value = Array.from(new Set([...groupPickerSelectedIds.value, ...ids]));
            }
        }

        async function assignSelectedEntriesToActiveGroup() {
            if (!activeGroupName.value || groupPickerSelectedIds.value.length === 0) return;
            const result = await store.assignEntriesToGroup(activeGroupName.value, groupPickerSelectedIds.value);
            if (result) {
                closeGroupEntryPicker();
                await Promise.all([loadEntries(currentPage.value), loadGroups()]);
            }
        }

        return {
            goToGroupPage,
            showGroupMode,
            openCreateGroupModal,
            openEditGroupModal,
            closeGroupModal,
            moveGroupOrder,
            resetGroupOrder,
            saveGroup,
            confirmDeleteGroup,
            filterByGroup,
            openCreateEntryForActiveGroup,
            openGroupEntryPicker,
            closeGroupEntryPicker,
            goToGroupPickerPage,
            toggleGroupPickerEntry,
            toggleAllGroupPickerEntries,
            assignSelectedEntriesToActiveGroup
        };
    }

    window.SecretBaseGroupController = {
        createGroupController
    };
})();
