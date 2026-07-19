/**
 * 跨平台桌面状态、目录入口、更新检查与关闭偏好。
 */
(function () {
    function nativeDesktopApi() {
        return window.pywebview && window.pywebview.api;
    }

    function createDesktopController({
        computed,
        copyToClipboard,
        openExternalUrl,
        store,
        showToast,
        showConfirmDialog,
        state
    }) {
        let updatePollTimer = null;
        let updatePollInFlight = false;
        let desktopRequestEpoch = 0;
        let desktopDialogEpoch = 0;
        const isCurrentDesktopRequest = epoch => epoch === desktopRequestEpoch;
        const diagnosticsSurfaceOpen = () => (
            state.showDesktopStatus?.value === true || state.showSettings?.value === true
        );
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
        const desktopUpdateBusy = computed(() => {
            return ['scheduled', 'checking', 'downloading', 'installing'].includes(
                state.desktopUpdateResult.value?.status
            );
        });
        const desktopUpdateProgress = computed(() => {
            return Math.max(0, Math.min(100, Number(state.desktopUpdateResult.value?.progress || 0)));
        });
        const desktopUpdateActionLabel = computed(() => {
            const result = state.desktopUpdateResult.value;
            if (!result) return '';
            if (result.status === 'downloading') return `正在下载 ${desktopUpdateProgress.value}%`;
            if (result.status === 'ready') return '立即更新';
            if (result.status === 'available' && result.install_supported) return '下载更新';
            if (result.status === 'available') return '打开下载链接';
            if (result.status === 'installing') return '正在启动安装';
            return '';
        });

        function requireDesktopApi(method) {
            const api = nativeDesktopApi();
            if (!state.isDesktopMode || !api || typeof api[method] !== 'function') {
                throw new Error('当前环境不支持该桌面功能');
            }
            return api;
        }

        async function loadDesktopDiagnostics() {
            if (!state.isDesktopMode || state.locked?.value) return null;
            const epoch = desktopRequestEpoch;
            const dialogEpoch = desktopDialogEpoch;
            state.desktopDiagnosticsLoading.value = true;
            state.desktopDiagnosticsError.value = '';
            try {
                const api = requireDesktopApi('get_diagnostics');
                const result = await api.get_diagnostics();
                if (
                    !isCurrentDesktopRequest(epoch)
                    || dialogEpoch !== desktopDialogEpoch
                    || state.locked?.value
                    || !diagnosticsSurfaceOpen()
                ) return null;
                state.desktopDiagnostics.value = result;
                return result;
            } catch (error) {
                if (
                    isCurrentDesktopRequest(epoch)
                    && dialogEpoch === desktopDialogEpoch
                    && diagnosticsSurfaceOpen()
                ) {
                    state.desktopDiagnosticsError.value = error.message || '无法读取桌面状态';
                }
                return null;
            } finally {
                if (isCurrentDesktopRequest(epoch) && dialogEpoch === desktopDialogEpoch) {
                    state.desktopDiagnosticsLoading.value = false;
                }
            }
        }

        async function openDesktopStatus() {
            if (!state.isDesktopMode) return;
            const dialogEpoch = ++desktopDialogEpoch;
            state.showDesktopStatus.value = true;
            await loadDesktopDiagnostics();
            if (dialogEpoch !== desktopDialogEpoch) return;
        }

        function closeDesktopStatus() {
            desktopDialogEpoch += 1;
            state.showDesktopStatus.value = false;
            state.desktopDiagnosticsLoading.value = false;
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

        function applyDesktopUpdateState(result) {
            if (!result) return null;
            state.desktopUpdateResult.value = result;
            state.desktopUpdateError.value = result.status === 'error' ? (result.message || '无法检查更新') : '';
            if (result.preferences) {
                state.settingsForm.desktopUpdateAutoCheck = result.preferences.auto_check !== false;
                state.settingsForm.desktopUpdateAutoDownload = result.preferences.auto_download !== false;
            }
            if (['scheduled', 'checking', 'downloading'].includes(result.status)) {
                startUpdatePolling();
            } else {
                stopUpdatePolling();
            }
            return result;
        }

        function stopUpdatePolling() {
            if (updatePollTimer !== null) {
                window.clearInterval(updatePollTimer);
                updatePollTimer = null;
            }
        }

        function startUpdatePolling() {
            if (updatePollTimer !== null) return;
            updatePollTimer = window.setInterval(refreshDesktopUpdateState, 700);
        }

        async function refreshDesktopUpdateState() {
            if (!state.isDesktopMode || state.locked?.value) return null;
            if (updatePollInFlight) return null;
            updatePollInFlight = true;
            const epoch = desktopRequestEpoch;
            try {
                const api = requireDesktopApi('get_update_state');
                const result = await api.get_update_state();
                return isCurrentDesktopRequest(epoch) && !state.locked?.value
                    ? applyDesktopUpdateState(result)
                    : null;
            } catch (error) {
                if (isCurrentDesktopRequest(epoch)) {
                    state.desktopUpdateError.value = error.message || '无法读取更新状态';
                    stopUpdatePolling();
                }
                return null;
            } finally {
                updatePollInFlight = false;
            }
        }

        async function initializeDesktopUpdates() {
            if (!state.isDesktopMode || state.locked?.value) return null;
            const epoch = desktopRequestEpoch;
            try {
                const api = requireDesktopApi('start_background_update_check');
                const result = await api.start_background_update_check();
                return isCurrentDesktopRequest(epoch) && !state.locked?.value
                    ? applyDesktopUpdateState(result)
                    : null;
            } catch (error) {
                if (isCurrentDesktopRequest(epoch)) {
                    state.desktopUpdateError.value = error.message || '无法初始化更新检查';
                }
                return null;
            }
        }

        function disposeDesktopUpdates() {
            desktopRequestEpoch += 1;
            desktopDialogEpoch += 1;
            stopUpdatePolling();
        }

        async function checkDesktopUpdates() {
            if (state.locked?.value || desktopUpdateBusy.value || state.desktopUpdateChecking.value) return null;
            const epoch = desktopRequestEpoch;
            state.desktopUpdateChecking.value = true;
            state.desktopUpdateError.value = '';
            try {
                const api = requireDesktopApi('check_for_updates');
                const result = await api.check_for_updates();
                return isCurrentDesktopRequest(epoch) && !state.locked?.value
                    ? applyDesktopUpdateState(result)
                    : null;
            } catch (error) {
                if (isCurrentDesktopRequest(epoch)) {
                    state.desktopUpdateResult.value = null;
                    state.desktopUpdateError.value = error.message || '无法检查更新';
                }
                return null;
            } finally {
                if (isCurrentDesktopRequest(epoch)) state.desktopUpdateChecking.value = false;
            }
        }

        async function openDesktopRelease() {
            const result = state.desktopUpdateResult.value;
            const url = result?.manual_download_url || result?.release_url;
            if (!url) return;
            try {
                await openExternalUrl(url);
            } catch (error) {
                showToast(error.message || '无法打开下载页面', 'error');
            }
        }

        async function saveDesktopUpdatePreferences() {
            const epoch = desktopRequestEpoch;
            try {
                const api = requireDesktopApi('set_update_preferences');
                const result = await api.set_update_preferences(
                    Boolean(state.settingsForm.desktopUpdateAutoCheck),
                    Boolean(state.settingsForm.desktopUpdateAutoDownload)
                );
                if (!isCurrentDesktopRequest(epoch)) return;
                applyDesktopUpdateState(result);
                showToast('更新偏好已保存', 'success');
            } catch (error) {
                showToast(error.message || '保存更新偏好失败', 'error');
                await refreshDesktopUpdateState();
            }
        }

        async function startDesktopUpdateDownload() {
            if (state.locked?.value || desktopUpdateBusy.value) return null;
            const epoch = desktopRequestEpoch;
            try {
                const api = requireDesktopApi('start_update_download');
                const result = await api.start_update_download();
                if (!isCurrentDesktopRequest(epoch)) return;
                applyDesktopUpdateState(result);
                startUpdatePolling();
            } catch (error) {
                showToast(error.message || '无法下载更新', 'error');
            }
        }

        async function cancelDesktopUpdateDownload() {
            if (state.locked?.value || state.desktopUpdateResult.value?.status !== 'downloading') return null;
            const epoch = desktopRequestEpoch;
            try {
                const api = requireDesktopApi('cancel_update_download');
                const result = await api.cancel_update_download();
                if (!isCurrentDesktopRequest(epoch)) return;
                applyDesktopUpdateState(result);
            } catch (error) {
                showToast(error.message || '无法取消更新下载', 'error');
            }
        }

        function installDesktopUpdate() {
            if (state.desktopUpdateResult.value?.status !== 'ready' || desktopUpdateBusy.value) return;
            showConfirmDialog(
                '安装更新',
                '应用将立即锁定密码库、退出并安装更新，完成后自动重新打开。确认继续？',
                async () => {
                    try {
                        const api = requireDesktopApi('install_downloaded_update');
                        applyDesktopUpdateState(await api.install_downloaded_update());
                    } catch (error) {
                        await refreshDesktopUpdateState();
                        throw new Error(error.message || '无法启动更新安装程序');
                    }
                }
            );
        }

        function handleDesktopUpdateAction() {
            const result = state.desktopUpdateResult.value;
            if (!result) return;
            if (result.status === 'ready') {
                installDesktopUpdate();
            } else if (result.status === 'available' && result.install_supported) {
                startDesktopUpdateDownload();
            } else if (result.status === 'available') {
                openDesktopRelease();
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
                desktopPlatformLabel,
                desktopUpdateBusy,
                desktopUpdateProgress,
                desktopUpdateActionLabel
            },
            actions: {
                loadDesktopDiagnostics,
                openDesktopStatus,
                closeDesktopStatus,
                openDesktopDirectory,
                copyDesktopDiagnostics,
                checkDesktopUpdates,
                refreshDesktopUpdateState,
                initializeDesktopUpdates,
                disposeDesktopUpdates,
                openDesktopRelease,
                saveDesktopUpdatePreferences,
                startDesktopUpdateDownload,
                cancelDesktopUpdateDownload,
                installDesktopUpdate,
                handleDesktopUpdateAction,
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
