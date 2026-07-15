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
            currentPage,
            loadTags
        } = options;

        async function filterByTag(tagName) {
            store.setFilter('entryIds', []);
            listContextNotice.value = '';
            store.setFilter('tag', tagName);
            store.setFilter('group', null);
            store.setFilter('starred', false);
            filter.value = 'tag';
            activeTagName.value = tagName;
            activeGroupName.value = '';
            showTagDropdown.value = false;
            showTagBrowser.value = false;
            await loadEntries(1);
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
            showConfirmDialog('删除标签', `确认删除标签 "${tag.name}"？`, async () => {
                const deleted = await store.deleteTag(tag.name);
                if (deleted) {
                    selectedManagedTagNames.value = selectedManagedTagNames.value.filter(name => name !== tag.name);
                    await Promise.all([loadTags(), loadEntries(currentPage.value)]);
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
            resetTagEditorForm();
            showTagEditorModal.value = true;
        }

        function closeTagEditorModal() {
            showTagEditorModal.value = false;
            resetTagEditorForm();
        }

        function closeTagManager() {
            showTagManager.value = false;
            closeTagEditorModal();
        }

        async function createTagFromManager() {
            const name = tagEditorForm.name.trim();
            if (!name) {
                showToast('请输入标签名称', 'warning');
                return;
            }
            const created = await store.createTag({
                name,
                description: tagEditorForm.description.trim(),
                color: tagEditorForm.color
            });
            if (created) {
                closeTagEditorModal();
                await loadTags();
            }
        }

        async function saveManagedTag() {
            if (tagEditorForm.mode !== 'edit') {
                await createTagFromManager();
                return;
            }
            const name = tagEditorForm.name.trim();
            if (!name) {
                showToast('请输入标签名称', 'warning');
                return;
            }
            const updated = await store.updateTag(tagEditorForm.originalName, {
                name,
                description: tagEditorForm.description.trim(),
                color: tagEditorForm.color
            });
            if (updated) {
                closeTagEditorModal();
                await Promise.all([loadTags(), loadEntries(currentPage.value)]);
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
            const names = [...selectedManagedTagNames.value];
            if (names.length === 0) {
                showToast('请选择要删除的标签', 'warning');
                return;
            }
            showConfirmDialog('批量删除标签', `确认删除已选 ${names.length} 个标签？这些标签会从相关条目中移除。`, async () => {
                const result = await store.batchDeleteTags(names);
                if (result) {
                    selectedManagedTagNames.value = [];
                    await Promise.all([loadTags(), loadEntries(currentPage.value)]);
                    goToTagManagerPage(tagManagerPage.value);
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
