const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const ref = value => ({ value });
const reactive = value => value;
const computed = getter => ({ get value() { return getter(); } });
const windowListeners = new Map();
const documentListeners = new Map();
const timers = new Map();
let timerId = 0;

function assert(condition, message) {
    if (!condition) throw new Error(message);
}

const context = vm.createContext({
    console,
    Date,
    Object,
    Array,
    String,
    Boolean,
    Number,
    Promise,
    encodeURIComponent,
    window: null,
    document: {
        hidden: false,
        addEventListener(type, handler) { documentListeners.set(type, handler); },
        removeEventListener(type) { documentListeners.delete(type); }
    }
});
context.window = context;
context.setTimeout = (handler, delay) => {
    timerId += 1;
    timers.set(timerId, { handler, delay });
    return timerId;
};
context.clearTimeout = id => timers.delete(id);
context.addEventListener = (type, handler) => windowListeners.set(type, handler);
context.removeEventListener = type => windowListeners.delete(type);

vm.runInContext(read('frontend/js/sync-state.js'), context, { filename: 'sync-state.js' });
vm.runInContext(read('frontend/js/sync-lifecycle.js'), context, { filename: 'sync-lifecycle.js' });
vm.runInContext(read('frontend/js/controllers/sync-controller.js'), context, { filename: 'sync-controller.js' });

const state = {
    ...context.SecretBaseSyncState.createSyncState({ ref, reactive }),
    showSettings: ref(false),
    activeSettingsTab: ref('general')
};
const calls = [];
let loadAllDataCount = 0;
const status = {
    configured: true,
    phase: 'synced',
    message: '已同步',
    last_error: '',
    pending_conflicts: 0,
    auto_sync: true,
    host: 'dav.example.invalid',
    base_url: 'https://dav.example.invalid/secretbase',
    username_mask: 't***r',
    device_name: '测试设备',
    vault_id: '11111111-1111-4111-8111-111111111111',
    last_synced_at: '2026-07-17T00:00:00Z',
    generation: 2
};
const api = {
    async get(url) {
        calls.push(['GET', url]);
        if (url === '/sync/status') return { data: { ...status } };
        if (url === '/sync/conflicts') return { data: { conflict_token: '', conflicts: [] } };
        if (url === '/sync/history') return { data: { items: [], current_snapshot_id: '' } };
        throw new Error(`unexpected GET ${url}`);
    },
    async post(url, payload) {
        calls.push(['POST', url, payload]);
        if (url === '/sync/create') return { data: { status: { ...status } }, message: '已创建' };
        if (url === '/sync/recovery-code') {
            return {
                data: {
                    recovery_code: 'SBSYNC1-TEST-CODE',
                    pairing_uri: 'secretbase://sync/join?key=test',
                    qr_data_uri: 'data:image/svg+xml;base64,PHN2Zy8+'
                }
            };
        }
        if (url === '/sync/run') {
            return { data: { status: { ...status, generation: 3 }, action: 'downloaded', revision: 4 }, message: '已下载' };
        }
        if (url === '/sync/conflicts/resolve') {
            return { data: { status: { ...status }, revision: 5 }, message: '已处理' };
        }
        throw new Error(`unexpected POST ${url}`);
    },
    async put(url, payload) {
        calls.push(['PUT', url, payload]);
        return { data: { ...status, auto_sync: payload.auto_sync ?? true }, message: '已保存' };
    },
    async delete(url) {
        calls.push(['DELETE', url]);
        return { data: { configured: false, phase: 'disabled', auto_sync: true } };
    }
};
const controller = context.SecretBaseSyncController.createSyncController({
    computed,
    api,
    showToast: () => {},
    showConfirmDialog: (_title, _message, callback) => callback(),
    copyToClipboard: async value => Boolean(value),
    state,
    loadAllData: async () => { loadAllDataCount += 1; }
});
const actions = controller.actions;

