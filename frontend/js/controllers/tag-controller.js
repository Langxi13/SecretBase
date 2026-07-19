/**
 * 标签筛选、标签浏览器与标签管理操作。
 */
(function () {
    function createTagController(options) {
        const {
            api,
            store,
            showToast,
            showConfirmDialog,
            filter,
            activeTagName,
            activeGroupName,
            listContextNotice,
            showTagDropdown,
            showTagBrowser,
            tagBrowserQuery,
            tagBrowserPage,
            tagBrowserTotalPages,
            loadEntries,
            resetAdvancedFilterForm,
            resetSearchScopes,
            searchQuery,
            selectedEntryIds,
            sortBy,
            sortOrder,
            showTagManager,
            showTagEditorModal,
            tagEditorForm,
            selectedManagedTagNames,
            tagManagerPage,
            tagManagerTotalPages,
            paginatedManagedTags,
            allManagedPageTagsSelected,
            tagMergeForm,
            tagMergeSourceList,
            tagSaving,
            tagMerging,
            currentPage,
            loadTags
        } = options;

        async function refreshTagMutationView(page = currentPage.value, reloadEntries = true) {
            const results = await Promise.allSettled([
                loadTags(),
                ...(reloadEntries ? [loadEntries(page)] : [])
            ]);
            return results.every(result => result.status === 'fulfilled' && result.value !== false);
        }

        async function returnToAllEntries() {
            searchQuery.value = '';
            resetSearchScopes();
            resetAdvancedFilterForm();
            store.clearFilters();
            sortBy.value = store.state.filters.sortBy;
            sortOrder.value = store.state.filters.sortOrder;
            filter.value = 'all';
            activeTagName.value = '';
            activeGroupName.value = '';
            listContextNotice.value = '';
            selectedEntryIds.value = [];
            return loadEntries(1);
        }

        async function filterByTag(tagName) {
            searchQuery.value = '';
            resetSearchScopes();
            resetAdvancedFilterForm();
            store.clearFilters();
            store.setFilter('entryIds', []);
            listContextNotice.value = '';
            store.setFilter('tag', tagName);
            store.setFilter('group', null);
            store.setFilter('starred', false);
            sortBy.value = store.state.filters.sortBy;
            sortOrder.value = store.state.filters.sortOrder;
            filter.value = 'tag';
            activeTagName.value = tagName;
            activeGroupName.value = '';
            showTagDropdown.value = false;
            showTagBrowser.value = false;
            selectedEntryIds.value = [];
            return loadEntries(1);
        }

        function openTagBrowser() {
            tagBrowserQuery.value = '';
            tagBrowserPage.value = 1;
            showTagBrowser.value = true;
        }

        function closeTagBrowser() {
            showTagBrowser.value = false;
            tagBrowserPage.value = 1;
        }

        function goToTagBrowserPage(page) {
            const target = Math.min(Math.max(Number(page) || 1, 1), tagBrowserTotalPages.value);
            tagBrowserPage.value = target;
        }

        function deleteTag(tag) {
            if (tagSaving.value || tagMerging.value) return;
            showConfirmDialog('删除标签', `确认删除标签 "${tag.name}"？`, async () => {
                const deleted = await store.deleteTag(tag.name);
                if (!deleted) return false;
                const wasActive = activeTagName.value === tag.name;
                selectedManagedTagNames.value = selectedManagedTagNames.value.filter(name => name !== tag.name);
                const tagsRefreshed = await loadTags();
                const entriesRefreshed = wasActive
                    ? await returnToAllEntries()
                    : await loadEntries(currentPage.value);
                if (tagsRefreshed === false || entriesRefreshed === false) {
                    showToast('标签已删除，但相关列表刷新不完整，请稍后重试。', 'warning');
                }
            });
        }

        function resetTagEditorForm() {
            tagEditorForm.mode = 'create';
            tagEditorForm.originalName = '';
            tagEditorForm.name = '';
            tagEditorForm.description = '';
            tagEditorForm.color = '#64748b';
        }

        function startEditManagedTag(tag) {
            if (tagSaving.value || tagMerging.value) return;
            tagEditorForm.mode = 'edit';
            tagEditorForm.originalName = tag.name;
            tagEditorForm.name = tag.name;
            tagEditorForm.description = tag.description || '';
            tagEditorForm.color = tag.color || '#64748b';
            showTagEditorModal.value = true;
        }

        function cancelManagedTagEdit() {
            closeTagEditorModal();
        }

        function openCreateTagModal() {
            if (tagSaving.value || tagMerging.value) return;
            resetTagEditorForm();
            showTagEditorModal.value = true;
        }

        function closeTagEditorModal(force = false) {
            if (tagSaving.value && !force) return false;
            showTagEditorModal.value = false;
            resetTagEditorForm();
            return true;
        }

        function closeTagManager(force = false) {
            if ((tagSaving.value || tagMerging.value) && !force) return false;
            showTagManager.value = false;
            closeTagEditorModal(force);
            return true;
        }

        async function createTagFromManager() {
            if (tagSaving.value) return;
            const name = tagEditorForm.name.trim();
            if (!name) {
                showToast('请输入标签名称', 'warning');
                return;
            }
            tagSaving.value = true;
            try {
                const created = await store.createTag({
                    name,
                    description: tagEditorForm.description.trim(),
                    color: tagEditorForm.color
                });
                if (created) {
                    closeTagEditorModal(true);
                    if (!(await refreshTagMutationView(currentPage.value, false))) {
                        showToast('标签已创建，但标签列表刷新不完整，请稍后重试。', 'warning');
                    }
                }
            } catch (error) {
                showToast(error.message || '创建标签失败，请重试', 'error');
            } finally {
                tagSaving.value = false;
            }
        }

        async function saveManagedTag() {
            if (tagSaving.value) return;
            if (tagEditorForm.mode !== 'edit') {
                await createTagFromManager();
                return;
            }
            const name = tagEditorForm.name.trim();
            if (!name) {
                showToast('请输入标签名称', 'warning');
                return;
            }
            tagSaving.value = true;
            try {
                const originalName = tagEditorForm.originalName;
                const updated = await store.updateTag(tagEditorForm.originalName, {
                    name,
                    description: tagEditorForm.description.trim(),
                    color: tagEditorForm.color
                });
                if (updated) {
                    closeTagEditorModal(true);
                    const nextName = updated.new_name || name;
                    const wasActive = activeTagName.value === originalName;
                    const tagsRefreshed = await refreshTagMutationView(currentPage.value, false);
                    if (wasActive) {
                        const entriesRefreshed = await filterByTag(nextName);
                        if (!tagsRefreshed || entriesRefreshed === false) {
                            showToast('标签已更新，但当前视图刷新不完整，请稍后重试。', 'warning');
                        }
                    } else {
                        const entriesRefreshed = await loadEntries(currentPage.value);
                        if (!tagsRefreshed || entriesRefreshed === false) {
                            showToast('标签已更新，但相关列表刷新不完整，请稍后重试。', 'warning');
                        }
                    }
                }
            } catch (error) {
                showToast(error.message || '保存标签失败，请重试', 'error');
            } finally {
                tagSaving.value = false;
            }
        }

        function isManagedTagSelected(tagName) {
            return selectedManagedTagNames.value.includes(tagName);
        }

        function toggleManagedTagSelection(tagName) {
            if (selectedManagedTagNames.value.includes(tagName)) {
                selectedManagedTagNames.value = selectedManagedTagNames.value.filter(name => name !== tagName);
                return;
            }
            selectedManagedTagNames.value = [...selectedManagedTagNames.value, tagName];
        }

        function toggleManagedTagPageSelection() {
            const pageNames = paginatedManagedTags.value.map(tag => tag.name);
            if (allManagedPageTagsSelected.value) {
                selectedManagedTagNames.value = selectedManagedTagNames.value.filter(name => !pageNames.includes(name));
                return;
            }
            const selected = new Set(selectedManagedTagNames.value);
            pageNames.forEach(name => selected.add(name));
            selectedManagedTagNames.value = Array.from(selected);
        }

        function goToTagManagerPage(page) {
            const target = Math.min(Math.max(Number(page) || 1, 1), tagManagerTotalPages.value);
            tagManagerPage.value = target;
        }

        async function batchDeleteManagedTags() {
            if (tagSaving.value || tagMerging.value) return;
            const names = [...selectedManagedTagNames.value];
            if (names.length === 0) {
                showToast('请选择要删除的标签', 'warning');
                return;
            }
            showConfirmDialog('批量删除标签', `确认删除已选 ${names.length} 个标签？这些标签会从相关条目中移除。`, async () => {
                const result = await store.batchDeleteTags(names);
                if (!result) return false;
                selectedManagedTagNames.value = [];
                const activeWasDeleted = names.includes(activeTagName.value);
                const tagsRefreshed = await loadTags();
                if (activeWasDeleted) {
                    const entriesRefreshed = await returnToAllEntries();
                    if (tagsRefreshed === false || entriesRefreshed === false) {
                        showToast('标签已删除，但当前视图刷新不完整，请稍后重试。', 'warning');
                    }
                } else {
                    const entriesRefreshed = await loadEntries(currentPage.value);
                    goToTagManagerPage(tagManagerPage.value);
                    if (tagsRefreshed === false || entriesRefreshed === false) {
                        showToast('标签已删除，但相关列表刷新不完整，请稍后重试。', 'warning');
                    }
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
            if (tagMerging.value || tagSaving.value) return;
            commitTagMergeSourceTags();
            const sourceTags = [...tagMergeSourceList.value];
            const targetTag = tagMergeForm.targetTag.trim();
            if (sourceTags.length === 0 || !targetTag) {
                showToast('请输入源标签和目标标签', 'error');
                return;
            }

            tagMerging.value = true;
            try {
                const result = await api.post('/tags/merge', {
                    source_tags: sourceTags,
                    target_tag: targetTag
                });
                tagMergeForm.sourceTags = '';
                tagMergeForm.targetTag = '';
                tagMergeSourceList.value = [];
                showToast(result.message || '标签已合并', 'success');
                const tagsRefreshed = await loadTags();
                if (sourceTags.includes(activeTagName.value)) {
                    const entriesRefreshed = await filterByTag(targetTag);
                    if (tagsRefreshed === false || entriesRefreshed === false) {
                        showToast('标签已合并，但当前视图刷新不完整，请稍后重试。', 'warning');
                    }
                } else {
                    const entriesRefreshed = await loadEntries(currentPage.value);
                    if (tagsRefreshed === false || entriesRefreshed === false) {
                        showToast('标签已合并，但相关列表刷新不完整，请稍后重试。', 'warning');
                    }
                }
            } catch (error) {
                showToast(error.message || '标签合并失败', 'error');
            } finally {
                tagMerging.value = false;
            }
        }

        return {
            filterByTag,
            openTagBrowser,
            closeTagBrowser,
            goToTagBrowserPage,
            deleteTag,
            startEditManagedTag,
            cancelManagedTagEdit,
            openCreateTagModal,
            closeTagEditorModal,
            closeTagManager,
            createTagFromManager,
            saveManagedTag,
            isManagedTagSelected,
            toggleManagedTagSelection,
            toggleManagedTagPageSelection,
            goToTagManagerPage,
            batchDeleteManagedTags,
            mergeTags,
            commitTagMergeSourceTags,
            removeTagMergeSourceTag,
            handleTagMergeSourceKey,
            handleTagMergeSourceInput
        };
    }

    window.SecretBaseTagController = {
        createTagController
    };
})();
