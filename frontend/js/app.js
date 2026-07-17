/**
 * SecretBase Vue 应用装配入口。
 *
 * 领域状态、控制器和模板上下文已拆至独立模块；此处只保留依赖连接顺序。
 */
const { createApp, ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } = Vue;

const app = createApp({
    setup() {
        const pagination = window.SecretBasePagination;
        const viewHelpers = window.SecretBaseViewHelpers;
        const state = window.SecretBaseAppState.createAppState({
            ref,
            reactive,
            computed,
            loadPageSizePreference: pagination.loadPageSizePreference,
            defaultSearchScopes: window.SecretBaseStoreState.DEFAULT_SEARCH_SCOPES
        });
        const ui = window.SecretBaseAppUiController.createAppUiController({
            state,
            store,
            viewHelpers
        });
        const theme = window.SecretBaseThemeController.createThemeController({
            ref,
            computed,
            settingsForm: state.settingsForm,
            store
        });

        let features;
        const data = window.SecretBaseAppDataController.createAppDataController({
            api,
            store,
            state,
            normalizeUniversalPageSize: pagination.normalizeUniversalPageSize,
            loadPageSizePreference: pagination.loadPageSizePreference,
            savePageSizePreference: pagination.savePageSizePreference,
            getGroupTotalPages: () => features.views.groupTotalPages.value
        });
        const settingsActions = {};
        features = window.SecretBaseFeatureComposition.createFeatureComposition({
            computed,
            nextTick,
            debounce,
            copyToClipboard,
            openExternalUrl,
            api,
            store,
            showToast,
            state,
            data,
            ui,
            viewHelpers,
            settingsActions,
            pagination
        });
        const session = window.SecretBaseAppSessionController.createAppSessionController({
            api,
            store,
            state,
            showToast,
            autoLockFactory: window.SecretBaseAutoLock.createAutoLockController,
            theme,
            data,
            loadSavedAdvancedFilters: features.actions.loadSavedAdvancedFilters,
            loadAiSettingsStatus: features.actions.loadAiSettingsStatus,
            loadDesktopDiagnostics: features.actions.loadDesktopDiagnostics,
            initializeDesktopUpdates: features.actions.initializeDesktopUpdates,
            disposeDesktopUpdates: features.actions.disposeDesktopUpdates,
            initializeSync: features.actions.initializeSync,
            pauseSync: features.actions.pauseSync,
            disposeSync: features.actions.disposeSync,
            handleDocumentClick: features.actions.handleDocumentClick
        });
        Object.assign(settingsActions, session);

        window.SecretBaseAppWatchers.registerAppWatchers({
            watch,
            state,
            views: features.views,
            actions: features.actions,
            savePageSizePreference: pagination.savePageSizePreference
        });
        session.registerLifecycle({ onMounted, onUnmounted });

        return window.SecretBaseTemplateContext.createTemplateContext({
            state,
            views: features.views,
            actions: features.actions,
            ui,
            theme,
            data,
            session
        });
    }
});

window.SecretBaseTemplateLoader.mount(app);
