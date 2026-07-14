const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'frontend/js/app-session-controller.js'), 'utf8');

function ref(value) {
    return { value };
}

const windowListeners = new Map();
const documentListeners = new Map();
let animationFrame = null;
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
vm.runInContext(source, vm.createContext(sandbox));

const state = {
    initialized: ref(true),
    locked: ref(false),
    password: ref('master-password'),
    confirmPassword: ref(''),
    passwordError: ref(''),
    unlockError: ref(''),
    submitting: ref(false),
    entries: ref([{ id: 'sensitive-entry' }]),
    tags: ref([{ name: 'sensitive-tag' }]),
    groups: ref([{ name: 'sensitive-group' }]),
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
    showChangePassword: ref(true),
    showBackupCenter: ref(true),
    showConfirm: ref(true),
    showTools: ref(true),
    showImportPreview: ref(true),
    showImportConflicts: ref(true),
    showImportReport: ref(true),
    copyMenuEntryId: ref('sensitive-entry'),
    showTagDropdown: ref(true),
    restoreWizard: { visible: true },
    revealedFields: ref(['sensitive-entry:password']),
    settingsForm: { autoLockMinutes: 5 },
    aiSettingsStatus: ref(null),
    aiNow: ref(0),
    loading: ref(true),
    activeSettingsTab: ref('general'),
    passwordForm: {}
};

const api = {
    token: 'sensitive-token',
    setToken(value) {
        this.token = value;
    },
    getToken() {
        return this.token;
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
    await mounted();
    if (sandbox.window.SECRETBASE_DESKTOP_LOCK_READY !== true) {
        throw new Error('桌面锁定监听器未就绪');
    }
    if (sandbox.window.SECRETBASE_DESKTOP_CLOSE_READY !== true) {
        throw new Error('桌面关闭确认监听器未就绪');
    }

    windowListeners.get('secretbase:desktop-close-request')();
    if (!state.showDesktopCloseConfirm.value || state.desktopCloseRemember.value
        || state.desktopCloseSubmitting.value || state.desktopCloseError.value) {
        throw new Error('桌面关闭确认没有初始化为可交互状态');
    }

    attributes.add('data-secretbase-desktop-locking');
    windowListeners.get('secretbase:desktop-lock')();

    if (api.token !== null || !store.lockedState || !state.locked.value) {
        throw new Error('桌面锁定没有立即清除认证状态');
    }
    if (state.entries.value.length || state.tags.value.length || state.groups.value.length) {
        throw new Error('桌面锁定没有立即清除敏感列表');
    }
    if (state.showSettings.value || state.showEditModal.value || state.restoreWizard.visible
        || state.showDesktopCloseConfirm.value || state.showAiAssistant.value
        || state.aiAssistantInput.value) {
        throw new Error('桌面锁定没有关闭敏感弹窗');
    }
    if (state.desktopCloseSettingsSaving.value) {
        throw new Error('桌面锁定没有清理关闭设置保存状态');
    }
    if (state.revealedFields.value.length || state.selectedEntry.value !== null) {
        throw new Error('桌面锁定没有清除已显示字段或选中条目');
    }
    if (!attributes.has('data-secretbase-desktop-locking') || typeof animationFrame !== 'function') {
        throw new Error('锁定页面切换期间缺少敏感画面遮罩');
    }

    animationFrame();
    if (attributes.has('data-secretbase-desktop-locking')) {
        throw new Error('锁定状态应用后遮罩没有释放');
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
