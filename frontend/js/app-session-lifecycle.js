/**
 * 根应用的启动、重试和生命周期监听。
 * 认证写入仍由会话控制器负责，这里只协调页面状态与跨模块初始化。
 */
(function () {
    function createSessionLifecycle({
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
        disposeAiSettings = () => {},
        disposeAiAssistant = () => {},
        disposeAiTools = () => {},
        initializeSync,
        pauseSync,
        disposeSync,
        handleDocumentClick,
        handleDocumentKeydown = () => {},
        handleDesktopLockRequest,
        handleDesktopCloseRequest
    }) {
        let aiNowTimer = null;
        let lifecycleMounted = false;
        let initializationEpoch = 0;

        function startupErrorMessage(error) {
            if (error?.code === 'NETWORK_ERROR') return '无法连接本地服务，请确认服务正在运行后重试。';
            if (error?.code === 'REQUEST_TIMEOUT') return '本地服务响应超时，请稍后重试。';
            if (Number(error?.status) >= 500) return '本地服务暂时不可用，请稍后重试。';
            return error?.message || '应用初始化失败，请重试。';
        }

        async function initializeSession() {
            if (!lifecycleMounted || state.startupRetrying.value) return;
            const epoch = ++initializationEpoch;
            state.startupRetrying.value = true;
            state.startupError.value = '';
            state.loading.value = true;
            try {
                const authStatus = await store.checkAuth();
                if (!lifecycleMounted || epoch !== initializationEpoch) return;
                state.initialized.value = authStatus.initialized;
                const hasSessionToken = Boolean(api.getToken());
                state.locked.value = authStatus.locked || (authStatus.initialized && !hasSessionToken);
                if (state.locked.value) {
                    api.setToken(null);
                    store.setState({ locked: true });
                }

                let settings = store.state.settings;
                if (!state.locked.value) {
                    settings = await store.loadSettings();
                    if (!lifecycleMounted || epoch !== initializationEpoch) return;
                } else {
                    settings = {
                        ...settings,
                        autoLockMinutes: authStatus.auto_lock_minutes ?? settings.autoLockMinutes
                    };
                }
                try {
                    await data.applySettings(settings, theme);
                    if (!lifecycleMounted || epoch !== initializationEpoch) return;
                } catch (error) {
                    state.dataLoadError.value = error?.message || '设置读取失败，已使用当前配置继续。';
                }

                if (!state.locked.value) {
                    await data.loadAllData();
                    if (!lifecycleMounted || epoch !== initializationEpoch) return;
                    await initializeSync();
                    if (!lifecycleMounted || epoch !== initializationEpoch) return;
                    autoLock.startAutoLockTimer();
                }
                state.startupError.value = '';
            } catch (error) {
                if (!lifecycleMounted || epoch !== initializationEpoch) return;
                console.error('初始化失败:', error);
                if (typeof api.invalidateSession === 'function') api.invalidateSession();
                api.setToken(null);
                state.locked.value = true;
                state.startupError.value = startupErrorMessage(error);
            } finally {
                if (lifecycleMounted && epoch === initializationEpoch) {
                    state.loading.value = false;
                    state.startupRetrying.value = false;
                    desktopLockCover.scheduleRelease();
                }
            }
        }

        function retryInitialization() {
            return initializeSession();
        }

        function registerLifecycle({ onMounted, onUnmounted }) {
            onMounted(async () => {
                lifecycleMounted = true;
                window.SECRETBASE_DESKTOP_LOCK_READY = true;
                window.SECRETBASE_DESKTOP_CLOSE_READY = true;
                window.addEventListener('secretbase:desktop-lock', handleDesktopLockRequest);
                window.addEventListener('secretbase:desktop-close-request', handleDesktopCloseRequest);
                window.addEventListener('secretbase:unauthorized', autoLock.handleUnauthorizedLock);
                document.addEventListener('click', handleDocumentClick);
                document.addEventListener('keydown', handleDocumentKeydown);
                initializeDesktopUpdates();
                theme.startAutoThemeTimer();
                loadSavedAdvancedFilters();
                autoLock.bindActivityListeners();
                aiNowTimer = window.setInterval(() => {
                    state.aiNow.value = Date.now();
                }, 1000);
                await initializeSession();
            });
            onUnmounted(() => {
                lifecycleMounted = false;
                initializationEpoch += 1;
                window.SECRETBASE_DESKTOP_LOCK_READY = false;
                window.SECRETBASE_DESKTOP_CLOSE_READY = false;
                window.removeEventListener('secretbase:desktop-lock', handleDesktopLockRequest);
                window.removeEventListener('secretbase:desktop-close-request', handleDesktopCloseRequest);
                window.removeEventListener('secretbase:unauthorized', autoLock.handleUnauthorizedLock);
                document.removeEventListener('click', handleDocumentClick);
                document.removeEventListener('keydown', handleDocumentKeydown);
                autoLock.unbindActivityListeners();
                theme.clearAutoThemeTimer();
                autoLock.clearAutoLockTimer();
                if (aiNowTimer !== null) {
                    window.clearInterval(aiNowTimer);
                    aiNowTimer = null;
                }
                disposeDesktopUpdates();
                if (typeof api.invalidateSession === 'function') api.invalidateSession();
                disposeAiSettings();
                disposeAiAssistant();
                disposeAiTools();
                disposeSync();
            });
        }

        return { registerLifecycle, retryInitialization };
    }

    window.SecretBaseSessionLifecycle = { createSessionLifecycle };
})();
