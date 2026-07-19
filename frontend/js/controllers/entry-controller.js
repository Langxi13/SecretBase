/**
 * 条目详情、编辑表单、批量操作与复制菜单行为。
 */
(function () {
    function createEntryController(options) {
        const {
            store,
            showToast,
            copyToClipboard,
            openExternalUrl,
            normalizeFieldForEdit,
            entries,
            filter,
            activeTagName,
            activeGroupName,
            currentPage,
            totalPages,
            selectedEntry,
            showEntryDetail,
            entryDetailTargetId,
            entryDetailLoading,
            entryDetailError,
            editingEntry,
            entryEditLoading,
            entryEditTargetId,
            entryEditError,
            entryForm,
            entryTemplates,
            selectedTemplate,
            newTag,
            newGroup,
            newGroupDescription,
            groups,
            showCreateModal,
            showEditModal,
            entrySaving,
            entryActionIds = { value: [] },
            selectedEntryIds,
            batchTagName,
            batchBusy = { value: false },
            allCurrentPageSelected,
            copyMenuEntryId,
            showTagDropdown,
            revealedFields,
            resetEntryForm,
            loadEntries,
            loadTags,
            loadGroups,
            showConfirmDialog
        } = options;
        let detailRequestSequence = 0;
        let editorRequestSequence = 0;

        async function refreshEntryLists(page = currentPage.value, includeTaxonomy = true) {
            const tasks = [loadEntries(page)];
            if (includeTaxonomy) tasks.push(loadTags(), loadGroups());
            const results = await Promise.allSettled(tasks);
            return results.every(result => result.status === 'fulfilled' && result.value !== false);
        }

        async function toggleStar(entry) {
            if (entryActionIds.value.includes(entry.id)) return false;
            entryActionIds.value = [...entryActionIds.value, entry.id];
            try {
                const result = await store.toggleStar(entry);
                if (!result) return false;
                const refreshed = await refreshEntryLists(currentPage.value, false);
                if (!refreshed) showToast('收藏状态已更新，但列表刷新不完整，请稍后重试。', 'warning');
                return true;
            } catch (error) {
                showToast(error.message || '更新收藏状态失败', 'error');
                return false;
            } finally {
                entryActionIds.value = entryActionIds.value.filter(id => id !== entry.id);
            }
        }

        async function loadEntryDetail(entryId) {
            const normalizedId = String(entryId || '').trim();
            if (!normalizedId) return false;
            const request = ++detailRequestSequence;
            entryDetailTargetId.value = normalizedId;
            showEntryDetail.value = true;
            selectedEntry.value = null;
            revealedFields.value = [];
            entryDetailLoading.value = true;
            entryDetailError.value = '';
            try {
                const detail = await store.getEntry(normalizedId);
                if (request !== detailRequestSequence) return false;
                if (!detail) {
                    entryDetailError.value = '条目详情暂时无法读取，请重试。';
                    return false;
                }
                selectedEntry.value = detail;
                return true;
            } catch (error) {
                if (request !== detailRequestSequence) return false;
                entryDetailError.value = error.message || '条目详情暂时无法读取，请重试。';
                return false;
            } finally {
                if (request === detailRequestSequence) entryDetailLoading.value = false;
            }
        }

        async function viewEntry(entry) {
            return loadEntryDetail(entry?.id);
        }

        function closeEntryDetail() {
            detailRequestSequence += 1;
            showEntryDetail.value = false;
            selectedEntry.value = null;
            entryDetailTargetId.value = '';
            entryDetailLoading.value = false;
            entryDetailError.value = '';
            revealedFields.value = [];
        }

        function openEntryDetail(entry) {
            const normalizedId = String(entry?.id || '').trim();
            if (!normalizedId || !entry) return false;
            detailRequestSequence += 1;
            entryDetailTargetId.value = normalizedId;
            entryDetailLoading.value = false;
            entryDetailError.value = '';
            revealedFields.value = [];
            selectedEntry.value = entry;
            showEntryDetail.value = true;
            return true;
        }

        function disposeEntryRequests() {
            detailRequestSequence += 1;
            editorRequestSequence += 1;
            entryDetailLoading.value = false;
            entryEditLoading.value = false;
        }

        function openCreateModal() {
            resetEntryForm();
            if (filter.value === 'tag' && activeTagName.value) {
                entryForm.tags = [activeTagName.value];
            }
            if (filter.value === 'group' && activeGroupName.value) {
                entryForm.groups = [activeGroupName.value];
            }
            showCreateModal.value = true;
        }

        function applyEntryTemplate() {
            const template = entryTemplates.find(item => item.id === selectedTemplate.value);
            if (!template) return;
            entryForm.fields = template.fields.map(normalizeFieldForEdit);
            if (!entryForm.title) {
                entryForm.title = template.name;
            }
        }

        async function editEntry(entry) {
            const request = ++editorRequestSequence;
            const normalizedId = String(entry?.id || '').trim();
            if (!normalizedId) return false;
            entryEditTargetId.value = normalizedId;
            entryEditLoading.value = true;
            entryEditError.value = '';
            editingEntry.value = null;
            showEditModal.value = true;
            try {
                const fullEntry = await store.getEntry(normalizedId);
                if (request !== editorRequestSequence) return false;
                if (!fullEntry) {
                    entryEditError.value = '条目暂时无法读取，请重试。';
                    return false;
                }
                editingEntry.value = fullEntry;
                entryForm.id = fullEntry.id;
                entryForm.title = fullEntry.title;
                entryForm.url = fullEntry.url || '';
                entryForm.starred = fullEntry.starred;
                entryForm.tags = [...(fullEntry.tags || [])];
                entryForm.groups = [...(fullEntry.groups || [])];
                entryForm.fields = (fullEntry.fields || []).map(normalizeFieldForEdit);
                entryForm.remarks = fullEntry.remarks || '';
                return true;
            } catch (error) {
                if (request !== editorRequestSequence) return false;
                entryEditError.value = error.message || '条目暂时无法读取，请重试。';
                return false;
            } finally {
                if (request === editorRequestSequence) entryEditLoading.value = false;
            }
        }

        function retryEditEntry() {
            return editEntry({ id: entryEditTargetId.value });
        }

        function createEntryFromCurrentEdit() {
            if (!showEditModal.value) return;
            entryForm.id = null;
            selectedTemplate.value = '';
            editingEntry.value = null;
            showEditModal.value = false;
            showCreateModal.value = true;
        }

        function closeEntryModal() {
            editorRequestSequence += 1;
            showCreateModal.value = false;
            showEditModal.value = false;
            entryEditLoading.value = false;
            entryEditTargetId.value = '';
            entryEditError.value = '';
            resetEntryForm();
        }

        function addTag() {
            const tag = newTag.value.trim();
            if (tag && !entryForm.tags.includes(tag)) {
                entryForm.tags.push(tag);
            }
            newTag.value = '';
        }

        function addExistingTag(tag) {
            const tagName = String(tag?.name || tag || '').trim();
            if (tagName && !entryForm.tags.includes(tagName)) {
                entryForm.tags.push(tagName);
            }
        }

        function removeTag(index) {
            entryForm.tags.splice(index, 1);
        }

        async function addGroup() {
            const groupName = newGroup.value.trim();
            if (!groupName) return;
            const alreadySelected = entryForm.groups.includes(groupName);
            if (!alreadySelected) entryForm.groups.push(groupName);
            try {
                const existingGroup = groups.value.find(group => group.name === groupName);
                if (!existingGroup) {
                    const created = await store.createGroup({
                        name: groupName,
                        description: newGroupDescription.value.trim()
                    });
                    if (!created) {
                        if (!alreadySelected) {
                            entryForm.groups = entryForm.groups.filter(group => group !== groupName);
                        }
                        return false;
                    }
                    await loadGroups();
                }
                newGroup.value = '';
                newGroupDescription.value = '';
                return true;
            } catch (error) {
                if (!alreadySelected) {
                    entryForm.groups = entryForm.groups.filter(group => group !== groupName);
                }
                showToast(error.message || '创建密码组失败，请重试', 'error');
                return false;
            }
        }

        function addExistingGroup(group) {
            const groupName = String(group?.name || group || '').trim();
            if (groupName && !entryForm.groups.includes(groupName)) {
                entryForm.groups.push(groupName);
            }
        }

        function removeGroup(index) {
            entryForm.groups.splice(index, 1);
        }

        function addField() {
            entryForm.fields.push({ name: '', value: '', copyable: true, hidden: false });
        }

        function removeField(index) {
            entryForm.fields.splice(index, 1);
        }

        async function saveEntry() {
            if (entrySaving.value) return;
            const title = entryForm.title.trim();
            if (!title) {
                showToast('请输入标题', 'error');
                return;
            }
            entrySaving.value = true;
            try {
                if (newTag.value.trim()) {
                    addTag();
                }
                if (newGroup.value.trim()) {
                    const groupAdded = await addGroup();
                    if (groupAdded === false) return;
                }

                const data = {
                    title,
                    url: (entryForm.url || '').trim(),
                    starred: entryForm.starred,
                    tags: Array.from(new Set(entryForm.tags.map(tag => String(tag).trim()).filter(Boolean))),
                    groups: Array.from(new Set(entryForm.groups.map(group => String(group).trim()).filter(Boolean))),
                    fields: entryForm.fields.map(normalizeFieldForEdit).filter(field => field.name),
                    remarks: entryForm.remarks
                };

                const result = showEditModal.value && entryForm.id
                    ? await store.updateEntry(entryForm.id, data)
                    : await store.createEntry(data);

                if (result) {
                    closeEntryModal();
                    const refreshed = await refreshEntryLists();
                    if (!refreshed) showToast('条目已保存，但相关列表刷新不完整，请稍后重试。', 'warning');
                }
            } catch (error) {
                showToast(error.message || '保存条目失败', 'error');
            } finally {
                entrySaving.value = false;
            }
        }

        function confirmDeleteEntry(entry) {
            showConfirmDialog('删除条目', `确认将「${entry.title}」移至回收站？`, async () => {
                const success = await store.deleteEntry(entry.id);
                if (!success) return false;
                closeEntryDetail();
                selectedEntryIds.value = selectedEntryIds.value.filter(id => id !== entry.id);
                const refreshed = await refreshEntryLists();
                if (!refreshed) showToast('条目已移至回收站，但列表刷新不完整，请稍后重试。', 'warning');
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
                const result = await store.batchDelete(selectedEntryIds.value);
                if (!result) return false;
                clearSelection();
                const refreshed = await refreshEntryLists(1);
                if (!refreshed) showToast('批量删除已完成，但列表刷新不完整，请稍后重试。', 'warning');
            });
        }

        async function batchStarSelected(starred) {
            if (batchBusy.value || selectedEntryIds.value.length === 0) return;
            batchBusy.value = true;
            try {
                const result = await store.batchStar(selectedEntryIds.value, starred);
                if (!result) return;
                clearSelection();
                const refreshed = await refreshEntryLists(currentPage.value, false);
                if (!refreshed) showToast('收藏状态已更新，但列表刷新不完整，请稍后重试。', 'warning');
            } catch (error) {
                showToast(error.message || '批量更新收藏状态失败，请重试', 'error');
            } finally {
                batchBusy.value = false;
            }
        }

        async function batchAddTagSelected() {
            const tag = batchTagName.value.trim();
            if (selectedEntryIds.value.length === 0 || !tag) return;
            showConfirmDialog('批量加标签', `确认给已选 ${selectedEntryIds.value.length} 个条目添加标签「${tag}」？`, async () => {
                if (batchBusy.value) return false;
                batchBusy.value = true;
                try {
                    const result = await store.batchUpdateTags(selectedEntryIds.value, [tag], []);
                    if (!result) return false;
                    batchTagName.value = '';
                    const refreshed = await refreshEntryLists(currentPage.value, true);
                    if (!refreshed) showToast('标签已更新，但列表刷新不完整，请稍后重试。', 'warning');
                } finally {
                    batchBusy.value = false;
                }
            });
        }

        async function batchRemoveTagSelected() {
            const tag = batchTagName.value.trim();
            if (selectedEntryIds.value.length === 0 || !tag) return;
            showConfirmDialog('批量移除标签', `确认从已选 ${selectedEntryIds.value.length} 个条目移除标签「${tag}」？`, async () => {
                if (batchBusy.value) return false;
                batchBusy.value = true;
                try {
                    const result = await store.batchUpdateTags(selectedEntryIds.value, [], [tag]);
                    if (!result) return false;
                    batchTagName.value = '';
                    const refreshed = await refreshEntryLists(currentPage.value, true);
                    if (!refreshed) showToast('标签已更新，但列表刷新不完整，请稍后重试。', 'warning');
                } finally {
                    batchBusy.value = false;
                }
            });
        }

        async function openUrl(url) {
            return openExternalUrl(url);
        }

        function toggleCopyMenu(entryId) {
            copyMenuEntryId.value = copyMenuEntryId.value === entryId ? null : entryId;
        }

        async function copyField(entryId, field, fieldIndex = -1) {
            try {
                const entryDetail = await store.getEntry(entryId);
                if (entryDetail) {
                    const targetField = Number.isInteger(fieldIndex) && fieldIndex >= 0
                        ? entryDetail.fields[fieldIndex]
                        : entryDetail.fields.find(item => item.name === field.name);
                    if (targetField) {
                        const copied = await copyToClipboard(targetField.value);
                        showToast(copied ? `已复制 ${field.name}` : '复制失败，请手动复制', copied ? 'success' : 'error');
                    } else {
                        showToast('字段已不存在，请刷新后重试', 'warning');
                    }
                } else {
                    showToast('条目详情读取失败，无法复制', 'error');
                }
            } catch (error) {
                showToast('复制失败', 'error');
            }
            copyMenuEntryId.value = null;
        }

        async function copyAllFields(entryId) {
            try {
                const entryDetail = await store.getEntry(entryId);
                if (entryDetail) {
                    const text = entryDetail.fields
                        .filter(field => field.copyable)
                        .map(field => `${field.name}: ${field.value}`)
                        .join('\n');
                    const copied = await copyToClipboard(text);
                    showToast(copied ? '已复制全部字段' : '复制失败，请手动复制', copied ? 'success' : 'error');
                } else {
                    showToast('条目详情读取失败，无法复制', 'error');
                }
            } catch (error) {
                showToast('复制失败', 'error');
            }
            copyMenuEntryId.value = null;
        }

        function handleDocumentClick(event) {
            const target = event.target;
            if (!(target instanceof Element)) return;
            if (!target.closest('.copy-dropdown')) {
                copyMenuEntryId.value = null;
            }
            if (!target.closest('.tag-filter')) {
                showTagDropdown.value = false;
            }
        }

        function goToPage(page) {
            if (page < 1 || page > totalPages.value) return;
            return loadEntries(page);
        }

        return {
            toggleStar,
            viewEntry,
            loadEntryDetail,
            openEntryDetail,
            retryEditEntry,
            closeEntryDetail,
            disposeEntryRequests,
            openCreateModal,
            applyEntryTemplate,
            editEntry,
            createEntryFromCurrentEdit,
            closeEntryModal,
            addTag,
            addExistingTag,
            removeTag,
            addGroup,
            addExistingGroup,
            removeGroup,
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
            handleDocumentClick,
            goToPage
        };
    }

    window.SecretBaseEntryController = {
        createEntryController
    };
})();
