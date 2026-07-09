/**
 * 备份中心、下载和恢复向导行为。
 */
(function () {
    function createBackupController(options) {
        const {
            api,
            showToast,
            showConfirmDialog,
            friendlyApiMessage,
            downloadProtectedFile,
            backups,
            highlightedBackupFilename,
            backupListLoading,
            showBackupCenter,
            backupPages,
            creatingBackup,
            restoringBackupFilename,
            downloadingBackupFilename,
            restoreWizard,
            loadAllData
        } = options;

        async function loadBackups() {
            if (backupListLoading.value) return;
            backupListLoading.value = true;
            try {
                const result = await api.get('/backups');
                backups.value = result.data.items || [];
            } catch (error) {
                showToast(error.message || '备份列表加载失败', 'error');
            } finally {
                backupListLoading.value = false;
            }
        }

        function openBackupCenter() {
            showBackupCenter.value = true;
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
                showToast(result.message || '已创建手动备份', 'success');
                await loadBackups();
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
                            showToast(friendlyApiMessage(error, '明文 JSON 下载失败'), 'error');
                            return;
                        }
                        const password = window.prompt('该备份需要对应的主密码才能下载明文 JSON。') || '';
                        if (!password) return;
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
                            showToast(friendlyApiMessage(passwordError, '明文 JSON 下载失败'), 'error');
                        }
                    }
                } finally {
                    downloadingBackupFilename.value = '';
                }
            });
        }

        function openRestoreWizard(backup) {
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
            restoreWizard.visible = false;
            restoreWizard.backup = null;
        }

        async function loadRestoreSummary() {
            if (!restoreWizard.backup || restoreWizard.loadingSummary) return;
            restoreWizard.loadingSummary = true;
            restoreWizard.error = '';
            try {
                const path = `/backups/${encodeURIComponent(restoreWizard.backup.filename)}/summary`;
                const result = restoreWizard.password
                    ? await api.post(path, { password: restoreWizard.password })
                    : await api.get(path);
                restoreWizard.summary = result.data;
                restoreWizard.needsPassword = false;
                restoreWizard.error = '';
            } catch (error) {
                if (error.data?.needs_password) {
                    restoreWizard.needsPassword = true;
                    restoreWizard.error = '该备份需要输入对应的主密码后才能读取概况。';
                } else {
                    restoreWizard.error = friendlyApiMessage(error, '备份概况读取失败');
                }
            } finally {
                restoreWizard.loadingSummary = false;
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
            try {
                const body = restoreWizard.password ? { password: restoreWizard.password } : {};
                const result = await api.post(`/backups/${encodeURIComponent(restoreWizard.backup.filename)}/restore`, body);
                showToast(result.message || '备份已恢复', 'success');
                restoreWizard.visible = false;
                restoreWizard.backup = null;
                await loadAllData();
                await loadBackups();
            } catch (error) {
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
