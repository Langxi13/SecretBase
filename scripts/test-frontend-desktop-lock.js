const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'frontend/js/app-session-controller.js'), 'utf8');
const lifecycleSource = fs.readFileSync(path.join(root, 'frontend/js/app-session-lifecycle.js'), 'utf8');
const securitySource = fs.readFileSync(path.join(root, 'frontend/js/app-session-security.js'), 'utf8');
const settingsSource = fs.readFileSync(path.join(root, 'frontend/js/app-session-settings.js'), 'utf8');
const coverSource = fs.readFileSync(path.join(root, 'frontend/js/desktop-lock-cover.js'), 'utf8');

function ref(value) {
    return { value };
}

const windowListeners = new Map();
const documentListeners = new Map();
let animationFrame = null;
let fallbackTimeout = null;
let finishPasswordChange = null;
let passwordChangeCalls = 0;
let invalidationCalls = 0;
const attributes = new Set();

const sandbox = {
    console,
    Promise,
    window: {
        addEventListener(name, callback) {
            windowListeners.set(name, callback);
        },
        removeEventListener(name, callback) {
            if (windowListeners.get(name) === callback) windowListeners.delete(name);
        },
        requestAnimationFrame(callback) {
            animationFrame = callback;
            return 1;
        },
        setTimeout(callback) {
            fallbackTimeout = callback;
            return 2;
        },
        setInterval() {
            return 1;
        },
        clearInterval() {}
    },
    document: {
        documentElement: {
            removeAttribute(name) {
                attributes.delete(name);
            }
        },
        addEventListener(name, callback) {
            documentListeners.set(name, callback);
        },
        removeEventListener(name, callback) {
            if (documentListeners.get(name) === callback) documentListeners.delete(name);
        }
    }
};
sandbox.window.window = sandbox.window;
const context = vm.createContext(sandbox);
vm.runInContext(coverSource, context);
vm.runInContext(lifecycleSource, context);
vm.runInContext(securitySource, context);
vm.runInContext(settingsSource, context);
vm.runInContext(source, context);

