const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const events = [];

const sandbox = {
    console,
    JSON,
    Object,
    Array,
    String,
    Number,
    Boolean,
    Promise,
    URLSearchParams,
    FormData: class FormData {
        append() {}
    },
    CustomEvent: class CustomEvent {
        constructor(type, init = {}) {
            this.type = type;
            this.detail = init.detail;
        }
    },
    location: {
        protocol: 'https:',
        hostname: 'example.test',
        port: '',
        origin: 'https://example.test'
    },
    setTimeout,
    clearTimeout,
    AbortController,
    fetch: async () => ({
        ok: true,
        status: 200,
        async text() {
            return JSON.stringify({ success: true, data: { ok: true } });
        }
    })
};
sandbox.window = sandbox;
sandbox.window.addEventListener = () => {};
sandbox.window.dispatchEvent = event => events.push(event);
Object.defineProperty(sandbox, 'localStorage', {
    get() {
        throw new Error('local storage disabled');
    }
});
Object.defineProperty(sandbox, 'sessionStorage', {
    get() {
        throw new Error('session storage disabled');
    }
});

const context = vm.createContext(sandbox);
vm.runInContext(read('frontend/js/storage.js'), context, { filename: 'storage.js' });
vm.runInContext(read('frontend/js/api.js'), context, { filename: 'api.js' });

const api = vm.runInContext('api', context);
api.setToken('session-only-token');
if (api.defaultTimeoutMs('/ai/organize/preview') < 120000) {
    throw new Error('AI 整理请求前端超时必须覆盖后端长任务时限');
}
if (api.defaultTimeoutMs('/ai/status') > 30000) {
    throw new Error('AI 状态读取不应使用长任务超时，避免故障时界面长时间无反馈');
}
if (api.getToken() !== 'session-only-token') {
    throw new Error('浏览器存储不可用时认证 token 必须保留在当前内存会话');
}
if (context.SecretBaseStorage.getLocal('missing') !== null) {
    throw new Error('受限 localStorage 读取必须安全降级');
}

async function expectApiError(promise, expectedCode, expectedStatus) {
    try {
        await promise;
    } catch (error) {
        if (error.code !== expectedCode || error.status !== expectedStatus) {
            throw new Error(`API 错误分类不正确：${error.code}/${error.status}`);
        }
        return error;
    }
    throw new Error('请求应返回受控 API 错误');
}

(async () => {
    context.fetch = async () => ({
        ok: false,
        status: 502,
        async text() {
            return '<html>bad gateway</html>';
        }
    });
    const proxyError = await expectApiError(api.get('/broken'), 'HTTP_ERROR', 502);
    if (!proxyError.message.includes('HTTP 502')) {
        throw new Error('非 JSON 代理错误必须保留 HTTP 状态');
    }

    context.fetch = async () => ({
        ok: false,
        status: 401,
        async text() {
            return '';
        }
    });
    await expectApiError(api.get('/locked'), 'HTTP_ERROR', 401);
    if (!events.some(event => event.type === 'secretbase:unauthorized')) {
        throw new Error('非 JSON 401 仍必须触发前端锁定流程');
    }

    context.fetch = async () => {
        throw new Error('offline');
    };
    await expectApiError(api.get('/offline'), 'NETWORK_ERROR', 0);

    const mutationEventCount = events.filter(event => event.type === 'secretbase:vault-mutated').length;
    context.fetch = async url => ({
        ok: true,
        status: 200,
        headers: {
            get(name) {
                if (name === 'X-SecretBase-Vault-Changed') return '1';
                if (name === 'X-SecretBase-Vault-Revision') return '7';
                return null;
            }
        },
        async text() {
            return JSON.stringify({ success: true, data: { url } });
        }
    });
    await api.post('/entries', { title: '测试' });
    const mutationEvents = events.filter(event => event.type === 'secretbase:vault-mutated');
    if (mutationEvents.length !== mutationEventCount + 1 || mutationEvents.at(-1).detail.revision !== '7') {
        throw new Error('Vault 写入响应必须派发带 revision 的自动同步事件');
    }
    await api.post('/sync/run', {});
    if (events.filter(event => event.type === 'secretbase:vault-mutated').length !== mutationEvents.length) {
        throw new Error('同步接口自身不得再次触发自动同步事件');
    }

    context.fetch = (_url, options) => new Promise((_resolve, reject) => {
        options.signal.addEventListener('abort', () => {
            const error = new Error('aborted');
            error.name = 'AbortError';
            reject(error);
        });
    });
    const staleRequest = api.get('/sensitive-data');
    api.invalidateSession();
    await expectApiError(staleRequest, 'SESSION_INVALIDATED', 401);
    if (api.activeControllers.size !== 0) {
        throw new Error('会话失效后仍保留已取消的网络请求控制器');
    }

    context.fetch = (_url, options) => new Promise((_resolve, reject) => {
        options.signal.addEventListener('abort', () => {
            const error = new Error('aborted by user');
            error.name = 'AbortError';
            reject(error);
        });
    });
    const userAbort = new AbortController();
    const cancelledRequest = api.get('/cancelled', { signal: userAbort.signal });
    userAbort.abort();
    await expectApiError(cancelledRequest, 'REQUEST_CANCELLED', 499);

    console.log('PASS frontend api runtime');
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
