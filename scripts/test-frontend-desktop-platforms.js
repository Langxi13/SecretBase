const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'frontend/js/controllers/desktop-controller.js'), 'utf8');
const nativeCalls = [];
const sandbox = {
    window: {
        pywebview: {
            api: {
                async get_diagnostics() {
                    return {
                        status: 'ok',
                        platform: 'macos',
                        architecture: 'arm64',
                        package_type: 'installed',
                        capabilities: {
                            tray: false,
                            directory_open: true,
                            single_instance: true,
                            close_confirmation: true,
                            zoom_controls: true,
                            native_zoom_feedback: true
                        }
                    };
                },
                async set_close_preferences(closeToTray, confirmClose) {
                    nativeCalls.push(['preferences', closeToTray, confirmClose]);
                    return { status: 'updated' };
                },
                async resolve_close_request(action, remember) {
                    nativeCalls.push(['close', action, remember]);
                    return { status: 'exiting' };
                }
            }
        }
    }
};
sandbox.window.window = sandbox.window;
vm.runInContext(source, vm.createContext(sandbox));

const ref = value => ({ value });
const state = {
    isDesktopMode: true,
    desktopPlatform: 'macos',
    desktopArchitecture: 'arm64',
    desktopRuntimeCapabilities: { tray: false, directory_open: true, zoom_controls: true },
    desktopDiagnostics: ref(null),
    desktopDiagnosticsLoading: ref(false),
    desktopDiagnosticsError: ref(''),
    desktopUpdateChecking: ref(false),
    desktopUpdateResult: ref(null),
    desktopUpdateError: ref(''),
    showDesktopStatus: ref(false),
    showDesktopCloseConfirm: ref(true),
    desktopCloseRemember: ref(false),
    desktopCloseSubmitting: ref(false),
    desktopCloseError: ref(''),
    desktopCloseSettingsSaving: ref(false),
    settingsForm: { closeToTray: true, confirmClose: true }
};
const store = {
    state: { settings: { closeToTray: true, confirmClose: true } },
    async updateSettings(update) {
        this.state.settings = { ...this.state.settings, ...update };
    }
};
const desktop = sandbox.window.SecretBaseDesktopController.createDesktopController({
    computed: getter => ({ get value() { return getter(); } }),
    copyToClipboard: async () => true,
    openExternalUrl: async () => {},
    store,
    showToast: () => {},
    state
});

(async () => {
    await desktop.actions.loadDesktopDiagnostics();
    if (desktop.views.desktopPlatformLabel.value !== 'macOS') throw new Error('macOS 平台标签错误');
    if (desktop.views.desktopSupportsTray.value !== false) throw new Error('macOS 不应声明托盘能力');
    if (desktop.views.desktopCapabilities.value.zoom_controls !== true) throw new Error('macOS 必须声明原生缩放能力');

    await desktop.actions.saveCloseToTraySetting();
    if (!nativeCalls.some(call => call[0] === 'preferences' && call[1] === false && call[2] === true)) {
        throw new Error('macOS 保存关闭偏好时必须强制关闭托盘');
    }

    await desktop.actions.resolveDesktopClose('tray');
    if (nativeCalls.some(call => call[0] === 'close' && call[1] === 'tray')) {
        throw new Error('macOS 不得提交托盘关闭动作');
    }
    await desktop.actions.resolveDesktopClose('exit');
    if (!nativeCalls.some(call => call[0] === 'close' && call[1] === 'exit')) {
        throw new Error('macOS 必须支持退出应用');
    }
    console.log('PASS frontend desktop platforms');
})().catch(error => {
    console.error(error);
    process.exit(1);
});
