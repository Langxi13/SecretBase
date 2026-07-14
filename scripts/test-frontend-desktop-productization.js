const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const controllerSource = read('frontend/js/controllers/desktop-controller.js');
const sessionSource = read('frontend/js/app-session-controller.js');
const stateSource = read('frontend/js/app-state.js');
const storeStateSource = read('frontend/js/store-state.js');
const desktopStyles = read('frontend/css/desktop-components.css');
const settingsTemplate = read('frontend/templates/settings-dialog.html');
const desktopTemplate = read('frontend/templates/desktop-dialog.html');
const appLayout = read('frontend/templates/app-layout.html');
const indexHtml = read('frontend/index.html');

function assertIncludes(content, needle, message) {
    if (!content.includes(needle)) throw new Error(message);
}

assertIncludes(indexHtml, 'js/controllers/desktop-controller.js?v=20260714-ai-v3', '入口页必须加载桌面控制器');
assertIncludes(indexHtml, 'css/desktop-components.css?v=20260714-ai-v3', '入口页必须加载桌面样式');
assertIncludes(stateSource, "runtimeConfig.mode === 'desktop'", '桌面入口必须由运行模式控制');
assertIncludes(stateSource, 'desktopRuntimeCapabilities', '桌面运行时必须提供平台能力');
assertIncludes(controllerSource, 'desktopSupportsTray', '桌面控制器必须按能力决定托盘 UI');
assertIncludes(stateSource, "{ key: 'desktop', label: '桌面' }", '桌面模式必须增加设置页签');
assertIncludes(storeStateSource, 'closeToTray: settings.closeToTray ?? settings.close_to_tray ?? false', '旧设置必须安全默认关闭托盘');
assertIncludes(storeStateSource, 'close_to_tray: settings.closeToTray ?? settings.close_to_tray', '托盘设置必须写回后端字段');
assertIncludes(storeStateSource, 'confirmClose: settings.confirmClose ?? settings.confirm_close ?? true', '关闭确认必须默认开启');
assertIncludes(storeStateSource, 'confirm_close: settings.confirmClose ?? settings.confirm_close', '关闭确认必须写回后端字段');
assertIncludes(storeStateSource, 'desktopZoomPercent: settings.desktopZoomPercent ?? settings.desktop_zoom_percent ?? 100', '桌面缩放比例必须安全默认到 100%');
assertIncludes(storeStateSource, 'desktop_zoom_percent: settings.desktopZoomPercent ?? settings.desktop_zoom_percent', '桌面缩放比例必须保留在设置模型中');
assertIncludes(settingsTemplate, '@change="saveCloseToTraySetting"', '托盘开关必须调用专用保存逻辑');
assertIncludes(settingsTemplate, 'v-if="desktopSupportsTray"', '不支持托盘的平台必须隐藏托盘设置');
assertIncludes(settingsTemplate, 'v-model="settingsForm.confirmClose"', '桌面设置必须允许恢复关闭提醒');
assertIncludes(settingsTemplate, '默认保留本地数据', 'macOS 桌面设置必须说明删除应用后默认保留数据');
assertIncludes(settingsTemplate, '@click="checkDesktopUpdates"', '桌面设置必须提供手动更新检查');
assertIncludes(desktopTemplate, '@click="copyDesktopDiagnostics"', '诊断弹窗必须支持复制脱敏摘要');
assertIncludes(desktopTemplate, 'openDesktopDirectory(kind)', '诊断弹窗必须使用目录白名单桥');
assertIncludes(desktopTemplate, '不再提醒，记住本次选择', '关闭确认必须提供记住选择选项');
assertIncludes(desktopTemplate, "resolveDesktopClose('tray')", '关闭确认必须支持隐藏到托盘');
assertIncludes(desktopTemplate, 'v-if="desktopSupportsTray"', 'macOS 关闭弹窗必须隐藏托盘操作');
assertIncludes(desktopTemplate, "resolveDesktopClose('exit')", '关闭确认必须支持完全退出');
assertIncludes(appLayout, 'v-if="isDesktopMode" type="button" class="auth-desktop-status"', '初始化和锁定页必须提供桌面状态入口');
assertIncludes(sessionSource, "window.addEventListener('secretbase:desktop-lock'", '桌面壳锁定必须立即通知前端清空解锁态');
assertIncludes(sessionSource, 'window.SECRETBASE_DESKTOP_LOCK_READY = true', '前端必须向桌面壳声明锁定事件已就绪');
assertIncludes(sessionSource, "window.addEventListener('secretbase:desktop-close-request'", '桌面壳必须能请求前端显示关闭确认');
assertIncludes(sessionSource, 'store.setState({ locked: true })', '桌面锁定必须同步更新 store 状态');
assertIncludes(desktopStyles, 'data-secretbase-desktop-locking="true"', '桌面锁定切换期间必须覆盖敏感画面');
if (controllerSource.includes('set_close_to_tray')) {
    throw new Error('设置开关不能再调用会立即启动托盘的旧桥');
}

