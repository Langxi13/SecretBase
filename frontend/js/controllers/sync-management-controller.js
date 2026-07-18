/**
 * 同步恢复、断开和危险操作的界面控制。
 */
(function () {
    function createSyncManagementController({
        api,
        state,
        showToast,
        showConfirmDialog,
        copyToClipboard,
        lifecycle,
        applySyncStatus,
        epochIsCurrent,
        responseBelongsToCurrentSession
    }) {
        function openSyncRecovery(mode = 'reveal') {
            state.syncRecoveryMode.value = ['rotate', 'migrate', 'compact'].includes(mode) ? mode : 'reveal';
            state.syncMasterPassword.value = '';
            state.syncCompactConfirmation.value = '';
            state.syncRecoveryMaterial.value = null;
            state.syncError.value = '';
            state.showSyncRecovery.value = true;
        }

        function closeSyncRecovery() {
            if (state.syncRecoveryBusy.value) return;
            state.showSyncRecovery.value = false;
            state.syncMasterPassword.value = '';
            state.syncCompactConfirmation.value = '';
            state.syncRecoveryMaterial.value = null;
        }

        async function submitSyncRecovery() {
            if (state.syncRecoveryBusy.value) return;
            state.syncRecoveryBusy.value = true;
            state.syncError.value = '';
            const epoch = lifecycle.currentEpoch();
            try {
                const mode = state.syncRecoveryMode.value;
                const path = mode === 'rotate'
                    ? '/sync/rotate-key'
                    : mode === 'migrate'
                        ? '/sync/migrate-v2'
                        : mode === 'compact' ? '/sync/compact' : '/sync/recovery-code';
                const payload = { password: state.syncMasterPassword.value };
                if (mode === 'compact') payload.confirmation = state.syncCompactConfirmation.value.trim();
                const result = await api.post(path, payload);
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncRecoveryMaterial.value = result.data;
                applySyncStatus(result.data?.status);
                if (['rotate', 'migrate', 'compact'].includes(mode)) {
                    showToast(result.message || (mode === 'compact' ? '同步历史已压缩' : '同步设置已更新'), 'success');
                }
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncError.value = error.message || '同步恢复信息读取失败';
            } finally {
                if (epochIsCurrent(epoch)) {
                    state.syncMasterPassword.value = '';
                    state.syncRecoveryBusy.value = false;
                }
            }
        }

        async function copySyncSecret(value, label) {
            const copied = await copyToClipboard(value || '');
            showToast(copied ? `${label}已复制` : `${label}复制失败`, copied ? 'success' : 'error');
        }

        function disconnectSync() {
            if (state.syncBusy.value) return;
            const pendingJoin = state.syncStatus.pending_join === true;
            const title = pendingJoin ? '取消加入同步空间' : '断开本机同步';
            const message = pendingJoin
                ? '将丢弃当前待处理的加入冲突，不会修改本机 Vault 或 WebDAV 数据。确认取消？'
                : '只删除本机保存的同步设置，不会删除 WebDAV 上的加密数据。确认断开？';
            showConfirmDialog(title, message, async () => {
                if (!lifecycle.isActive()) return;
                state.syncBusy.value = true;
                const epoch = lifecycle.currentEpoch();
                try {
                    const result = await api.delete('/sync/config');
                    if (!responseBelongsToCurrentSession(epoch)) return;
                    applySyncStatus(result.data);
                    showToast(result.message || '已断开本机同步', 'success');
                } catch (error) {
                    if (!responseBelongsToCurrentSession(epoch)) return;
                    showToast(error.message || '断开同步失败', 'error');
                } finally {
                    if (epochIsCurrent(epoch)) state.syncBusy.value = false;
                }
            });
        }

        function openDeleteRemoteSync() {
            state.syncDeleteForm.password = '';
            state.syncDeleteForm.confirmation = '';
            state.syncError.value = '';
            state.showSyncDeleteRemote.value = true;
        }

        async function deleteRemoteSync() {
            if (state.syncBusy.value) return;
            state.syncBusy.value = true;
            state.syncError.value = '';
            const epoch = lifecycle.currentEpoch();
            try {
                const result = await api.post('/sync/reset', {
                    password: state.syncDeleteForm.password,
                    confirmation: state.syncDeleteForm.confirmation
                });
                if (!responseBelongsToCurrentSession(epoch)) return;
                applySyncStatus(result.data);
                state.showSyncDeleteRemote.value = false;
                showToast(result.message || '远端同步数据已删除', 'success');
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncError.value = error.message || '远端同步数据删除失败';
            } finally {
                if (epochIsCurrent(epoch)) {
                    state.syncDeleteForm.password = '';
                    state.syncBusy.value = false;
                }
            }
        }

        return {
            openSyncRecovery,
            closeSyncRecovery,
            submitSyncRecovery,
            copySyncSecret,
            disconnectSync,
            openDeleteRemoteSync,
            deleteRemoteSync
        };
    }

    window.SecretBaseSyncManagementController = { createSyncManagementController };
})();