const state = {
    initialized: ref(true),
    locked: ref(false),
    password: ref('master-password'),
    confirmPassword: ref(''),
    passwordError: ref(''),
    unlockError: ref(''),
    submitting: ref(false),
    passwordChanging: ref(false),
    entries: ref([{ id: 'sensitive-entry' }]),
    tags: ref([{ name: 'sensitive-tag' }]),
    groups: ref([{ name: 'sensitive-group' }]),
    trashItems: ref([{ id: 'sensitive-trash' }]),
    backups: ref([{ filename: 'sensitive-backup' }]),
    groupPickerEntries: ref([{ id: 'sensitive-picker-entry' }]),
    healthReport: ref({ sensitive: true }),
    maintenanceReport: ref({ sensitive: true }),
    securityReport: ref({ sensitive: true }),
    importPreview: ref({ sensitive: true }),
    importConflicts: ref([{ sensitive: true }]),
    importReport: ref({ sensitive: true }),
    lastImportPlainFile: ref({ name: 'sensitive.json' }),
    importPreviewSelectedIds: ref(['sensitive-entry']),
    lastImportSelectedIds: ref(['sensitive-entry']),
    importConflictResolutions: ref({ sensitive: 'skip' }),
    lastImportConflictResolutions: ref({ sensitive: 'skip' }),
    trashError: ref('stale-trash-error'),
    importConflictMessage: ref('stale-import-error'),
    selectedEntry: ref({ id: 'sensitive-entry' }),
    editingEntry: ref({ id: 'sensitive-entry' }),
    selectedEntryIds: ref(['sensitive-entry']),
    groupPickerSelectedIds: ref(['sensitive-entry']),
    showCreateModal: ref(true),
    showEditModal: ref(true),
    showAiParse: ref(true),
    showAiAssistant: ref(true),
    aiAssistantInput: ref('sensitive prompt'),
    resetAiAssistantSession() {
        this.aiAssistantInput.value = '';
    },
    showSettings: ref(true),
    showDesktopStatus: ref(true),
    showDesktopCloseConfirm: ref(false),
    desktopCloseRemember: ref(true),
    desktopCloseSubmitting: ref(true),
    desktopCloseError: ref('stale-error'),
    desktopCloseSettingsSaving: ref(true),
    showTrash: ref(true),
    showTagManager: ref(true),
    showTagEditorModal: ref(true),
    showGroupModal: ref(true),
    showTagBrowser: ref(true),
    showGroupEntryPicker: ref(true),
    entrySaving: ref(true),
    groupSaving: ref(true),
    tagSaving: ref(true),
    tagMerging: ref(true),
    groupPickerSaving: ref(true),
    showChangePassword: ref(true),
    showBackupCenter: ref(true),
    showConfirm: ref(true),
    confirmSubmitting: ref(true),
    showTools: ref(true),
    showImportPreview: ref(true),
    showImportConflicts: ref(true),
    showImportReport: ref(true),
    copyMenuEntryId: ref('sensitive-entry'),
    showTagDropdown: ref(true),
    restoreWizard: {
        visible: true,
        backup: { filename: 'sensitive-backup' },
        summary: { sensitive: true },
        password: 'sensitive-backup-password',
        confirmation: 'RESTORE',
        error: 'stale-restore-error'
    },
    revealedFields: ref(['sensitive-entry:password']),
    settingsForm: { autoLockMinutes: 5 },
    aiSettingsStatus: ref(null),
    aiNow: ref(0),
    loading: ref(true),
    startupError: ref(''),
    startupRetrying: ref(false),
    dataLoadError: ref(''),
    dataLoading: ref(false),
    settingsSaving: ref(false),
    settingsError: ref(''),
    confirmError: ref(''),
    activeSettingsTab: ref('general'),
    passwordForm: {
        oldPassword: 'old-password',
        newPassword: 'new-password',
        confirmPassword: 'new-password',
        error: ''
    },
    tagMergeForm: { sourceTags: 'sensitive', targetTag: 'target' },
    tagMergeSourceList: ref(['sensitive']),
    tagEditorForm: { name: 'sensitive-tag', description: 'sensitive-description' },
    groupForm: { name: 'sensitive-group', description: 'sensitive-description' },
    searchQuery: ref('sensitive-search'),
    aiText: ref('sensitive-ai-text'),
    lastAiParseText: ref('sensitive-ai-parse'),
    aiActionInstruction: ref('sensitive-ai-action'),
    aiOrganizeResult: ref({ sensitive: true }),
    aiActionResult: ref({ sensitive: true }),
    aiResult: ref({ sensitive: true }),
    aiSettingsForm: { apiKey: 'sensitive-api-key' },
    aiModels: ref([{ id: 'sensitive-model' }]),
    aiDiagnosticsPreview: ref({ sensitive: true }),
    aiDiagnosticsReport: ref({ sensitive: true })
};

const api = {
    token: 'sensitive-token',
    setToken(value) {
        this.token = value;
    },
    invalidateSession() {
        invalidationCalls += 1;
    },
    getToken() {
        return this.token;
    },
    post() {
        passwordChangeCalls += 1;
        return new Promise(resolve => { finishPasswordChange = resolve; });
    }
};
const store = {
    state: { settings: { autoLockMinutes: 5 } },
    lockedState: false,
    setState(update) {
        if (Object.prototype.hasOwnProperty.call(update, 'locked')) this.lockedState = update.locked;
    },
    async checkAuth() {
        return { initialized: true, locked: false, auto_lock_minutes: 5 };
    },
    async loadSettings() {
        return this.state.settings;
    }
};
const autoLock = {
    startAutoLockTimer() {},
    clearAutoLockTimer() {},
    resetAutoLockTimer() {},
    bindActivityListeners() {},
    unbindActivityListeners() {},
    handleUnauthorizedLock() {}
};

const controller = sandbox.window.SecretBaseAppSessionController.createAppSessionController({
    api,
    store,
    state,
    showToast() {},
    autoLockFactory: () => autoLock,
    theme: {
        startAutoThemeTimer() {},
        clearAutoThemeTimer() {}
    },
    data: {
        async applySettings() {},
        async loadAllData() {}
    },
    loadSavedAdvancedFilters() {},
    async loadAiSettingsStatus() {},
    async loadDesktopDiagnostics() {},
    handleDocumentClick() {}
});

let mounted = null;
let unmounted = null;
controller.registerLifecycle({
    onMounted(callback) {
        mounted = callback;
    },
    onUnmounted(callback) {
        unmounted = callback;
    }
});

