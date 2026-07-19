/**
 * 同步执行、设置、历史和恢复操作。
 *
 * 同步状态读取与配对流程由主控制器负责；这里集中处理会改变远端或
 * 需要较长时间等待的动作，确保它们共享同一会话和刷新反馈规则。
 */
(function () {
    function createSyncOperationController({
        api,
        state,
        showToast,
        showConfirmDialog,
        lifecycle,
        applySyncStatus,
        setConflicts,
        loadSyncStatus,
        allSyncConflictsResolved,
        responseBelongsToCurrentSession,
        epochIsCurrent,
        loadAllData,
        scheduleAutoSync,
        clearAutoSyncTimer,
        formatSyncTime
    }) {
        let historyRequestSequence = 0;

        async function runSync(options = {}) {
            const silent = options?.silent === true;
            if (state.syncBusy.value) {
                if (silent) scheduleAutoSync(5000);
                return null;
            }
            if (!state.syncStatus.configured) return null;
            clearAutoSyncTimer();
            state.syncBusy.value = true;
            state.syncStatus.phase = 'syncing';
            state.syncStatus.message = '正在检查多端修改';
            state.syncError.value = '';
            const epoch = lifecycle.currentEpoch();
            try {
                const result = await api.post('/sync/run', {});
                if (!responseBelongsToCurrentSession(epoch)) return null;
                const payload = result.data || {};
                applySyncStatus(payload.status);
                let refreshed = true;
                if (payload.conflicts?.length) {
                    setConflicts(payload);
                    if (!silent) showToast('发现多端修改冲突，请选择保留方式', 'warning');
                } else if (['downloaded', 'merged'].includes(payload.action)) {
                    refreshed = await loadAllData();
                    if (!responseBelongsToCurrentSession(epoch)) return null;
                }
                if (!silent && !payload.conflicts?.length) {
                    showToast(
                        refreshed === false
                            ? '同步数据已更新，但本机列表刷新不完整，请稍后重试。'
                            : (result.message || '同步完成'),
                        refreshed === false ? 'warning' : 'success'
                    );
                }
                return payload;
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return null;
                if (error.code === 'SYNC_NOT_CONFIGURED') {
                    await loadSyncStatus({ silent: true });
                    if (!responseBelongsToCurrentSession(epoch)) return null;
                }
                state.syncStatus.phase = 'error';
                state.syncStatus.message = '同步未完成';
                state.syncStatus.last_error = error.message || '同步失败';
                state.syncError.value = state.syncStatus.last_error;
                if (!silent) showToast(state.syncError.value, 'error');
                return null;
            } finally {
                if (epochIsCurrent(epoch)) state.syncBusy.value = false;
            }
        }

        async function resolveSyncConflicts() {
            if (state.syncBusy.value || !allSyncConflictsResolved.value) return;
            state.syncBusy.value = true;
            state.syncError.value = '';
            const epoch = lifecycle.currentEpoch();
            try {
                const result = await api.post('/sync/conflicts/resolve', {
                    conflict_token: state.syncConflictToken.value,
                    resolutions: { ...state.syncConflictResolutions }
                });
                if (!responseBelongsToCurrentSession(epoch)) return;
                const payload = result.data || {};
                applySyncStatus(payload.status);
                if (Array.isArray(payload.conflicts) && payload.conflicts.length > 0) {
                    setConflicts(payload);
                    showToast(
                        '当前选择已保存，请继续处理剩余 ' + payload.conflicts.length + ' 项冲突',
                        'warning'
                    );
                    return;
                }
                setConflicts({});
                const refreshed = await loadAllData();
                if (!responseBelongsToCurrentSession(epoch)) return;
                showToast(
                    refreshed === false
                        ? '同步冲突已处理，但本机列表刷新不完整，请稍后重试。'
                        : (result.message || '同步冲突已处理'),
                    refreshed === false ? 'warning' : 'success'
                );
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncError.value = error.message || '同步冲突处理失败';
                showToast(state.syncError.value, 'error');
            } finally {
                if (epochIsCurrent(epoch)) state.syncBusy.value = false;
            }
        }

        function openSyncConfig() {
            Object.assign(state.syncConfigForm, {
                baseUrl: state.syncStatus.base_url || '',
                username: '',
                password: '',
                deviceName: state.syncStatus.device_name || '',
                autoSync: state.syncStatus.auto_sync !== false
            });
            state.syncError.value = '';
            state.showSyncConfig.value = true;
        }

        function closeSyncConfig(force = false) {
            if (state.syncBusy.value && !force) return;
            state.showSyncConfig.value = false;
            state.syncConfigForm.baseUrl = '';
            state.syncConfigForm.password = '';
            state.syncConfigForm.username = '';
            state.syncConfigForm.deviceName = '';
            state.syncError.value = '';
        }

        async function saveSyncConfig() {
            if (state.syncBusy.value) return;
            state.syncBusy.value = true;
            state.syncError.value = '';
            const baseUrl = state.syncConfigForm.baseUrl.trim();
            const payload = {
                device_name: state.syncConfigForm.deviceName.trim(),
                auto_sync: Boolean(state.syncConfigForm.autoSync)
            };
            if (baseUrl !== state.syncStatus.base_url) payload.base_url = baseUrl;
            if (state.syncConfigForm.username.trim()) payload.username = state.syncConfigForm.username.trim();
            if (state.syncConfigForm.password) payload.password = state.syncConfigForm.password;
            const epoch = lifecycle.currentEpoch();
            try {
                const result = await api.put('/sync/config', payload);
                if (!responseBelongsToCurrentSession(epoch)) return;
                applySyncStatus(result.data);
                closeSyncConfig(true);
                showToast(result.message || '同步设置已保存', 'success');
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncError.value = error.message || '同步设置保存失败';
                showToast(state.syncError.value, 'error');
            } finally {
                if (epochIsCurrent(epoch)) {
                    state.syncConfigForm.password = '';
                    state.syncBusy.value = false;
                }
            }
        }

        async function setAutoSync() {
            if (state.syncBusy.value) return;
            state.syncBusy.value = true;
            const nextValue = Boolean(state.syncStatus.auto_sync);
            const epoch = lifecycle.currentEpoch();
            try {
                const result = await api.put('/sync/config', { auto_sync: nextValue });
                if (!responseBelongsToCurrentSession(epoch)) return;
                applySyncStatus(result.data);
                if (nextValue) scheduleAutoSync(0);
                else clearAutoSyncTimer();
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncStatus.auto_sync = !nextValue;
                showToast(error.message || '自动同步设置失败', 'error');
            } finally {
                if (epochIsCurrent(epoch)) state.syncBusy.value = false;
            }
        }

        async function openSyncHistory() {
            if (state.syncHistoryLoading.value) return;
            const request = ++historyRequestSequence;
            state.showSyncHistory.value = true;
            state.syncHistoryLoading.value = true;
            state.syncError.value = '';
            const epoch = lifecycle.currentEpoch();
            try {
                const result = await api.get('/sync/history');
                if (!responseBelongsToCurrentSession(epoch)) return;
                if (request !== historyRequestSequence || !state.showSyncHistory.value) return;
                state.syncHistory.value = result.data?.items || [];
                state.syncCurrentSnapshotId.value = result.data?.current_snapshot_id || '';
            } catch (error) {
                if (
                    !responseBelongsToCurrentSession(epoch)
                    || request !== historyRequestSequence
                    || !state.showSyncHistory.value
                ) return;
                state.syncError.value = error.message || '同步历史读取失败';
                showToast(state.syncError.value, 'error');
            } finally {
                if (epochIsCurrent(epoch) && request === historyRequestSequence) {
                    state.syncHistoryLoading.value = false;
                }
            }
        }

        function closeSyncHistory(force = false) {
            if (state.syncBusy.value && !force) return false;
            historyRequestSequence += 1;
            state.showSyncHistory.value = false;
            state.syncHistoryLoading.value = false;
            return true;
        }

        function restoreSyncHistory(item) {
            showConfirmDialog(
                '恢复同步历史',
                '将把 ' + formatSyncTime(item.created_at) + ' 的加密快照恢复为所有设备可见的最新版本。确认继续？',
                async () => {
                    if (!lifecycle.isActive()) return;
                    state.syncBusy.value = true;
                    const epoch = lifecycle.currentEpoch();
                    try {
                        const result = await api.post(
                            '/sync/history/' + encodeURIComponent(item.snapshot_id) + '/restore',
                            {}
                        );
                        if (!responseBelongsToCurrentSession(epoch)) return;
                        applySyncStatus(result.data?.status);
                        closeSyncHistory(true);
                        const refreshed = await loadAllData();
                        if (!responseBelongsToCurrentSession(epoch)) return;
                        showToast(
                            refreshed === false
                                ? '同步历史已恢复，但本机列表刷新不完整，请稍后重试。'
                                : (result.message || '同步历史已恢复'),
                            refreshed === false ? 'warning' : 'success'
                        );
                    } catch (error) {
                        if (!responseBelongsToCurrentSession(epoch)) return;
                        const message = error.message || '同步历史恢复失败';
                        state.syncError.value = message;
                        showToast(message, 'error');
                        throw new Error(message);
                    } finally {
                        if (epochIsCurrent(epoch)) state.syncBusy.value = false;
                    }
                }
            );
        }

        function invalidateHistoryRequests() {
            historyRequestSequence += 1;
            state.syncHistoryLoading.value = false;
        }

        return {
            runSync,
            resolveSyncConflicts,
            openSyncConfig,
            closeSyncConfig,
            saveSyncConfig,
            setAutoSync,
            openSyncHistory,
            closeSyncHistory,
            restoreSyncHistory,
            invalidateHistoryRequests
        };
    }

    window.SecretBaseSyncOperationController = { createSyncOperationController };
})();
