const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(
    path.join(root, 'frontend/js/controllers/desktop-controller.js'),
    'utf8'
);
const ref = value => ({ value });
const pending = [];
const sandbox = {
    window: {
        pywebview: {
            api: {
                async get_update_state() {
                    return new Promise(resolve => pending.push(resolve));
                }
            }
        },
        setInterval() { return 1; },
        clearInterval() {}
    }
};
sandbox.window.window = sandbox.window;
const context = vm.createContext(sandbox);
vm.runInContext(source, context, { filename: 'desktop-controller.js' });

const state = {
    isDesktopMode: true,
    locked: ref(false),
    desktopUpdateResult: ref(null),
    desktopUpdateError: ref(''),
    desktopUpdateChecking: ref(false),
    desktopDiagnostics: ref(null),
    desktopDiagnosticsLoading: ref(false),
    desktopDiagnosticsError: ref(''),
    showDesktopStatus: ref(false),
    showSettings: ref(false),
    desktopRuntimeCapabilities: {},
    desktopPlatform: 'windows',
    settingsForm: {
        desktopUpdateAutoCheck: true,
        desktopUpdateAutoDownload: true,
        closeToTray: false,
        confirmClose: true
    },
    desktopCloseSettingsSaving: ref(false),
    desktopCloseSubmitting: ref(false),
    desktopCloseRemember: ref(false),
    desktopCloseError: ref(''),
    showDesktopCloseConfirm: ref(false)
};
const controller = context.window.SecretBaseDesktopController.createDesktopController({
    computed: getter => ({ get value() { return getter(); } }),
    copyToClipboard: async () => true,
    openExternalUrl: async () => {},
    store: { state: { settings: {} }, async updateSettings() {} },
    showToast: () => {},
    showConfirmDialog: () => {},
    state
});
const assert = (condition, message) => {
    if (!condition) throw new Error(message);
};

(async () => {
    const first = controller.actions.refreshDesktopUpdateState();
    const second = controller.actions.refreshDesktopUpdateState();
    await Promise.resolve();
    assert(pending.length === 1, '桌面更新轮询不得并发发起重复请求');
    pending.shift()({ status: 'idle' });
    await Promise.all([first, second]);

    const third = controller.actions.refreshDesktopUpdateState();
    await Promise.resolve();
    assert(pending.length === 1, '上一轮结束后应允许下一次更新检查');
    pending.shift()({ status: 'idle' });
    await third;
    console.log('PASS frontend desktop polling');
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
