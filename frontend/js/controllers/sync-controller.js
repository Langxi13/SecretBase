/**
 * WebDAV 端到端加密同步的界面行为与自动触发调度。
 */
(function () {
    function createSyncController({
        computed,
        api,
        showToast,
        showConfirmDialog,
        copyToClipboard,
        state,
        loadAllData
    }) {
        const lifecycle = window.SecretBaseSyncLifecycle.createSyncLifecycle({
            state,
            runSync: options => runSync(options)
        });
        const epochIsCurrent = lifecycle.epochIsCurrent, responseBelongsToCurrentSession = lifecycle.responseBelongsToCurrentSession;
        const clearAutoSyncTimer = lifecycle.clearTimer, scheduleAutoSync = lifecycle.schedule;
        const syncStatusLabel = computed(() => {
            const phase = state.syncStatus.phase;
            if (state.syncStatus.pending_join) return `待处理 ${state.syncStatus.pending_conflicts || 0} 项加入冲突`;
            if (!state.syncStatus.configured) return phase === 'error' ? '同步异常' : '未配置同步';
            if (phase === 'syncing') return '正在同步';
            if (phase === 'conflict') return `待处理 ${state.syncStatus.pending_conflicts || 0} 项冲突`;
            if (phase === 'error') return '同步失败';
            if (phase === 'synced') return '已同步';
            return '同步已就绪';
        });
        const syncStatusTone = computed(() => {
            if (state.syncStatus.phase === 'conflict') return 'warning';
            if (state.syncStatus.phase === 'error') return 'error';
            if (state.syncStatus.phase === 'syncing') return 'working';
            if (state.syncStatus.configured) return 'success';
            return 'muted';
        });
        const syncStatusIcon = computed(() => {
            if (state.syncStatus.phase === 'syncing') return '↻';
            if (state.syncStatus.phase === 'conflict') return '!';
            if (state.syncStatus.phase === 'error') return '×';
            if (state.syncStatus.configured) return '✓';
            return '☁';
        });
        const allSyncConflictsResolved = computed(() => {
            return state.syncConflicts.value.length > 0
                && state.syncConflicts.value.every(item => Boolean(state.syncConflictResolutions[item.conflict_id]));
        });

        function applySyncStatus(payload) {
            if (!payload || typeof payload !== 'object') return;
            Object.assign(state.syncStatus, {
                pending_join: false, last_error: '', host: '', base_url: '', username_mask: '',
                device_name: '', vault_id: '', last_synced_at: '', generation: 0
            }, payload);
            state.syncError.value = payload.last_error || '';
            if (payload.configured === false && payload.pending_join !== true) {
                clearAutoSyncTimer();
                setConflicts({});
                state.syncHistory.value = [];
                state.syncRecoveryMaterial.value = null;
            }
        }

        function formatSyncTime(value) {
            if (!value) return '尚未同步';
            const timestamp = new Date(value);
            if (Number.isNaN(timestamp.getTime())) return String(value);
            return timestamp.toLocaleString('zh-CN', { hour12: false });
        }

        function syncConflictStateLabel(summary) {
            const labels = {
                active: '正常条目',
                deleted: '回收站条目',
                absent: '不存在',
                present: '存在',
                changed: '已修改'
            };
            return labels[summary?.state] || '状态未知';
        }

        function setConflicts(payload) {
            const conflicts = Array.isArray(payload?.conflicts) ? payload.conflicts : [];
            state.syncConflictToken.value = payload?.conflict_token || '';
            state.syncConflicts.value = conflicts;
            for (const key of Object.keys(state.syncConflictResolutions)) {
                delete state.syncConflictResolutions[key];
            }
            state.showSyncConflicts.value = conflicts.length > 0;
        }

        async function loadSyncConflicts(openWhenFound = true) {
            const epoch = lifecycle.currentEpoch();
            try {
                const result = await api.get('/sync/conflicts');
                if (!responseBelongsToCurrentSession(epoch)) return [];
                setConflicts(result.data || {});
                if (!openWhenFound && state.syncConflicts.value.length > 0) {
                    state.showSyncConflicts.value = false;
                }
                return state.syncConflicts.value;
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return [];
                state.syncError.value = error.message || '同步冲突读取失败';
                return [];
            }
        }

        async function loadSyncStatus({ silent = false } = {}) {
            if (state.syncStatusLoading.value) return state.syncStatus;
            state.syncStatusLoading.value = true;
            const epoch = lifecycle.currentEpoch();
            try {
                const result = await api.get('/sync/status');
                if (!responseBelongsToCurrentSession(epoch)) return null;
                applySyncStatus(result.data);
                if (state.syncStatus.pending_conflicts > 0 || state.syncStatus.phase === 'conflict') {
                    await loadSyncConflicts(false);
                }
                return state.syncStatus;
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return null;
                state.syncError.value = error.message || '同步状态读取失败';
                if (!silent) showToast(state.syncError.value, 'error');
                return null;
            } finally {
                if (epochIsCurrent(epoch)) state.syncStatusLoading.value = false;
            }
        }

        async function openSyncCenter() {
            state.showSettings.value = true;
            state.activeSettingsTab.value = 'sync';
            await loadSyncStatus({ silent: true });
            if (state.syncStatus.pending_conflicts > 0) await loadSyncConflicts(true);
        }

        function resetSetupForm() {
            Object.assign(state.syncSetupForm, {
                baseUrl: '',
                username: '',
                password: '',
                deviceName: '',
                autoSync: true,
                recoveryCode: '',
                mergeExisting: false
            });
            state.syncSetupMessage.value = '';
            state.syncError.value = '';
        }
        function openSyncSetup(mode) {
            resetSetupForm();
            state.syncSetupMode.value = mode === 'join' ? 'join' : 'create';
            state.showSyncSetup.value = true;
        }

        function closeSyncSetup() {
            if (state.syncBusy.value || state.syncSetupTesting.value) return;
            state.showSyncSetup.value = false;
            state.syncSetupForm.password = '';
            state.syncSetupForm.recoveryCode = '';
        }

        function connectionPayload() {
            return {
                base_url: state.syncSetupForm.baseUrl.trim(),
                username: state.syncSetupForm.username.trim(),
                password: state.syncSetupForm.password,
                device_name: state.syncSetupForm.deviceName.trim(),
                auto_sync: Boolean(state.syncSetupForm.autoSync)
            };
        }

        async function testSyncConnection() {
            if (state.syncSetupTesting.value) return;
            state.syncSetupTesting.value = true;
            state.syncSetupMessage.value = '';
            state.syncError.value = '';
            const epoch = lifecycle.currentEpoch();
            try {
                const result = await api.post('/sync/config/test', connectionPayload());
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncSetupMessage.value = result.message || 'WebDAV 连接测试通过';
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncError.value = error.message || 'WebDAV 连接测试失败';
            } finally {
                if (epochIsCurrent(epoch)) state.syncSetupTesting.value = false;
            }
        }

        async function submitSyncSetup() {
            if (state.syncBusy.value) return;
            state.syncBusy.value = true;
            state.syncError.value = '';
            const epoch = lifecycle.currentEpoch();
            try {
                const payload = connectionPayload();
                let result;
                if (state.syncSetupMode.value === 'join') {
                    result = await api.post('/sync/join', {
                        ...payload,
                        recovery_code: state.syncSetupForm.recoveryCode.trim(),
                        merge_existing: Boolean(state.syncSetupForm.mergeExisting)
                    });
                } else {
                    result = await api.post('/sync/create', payload);
                }
                if (!responseBelongsToCurrentSession(epoch)) return;
                applySyncStatus(result.data?.status);
                if (result.data?.conflicts?.length) {
                    state.showSyncSetup.value = false;
                    state.syncSetupForm.recoveryCode = '';
                    setConflicts(result.data);
                } else {
                    state.showSyncSetup.value = false;
                    state.syncSetupForm.recoveryCode = '';
                    if (state.syncSetupMode.value === 'join') {
                        await loadAllData();
                        if (!responseBelongsToCurrentSession(epoch)) return;
                        scheduleAutoSync(5000);
                    }
                    showToast(result.message || '同步空间配置完成', 'success');
                    if (state.syncSetupMode.value === 'create') openSyncRecovery('reveal');
                }
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncError.value = error.message || '同步空间配置失败';
            } finally {
                if (epochIsCurrent(epoch)) {
                    state.syncSetupForm.password = '';
                    state.syncBusy.value = false;
                }
            }
        }

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
                if (payload.conflicts?.length) {
                    setConflicts(payload);
                    if (!silent) showToast('发现多端修改冲突，请选择保留方式', 'warning');
                } else if (['downloaded', 'merged'].includes(payload.action)) {
                    await loadAllData();
                    if (!responseBelongsToCurrentSession(epoch)) return null;
                }
                if (!silent && !payload.conflicts?.length) showToast(result.message || '同步完成', 'success');
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
                applySyncStatus(result.data?.status);
                state.showSyncConflicts.value = false;
                setConflicts({});
                await loadAllData();
                if (!responseBelongsToCurrentSession(epoch)) return;
                showToast(result.message || '同步冲突已处理', 'success');
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncError.value = error.message || '同步冲突处理失败';
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
                state.showSyncConfig.value = false;
                showToast(result.message || '同步设置已保存', 'success');
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncError.value = error.message || '同步设置保存失败';
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
            state.showSyncHistory.value = true;
            state.syncHistoryLoading.value = true;
            state.syncError.value = '';
            const epoch = lifecycle.currentEpoch();
            try {
                const result = await api.get('/sync/history');
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncHistory.value = result.data?.items || [];
                state.syncCurrentSnapshotId.value = result.data?.current_snapshot_id || '';
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncError.value = error.message || '同步历史读取失败';
            } finally {
                if (epochIsCurrent(epoch)) state.syncHistoryLoading.value = false;
            }
        }

        function restoreSyncHistory(item) {
            showConfirmDialog(
                '恢复同步历史',
                `将把 ${formatSyncTime(item.created_at)} 的加密快照恢复为所有设备可见的最新版本。确认继续？`,
                async () => {
                    if (!lifecycle.isActive()) return;
                    state.syncBusy.value = true;
                    const epoch = lifecycle.currentEpoch();
                    try {
                        const result = await api.post(`/sync/history/${encodeURIComponent(item.snapshot_id)}/restore`, {});
                        if (!responseBelongsToCurrentSession(epoch)) return;
                        applySyncStatus(result.data?.status);
                        state.showSyncHistory.value = false;
                        await loadAllData();
                        if (!responseBelongsToCurrentSession(epoch)) return;
                        showToast(result.message || '同步历史已恢复', 'success');
                    } catch (error) {
                        if (!responseBelongsToCurrentSession(epoch)) return;
                        showToast(error.message || '同步历史恢复失败', 'error');
                    } finally {
                        if (epochIsCurrent(epoch)) state.syncBusy.value = false;
                    }
                }
            );
        }

        function openSyncRecovery(mode = 'reveal') {
            state.syncRecoveryMode.value = mode === 'rotate' ? 'rotate' : 'reveal';
            state.syncMasterPassword.value = '';
            state.syncRecoveryMaterial.value = null;
            state.syncError.value = '';
            state.showSyncRecovery.value = true;
        }

        function closeSyncRecovery() {
            if (state.syncRecoveryBusy.value) return;
            state.showSyncRecovery.value = false;
            state.syncMasterPassword.value = '';
            state.syncRecoveryMaterial.value = null;
        }

        async function submitSyncRecovery() {
            if (state.syncRecoveryBusy.value) return;
            state.syncRecoveryBusy.value = true;
            state.syncError.value = '';
            const epoch = lifecycle.currentEpoch();
            try {
                const path = state.syncRecoveryMode.value === 'rotate' ? '/sync/rotate-key' : '/sync/recovery-code';
                const result = await api.post(path, { password: state.syncMasterPassword.value });
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncRecoveryMaterial.value = result.data;
                applySyncStatus(result.data?.status);
                if (state.syncRecoveryMode.value === 'rotate') {
                    showToast(result.message || '同步密钥已轮换', 'success');
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

        async function initializeSync() {
            await lifecycle.initialize({
                loadStatus: loadSyncStatus,
                loadConflicts: loadSyncConflicts
            });
        }

        function clearSyncSessionState() {
            state.syncStatusLoading.value = false;
            state.syncBusy.value = false;
            state.syncSetupTesting.value = false;
            state.syncHistoryLoading.value = false;
            state.syncRecoveryBusy.value = false;
            state.syncError.value = '';
            state.showSyncSetup.value = false;
            state.showSyncConfig.value = false;
            state.showSyncConflicts.value = false;
            state.showSyncHistory.value = false;
            state.showSyncRecovery.value = false;
            state.showSyncDeleteRemote.value = false;
            state.syncRecoveryMaterial.value = null;
            state.syncMasterPassword.value = '';
            state.syncConflictToken.value = '';
            state.syncConflicts.value = [];
            state.syncHistory.value = [];
            for (const key of Object.keys(state.syncConflictResolutions)) {
                delete state.syncConflictResolutions[key];
            }
            state.syncSetupForm.password = '';
            state.syncSetupForm.recoveryCode = '';
            state.syncConfigForm.password = '';
            state.syncDeleteForm.password = '';
            state.syncDeleteForm.confirmation = '';
        }

        function pauseSync() {
            lifecycle.pause();
            clearSyncSessionState();
        }

        function disposeSync() {
            lifecycle.dispose();
            clearSyncSessionState();
        }

        return {
            views: {
                syncStatusLabel,
                syncStatusTone,
                syncStatusIcon,
                allSyncConflictsResolved
            },
            actions: {
                formatSyncTime,
                syncConflictStateLabel,
                loadSyncStatus,
                openSyncCenter,
                openSyncSetup,
                closeSyncSetup,
                testSyncConnection,
                submitSyncSetup,
                runSync,
                loadSyncConflicts,
                resolveSyncConflicts,
                openSyncConfig,
                saveSyncConfig,
                setAutoSync,
                openSyncHistory,
                restoreSyncHistory,
                openSyncRecovery,
                closeSyncRecovery,
                submitSyncRecovery,
                copySyncSecret,
                disconnectSync,
                openDeleteRemoteSync,
                deleteRemoteSync,
                initializeSync,
                pauseSync,
                disposeSync
            }
        };
    }

    window.SecretBaseSyncController = { createSyncController };
})();