(async () => {
    await actions.initializeSync();
    assert(state.syncStatus.configured === true, '解锁后必须加载同步状态');
    assert(windowListeners.has('secretbase:vault-mutated'), '必须监听 Vault 写入事件');
    assert(documentListeners.has('visibilitychange'), '必须监听前台恢复事件');
    assert([...timers.values()].some(timer => timer.delay === 0), '解锁后启用自动同步时必须安排立即检查');

    timers.clear();
    windowListeners.get('secretbase:vault-mutated')();
    assert([...timers.values()].some(timer => timer.delay === 5000), 'Vault 写入后必须使用 5 秒防抖同步');

    timers.clear();
    state.syncBusy.value = true;
    await actions.runSync({ silent: true });
    assert([...timers.values()].some(timer => timer.delay === 5000), '自动同步遇到短暂忙碌时必须重新排队');
    state.syncBusy.value = false;

    const regularPost = api.post;
    api.post = async (url, payload) => {
        if (url !== '/sync/join') return regularPost.call(api, url, payload);
        return {
            data: {
                status: {
                    ...status,
                    configured: false,
                    pending_join: true,
                    phase: 'conflict',
                    pending_conflicts: 1
                },
                conflict_token: 'join-conflict-token-1234567890',
                conflicts: [{
                    conflict_id: 'entry:join',
                    label: '加入冲突',
                    allow_both: true,
                    local: { state: 'active' },
                    remote: { state: 'active' },
                    changed_sections: ['标题']
                }]
            }
        };
    };
    actions.openSyncSetup('join');
    Object.assign(state.syncSetupForm, {
        baseUrl: 'https://dav.example.invalid/secretbase',
        username: 'tester',
        password: 'app-password',
        deviceName: '测试设备',
        recoveryCode: 'SBSYNC1-JOIN-TEST-CODE',
        mergeExisting: true
    });
    await actions.submitSyncSetup();
    assert(state.showSyncSetup.value === false, '加入冲突出现后必须关闭配置弹窗');
    assert(state.showSyncConflicts.value === true, '加入冲突必须直接打开独立处理弹窗');
    assert(state.syncStatus.pending_join === true && state.syncStatus.configured === false, '待处理加入不得伪装成已配置同步');
    assert(state.syncSetupForm.recoveryCode === '', '进入冲突处理后必须清除恢复码输入');
    api.post = regularPost;
    state.showSyncConflicts.value = false;
    state.syncConflicts.value = [];
    state.syncConflictToken.value = '';
    Object.assign(state.syncStatus, status);

    actions.openSyncSetup('create');
    Object.assign(state.syncSetupForm, {
        baseUrl: 'https://dav.example.invalid/secretbase',
        username: 'tester',
        password: 'app-password',
        deviceName: '测试设备'
    });
    await actions.submitSyncSetup();
    assert(state.showSyncRecovery.value === true, '创建同步空间后必须进入二次主密码验证界面');
    assert(state.syncRecoveryMaterial.value === null, '创建接口不得直接在界面暴露同步密钥');

    state.syncMasterPassword.value = 'master-password';
    await actions.submitSyncRecovery();
    assert(state.syncRecoveryMaterial.value?.recovery_code === 'SBSYNC1-TEST-CODE', '验证主密码后才能显示恢复码');

    await actions.runSync();
    assert(loadAllDataCount === 1, '下载远端修改后必须刷新全部本机视图');
    assert(state.syncStatus.generation === 3, '同步完成后必须刷新远端代数');

    state.syncConflicts.value = [{ conflict_id: 'entry:1', allow_both: true }];
    state.syncConflictToken.value = 'token-12345678901234567890';
    assert(controller.views.allSyncConflictsResolved.value === false, '冲突未逐项选择时不得应用');
    state.syncConflictResolutions['entry:1'] = 'both';
    assert(controller.views.allSyncConflictsResolved.value === true, '全部冲突选择后应允许应用');
    await actions.resolveSyncConflicts();
    assert(loadAllDataCount === 2, '冲突处理后必须刷新全部本机视图');

    state.showSyncRecovery.value = true;
    state.syncRecoveryMaterial.value = { recovery_code: 'secret' };
    state.syncSetupForm.password = 'dav-secret';
    state.syncSetupForm.recoveryCode = 'recovery-secret';
    state.syncMasterPassword.value = 'master-password';
    let finishLateRecovery;
    api.post = async url => {
        if (url !== '/sync/recovery-code') throw new Error(`unexpected late POST ${url}`);
        return new Promise(resolve => { finishLateRecovery = resolve; });
    };
    const lateRecovery = actions.submitSyncRecovery();
    actions.pauseSync();
    await actions.initializeSync();
    state.syncRecoveryBusy.value = true;
    finishLateRecovery({ data: { recovery_code: 'must-not-return-after-lock' } });
    await lateRecovery;
    assert(state.syncRecoveryBusy.value === true, '旧会话迟到响应不得清除新会话操作状态');
    state.syncRecoveryBusy.value = false;
    actions.pauseSync();
    assert(state.showSyncRecovery.value === false, '锁定时必须关闭同步密钥界面');
    assert(state.syncRecoveryMaterial.value === null, '锁定时必须清除内存中的恢复材料');
    assert(state.syncSetupForm.password === '' && state.syncSetupForm.recoveryCode === '', '锁定时必须清除同步凭据表单');

    actions.disposeSync();
    assert(!windowListeners.has('secretbase:vault-mutated'), '卸载时必须移除同步事件监听');
    console.log('PASS frontend sync runtime');
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
