/**
 * 认证、锁定、设置与根生命周期协调。
 */
(function () {
    function createAppSessionController({
        api,
        store,
        state,
        showToast,
        autoLockFactory,
        theme,
        data,
        loadSavedAdvancedFilters,
        loadAiSettingsStatus,
        loadDesktopDiagnostics,
        disposeAiSettings = () => {},
        disposeAiAssistant = () => {},
        disposeAiTools = () => {},
        disposeMaintenance = () => {},
        disposeEntryRequests = () => {},
        initializeDesktopUpdates = () => null,
        disposeDesktopUpdates = () => {},
        initializeSync = async () => {},
        pauseSync = () => {},
        disposeSync = () => {},
        closeSyncOverlays = () => true,
        handleDocumentClick,
        handleDocumentKeydown = () => {},
        clearPendingDialogs = () => {},
        clearDataLoadErrors = () => {},
        invalidateDataRequests = () => {}
    }) {
        const desktopLockCover = window.SecretBaseDesktopLockCover;
        let authOperationEpoch = 0;
        let settingsInteractionEpoch = 0;
        const isCurrentAuthOperation = epoch => epoch === authOperationEpoch;
        let autoLock;
        const security = window.SecretBaseSessionSecurity.createSessionSecurityController({
            api,
            store,
            state,
            desktopLockCover,
            pauseSync,
            pauseDesktopUpdates: disposeDesktopUpdates,
            invalidateDataRequests,
            clearDataLoadErrors,
            clearPendingDialogs,
            pauseAi: disposeAiSettings,
            disposeAiAssistant,
            disposeAiTools,
            disposeMaintenance,
            disposeEntryRequests,
            invalidateAuthOperations: () => {
                authOperationEpoch += 1;
                settingsInteractionEpoch += 1;
            },
            clearAutoLockTimer: () => autoLock?.clearAutoLockTimer?.()
        });
        const { applyLockedState, handleDesktopLockRequest } = security;
        function handleDesktopCloseRequest() {
            state.desktopCloseRemember.value = false;
            state.desktopCloseSubmitting.value = false;
            state.desktopCloseError.value = '';
            state.showDesktopCloseConfirm.value = true;
        }
        autoLock = autoLockFactory({
            settingsForm: state.settingsForm,
            locked: state.locked,
            initialized: state.initialized,
            store,
            applyLockedState,
            showToast
        });
        const sessionSettings = window.SecretBaseSessionSettings.createSessionSettingsActions({
            api,
            store,
            state,
            showToast,
            theme,
            data,
            autoLock,
            getAuthOperationEpoch: () => authOperationEpoch,
            isCurrentAuthOperation
        });
        async function initPassword() {
            if (state.password.value !== state.confirmPassword.value) {
                state.passwordError.value = '两次输入的密码不一致';
                return;
            }
            if (state.password.value.length < 8 || state.password.value.length > 128) {
                state.passwordError.value = '主密码必须为 8 至 128 个字符';
                return;
            }

            state.submitting.value = true;
            state.passwordError.value = '';
            const epoch = ++authOperationEpoch;
            try {
                await store.initPassword(state.password.value);
                if (!isCurrentAuthOperation(epoch)) return;
            } catch (error) {
                if (isCurrentAuthOperation(epoch)) state.passwordError.value = error.message || '设置失败';
                return;
            } finally {
                if (isCurrentAuthOperation(epoch)) state.submitting.value = false;
            }

            if (!isCurrentAuthOperation(epoch)) return;
            state.initialized.value = true;
            state.locked.value = false;
            desktopLockCover.clear();
            state.password.value = '';
            state.confirmPassword.value = '';
            try {
                const settings = await store.loadSettings();
                if (!isCurrentAuthOperation(epoch)) return;
                await data.applySettings(settings, theme);
                if (!isCurrentAuthOperation(epoch)) return;
                await data.loadAllData();
                if (!isCurrentAuthOperation(epoch)) return;
                await initializeSync();
                if (!isCurrentAuthOperation(epoch)) return;
                initializeDesktopUpdates();
            } catch (error) {
                if (isCurrentAuthOperation(epoch)) {
                    state.dataLoadError.value = error?.message || '密码库已创建，但部分数据暂时无法加载。';
                }
            }
            if (!isCurrentAuthOperation(epoch)) return;
            autoLock.startAutoLockTimer();
            state.showOnboarding.value = true;
            showToast('欢迎使用 SecretBase', 'success');
        }
        async function unlock() {
            if (!state.password.value) {
                state.unlockError.value = '请输入密码';
                return;
            }

            state.submitting.value = true;
            state.unlockError.value = '';
            const epoch = ++authOperationEpoch;
            try {
                await store.unlock(state.password.value);
                if (!isCurrentAuthOperation(epoch)) return;
            } catch (error) {
                if (isCurrentAuthOperation(epoch)) state.unlockError.value = error.message || '解锁失败';
                return;
            } finally {
                if (isCurrentAuthOperation(epoch)) state.submitting.value = false;
            }

            if (!isCurrentAuthOperation(epoch)) return;
            state.locked.value = false;
            desktopLockCover.clear();
            state.password.value = '';
            try {
                const settings = await store.loadSettings();
                if (!isCurrentAuthOperation(epoch)) return;
                await data.applySettings(settings, theme);
                if (!isCurrentAuthOperation(epoch)) return;
                await data.loadAllData();
                if (!isCurrentAuthOperation(epoch)) return;
                await initializeSync();
                if (!isCurrentAuthOperation(epoch)) return;
                initializeDesktopUpdates();
            } catch (error) {
                if (isCurrentAuthOperation(epoch)) {
                    state.dataLoadError.value = error?.message || '密码库已解锁，但部分数据暂时无法加载。';
                }
            }
            if (!isCurrentAuthOperation(epoch)) return;
            autoLock.startAutoLockTimer();
        }
        async function lock() {
            authOperationEpoch += 1;
            try {
                await store.lock();
            } finally {
                applyLockedState();
            }
        }
        async function openSettings() {
            const epoch = ++settingsInteractionEpoch;
            state.showSettings.value = true;
            state.activeSettingsTab.value = 'general';
            if (state.aiSettingsStatus.value === null) {
                await loadAiSettingsStatus();
                if (epoch !== settingsInteractionEpoch || !state.showSettings.value) return;
            }
        }
        function closeSettings() {
            if (
                state.settingsSaving.value
                || state.transferBusy.value
                || state.aiSettingsSaving.value
                || state.syncBusy.value
                || state.syncRecoveryBusy.value
            ) {
                showToast('当前设置操作正在处理中，请稍候再关闭', 'warning');
                return false;
            }
            if (closeSyncOverlays() === false) {
                showToast('同步操作正在处理中，请稍候再关闭设置', 'warning');
                return false;
            }
            settingsInteractionEpoch += 1;
            disposeAiSettings();
            state.showSettings.value = false;
            state.settingsError.value = '';
            return true;
        }
        function closeChangePassword() {
            if (state.passwordChanging.value) return false;
            state.showChangePassword.value = false;
            state.passwordForm.oldPassword = '';
            state.passwordForm.newPassword = '';
            state.passwordForm.confirmPassword = '';
            state.passwordForm.error = '';
            return true;
        }
        async function selectSettingsTab(tabKey) {
            const epoch = ++settingsInteractionEpoch;
            state.activeSettingsTab.value = tabKey;
            if (tabKey === 'ai') {
                await loadAiSettingsStatus();
            } else if (tabKey === 'desktop') {
                await loadDesktopDiagnostics();
            }
            if (epoch !== settingsInteractionEpoch || !state.showSettings.value) return;
        }
        const lifecycle = window.SecretBaseSessionLifecycle.createSessionLifecycle({
            api,
            store,
            state,
            theme,
            data,
            autoLock,
            desktopLockCover,
            loadSavedAdvancedFilters,
            initializeDesktopUpdates,
            disposeDesktopUpdates,
            disposeAiSettings,
            disposeAiAssistant,
            disposeAiTools,
            initializeSync,
            pauseSync,
            disposeSync,
            handleDocumentClick,
            handleDocumentKeydown,
            handleDesktopLockRequest,
            handleDesktopCloseRequest
        });
        return {
            ...autoLock,
            applyLockedState,
            initPassword,
            unlock,
            lock,
            openSettings,
            closeSettings,
            closeChangePassword,
            selectSettingsTab,
            ...sessionSettings,
            retryInitialization: lifecycle.retryInitialization,
            registerLifecycle: lifecycle.registerLifecycle
        };
    }
    window.SecretBaseAppSessionController = { createAppSessionController };
})();
