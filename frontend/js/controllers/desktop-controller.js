/**
 * 跨平台桌面状态、目录入口、更新检查与关闭偏好。
 */
(function () {
    function nativeDesktopApi() {
        return window.pywebview && window.pywebview.api;
    }

    function createDesktopController({ computed, copyToClipboard, openExternalUrl, store, showToast, state }) {
        const desktopPackageLabel = computed(() => {
            const packageType = state.desktopDiagnostics.value?.package_type;
            if (packageType === 'installed') return '安装版';
            if (packageType === 'portable') return '便携版';
            if (packageType === 'source') return '源码模式';
            return '检测中';
        });
        const desktopStatusLabel = computed(() => {
            if (!state.desktopDiagnostics.value) return '尚未检查';
            return state.desktopDiagnostics.value.status === 'ok' ? '运行正常' : '需要处理';
        });
        const desktopCapabilities = computed(() => {
            return state.desktopDiagnostics.value?.capabilities || state.desktopRuntimeCapabilities || {};
        });
        const desktopSupportsTray = computed(() => desktopCapabilities.value.tray === true);
        const desktopPlatformLabel = computed(() => {
            const platform = state.desktopDiagnostics.value?.platform || state.desktopPlatform;
            if (platform === 'windows') return 'Windows';
            if (platform === 'macos') return 'macOS';
            return '桌面';
        });

        function requireDesktopApi(method) {
            const api = nativeDesktopApi();
            if (!state.isDesktopMode || !api || typeof api[method] !== 'function') {
                throw new Error('当前环境不支持该桌面功能');
            }
            return api;
        }

        async function loadDesktopDiagnostics() {
            if (!state.isDesktopMode) return null;
            state.desktopDiagnosticsLoading.value = true;
            state.desktopDiagnosticsError.value = '';
            try {
                const api = requireDesktopApi('get_diagnostics');
                const result = await api.get_diagnostics();
                state.desktopDiagnostics.value = result;
                return result;
            } catch (error) {
                state.desktopDiagnosticsError.value = error.message || '无法读取桌面状态';
                return null;
            } finally {
                state.desktopDiagnosticsLoading.value = false;
            }
        }

        async function openDesktopStatus() {
            if (!state.isDesktopMode) return;
            state.showDesktopStatus.value = true;
            await loadDesktopDiagnostics();
        }

        async function openDesktopDirectory(kind) {
            try {
                const api = requireDesktopApi('open_directory');
                await api.open_directory(kind);
            } catch (error) {
                showToast(error.message || '无法打开目录', 'error');
            }
        }

        async function copyDesktopDiagnostics() {
            const diagnostics = state.desktopDiagnostics.value || await loadDesktopDiagnostics();
            if (!diagnostics?.support_summary) {
                showToast('暂无可复制的诊断信息', 'warning');
                return;
            }
            const copied = await copyToClipboard(diagnostics.support_summary);
            showToast(copied ? '诊断信息已复制' : '复制诊断信息失败', copied ? 'success' : 'error');
        }

        async function checkDesktopUpdates() {
            state.desktopUpdateChecking.value = true;
            state.desktopUpdateError.value = '';
            try {
                const api = requireDesktopApi('check_for_updates');
                const result = await api.check_for_updates();
                state.desktopUpdateResult.value = result;
                if (result.status === 'error') {
                    state.desktopUpdateError.value = result.message || '无法检查更新';
                }
                return result;
            } catch (error) {
                state.desktopUpdateResult.value = null;
                state.desktopUpdateError.value = error.message || '无法检查更新';
                return null;
            } finally {
                state.desktopUpdateChecking.value = false;
            }
        }

        async function openDesktopRelease() {
            const url = state.desktopUpdateResult.value?.release_url;
            if (!url) return;
            try {
                await openExternalUrl(url);
            } catch (error) {
                showToast(error.message || '无法打开下载页面', 'error');
            }
        }

        async function saveCloseToTraySetting() {
            if (state.desktopCloseSettingsSaving.value) return;
            state.desktopCloseSettingsSaving.value = true;
            const desired = {
                closeToTray: desktopSupportsTray.value && Boolean(state.settingsForm.closeToTray),
                confirmClose: state.settingsForm.confirmClose !== false
            };
            const previous = {
                closeToTray: Boolean(store.state.settings.closeToTray),
                confirmClose: store.state.settings.confirmClose !== false
            };
            try {
                const api = requireDesktopApi('set_close_preferences');
                await api.set_close_preferences(desired.closeToTray, desired.confirmClose);
                await store.updateSettings(desired);
                const message = desired.confirmClose
                    ? '关闭窗口时将先询问'
                    : (desired.closeToTray ? '关闭窗口将隐藏到托盘' : '关闭窗口将直接退出');
                showToast(message, 'success');
            } catch (error) {
                state.settingsForm.closeToTray = previous.closeToTray;
                state.settingsForm.confirmClose = previous.confirmClose;
                try {
                    const api = requireDesktopApi('set_close_preferences');
                    await api.set_close_preferences(previous.closeToTray, previous.confirmClose);
                } catch (_rollbackError) {
                    // 原始错误更有助于用户处理。
                }
                showToast(error.message || '保存关闭设置失败', 'error');
            } finally {
                state.desktopCloseSettingsSaving.value = false;
            }
        }

        function cancelDesktopClose() {
            if (state.desktopCloseSubmitting.value) return;
            state.showDesktopCloseConfirm.value = false;
            state.desktopCloseRemember.value = false;
            state.desktopCloseError.value = '';
        }

        async function resolveDesktopClose(action) {
            if (!['tray', 'exit'].includes(action) || state.desktopCloseSubmitting.value) return;
            if (action === 'tray' && !desktopSupportsTray.value) return;
            state.desktopCloseSubmitting.value = true;
            state.desktopCloseError.value = '';
            try {
                const api = requireDesktopApi('resolve_close_request');
                await api.resolve_close_request(action, Boolean(state.desktopCloseRemember.value));
            } catch (error) {
                state.desktopCloseError.value = error.message || '无法完成关闭操作';
                state.showDesktopCloseConfirm.value = true;
            } finally {
                state.desktopCloseSubmitting.value = false;
            }
        }

        function desktopCheckStatusLabel(status) {
            if (status === 'ok') return '正常';
            if (status === 'warning') return '提醒';
            return '异常';
        }

        return {
            views: {
                desktopPackageLabel,
                desktopStatusLabel,
                desktopCapabilities,
                desktopSupportsTray,
                desktopPlatformLabel
            },
            actions: {
                loadDesktopDiagnostics,
                openDesktopStatus,
                openDesktopDirectory,
                copyDesktopDiagnostics,
                checkDesktopUpdates,
                openDesktopRelease,
                saveCloseToTraySetting,
                cancelDesktopClose,
                resolveDesktopClose,
                desktopCheckStatusLabel
            }
        };
    }

    window.SecretBaseDesktopController = {
        createDesktopController
    };
})();
