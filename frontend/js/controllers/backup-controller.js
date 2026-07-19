/**
 * 备份中心、下载和恢复向导行为。
 */
(function () {
    function createBackupController(options) {
        const {
            api,
            showToast,
            showConfirmDialog,
            showPromptDialog = async () => null,
            friendlyApiMessage,
            downloadProtectedFile,
            backups,
            backupError = { value: '' },
            highlightedBackupFilename,
            backupListLoading,
            showBackupCenter,
            backupPages,
            creatingBackup,
            restoringBackupFilename,
            downloadingBackupFilename,
            restoreWizard,
            loadAllData,
            locked
        } = options;
        let restoreRequestSequence = 0;
        let listRequestSequence = 0;

        async function loadBackups() {
            if (backupListLoading.value || locked?.value) return false;
            const request = ++listRequestSequence;
            backupListLoading.value = true;
            backupError.value = '';
            try {
                const result = await api.get('/backups');
                if (request !== listRequestSequence || locked?.value) return false;
                backups.value = result.data.items || [];
                return true;
            } catch (error) {
                if (
                    request !== listRequestSequence
                    || error?.code === 'SESSION_INVALIDATED'
                    || locked?.value
                ) return false;
                backupError.value = error.message || '备份列表加载失败，请重试。';
                return false;
            } finally {
                if (request === listRequestSequence) backupListLoading.value = false;
            }
        }

        function openBackupCenter() {
            if (showBackupCenter.value) return;
            listRequestSequence += 1;
            showBackupCenter.value = true;
        }

        function closeBackupCenter() {
            listRequestSequence += 1;
            showBackupCenter.value = false;
            backupListLoading.value = false;
            backupError.value = '';
        }

        function setBackupPage(type, page) {
            backupPages[type] = Math.max(1, page);
        }

        async function createManualBackup() {
            if (creatingBackup.value) return;
            creatingBackup.value = true;
            try {
                const result = await api.post('/backups', {});
                highlightedBackupFilename.value = result.data?.filename || '';
                const refreshed = await loadBackups();
                showToast(
                    refreshed === false
                        ? `${result.message || '已创建手动备份'}，但备份列表刷新不完整，请稍后重试。`
                        : (result.message || '已创建手动备份'),
                    refreshed === false ? 'warning' : 'success'
                );
            } catch (error) {
                showToast(friendlyApiMessage(error, '创建备份失败'), 'error');
            } finally {
                creatingBackup.value = false;
            }
        }

        function backupDisplayName(backup) {
            return backup.display_name || backup.filename;
        }

        async function downloadBackupFile(backup, kind) {
            if (downloadingBackupFilename.value) return;
            if (kind === 'encrypted') {
                downloadingBackupFilename.value = backup.filename;
                try {
                    await downloadProtectedFile({
                        api,
                        showToast,
                        path: `/backups/${encodeURIComponent(backup.filename)}/download/encrypted`,
                        filename: backup.download_name_encrypted || backup.filename,
                        method: 'GET'
                    });
                } catch (error) {
                    showToast(friendlyApiMessage(error, '备份下载失败'), 'error');
                } finally {
                    downloadingBackupFilename.value = '';
                }
                return;
            }

            showConfirmDialog('下载明文 JSON', `明文 JSON 会包含这个备份里的所有密码和密钥。\n\n备份：${backupDisplayName(backup)}\n\n确认下载？`, async () => {
                downloadingBackupFilename.value = backup.filename;
                try {
                    try {
                        await downloadProtectedFile({
                            api,
                            showToast,
                            path: `/backups/${encodeURIComponent(backup.filename)}/download/plain`,
                            body: { confirm: true },
                            filename: backup.download_name_plain || backup.filename.replace(/\.bak$/, '.json'),
                            throwOnError: true
                        });
                    } catch (error) {
                        if (!error.data?.needs_password) {
                            throw new Error(friendlyApiMessage(error, '明文 JSON 下载失败'));
                        }
                        const password = await showPromptDialog({
                            title: '输入备份主密码',
                            message: '该备份使用创建时的主密码保护。请输入对应主密码后继续导出明文 JSON。',
                            placeholder: '备份对应的主密码',
                            type: 'password',
                            confirmLabel: '验证并下载',
                            maxLength: 128
                        });
                        if (password === null) return false;
                        try {
                            await downloadProtectedFile({
                                api,
                                showToast,
                                path: `/backups/${encodeURIComponent(backup.filename)}/download/plain`,
                                body: { confirm: true, password },
                                filename: backup.download_name_plain || backup.filename.replace(/\.bak$/, '.json'),
                                throwOnError: true
                            });
                        } catch (passwordError) {
                            throw new Error(friendlyApiMessage(passwordError, '明文 JSON 下载失败'));
                        }
                    }
                } finally {
                    downloadingBackupFilename.value = '';
                }
            });
        }

        function openRestoreWizard(backup) {
            restoreRequestSequence += 1;
            restoreWizard.visible = true;
            restoreWizard.step = 1;
            restoreWizard.backup = backup;
            restoreWizard.summary = null;
            restoreWizard.password = '';
            restoreWizard.needsPassword = false;
            restoreWizard.confirmation = '';
            restoreWizard.loadingSummary = false;
            restoreWizard.restoring = false;
            restoreWizard.error = '';
            loadRestoreSummary();
        }

        function closeRestoreWizard() {
            if (restoreWizard.restoring) return;
            restoreRequestSequence += 1;
            restoreWizard.visible = false;
            restoreWizard.backup = null;
            restoreWizard.summary = null;
            restoreWizard.password = '';
            restoreWizard.confirmation = '';
            restoreWizard.needsPassword = false;
            restoreWizard.loadingSummary = false;
            restoreWizard.error = '';
        }

        async function loadRestoreSummary() {
            if (!restoreWizard.backup || restoreWizard.loadingSummary) return;
            const request = ++restoreRequestSequence;
            const backupFilename = restoreWizard.backup.filename;
            restoreWizard.loadingSummary = true;
            restoreWizard.error = '';
            try {
                const path = `/backups/${encodeURIComponent(restoreWizard.backup.filename)}/summary`;
                const result = restoreWizard.password
                    ? await api.post(path, { password: restoreWizard.password })
                    : await api.get(path);
                if (
                    request !== restoreRequestSequence
                    || !restoreWizard.visible
                    || restoreWizard.backup?.filename !== backupFilename
                    || locked?.value
                ) return;
                restoreWizard.summary = result.data;
                restoreWizard.needsPassword = false;
                restoreWizard.error = '';
            } catch (error) {
                if (
                    request !== restoreRequestSequence
                    || !restoreWizard.visible
                    || restoreWizard.backup?.filename !== backupFilename
                    || error?.code === 'SESSION_INVALIDATED'
                    || locked?.value
                ) return;
                if (error.data?.needs_password) {
                    restoreWizard.needsPassword = true;
                    restoreWizard.error = '该备份需要输入对应的主密码后才能读取概况。';
                } else {
                    restoreWizard.error = friendlyApiMessage(error, '备份概况读取失败');
                }
            } finally {
                if (request === restoreRequestSequence) restoreWizard.loadingSummary = false;
            }
        }

        function restoreWizardNext() {
            if (restoreWizard.step === 1 && !restoreWizard.summary) {
                showToast('请先读取备份概况', 'warning');
                return;
            }
            restoreWizard.step = Math.min(3, restoreWizard.step + 1);
        }

        function restoreWizardBack() {
            restoreWizard.step = Math.max(1, restoreWizard.step - 1);
        }

        async function restoreBackup(backup) {
            openRestoreWizard(backup);
        }

        async function confirmRestoreBackup() {
            if (!restoreWizard.backup || restoreWizard.confirmation !== 'RESTORE') {
                showToast('请输入 RESTORE 后再恢复', 'warning');
                return;
            }
            restoreWizard.restoring = true;
            restoringBackupFilename.value = restoreWizard.backup.filename;
            const backupFilename = restoreWizard.backup.filename;
            const request = ++restoreRequestSequence;
            try {
                const body = restoreWizard.password ? { password: restoreWizard.password } : {};
                const result = await api.post(`/backups/${encodeURIComponent(backupFilename)}/restore`, body);
                if (
                    request !== restoreRequestSequence
                    || !restoreWizard.visible
                    || restoreWizard.backup?.filename !== backupFilename
                    || locked?.value
                ) return;
                // 恢复接口已经成功，后续页面刷新属于独立步骤，不能把刷新失败误报成恢复失败。
                restoreWizard.visible = false;
                restoreWizard.backup = null;
                restoreWizard.summary = null;
                restoreWizard.password = '';
                restoreWizard.confirmation = '';
                restoreWizard.needsPassword = false;
                restoreWizard.error = '';
                showToast(result.message || '备份已恢复', 'success');
                const refreshed = await Promise.allSettled([loadAllData(), loadBackups()]);
                if (
                    refreshed.some(item => item.status === 'rejected' || item.value === false)
                    && !locked?.value
                ) {
                    showToast('备份已恢复，但界面刷新不完整，请重新打开相关列表重试。', 'warning');
                }
            } catch (error) {
                if (
                    request !== restoreRequestSequence
                    || error?.code === 'SESSION_INVALIDATED'
                    || locked?.value
                ) return;
                restoreWizard.error = friendlyApiMessage(error, '备份恢复失败');
                showToast(restoreWizard.error, 'error');
            } finally {
                restoreWizard.restoring = false;
                restoringBackupFilename.value = '';
            }
        }

        return {
            loadBackups,
            openBackupCenter,
            closeBackupCenter,
            setBackupPage,
            createManualBackup,
            backupDisplayName,
            downloadBackupFile,
            restoreBackup,
            closeRestoreWizard,
            loadRestoreSummary,
            restoreWizardNext,
            restoreWizardBack,
            confirmRestoreBackup
        };
    }

    window.SecretBaseBackupController = {
        createBackupController
    };
})();
