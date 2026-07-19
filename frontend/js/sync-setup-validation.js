/**
 * 同步创建/加入表单的校验与反馈，不承载实际网络操作。
 */
(function () {
    function createSyncSetupValidation({ computed, state, showToast }) {
        const syncSetupMissingFields = computed(() => {
            const form = state.syncSetupForm;
            const missing = [];
            if (!String(form.baseUrl || '').trim()) missing.push('WebDAV 地址');
            if (!String(form.username || '').trim()) missing.push('用户名');
            if (!String(form.password || '')) missing.push('WebDAV 应用密码');
            if (state.syncSetupMode.value === 'join' && !String(form.recoveryCode || '').trim()) {
                missing.push('同步恢复码或配对链接');
            }
            return missing;
        });
        const syncSetupCanSubmit = computed(() => {
            return !state.syncBusy.value && !state.syncSetupTesting.value && !state.syncPairingReading.value;
        });

        function clearSyncSetupFeedback({ clearMessage = false } = {}) {
            state.syncSetupError.value = '';
            if (clearMessage) state.syncSetupMessage.value = '';
        }

        function markSyncSetupDirty() {
            state.syncSetupTestPassed.value = false;
            clearSyncSetupFeedback();
            state.syncError.value = '';
        }

        function reportSyncSetupError(error, fallback = '同步空间配置失败') {
            const message = typeof error === 'string' ? error : error?.message || fallback;
            state.syncSetupError.value = message;
            state.syncError.value = message;
            showToast(message, 'error');
            return message;
        }

        function validateSyncSetup({ requireRecovery = true } = {}) {
            const form = state.syncSetupForm;
            const baseUrl = String(form.baseUrl || '').trim();
            const username = String(form.username || '').trim();
            const password = String(form.password || '');
            const recoveryCode = String(form.recoveryCode || '').trim();
            if (!baseUrl || !username || !password) {
                const missing = syncSetupMissingFields.value.filter(item => item !== '同步恢复码或配对链接');
                reportSyncSetupError(`请补充：${missing.length ? missing.join('、') : 'WebDAV 连接信息'}`);
                return false;
            }
            try {
                const url = new URL(baseUrl);
                if (url.protocol !== 'https:' || !url.hostname) {
                    reportSyncSetupError('WebDAV 地址必须是有效的 HTTPS 地址');
                    return false;
                }
            } catch (_) {
                reportSyncSetupError('WebDAV 地址格式无效，请检查后重试');
                return false;
            }
            if (requireRecovery && state.syncSetupMode.value === 'join' && !recoveryCode) {
                reportSyncSetupError(
                    String(form.pairingUri || '').trim()
                        ? '请先点击“读取配对信息”，或再次点击加入让系统自动读取配对链接'
                        : '加入现有空间需要填写同步恢复码，或粘贴配对链接'
                );
                return false;
            }
            return true;
        }

        return {
            syncSetupMissingFields,
            syncSetupCanSubmit,
            clearSyncSetupFeedback,
            markSyncSetupDirty,
            reportSyncSetupError,
            validateSyncSetup
        };
    }

    window.SecretBaseSyncSetupValidation = { createSyncSetupValidation };
})();
