/**
 * 条目详情、编辑表单、批量操作与复制菜单行为。
 */
(function () {
    function createEntryController(options) {
        const {
            api,
            store,
            showToast,
            copyToClipboard,
            normalizeFieldForEdit,
            entries,
            currentPage,
            totalPages,
            selectedEntry,
            editingEntry,
            entryForm,
            entryTemplates,
            selectedTemplate,
            newTag,
            newGroup,
            newGroupDescription,
            groups,
            showCreateModal,
            showEditModal,
            showOnboarding,
            importingSamples,
            selectedEntryIds,
            batchTagName,
            allCurrentPageSelected,
            copyMenuEntryId,
            showTagDropdown,
            revealedFields,
            resetEntryForm,
            loadEntries,
            loadTags,
            loadGroups,
            loadAllData,
            showConfirmDialog
        } = options;

        async function toggleStar(entry) {
            await store.toggleStar(entry);
            await loadEntries(currentPage.value);
        }

        async function viewEntry(entry) {
            selectedEntry.value = await store.getEntry(entry.id);
            revealedFields.value = [];
        }

        function closeEntryDetail() {
            selectedEntry.value = null;
        }

        function openCreateModal() {
            resetEntryForm();
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
                            { name: '账号', value: 'demo-cloud-user', copyable: true, hidden: false },
                            { name: '密码', value: 'Demo-Password-123!', copyable: true, hidden: true }
                        ],
                        remarks: '这是示例数据，可删除。用于体验字段复制、星标和标签筛选。'
                    },
                    {
                        title: '示例：测试邮箱',
                        url: 'https://example.invalid/mail',
                        starred: false,
                        tags: ['示例', '邮箱'],
                        fields: [
                            { name: '邮箱', value: 'demo@example.invalid', copyable: true, hidden: false },
                            { name: '恢复码', value: 'DEMO-CODE-0000', copyable: true, hidden: true }
                        ],
                        remarks: '这是示例数据，可删除。这里不包含任何真实账号。'
                    },
                    {
                        title: '示例：本地开发密钥',
                        url: '',
                        starred: false,
                        tags: ['示例', '开发'],
                        fields: [
                            { name: 'API Key', value: 'demo_api_key_not_real', copyable: true, hidden: true },
                            { name: '环境', value: 'local-demo', copyable: false, hidden: false }
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

        async function editEntry(entry) {
            const fullEntry = await store.getEntry(entry.id);
            if (!fullEntry) return;

            editingEntry.value = fullEntry;
            entryForm.id = fullEntry.id;
            entryForm.title = fullEntry.title;
            entryForm.url = fullEntry.url || '';
            entryForm.starred = fullEntry.starred;
            entryForm.tags = [...fullEntry.tags];
            entryForm.groups = [...(fullEntry.groups || [])];
            entryForm.fields = fullEntry.fields.map(normalizeFieldForEdit);
            entryForm.remarks = fullEntry.remarks || '';
            showEditModal.value = true;
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
            showCreateModal.value = false;
            showEditModal.value = false;
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
            if (!entryForm.groups.includes(groupName)) {
                entryForm.groups.push(groupName);
            }
            const existingGroup = groups.value.find(group => group.name === groupName);
            if (!existingGroup) {
                await store.createGroup({
                    name: groupName,
                    description: newGroupDescription.value.trim()
                });
                await loadGroups();
            }
            newGroup.value = '';
            newGroupDescription.value = '';
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
            if (!entryForm.title) {
                showToast('请输入标题', 'error');
                return;
            }
            if (newTag.value.trim()) {
                addTag();
            }
            if (newGroup.value.trim()) {
                await addGroup();
            }

            const data = {
                title: entryForm.title,
                url: entryForm.url || '',
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
                await loadEntries(currentPage.value);
                await Promise.all([loadTags(), loadGroups()]);
            }
        }

        function confirmDeleteEntry(entry) {
            showConfirmDialog('删除条目', `确认将「${entry.title}」移至回收站？`, async () => {
                const success = await store.deleteEntry(entry.id);
                if (!success) return;
                selectedEntry.value = null;
                selectedEntryIds.value = selectedEntryIds.value.filter(id => id !== entry.id);
                await loadEntries(currentPage.value);
                await Promise.all([loadTags(), loadGroups()]);
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
                await Promise.all([loadTags(), loadGroups()]);
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

        async function openUrl(url) {
            return openExternalUrl(url);
        }

        function toggleCopyMenu(entryId) {
            copyMenuEntryId.value = copyMenuEntryId.value === entryId ? null : entryId;
        }

        async function copyField(entryId, field) {
            try {
                const entryDetail = await store.getEntry(entryId);
                if (entryDetail) {
                    const targetField = entryDetail.fields.find(item => item.name === field.name);
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
            closeEntryDetail,
            openCreateModal,
            applyEntryTemplate,
            skipOnboarding,
            importSampleData,
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
