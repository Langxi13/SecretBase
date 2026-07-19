/**
 * 会话内的通用设置保存和主密码修改。
 */
(function () {
    function createSessionSettingsActions({
        api,
        store,
        state,
        showToast,
        theme,
        data,
        autoLock,
        getAuthOperationEpoch,
        isCurrentAuthOperation
    }) {
        async function saveSettings() {
            if (state.settingsSaving.value) return;
            const persistedSettings = store.state.settings || {};
            const previousForm = {
                ...state.settingsForm,
                theme: persistedSettings.theme ?? theme.currentTheme.value,
                pageSize: persistedSettings.pageSize ?? state.settingsForm.pageSize,
                autoLockMinutes: persistedSettings.autoLockMinutes ?? state.settingsForm.autoLockMinutes,
                autoBackupRetention: persistedSettings.autoBackupRetention ?? state.settingsForm.autoBackupRetention
            };
            state.settingsSaving.value = true;
            state.settingsError.value = '';
            state.settingsForm.autoBackupRetention = Math.min(
                200,
                Math.max(5, Number(state.settingsForm.autoBackupRetention || 30))
            );
            const epoch = getAuthOperationEpoch();
            try {
                await store.updateSettings({
                    theme: state.settingsForm.theme,
                    pageSize: state.settingsForm.pageSize,
                    autoLockMinutes: state.settingsForm.autoLockMinutes,
                    autoBackupRetention: state.settingsForm.autoBackupRetention
                });
                if (!isCurrentAuthOperation(epoch)) return;
                theme.currentTheme.value = state.settingsForm.theme;
                theme.applyTheme(state.settingsForm.theme);
                autoLock.startAutoLockTimer();
                if (!state.locked.value) {
                    const refreshed = await data.loadEntries(1);
                    if (!isCurrentAuthOperation(epoch)) return;
                    if (refreshed === false) {
                        showToast('设置已保存，但条目列表刷新不完整，请稍后重试。', 'warning');
                    }
                }
            } catch (error) {
                if (!isCurrentAuthOperation(epoch)) return;
                Object.assign(state.settingsForm, previousForm);
                theme.currentTheme.value = previousForm.theme;
                theme.applyTheme(previousForm.theme);
                state.settingsError.value = error?.message || '设置保存失败，请重试。';
                showToast(state.settingsError.value, 'error');
            } finally {
                if (isCurrentAuthOperation(epoch)) state.settingsSaving.value = false;
            }
        }

        async function changePassword() {
            if (state.passwordChanging.value) return;
            state.passwordForm.error = '';
            if (!state.passwordForm.oldPassword) {
                state.passwordForm.error = '请输入旧密码';
                return;
            }
            if (
                state.passwordForm.newPassword.length < 8
                || state.passwordForm.newPassword.length > 128
            ) {
                state.passwordForm.error = '新密码必须为 8 至 128 个字符';
                return;
            }
            if (state.passwordForm.newPassword !== state.passwordForm.confirmPassword) {
                state.passwordForm.error = '两次输入的密码不一致';
                return;
            }

            state.passwordChanging.value = true;
            const epoch = getAuthOperationEpoch();
            try {
                await api.post('/auth/change-password', {
                    old_password: state.passwordForm.oldPassword,
                    new_password: state.passwordForm.newPassword
                });
                if (!isCurrentAuthOperation(epoch)) return;
                showToast('主密码已更新', 'success');
                state.showChangePassword.value = false;
                state.passwordForm.oldPassword = '';
                state.passwordForm.newPassword = '';
                state.passwordForm.confirmPassword = '';
            } catch (error) {
                if (isCurrentAuthOperation(epoch)) {
                    state.passwordForm.error = error.message || '修改失败';
                }
            } finally {
                if (isCurrentAuthOperation(epoch)) state.passwordChanging.value = false;
            }
        }

        return { saveSettings, changePassword };
    }

    window.SecretBaseSessionSettings = { createSessionSettingsActions };
})();
