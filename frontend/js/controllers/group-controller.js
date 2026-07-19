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
            groupSaving,
            groupOrdering = { value: false },
            showGroupModal,
            loadGroups,
            loadEntries,
            currentPage,
            showGroupEntryPicker,
            groupPickerEntries,
            groupPickerSelectedIds,
            groupPickerTagFilter,
            groupPickerGroupFilter,
            groupPickerPage,
            groupPickerLoading,
            groupPickerError = { value: '' },
            groupPickerSaving,
            groupPickerTotalPages,
            paginatedGroupPickerEntries,
            allGroupPickerEntriesSelected,
            locked
        } = options;
        let pickerRequestSequence = 0;

        async function refreshGroupMutationView(page = currentPage.value, reloadEntries = true) {
            const results = await Promise.allSettled([
                loadGroups(),
                ...(reloadEntries ? [loadEntries(page)] : [])
            ]);
            return results.every(result => result.status === 'fulfilled' && result.value !== false);
        }

        function goToGroupPage(page) {
            if (page < 1 || page > groupTotalPages.value) return;
            groupCurrentPage.value = page;
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        async function showGroupMode() {
            if (showGroupEntryPicker.value) closeGroupEntryPicker();
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
            return loadGroups();
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
            if (groupOrdering.value) return;
            const nextNames = groupOrderNamesAfterMove(groupName, direction);
            if (nextNames.join('\n') === groups.value.map(group => group.name).join('\n')) {
                return;
            }
            groupOrdering.value = true;
            try {
                const updatedGroups = await store.updateGroupOrder(nextNames);
                if (updatedGroups) groups.value = updatedGroups;
            } catch (error) {
                showToast(error.message || '密码组排序失败，请重试', 'error');
            } finally {
                groupOrdering.value = false;
            }
        }

        async function resetGroupOrder() {
            if (groupOrdering.value) return;
            groupOrdering.value = true;
            try {
                const updatedGroups = await store.updateGroupOrder([]);
                if (updatedGroups) groups.value = updatedGroups;
            } catch (error) {
                showToast(error.message || '恢复默认排序失败，请重试', 'error');
            } finally {
                groupOrdering.value = false;
            }
        }

        async function saveGroup() {
            if (groupSaving.value) return;
            const name = groupForm.name.trim();
            if (!name) {
                showToast('请输入密码组名称', 'error');
                return;
            }
            groupSaving.value = true;
            try {
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
                    const groupsRefreshed = await loadGroups();
                    if (oldName && activeGroupName.value === oldName) {
                        const entriesRefreshed = await filterByGroup(result.new_name || name);
                        if (groupsRefreshed === false || entriesRefreshed === false) {
                            showToast('密码组已更新，但当前视图刷新不完整，请稍后重试。', 'warning');
                        }
                    } else if (oldName) {
                        const entriesRefreshed = await loadEntries(currentPage.value);
                        if (groupsRefreshed === false || entriesRefreshed === false) {
                            showToast('密码组已更新，但相关列表刷新不完整，请稍后重试。', 'warning');
                        }
                    } else if (groupsRefreshed === false) {
                        showToast('密码组已创建，但列表刷新不完整，请稍后重试。', 'warning');
                    }
                }
            } catch (error) {
                showToast(error.message || '保存密码组失败', 'error');
            } finally {
                groupSaving.value = false;
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
                if (!result) return false;
                if (filter.value === 'group' && activeGroupName.value === name) {
                    const refreshed = await showGroupMode();
                    if (refreshed === false) showToast('密码组已删除，但列表刷新不完整，请稍后重试。', 'warning');
                    return;
                }
                if (!(await refreshGroupMutationView())) {
                    showToast('密码组已删除，但相关列表刷新不完整，请稍后重试。', 'warning');
                }
            });
        }

        async function filterByGroup(groupName) {
            const normalized = String(groupName || '').trim();
            if (!normalized) return;
            if (showGroupEntryPicker.value) closeGroupEntryPicker();
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
            return loadEntries(1);
        }

        async function loadGroupEntryPicker() {
            if (locked?.value || !activeGroupName.value || groupPickerLoading.value || groupPickerSaving.value) return;
            const requestSequence = ++pickerRequestSequence;
            const targetGroupName = activeGroupName.value;
            groupPickerLoading.value = true;
            groupPickerError.value = '';
            try {
                const params = new URLSearchParams({
                    page: '1',
                    page_size: '1000',
                    sort_by: 'title',
                    sort_order: 'asc'
                });
                const result = await api.get(`/entries?${params}`);
                if (
                    requestSequence !== pickerRequestSequence
                    || locked?.value
                    || activeGroupName.value !== targetGroupName
                ) return;
                const items = [...(result.data?.items || [])];
                const totalPages = Math.max(
                    1,
                    Number(result.data?.pagination?.total_pages || result.data?.pagination?.totalPages || 1)
                );
                // 选择器支持跨页选择；一次打开时把后续元数据页补齐，避免超过 1000 条后静默缺失。
                for (let page = 2; page <= totalPages; page += 1) {
                    if (
                        requestSequence !== pickerRequestSequence
                        || locked?.value
                        || activeGroupName.value !== targetGroupName
                    ) return;
                    const nextParams = new URLSearchParams(params);
                    nextParams.set('page', String(page));
                    const nextResult = await api.get(`/entries?${nextParams}`);
                    items.push(...(nextResult.data?.items || []));
                }
                if (
                    requestSequence !== pickerRequestSequence
                    || locked?.value
                    || activeGroupName.value !== targetGroupName
                ) return;
                groupPickerEntries.value = items;
                return true;
            } catch (error) {
                if (
                    requestSequence !== pickerRequestSequence
                    || error?.code === 'SESSION_INVALIDATED'
                    || locked?.value
                    || activeGroupName.value !== targetGroupName
                ) return;
                groupPickerEntries.value = [];
                groupPickerError.value = error.message || '加载可选条目失败，请重试。';
                showToast(groupPickerError.value, 'error');
                return false;
            } finally {
                if (requestSequence === pickerRequestSequence) groupPickerLoading.value = false;
            }
        }

        async function openGroupEntryPicker() {
            if (locked?.value || !activeGroupName.value || groupPickerLoading.value || groupPickerSaving.value) return;
            showGroupEntryPicker.value = true;
            groupPickerTagFilter.value = '';
            groupPickerGroupFilter.value = '';
            groupPickerPage.value = 1;
            groupPickerSelectedIds.value = [];
            await loadGroupEntryPicker();
        }

        async function retryGroupEntryPicker() {
            if (!showGroupEntryPicker.value || groupPickerLoading.value || groupPickerSaving.value) return;
            groupPickerPage.value = 1;
            groupPickerSelectedIds.value = [];
            await loadGroupEntryPicker();
        }

        function closeGroupEntryPicker() {
            pickerRequestSequence += 1;
            showGroupEntryPicker.value = false;
            // 关闭弹窗即取消当前读取上下文，避免迟到请求让下一次打开永久停在加载态。
            groupPickerLoading.value = false;
            groupPickerError.value = '';
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
            if (groupPickerSaving.value || !activeGroupName.value || groupPickerSelectedIds.value.length === 0) return;
            groupPickerSaving.value = true;
            try {
                const result = await store.assignEntriesToGroup(activeGroupName.value, groupPickerSelectedIds.value);
                if (result) {
                    closeGroupEntryPicker();
                    if (!(await refreshGroupMutationView())) {
                        showToast('条目已加入密码组，但相关列表刷新不完整，请稍后重试。', 'warning');
                    }
                }
            } catch (error) {
                showToast(error.message || '加入密码组失败，请重试', 'error');
            } finally {
                groupPickerSaving.value = false;
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
            openGroupEntryPicker,
            retryGroupEntryPicker,
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
