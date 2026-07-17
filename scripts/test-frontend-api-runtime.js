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

    console.log('PASS frontend api runtime');
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
