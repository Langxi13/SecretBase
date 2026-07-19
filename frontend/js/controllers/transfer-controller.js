/**
 * 加密/明文导入导出与导入预览确认流程。
 */
(function () {
    function createTransferController(options) {
        const {
            api,
            showToast,
            showConfirmDialog,
            showPromptDialog = async () => null,
            friendlyApiMessage,
            downloadProtectedFile,
            loadAllData,
            importConflictStrategy,
            importConflictMessage,
            transferBusy = { value: false },
            transferError = { value: '' },
            showImportConflicts,
            importConflicts,
            showImportReport,
            importReport,
            showImportPreview,
            importPreview,
            lastImportPlainFile,
            importPreviewSelectedIds,
            lastImportSelectedIds,
            importConflictResolutions,
            lastImportConflictResolutions
        } = options;

        function beginTransfer() {
            if (transferBusy.value) return false;
            transferBusy.value = true;
            transferError.value = '';
            return true;
        }

        function endTransfer() {
            transferBusy.value = false;
        }

        function showImportResultReport(resultData = {}, fallbackConflictCount = 0, refreshIncomplete = false) {
                importReport.value = {
                importedCount: resultData.imported_count ?? 0,
                createdCount: resultData.created_count ?? 0,
                overwrittenCount: resultData.overwritten_count ?? 0,
                skippedCount: resultData.skipped_count ?? 0,
                conflictCount: resultData.conflicts?.length ?? fallbackConflictCount,
                selectedCount: lastImportSelectedIds.value.length,
                refreshIncomplete
            };
            showImportReport.value = true;
        }

        async function exportEncrypted() {
            if (!beginTransfer()) return;
            try {
                await downloadProtectedFile({
                    api,
                    showToast,
                    path: '/export/encrypted',
                    body: {},
                    filename: `secretbase-backup-${new Date().toISOString().slice(0, 10)}.enc`
                });
                transferError.value = '';
            } finally {
                endTransfer();
            }
        }

        function exportPlain() {
            showConfirmDialog('导出明文', '明文包含所有密码，是否继续？', async () => {
                if (!beginTransfer()) return false;
                try {
                    await downloadProtectedFile({
                        api,
                        showToast,
                        path: '/export/plain',
                        body: { confirm: true },
                        filename: `secretbase-backup-${new Date().toISOString().slice(0, 10)}.json`,
                        throwOnError: true
                    });
                    transferError.value = '';
                    return true;
                } catch (error) {
                    transferError.value = friendlyApiMessage(error, '明文导出失败');
                    throw new Error(transferError.value);
                } finally {
                    endTransfer();
                }
            });
        }

        async function importEncryptedFile(event) {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (!file) return;

            showConfirmDialog('导入加密备份', '导入会替换当前数据文件，系统会先自动备份当前数据。确认继续？', async () => {
                if (!beginTransfer()) return false;
                try {
                    let result;
                    try {
                        result = await api.upload('/import/encrypted', file);
                    } catch (error) {
                        if (!error.data?.needs_password) throw error;
                        const password = await showPromptDialog({
                            title: '输入备份主密码',
                            message: '该加密备份可能来自旧版本或其他密码库。请输入这份备份原主人的主密码。',
                            placeholder: '备份对应的主密码',
                            type: 'password',
                            confirmLabel: '继续导入',
                            maxLength: 128
                        });
                        if (password === null) return false;
                        result = await api.upload('/import/encrypted', file, { password });
                    }
                    if (!result.success) throw new Error(result.message || '导入失败');
                    transferError.value = '';
                    const refreshed = await loadAllData();
                    showToast(
                        refreshed === false
                            ? `${result.message || '导入成功'}，但列表刷新不完整，请稍后重试。`
                            : (result.message || '导入成功'),
                        refreshed === false ? 'warning' : 'success'
                    );
                } catch (error) {
                    throw new Error(friendlyApiMessage(error, '导入失败'));
                } finally {
                    endTransfer();
                }
            });
        }

        async function importPlainFile(event) {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (!file) return;
            lastImportPlainFile.value = file;
            if (!beginTransfer()) return;

            try {
                const preview = await api.upload('/import/plain/preview', file);
                importPreview.value = preview.data;
                importPreviewSelectedIds.value = (preview.data.entries || []).map(entry => entry.id);
                importConflictResolutions.value = Object.fromEntries(
                    (preview.data.entries || [])
                        .filter(entry => entry.is_conflict)
                        .map(entry => [entry.id, importConflictStrategy.value === 'ask' ? 'skip' : importConflictStrategy.value])
                );
                showImportPreview.value = true;
            } catch (error) {
                transferError.value = error.message || '导入预览失败';
                showToast(transferError.value, 'error');
            } finally {
                endTransfer();
            }
        }

        async function confirmImportPlain() {
            if (!lastImportPlainFile.value) return;
            if (!beginTransfer()) return;
            if (importPreview.value?.entries?.length && importPreviewSelectedIds.value.length === 0) {
                showToast('请至少选择一个要导入的条目', 'warning');
                endTransfer();
                return;
            }
            const selectedIds = [...importPreviewSelectedIds.value];
            lastImportSelectedIds.value = selectedIds;
            const conflictResolutions = Object.fromEntries(
                Object.entries(importConflictResolutions.value)
                    .filter(([id]) => selectedIds.includes(id))
            );
            const selectedConflictCount = (importPreview.value?.entries || [])
                .filter(entry => entry.is_conflict && selectedIds.includes(entry.id))
                .length;
            lastImportConflictResolutions.value = conflictResolutions;
            try {
                const result = await api.upload('/import/plain', lastImportPlainFile.value, {
                    conflict_strategy: importConflictStrategy.value,
                    selected_entry_ids: JSON.stringify(selectedIds),
                    conflict_resolutions: JSON.stringify(conflictResolutions)
                });
                if (!result.success) throw new Error(result.message || '导入失败');
                importConflictMessage.value = '';
                transferError.value = '';
                const refreshed = await loadAllData();
                showToast(
                    refreshed === false
                        ? `${result.message || '导入成功'}，但列表刷新不完整，请稍后重试。`
                        : (result.message || '导入成功'),
                    refreshed === false ? 'warning' : 'success'
                );
                closeImportPreview();
                lastImportPlainFile.value = null;
                showImportResultReport(result.data, selectedConflictCount, refreshed === false);
            } catch (error) {
                const conflicts = error.data?.conflicts || [];
                if (conflicts.length > 0) {
                    importConflictMessage.value = `发现 ${conflicts.length} 个冲突：${conflicts.slice(0, 3).map(conflict => conflict.import_title).join('、')}`;
                    importConflicts.value = conflicts;
                    closeImportPreview();
                    showImportConflicts.value = true;
                }
                transferError.value = error.message || '导入失败';
                showToast(error.message || '导入失败', 'error');
            } finally {
                endTransfer();
            }
        }

        async function retryImportPlain(strategy) {
            if (!lastImportPlainFile.value) {
                showToast('请重新选择导入文件', 'error');
                closeImportConflicts();
                return;
            }
            if (!beginTransfer()) return;

            try {
                const unresolvedConflictCount = importConflicts.value.length;
                const result = await api.upload('/import/plain', lastImportPlainFile.value, {
                    conflict_strategy: strategy,
                    selected_entry_ids: JSON.stringify(lastImportSelectedIds.value),
                    conflict_resolutions: JSON.stringify(lastImportConflictResolutions.value)
                });
                if (!result.success) throw new Error(result.message || '导入失败');
                importConflictStrategy.value = strategy;
                importConflictMessage.value = '';
                closeImportConflicts();
                lastImportPlainFile.value = null;
                const refreshed = await loadAllData();
                showToast(
                    refreshed === false
                        ? `${result.message || '导入成功'}，但列表刷新不完整，请稍后重试。`
                        : (result.message || '导入成功'),
                    refreshed === false ? 'warning' : 'success'
                );
                showImportResultReport(result.data, unresolvedConflictCount, refreshed === false);
            } catch (error) {
                transferError.value = error.message || '导入失败';
                showToast(transferError.value, 'error');
            } finally {
                endTransfer();
            }
        }

        function closeImportConflicts() {
            showImportConflicts.value = false;
            importConflicts.value = [];
        }

        function closeImportPreview() {
            showImportPreview.value = false;
            importPreview.value = null;
            importPreviewSelectedIds.value = [];
            importConflictResolutions.value = {};
        }

        function isImportPreviewSelected(id) {
            return importPreviewSelectedIds.value.includes(id);
        }

        function toggleImportPreviewSelection(id) {
            if (isImportPreviewSelected(id)) {
                importPreviewSelectedIds.value = importPreviewSelectedIds.value.filter(item => item !== id);
            } else {
                importPreviewSelectedIds.value = [...importPreviewSelectedIds.value, id];
            }
        }

        function selectAllImportPreviewEntries() {
            importPreviewSelectedIds.value = (importPreview.value?.entries || []).map(entry => entry.id);
        }

        function clearImportPreviewSelection() {
            importPreviewSelectedIds.value = [];
        }

        function setImportConflictResolution(id, strategy) {
            importConflictResolutions.value = {
                ...importConflictResolutions.value,
                [id]: strategy
            };
        }

        return {
            exportEncrypted,
            exportPlain,
            importEncryptedFile,
            importPlainFile,
            confirmImportPlain,
            retryImportPlain,
            closeImportConflicts,
            closeImportPreview,
            isImportPreviewSelected,
            toggleImportPreviewSelection,
            selectAllImportPreviewEntries,
            clearImportPreviewSelection,
            setImportConflictResolution
        };
    }

    window.SecretBaseTransferController = {
        createTransferController
    };
})();