(async () => {
    attributes.add('data-secretbase-desktop-locking');
    await mounted();
    if (sandbox.window.SECRETBASE_DESKTOP_LOCK_READY !== true) {
        throw new Error('桌面锁定监听器未就绪');
    }
    if (sandbox.window.SECRETBASE_DESKTOP_CLOSE_READY !== true) {
        throw new Error('桌面关闭确认监听器未就绪');
    }
    if (typeof fallbackTimeout !== 'function') {
        throw new Error('初始化完成后没有安排保护层兜底释放');
    }
    fallbackTimeout();
    if (attributes.has('data-secretbase-desktop-locking')) {
        throw new Error('初始化完成后残留的桌面保护层没有释放');
    }

    const passwordChangeFirst = controller.changePassword();
    const passwordChangeSecond = controller.changePassword();
    await Promise.resolve();
    if (passwordChangeCalls !== 1 || !state.passwordChanging.value) {
        throw new Error('修改主密码没有阻止重复提交');
    }
    finishPasswordChange();
    await Promise.all([passwordChangeFirst, passwordChangeSecond]);
    if (state.passwordChanging.value) {
        throw new Error('修改主密码完成后没有恢复交互状态');
    }

    windowListeners.get('secretbase:desktop-close-request')();
    if (!state.showDesktopCloseConfirm.value || state.desktopCloseRemember.value
        || state.desktopCloseSubmitting.value || state.desktopCloseError.value) {
        throw new Error('桌面关闭确认没有初始化为可交互状态');
    }

    attributes.add('data-secretbase-desktop-locking');
    state.passwordChanging.value = true;
    windowListeners.get('secretbase:desktop-lock')();

    if (api.token !== null || !store.lockedState || !state.locked.value) {
        throw new Error('桌面锁定没有立即清除认证状态');
    }
    if (invalidationCalls < 1) {
        throw new Error('桌面锁定没有终止仍在执行的敏感请求');
    }
    if (state.entries.value.length || state.tags.value.length || state.groups.value.length) {
        throw new Error('桌面锁定没有立即清除敏感列表');
    }
    if (state.trashItems.value.length || state.backups.value.length || state.groupPickerEntries.value.length
        || state.importPreview.value || state.importConflicts.value.length || state.lastImportPlainFile.value
        || state.aiSettingsForm.apiKey || state.restoreWizard.password || state.passwordForm.oldPassword) {
        throw new Error('桌面锁定没有清除缓存的敏感数据');
    }
    if (state.showSettings.value || state.showEditModal.value || state.restoreWizard.visible
        || state.showDesktopCloseConfirm.value || state.showAiAssistant.value
        || state.aiAssistantInput.value) {
        throw new Error('桌面锁定没有关闭敏感弹窗');
    }
    if (state.desktopCloseSettingsSaving.value) {
        throw new Error('桌面锁定没有清理关闭设置保存状态');
    }
    if (state.entrySaving.value || state.groupSaving.value || state.tagSaving.value
        || state.tagMerging.value || state.groupPickerSaving.value
        || state.passwordChanging.value) {
        throw new Error('桌面锁定没有清理弹窗写入状态');
    }
    if (state.revealedFields.value.length || state.selectedEntry.value !== null) {
        throw new Error('桌面锁定没有清除已显示字段或选中条目');
    }
    if (!attributes.has('data-secretbase-desktop-locking')
        || typeof animationFrame !== 'function'
        || typeof fallbackTimeout !== 'function') {
        throw new Error('锁定页面切换期间缺少敏感画面遮罩或兜底释放');
    }

    fallbackTimeout();
    if (attributes.has('data-secretbase-desktop-locking')) {
        throw new Error('隐藏窗口暂停动画帧时，锁定遮罩没有通过兜底计时器释放');
    }

    unmounted();
    if (sandbox.window.SECRETBASE_DESKTOP_LOCK_READY !== false
        || sandbox.window.SECRETBASE_DESKTOP_CLOSE_READY !== false
        || windowListeners.has('secretbase:desktop-lock')
        || windowListeners.has('secretbase:desktop-close-request')) {
        throw new Error('桌面生命周期监听器没有在卸载时清理');
    }
    console.log('PASS frontend desktop immediate lock');
})().catch(error => {
    console.error(error);
    process.exit(1);
});
