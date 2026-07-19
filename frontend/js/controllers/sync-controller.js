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
            runSync: options => syncOperations?.runSync(options)
        });
        const epochIsCurrent = lifecycle.epochIsCurrent, responseBelongsToCurrentSession = lifecycle.responseBelongsToCurrentSession;
        let pairingRequestSequence = 0, conflictRequestSequence = 0;
        let conflictLoadPromise = null;
        let syncOperations;
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
        const setupValidation = window.SecretBaseSyncSetupValidation.createSyncSetupValidation({
            computed,
            state,
            showToast
        });
        const {
            syncSetupMissingFields,
            syncSetupCanSubmit,
            clearSyncSetupFeedback,
            markSyncSetupDirty,
            reportSyncSetupError,
            validateSyncSetup
        } = setupValidation;

        function applySyncStatus(payload) {
            if (!payload || typeof payload !== 'object') return;
            Object.assign(state.syncStatus, {
                pending_join: false, last_error: '', host: '', base_url: '', username_mask: '',
                device_name: '', vault_id: '', space_id: '', last_synced_at: '', generation: 0,
                protocol_version: 2, sync_mode: '坚果云兼容快照模式', frontier: []
            }, payload);
            state.syncError.value = payload.last_error || '';
            if (payload.configured === false && payload.pending_join !== true) {
                clearAutoSyncTimer();
                setConflicts({});
                state.syncHistory.value = [];
                state.syncRecoveryMaterial.value = null;
            }
        }

        const syncManagement = window.SecretBaseSyncManagementController.createSyncManagementController({
            api,
            state,
            showToast,
            showConfirmDialog,
            copyToClipboard,
            lifecycle,
            applySyncStatus,
            epochIsCurrent,
            responseBelongsToCurrentSession
        });
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

        function setConflicts(payload, { preserveOpen = false } = {}) {
            const conflicts = Array.isArray(payload?.conflicts) ? payload.conflicts : [];
            state.syncConflictToken.value = payload?.conflict_token || '';
            state.syncConflicts.value = conflicts;
            state.syncConflictsError.value = '';
            state.syncStatus.pending_conflicts = conflicts.length;
            if (conflicts.length === 0 && state.syncStatus.phase === 'conflict' && !state.syncStatus.pending_join) {
                state.syncStatus.phase = state.syncStatus.configured ? 'synced' : state.syncStatus.phase;
            }
            for (const key of Object.keys(state.syncConflictResolutions)) {
                delete state.syncConflictResolutions[key];
            }
            state.showSyncConflicts.value = preserveOpen || conflicts.length > 0;
        }

        async function loadSyncConflicts(openWhenFound = true) {
            if (state.syncConflictsLoading.value && conflictLoadPromise) {
                const request = conflictRequestSequence;
                if (!openWhenFound) return conflictLoadPromise;
                state.showSyncConflicts.value = true;
                return conflictLoadPromise.then(result => {
                    if (request === conflictRequestSequence) state.showSyncConflicts.value = true;
                    return result;
                });
            }
            const epoch = lifecycle.currentEpoch();
            const request = ++conflictRequestSequence;
            state.syncConflictsLoading.value = true;
            state.syncConflictsError.value = '';
            if (openWhenFound) state.showSyncConflicts.value = true;
            const pending = (async () => {
                try {
                    const result = await api.get('/sync/conflicts');
                    if (!responseBelongsToCurrentSession(epoch) || request !== conflictRequestSequence) return [];
                    setConflicts(result.data || {}, { preserveOpen: openWhenFound });
                    return state.syncConflicts.value;
                } catch (error) {
                    if (!responseBelongsToCurrentSession(epoch) || request !== conflictRequestSequence) return [];
                    state.syncConflictsError.value = error.message || '同步冲突读取失败，请重试。';
                    state.syncError.value = state.syncConflictsError.value;
                    state.showSyncConflicts.value = openWhenFound;
                    if (openWhenFound) showToast(state.syncConflictsError.value, 'error');
                    return [];
                } finally {
                    if (epochIsCurrent(epoch) && request === conflictRequestSequence) {
                        state.syncConflictsLoading.value = false;
                    }
                }
            })();
            conflictLoadPromise = pending;
            try {
                return await pending;
            } finally {
                if (conflictLoadPromise === pending) conflictLoadPromise = null;
            }
        }

        function closeSyncConflicts(force = false) {
            if ((state.syncBusy.value || state.syncConflictsLoading.value) && !force) return false;
            conflictRequestSequence += 1;
            state.showSyncConflicts.value = false;
            state.syncConflictsLoading.value = false;
            state.syncConflictsError.value = '';
            return true;
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

        syncOperations = window.SecretBaseSyncOperationController.createSyncOperationController({
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
        });

        async function openSyncCenter() {
            state.showSettings.value = true;
            state.activeSettingsTab.value = 'sync';
            await loadSyncStatus({ silent: false });
            if (state.syncStatus.pending_conflicts > 0) await loadSyncConflicts(true);
        }

        function resetSetupForm() {
            Object.assign(state.syncSetupForm, {
                baseUrl: '',
                username: '',
                password: '',
                deviceName: '',
                protocolVersion: 2,
                autoSync: true,
                recoveryCode: '',
                pairingUri: '',
                mergeExisting: false
            });
            state.syncSetupMessage.value = '';
            state.syncSetupError.value = '';
            state.syncSetupTestPassed.value = false;
            state.syncError.value = '';
        }
        function setSyncSetupMode(mode) {
            if (state.syncBusy.value || state.syncSetupTesting.value || state.syncPairingReading.value) {
                showToast('当前同步操作正在处理中，请稍候再切换模式', 'warning');
                return false;
            }
            state.syncSetupMode.value = mode === 'join' ? 'join' : 'create';
            state.syncSetupMessage.value = '';
            state.syncSetupError.value = '';
            state.syncSetupTestPassed.value = false;
            state.syncError.value = '';
            if (state.syncSetupMode.value === 'create') {
                state.syncSetupForm.recoveryCode = '';
                state.syncSetupForm.pairingUri = '';
                state.syncSetupForm.mergeExisting = false;
                state.syncSetupForm.protocolVersion = 2;
            }
            return true;
        }

        function openSyncSetup(mode) {
            if (state.syncBusy.value || state.syncSetupTesting.value || state.syncPairingReading.value) {
                showToast('当前同步操作正在处理中，请稍候再打开配置', 'warning');
                return false;
            }
            resetSetupForm();
            if (!setSyncSetupMode(mode)) return false;
            state.showSyncSetup.value = true;
            return true;
        }

        function inferSyncProtocolFromRecovery() {
            markSyncSetupDirty();
            const value = String(state.syncSetupForm.recoveryCode || '').trim().toUpperCase();
            if (value.startsWith('SBSYNC1')) state.syncSetupForm.protocolVersion = 1;
            else if (value.startsWith('SBSYNC2')) state.syncSetupForm.protocolVersion = 2;
        }

        async function applySyncPairingUri() {
            if (state.syncPairingReading.value) return false;
            const request = ++pairingRequestSequence;
            state.syncPairingReading.value = true;
            clearSyncSetupFeedback({ clearMessage: true });
            state.syncError.value = '';
            try {
                const pairing = await window.SecretBaseSyncPairing.parse(state.syncSetupForm.pairingUri);
                if (request !== pairingRequestSequence) return false;
                state.syncSetupForm.protocolVersion = pairing.version;
                state.syncSetupForm.baseUrl = pairing.baseUrl;
                state.syncSetupForm.username = pairing.username;
                state.syncSetupForm.recoveryCode = pairing.recoveryCode;
                state.syncSetupForm.pairingUri = '';
                state.syncSetupMessage.value = '已读取配对信息，请输入 WebDAV 应用密码后加入';
                state.syncSetupTestPassed.value = false;
                return true;
            } catch (error) {
                reportSyncSetupError(error, '配对链接格式无效');
                return false;
            } finally {
                state.syncPairingReading.value = false;
            }
        }

        function closeSyncSetup() {
            if (state.syncBusy.value || state.syncSetupTesting.value || state.syncPairingReading.value) return;
            pairingRequestSequence += 1;
            state.showSyncSetup.value = false;
            state.syncSetupForm.baseUrl = '';
            state.syncSetupForm.username = '';
            state.syncSetupForm.deviceName = '';
            state.syncSetupForm.password = '';
            state.syncSetupForm.recoveryCode = '';
            state.syncSetupForm.pairingUri = '';
            state.syncSetupMessage.value = '';
            state.syncSetupError.value = '';
            state.syncSetupTestPassed.value = false;
            state.syncError.value = '';
        }

        function connectionPayload() {
            return {
                base_url: state.syncSetupForm.baseUrl.trim(),
                username: state.syncSetupForm.username.trim(),
                password: state.syncSetupForm.password,
                device_name: state.syncSetupForm.deviceName.trim(),
                auto_sync: Boolean(state.syncSetupForm.autoSync),
                protocol_version: Number(state.syncSetupForm.protocolVersion) === 1 ? 1 : 2
            };
        }

        async function testSyncConnection() {
            if (state.syncSetupTesting.value) return;
            if (!validateSyncSetup({ requireRecovery: false })) return false;
            state.syncSetupTesting.value = true;
            state.syncSetupMessage.value = '';
            state.syncSetupError.value = '';
            state.syncSetupTestPassed.value = false;
            state.syncError.value = '';
            const epoch = lifecycle.currentEpoch();
            try {
                const result = await api.post('/sync/config/test', connectionPayload());
                if (!responseBelongsToCurrentSession(epoch)) return;
                state.syncSetupMessage.value = result.message || 'WebDAV 连接测试通过';
                state.syncSetupTestPassed.value = true;
                return true;
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return;
                reportSyncSetupError(error, 'WebDAV 连接测试失败');
                return false;
            } finally {
                if (epochIsCurrent(epoch)) state.syncSetupTesting.value = false;
            }
        }

        async function submitSyncSetup() {
            if (state.syncBusy.value) return;
            if (
                state.syncSetupMode.value === 'join'
                && !String(state.syncSetupForm.recoveryCode || '').trim()
                && String(state.syncSetupForm.pairingUri || '').trim()
            ) {
                const parsed = await applySyncPairingUri();
                if (!parsed) return false;
            }
            if (!validateSyncSetup()) return false;
            state.syncBusy.value = true;
            state.syncSetupError.value = '';
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
                    state.syncSetupForm.pairingUri = '';
                    setConflicts(result.data);
                    showToast('加入同步空间需要先处理冲突', 'warning');
                } else {
                    state.showSyncSetup.value = false;
                    state.syncSetupForm.recoveryCode = '';
                    state.syncSetupForm.pairingUri = '';
                    let refreshed = true;
                    if (state.syncSetupMode.value === 'join') {
                        refreshed = await loadAllData();
                        if (!responseBelongsToCurrentSession(epoch)) return;
                        scheduleAutoSync(5000);
                    }
                    showToast(
                        refreshed === false
                            ? '已加入同步空间，但本机列表刷新不完整，请稍后重试。'
                            : (result.message || '同步空间配置完成'),
                        refreshed === false ? 'warning' : 'success'
                    );
                    if (state.syncSetupMode.value === 'create') syncManagement.openSyncRecovery('reveal');
                }
                return true;
            } catch (error) {
                if (!responseBelongsToCurrentSession(epoch)) return;
                reportSyncSetupError(error, '同步空间配置失败');
                return false;
            } finally {
                if (epochIsCurrent(epoch)) {
                    state.syncSetupForm.password = '';
                    state.syncBusy.value = false;
                }
            }
        }

        function closeSyncOverlays() {
            if (
                state.syncBusy.value
                || state.syncSetupTesting.value
                || state.syncPairingReading.value
                || state.syncRecoveryBusy.value
            ) return false;
            pairingRequestSequence += 1;
            syncOperations.invalidateHistoryRequests();
            conflictRequestSequence += 1;
            state.showSyncSetup.value = false;
            state.showSyncConfig.value = false;
            state.showSyncConflicts.value = false;
            state.showSyncHistory.value = false;
            state.showSyncRecovery.value = false;
            state.showSyncDeleteRemote.value = false;
            state.syncConflictsLoading.value = false;
            state.syncConflictsError.value = '';
            state.syncSetupForm.baseUrl = '';
            state.syncSetupForm.username = '';
            state.syncSetupForm.deviceName = '';
            state.syncSetupForm.password = '';
            state.syncSetupForm.recoveryCode = '';
            state.syncSetupForm.pairingUri = '';
            state.syncSetupMessage.value = '';
            state.syncSetupError.value = '';
            state.syncSetupTestPassed.value = false;
            state.syncConfigForm.password = '';
            state.syncConfigForm.baseUrl = '';
            state.syncConfigForm.username = '';
            state.syncConfigForm.deviceName = '';
            state.syncDeleteForm.password = '';
            state.syncDeleteForm.confirmation = '';
            state.syncMasterPassword.value = '';
            state.syncCompactConfirmation.value = '';
            state.syncRecoveryMaterial.value = null;
            state.syncError.value = '';
            state.syncSetupError.value = '';
            state.syncSetupTestPassed.value = false;
            return true;
        }

        async function initializeSync() {
            await lifecycle.initialize({
                loadStatus: loadSyncStatus,
                loadConflicts: loadSyncConflicts
            });
        }

        function clearSyncSessionState() {
            pairingRequestSequence += 1;
            conflictRequestSequence += 1;
            Object.assign(state.syncStatus, {
                configured: false,
                pending_join: false,
                protocol_version: 2,
                sync_mode: '坚果云兼容快照模式',
                phase: 'disabled',
                message: '尚未配置 WebDAV 同步',
                last_error: '',
                pending_conflicts: 0,
                auto_sync: true,
                host: '',
                base_url: '',
                username_mask: '',
                device_name: '',
                vault_id: '',
                last_synced_at: '',
                generation: 0,
                frontier: []
            });
            state.syncStatusLoading.value = false;
            state.syncBusy.value = false;
            state.syncConflictsLoading.value = false;
            state.syncConflictsError.value = '';
            state.syncSetupTesting.value = false;
            state.syncPairingReading.value = false;
            syncOperations.invalidateHistoryRequests();
            state.syncRecoveryBusy.value = false;
            state.syncError.value = '';
            state.syncSetupError.value = '';
            state.syncSetupTestPassed.value = false;
            state.showSyncSetup.value = false;
            state.showSyncConfig.value = false;
            state.showSyncConflicts.value = false;
            state.showSyncHistory.value = false;
            state.showSyncRecovery.value = false;
            state.showSyncDeleteRemote.value = false;
            state.syncRecoveryMaterial.value = null;
            state.syncCurrentSnapshotId.value = '';
            state.syncSetupMessage.value = '';
            state.syncMasterPassword.value = '';
            state.syncCompactConfirmation.value = '';
            state.syncConflictToken.value = '';
            state.syncConflicts.value = [];
            state.syncHistory.value = [];
            for (const key of Object.keys(state.syncConflictResolutions)) {
                delete state.syncConflictResolutions[key];
            }
            state.syncSetupForm.password = '';
            state.syncSetupForm.baseUrl = '';
            state.syncSetupForm.username = '';
            state.syncSetupForm.deviceName = '';
            state.syncSetupForm.recoveryCode = '';
            state.syncSetupForm.pairingUri = '';
            state.syncConfigForm.password = '';
            state.syncConfigForm.baseUrl = '';
            state.syncConfigForm.username = '';
            state.syncConfigForm.deviceName = '';
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
                allSyncConflictsResolved,
                syncSetupMissingFields,
                syncSetupCanSubmit
            },
            actions: {
                formatSyncTime,
                syncConflictStateLabel,
                loadSyncStatus,
                openSyncCenter,
                openSyncSetup,
                setSyncSetupMode,
                inferSyncProtocolFromRecovery,
                markSyncSetupDirty,
                applySyncPairingUri,
                closeSyncSetup,
                testSyncConnection,
                submitSyncSetup,
                runSync: syncOperations.runSync,
                loadSyncConflicts,
                closeSyncConflicts,
                resolveSyncConflicts: syncOperations.resolveSyncConflicts,
                openSyncConfig: syncOperations.openSyncConfig,
                closeSyncConfig: syncOperations.closeSyncConfig,
                saveSyncConfig: syncOperations.saveSyncConfig,
                setAutoSync: syncOperations.setAutoSync,
                openSyncHistory: syncOperations.openSyncHistory,
                closeSyncHistory: syncOperations.closeSyncHistory,
                restoreSyncHistory: syncOperations.restoreSyncHistory,
                closeSyncOverlays,
                ...syncManagement,
                initializeSync,
                pauseSync,
                disposeSync
            }
        };
    }

    window.SecretBaseSyncController = { createSyncController };
})();