function ref(value) {
    return { value };
}

const nativeCalls = [];
const openedUrls = [];
const toasts = [];
const sandbox = {
    window: {
        pywebview: {
            api: {
                async get_diagnostics() {
                    nativeCalls.push(['diagnostics']);
                    return {
                        status: 'ok',
                        package_type: 'installed',
                        platform: 'windows',
                        architecture: 'x64',
                        capabilities: { tray: true, directory_open: true },
                        support_summary: 'SecretBase 4.0.0'
                    };
                },
                async open_directory(kind) {
                    nativeCalls.push(['directory', kind]);
                    return { status: 'opened', kind };
                },
                async check_for_updates() {
                    nativeCalls.push(['updates']);
                    return {
                        status: 'available',
                        latest_version: '3.2.1',
                        release_url: 'https://github.com/Langxi13/SecretBase/releases/tag/v3.2.1'
                    };
                },
                async set_close_preferences(closeToTray, confirmClose) {
                    nativeCalls.push(['close-preferences', closeToTray, confirmClose]);
                    return { status: 'updated', close_to_tray: closeToTray, confirm_close: confirmClose };
                },
                async resolve_close_request(action, remember) {
                    nativeCalls.push(['close-request', action, remember]);
                    return { status: action === 'tray' ? 'hidden' : 'exiting' };
                }
            }
        }
    }
};
sandbox.window.window = sandbox.window;
vm.runInContext(controllerSource, vm.createContext(sandbox));

const state = {
    isDesktopMode: true,
    desktopPlatform: 'windows',
    desktopArchitecture: 'x64',
    desktopRuntimeCapabilities: { tray: true, directory_open: true },
    desktopDiagnostics: ref(null),
    desktopDiagnosticsLoading: ref(false),
    desktopDiagnosticsError: ref(''),
    desktopUpdateChecking: ref(false),
    desktopUpdateResult: ref(null),
    desktopUpdateError: ref(''),
    showDesktopStatus: ref(false),
    showDesktopCloseConfirm: ref(true),
    desktopCloseRemember: ref(true),
    desktopCloseSubmitting: ref(false),
    desktopCloseError: ref(''),
    desktopCloseSettingsSaving: ref(false),
    settingsForm: { closeToTray: true, confirmClose: true }
};
const storeUpdates = [];
const store = {
    state: { settings: { closeToTray: false, confirmClose: true } },
    async updateSettings(update) {
        storeUpdates.push(update);
        this.state.settings.closeToTray = update.closeToTray;
        this.state.settings.confirmClose = update.confirmClose;
    }
};
const desktop = sandbox.window.SecretBaseDesktopController.createDesktopController({
    computed: getter => ({ get value() { return getter(); } }),
    copyToClipboard: async text => text === 'SecretBase 4.0.0',
    openExternalUrl: async url => openedUrls.push(url),
    store,
    showToast: (...args) => toasts.push(args),
    state
});

(async () => {
    await desktop.actions.openDesktopStatus();
    if (!state.showDesktopStatus.value || state.desktopDiagnostics.value?.status !== 'ok') {
        throw new Error('桌面状态入口没有加载诊断结果');
    }
    if (desktop.views.desktopPackageLabel.value !== '安装版') throw new Error('运行方式标签错误');

    await desktop.actions.openDesktopDirectory('logs');
    await desktop.actions.copyDesktopDiagnostics();
    await desktop.actions.checkDesktopUpdates();
    await desktop.actions.openDesktopRelease();
    await desktop.actions.saveCloseToTraySetting();
    await desktop.actions.resolveDesktopClose('tray');

    if (!nativeCalls.some(call => call[0] === 'directory' && call[1] === 'logs')) throw new Error('目录桥未调用');
    if (!nativeCalls.some(call => call[0] === 'close-preferences' && call[1] === true && call[2] === true)) {
        throw new Error('关闭偏好桥未调用');
    }
    if (!nativeCalls.some(call => call[0] === 'close-request' && call[1] === 'tray' && call[2] === true)) {
        throw new Error('关闭确认结果未传给桌面壳');
    }
    if (storeUpdates.length !== 1 || storeUpdates[0].closeToTray !== true || storeUpdates[0].confirmClose !== true) {
        throw new Error('关闭设置未持久化');
    }
    if (openedUrls.length !== 1 || !openedUrls[0].includes('/releases/tag/v3.2.1')) throw new Error('更新下载页未打开');
    if (!toasts.some(item => item[0] === '诊断信息已复制')) throw new Error('复制诊断提示缺失');
    console.log('PASS frontend desktop productization');
})().catch(error => {
    console.error(error);
    process.exit(1);
});
