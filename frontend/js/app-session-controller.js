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
        initializeDesktopUpdates = () => null,
        disposeDesktopUpdates = () => {},
        handleDocumentClick
    }) {
        let aiNowTimer = null;
        const desktopLockCover = window.SecretBaseDesktopLockCover;
        function applyLockedState() {
            api.setToken(null);
            store.setState({ locked: true });
            state.locked.value = true;
            state.submitting.value = false;
            state.passwordChanging.value = false;
            state.password.value = '';
            state.entries.value = [];
            state.tags.value = [];
            state.groups.value = [];
            state.selectedEntry.value = null;
            state.editingEntry.value = null;
            state.selectedEntryIds.value = [];
            state.groupPickerSelectedIds.value = [];
            state.showCreateModal.value = false;
            state.showEditModal.value = false;
            state.showAiParse.value = false;
            state.showAiAssistant.value = false;
            state.resetAiAssistantSession();
            state.showSettings.value = false;
            state.showDesktopStatus.value = false;
            state.showDesktopCloseConfirm.value = false;
            state.desktopCloseRemember.value = false;
            state.desktopCloseSubmitting.value = false;
            state.desktopCloseError.value = '';
            state.desktopCloseSettingsSaving.value = false;
            state.showTrash.value = false;
            state.showTagManager.value = false;
            state.showTagEditorModal.value = false;
            state.showGroupModal.value = false;
            state.showTagBrowser.value = false;
            state.showGroupEntryPicker.value = false;
            [state.entrySaving, state.groupSaving, state.tagSaving, state.tagMerging, state.groupPickerSaving]
                .forEach(flag => { flag.value = false; });
            state.showChangePassword.value = false;
            state.showBackupCenter.value = false;
            state.showConfirm.value = false;
            state.confirmSubmitting.value = false;
            state.showTools.value = false;
            state.showImportPreview.value = false;
            state.showImportConflicts.value = false;
            state.showImportReport.value = false;
            state.copyMenuEntryId.value = null;
            state.showTagDropdown.value = false;
            state.restoreWizard.visible = false;
            state.revealedFields.value = [];
            autoLock.clearAutoLockTimer();
        }

        function handleDesktopLockRequest() {
            applyLockedState();
            desktopLockCover.scheduleRelease();
        }

        function handleDesktopCloseRequest() {
            state.desktopCloseRemember.value = false;
            state.desktopCloseSubmitting.value = false;
            state.desktopCloseError.value = '';
            state.showDesktopCloseConfirm.value = true;
        }

        const autoLock = autoLockFactory({
            settingsForm: state.settingsForm,
            locked: state.locked,
            initialized: state.initialized,
            store,
            applyLockedState
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
            try {
                await store.initPassword(state.password.value);
                state.initialized.value = true;
                state.locked.value = false;
                desktopLockCover.clear();
                state.password.value = '';
                state.confirmPassword.value = '';
                await data.applySettings(await store.loadSettings(), theme);
                await data.loadAllData();
                autoLock.startAutoLockTimer();
                state.showOnboarding.value = true;
                showToast('欢迎使用 SecretBase', 'success');
            } catch (error) {
                state.passwordError.value = error.message || '设置失败';
            } finally {
                state.submitting.value = false;
            }
        }

        async function unlock() {
            if (!state.password.value) {
                state.unlockError.value = '请输入密码';
                return;
            }

            state.submitting.value = true;
            state.unlockError.value = '';
            try {
                await store.unlock(state.password.value);
                state.locked.value = false;
                desktopLockCover.clear();
                state.password.value = '';
                await data.applySettings(await store.loadSettings(), theme);
                await data.loadAllData();
                autoLock.startAutoLockTimer();
            } catch (error) {
                state.unlockError.value = error.message || '解锁失败';
            } finally {
                state.submitting.value = false;
            }
        }

        async function lock() {
            try {
                await store.lock();
            } finally {
                applyLockedState();
            }
        }

        async function openSettings() {
            state.showSettings.value = true;
            state.activeSettingsTab.value = 'general';
            if (state.aiSettingsStatus.value === null) {
                await loadAiSettingsStatus();
            }
        }

        async function selectSettingsTab(tabKey) {
            state.activeSettingsTab.value = tabKey;
            if (tabKey === 'ai') {
                await loadAiSettingsStatus();
            } else if (tabKey === 'desktop') {
                await loadDesktopDiagnostics();
            }
        }

        async function saveSettings() {
            state.settingsForm.autoBackupRetention = Math.min(
                200,
                Math.max(5, Number(state.settingsForm.autoBackupRetention || 30))
            );
            await store.updateSettings({
                theme: state.settingsForm.theme,
                pageSize: state.settingsForm.pageSize,
                autoLockMinutes: state.settingsForm.autoLockMinutes,
                autoBackupRetention: state.settingsForm.autoBackupRetention
            });
            theme.currentTheme.value = state.settingsForm.theme;
            theme.applyTheme(state.settingsForm.theme);
            autoLock.startAutoLockTimer();
            if (!state.locked.value) {
                await data.loadEntries(1);
            }
        }

        async function changePassword() {
            if (state.passwordChanging.value) return;
            state.passwordForm.error = '';
            if (!state.passwordForm.oldPassword) {
                state.passwordForm.error = '请输入旧密码';
                return;
            }
            if (state.passwordForm.newPassword.length < 8 || state.passwordForm.newPassword.length > 128) {
                state.passwordForm.error = '新密码必须为 8 至 128 个字符';
                return;
            }
            if (state.passwordForm.newPassword !== state.passwordForm.confirmPassword) {
                state.passwordForm.error = '两次输入的密码不一致';
                return;
            }

            state.passwordChanging.value = true;
            try {
                await api.post('/auth/change-password', {
                    old_password: state.passwordForm.oldPassword,
                    new_password: state.passwordForm.newPassword
                });
                showToast('主密码已更新', 'success');
                state.showChangePassword.value = false;
                state.passwordForm.oldPassword = '';
                state.passwordForm.newPassword = '';
                state.passwordForm.confirmPassword = '';
            } catch (error) {
                state.passwordForm.error = error.message || '修改失败';
            } finally { state.passwordChanging.value = false; }
        }

        function registerLifecycle({ onMounted, onUnmounted }) {
            onMounted(async () => {
                window.SECRETBASE_DESKTOP_LOCK_READY = true;
                window.SECRETBASE_DESKTOP_CLOSE_READY = true;
                window.addEventListener('secretbase:desktop-lock', handleDesktopLockRequest);
                window.addEventListener('secretbase:desktop-close-request', handleDesktopCloseRequest);
                initializeDesktopUpdates();
                try {
                    const authStatus = await store.checkAuth();
                    state.initialized.value = authStatus.initialized;
                    window.addEventListener('secretbase:unauthorized', autoLock.handleUnauthorizedLock);
                    document.addEventListener('click', handleDocumentClick);

                    const hasSessionToken = Boolean(api.getToken());
                    state.locked.value = authStatus.locked || (authStatus.initialized && !hasSessionToken);
                    if (state.locked.value) {
                        api.setToken(null);
                        store.setState({ locked: true });
                    }

                    const settings = state.locked.value
                        ? {
                            ...store.state.settings,
                            autoLockMinutes: authStatus.auto_lock_minutes ?? store.state.settings.autoLockMinutes
                        }
                        : await store.loadSettings();
                    await data.applySettings(settings, theme);
                    theme.startAutoThemeTimer();
                    loadSavedAdvancedFilters();
                    autoLock.bindActivityListeners();
                    aiNowTimer = window.setInterval(() => {
                        state.aiNow.value = Date.now();
                    }, 1000);

                    if (!state.locked.value) {
                        await data.loadAllData();
                        autoLock.startAutoLockTimer();
                    }
                } catch (error) {
                    console.error('初始化失败:', error);
                } finally {
                    state.loading.value = false;
                    desktopLockCover.scheduleRelease();
                }
            });
            onUnmounted(() => {
                window.SECRETBASE_DESKTOP_LOCK_READY = false;
                window.SECRETBASE_DESKTOP_CLOSE_READY = false;
                window.removeEventListener('secretbase:desktop-lock', handleDesktopLockRequest);
                window.removeEventListener('secretbase:desktop-close-request', handleDesktopCloseRequest);
                window.removeEventListener('secretbase:unauthorized', autoLock.handleUnauthorizedLock);
                document.removeEventListener('click', handleDocumentClick);
                autoLock.unbindActivityListeners();
                theme.clearAutoThemeTimer();
                autoLock.clearAutoLockTimer();
                if (aiNowTimer !== null) {
                    window.clearInterval(aiNowTimer);
                    aiNowTimer = null;
                }
                disposeDesktopUpdates();
            });
        }
        return {
            ...autoLock,
            applyLockedState,
            initPassword,
            unlock,
            lock,
            openSettings,
            selectSettingsTab,
            saveSettings,
            changePassword,
            registerLifecycle
        };
    }
    window.SecretBaseAppSessionController = { createAppSessionController };
})();
