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
    URL,
    TextEncoder,
    Uint8Array,
    atob,
    crypto: require('crypto').webcrypto,
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
vm.runInContext(read('frontend/js/sync-pairing.js'), context, { filename: 'sync-pairing.js' });
vm.runInContext(read('frontend/js/sync-lifecycle.js'), context, { filename: 'sync-lifecycle.js' });
vm.runInContext(read('frontend/js/sync-setup-validation.js'), context, { filename: 'sync-setup-validation.js' });
vm.runInContext(read('frontend/js/controllers/sync-management-controller.js'), context, { filename: 'sync-management-controller.js' });
vm.runInContext(read('frontend/js/controllers/sync-operation-controller.js'), context, { filename: 'sync-operation-controller.js' });
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
        if (url === '/sync/config/test') return { message: '连接测试通过' };
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
    showToast: (message, type) => toasts.push({ message, type }),
    showConfirmDialog: (_title, _message, callback) => callback(),
    copyToClipboard: async value => Boolean(value),
    state,
    loadAllData: async () => { loadAllDataCount += 1; }
});
const actions = controller.actions;
const toasts = [];

(async () => {
    await actions.initializeSync();
    assert(state.syncStatus.configured === true, '解锁后必须加载同步状态');
    assert(windowListeners.has('secretbase:vault-mutated'), '必须监听 Vault 写入事件');
    assert(documentListeners.has('visibilitychange'), '必须监听前台恢复事件');
    assert([...timers.values()].some(timer => timer.delay === 0), '解锁后启用自动同步时必须安排立即检查');

    const originalGet = api.get;
    let conflictCalls = 0;
    api.get = async url => {
        if (url === '/sync/conflicts') {
            conflictCalls += 1;
            throw new Error('冲突服务暂时不可用');
        }
        return originalGet.call(api, url);
    };
    state.syncStatus.pending_conflicts = 1;
    await actions.loadSyncConflicts(true);
    assert(conflictCalls === 1, '同步冲突读取失败时必须只发起一次请求');
    assert(state.syncConflictsError.value.includes('冲突服务暂时不可用'), '同步冲突失败必须保留原地错误');
    assert(!state.syncConflictsLoading.value && state.showSyncConflicts.value, '同步冲突失败后必须恢复交互并保留重试弹窗');

    let releaseConflictLoad;
    api.get = async url => {
        if (url === '/sync/conflicts') {
            conflictCalls += 1;
            return new Promise(resolve => { releaseConflictLoad = resolve; });
        }
        return originalGet.call(api, url);
    };
    state.showSyncConflicts.value = false;
    const firstConflictLoad = actions.loadSyncConflicts(false);
    const duplicateConflictLoad = actions.loadSyncConflicts(true);
    assert(state.syncConflictsLoading.value && conflictCalls === 2, '同步冲突读取期间重复点击必须复用同一请求');
    releaseConflictLoad({ data: {
        conflict_token: 'conflict-token',
        conflicts: [{ conflict_id: 'entry:runtime', allow_both: true, changed_sections: ['标题'] }]
    } });
    await Promise.all([firstConflictLoad, duplicateConflictLoad]);
    assert(state.syncConflicts.value.length === 1 && state.syncConflictsError.value === '', '同步冲突重试成功后必须填充结果并清除错误');
    assert(state.showSyncConflicts.value, '后台冲突读取期间用户主动打开后，结果返回不得再次隐藏弹窗');
    assert(state.syncStatus.pending_conflicts === 1, '同步冲突结果必须同步待处理数量');
    api.get = originalGet;
    state.showSyncConflicts.value = false;
    state.syncConflicts.value = [];
    state.syncStatus.pending_conflicts = 0;

    timers.clear();
    windowListeners.get('secretbase:vault-mutated')();
    assert([...timers.values()].some(timer => timer.delay === 5000), 'Vault 写入后必须使用 5 秒防抖同步');

    timers.clear();
    state.syncBusy.value = true;
    await actions.runSync({ silent: true });
    assert([...timers.values()].some(timer => timer.delay === 5000), '自动同步遇到短暂忙碌时必须重新排队');
    state.syncBusy.value = false;

    actions.openSyncSetup('join');
    Object.assign(state.syncSetupForm, {
        baseUrl: 'https://dav.example.invalid/secretbase',
        username: 'tester',
        password: 'app-password',
        recoveryCode: ''
    });
    await actions.testSyncConnection();
    assert(state.syncSetupTestPassed.value === true, '连接测试成功后必须保留通过状态');
    assert(controller.views.syncSetupCanSubmit.value === true, '连接测试结束后加入按钮必须恢复可交互');
    const joinCallsBeforeValidation = calls.filter(call => call[0] === 'POST' && call[1] === '/sync/join').length;
    await actions.submitSyncSetup();
    assert(state.syncSetupError.value.includes('同步恢复码'), '缺少恢复码时必须在配置弹窗保留明确错误');
    assert(calls.filter(call => call[0] === 'POST' && call[1] === '/sync/join').length === joinCallsBeforeValidation, '表单不完整时不得发送加入请求');
    assert(toasts.some(item => item.type === 'error' && item.message.includes('同步恢复码')), '同步配置错误必须触发顶层提示');

    const autoPairingUri = 'secretbase://sync/join?v=2&vault_id=11111111-1111-4111-8111-111111111111&space_id=22222222-2222-4222-8222-222222222222&key=AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA&url=https%3A%2F%2Fdav.example.invalid%2Fsecretbase&username=tester';
    let autoJoinPayload = null;
    const postBeforeAutoJoin = api.post;
    api.post = async (url, payload) => {
        if (url === '/sync/join') {
            autoJoinPayload = payload;
            return { data: { status: { ...status } }, message: '已加入' };
        }
        return postBeforeAutoJoin.call(api, url, payload);
    };
    actions.openSyncSetup('join');
    Object.assign(state.syncSetupForm, {
        password: 'app-password',
        pairingUri: autoPairingUri
    });
    await actions.submitSyncSetup();
    assert(autoJoinPayload?.recovery_code?.startsWith('SBSYNC2-'), '直接提交配对链接时必须自动转换并提交恢复码');
    assert(state.showSyncSetup.value === false, '自动读取配对链接成功后必须关闭配置弹窗');
    loadAllDataCount = 0;
    api.post = postBeforeAutoJoin;

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
    state.syncSetupForm.pairingUri = 'secretbase://sync/join?v=2&vault_id=11111111-1111-4111-8111-111111111111&space_id=22222222-2222-4222-8222-222222222222&recovery_code=SBSYNC2-AIIRC-EIRCE-IUCEM-BCEIR-CEIRC-EISEI-RCEIR-CEQRC-QIRCE-IRCEI-RCEAI-CAMCA-KBQHB-AEQUC-YMBUH-A6EAR-CIJRI-FIWC4-MBSGQ-3DQOR-4HZAJ-QFRST-Q&url=https%3A%2F%2Fdav.example.invalid%2Fsecretbase&username=tester';
    assert(await actions.applySyncPairingUri() === true, '配对链接应自动填充同步连接信息');
    assert(state.syncSetupForm.baseUrl === 'https://dav.example.invalid/secretbase', '配对链接应填充 WebDAV 地址');
    assert(state.syncSetupForm.username === 'tester', '配对链接应填充 WebDAV 用户名');
    assert(state.syncSetupForm.recoveryCode.startsWith('SBSYNC2-'), '配对链接应填充 V2 恢复码');
    state.syncSetupForm.pairingUri = '';
    const legacyPairing = await context.SecretBaseSyncPairing.parse(
        'secretbase://sync/join?v=2&vault_id=11111111-1111-4111-8111-111111111111&space_id=22222222-2222-4222-8222-222222222222&key=AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA&url=https%3A%2F%2Fdav.example.invalid%2Fsecretbase&username=tester'
    );
    assert(legacyPairing.recoveryCode.startsWith('SBSYNC2-'), '旧版 V2 配对链接应转换为恢复码');
    assert(!legacyPairing.recoveryCode.includes('key='), '转换结果不得保留裸同步密钥');
    const webCrypto = context.crypto;
    context.crypto = undefined;
    const fallbackPairing = await context.SecretBaseSyncPairing.parse(
        'secretbase://sync/join?v=2&vault_id=11111111-1111-4111-8111-111111111111&space_id=22222222-2222-4222-8222-222222222222&key=AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA&url=https%3A%2F%2Fdav.example.invalid%2Fsecretbase&username=tester'
    );
    assert(fallbackPairing.recoveryCode === legacyPairing.recoveryCode, '无 Web Crypto 时仍应完成配对校验');
    context.crypto = webCrypto;
    const v1Pairing = await context.SecretBaseSyncPairing.parse(
        'secretbase://sync/join?v=1&vault_id=11111111-1111-4111-8111-111111111111&recovery_code=SBSYNC1-AEIRC-EIRCE-IUCEM-BCEIR-CEIRC-EIQCA-QDAQC-QMBYI-BEFAW-DANBY-HRAEI-SCMKB-KFQXD-AMRUG-Y4DUP-B6IDR-H3HFC&url=https%3A%2F%2Fdav.example.invalid%2Fsecretbase&username=tester'
    );
    assert(v1Pairing.version === 1, 'V1 配对链接应保留协议版本');
    for (const invalid of [
        'secretbase://sync/join?v=2&v=2&recovery_code=SBSYNC2-TEST&url=https%3A%2F%2Fdav.example.invalid&username=tester',
        'secretbase://sync/join?v=2&recovery_code=SBSYNC2-TEST&password=secret&url=https%3A%2F%2Fdav.example.invalid&username=tester'
    ]) {
        let rejected = false;
        try {
            await context.SecretBaseSyncPairing.parse(invalid);
        } catch (_) {
            rejected = true;
        }
        assert(rejected, '配对链接必须拒绝重复参数和嵌入式凭据');
    }
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
