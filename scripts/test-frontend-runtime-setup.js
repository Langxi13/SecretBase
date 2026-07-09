const vm = require('vm');
const {
    readProjectFile
} = require('./frontend-source');

const indexHtml = readProjectFile('frontend/index.html');
const scriptPaths = [...indexHtml.matchAll(/<script src="([^"]+)"/g)]
    .map(match => match[1].split('?')[0])
    .filter(path => path.startsWith('js/'));

let setupBindings = null;

function ref(value) {
    return { value };
}

function reactive(value) {
    return value;
}

function computed(source) {
    return {
        get value() {
            return typeof source === 'function' ? source() : source.get();
        },
        set value(nextValue) {
            if (typeof source !== 'function' && source.set) source.set(nextValue);
        }
    };
}

const sandbox = {
    console,
    Date,
    Math,
    JSON,
    Promise,
    Set,
    Map,
    Array,
    Object,
    String,
    Number,
    Boolean,
    RegExp,
    Error,
    URLSearchParams,
    Intl,
    Element: class Element {},
    CustomEvent: class CustomEvent {
        constructor(type, init = {}) {
            this.type = type;
            this.detail = init.detail;
        }
    },
    FormData: class FormData {
        append() {}
    },
    localStorage: {
        getItem() { return null; },
        setItem() {},
        removeItem() {}
    },
    location: {
        protocol: 'http:',
        hostname: '127.0.0.1',
        port: '10014',
        origin: 'http://127.0.0.1:10014'
    },
    document: {
        documentElement: {
            setAttribute() {}
        },
        addEventListener() {},
        removeEventListener() {},
        createElement() {
            return {
                style: {},
                append() {},
                appendChild() {},
                removeChild() {},
                click() {},
                select() {}
            };
        }
    },
    navigator: {
        clipboard: {
            async writeText() {}
        }
    },
    URL: {
        createObjectURL() { return 'blob:test'; },
        revokeObjectURL() {}
    },
    fetch: async () => ({
        ok: true,
        status: 200,
        async json() { return { success: true, data: {} }; },
        async text() { return ''; },
        async blob() { return {}; }
    }),
    setTimeout() { return 1; },
    clearTimeout() {},
    setInterval() { return 1; },
    clearInterval() {},
    Vue: {
        createApp(options) {
            return {
                mount() {
                    setupBindings = options.setup();
                }
            };
        },
        ref,
        reactive,
        computed,
        watch() {},
        onMounted() {},
        onUnmounted() {},
        nextTick: async () => {}
    }
};

sandbox.window = sandbox;
sandbox.window.addEventListener = () => {};
sandbox.window.removeEventListener = () => {};
sandbox.window.dispatchEvent = () => {};
sandbox.window.scrollTo = () => {};

const context = vm.createContext(sandbox);

for (const scriptPath of scriptPaths) {
    if (scriptPath === 'js/app.js') {
        context.window.SecretBaseTemplateLoader.mount = app => app.mount('#app');
    }
    vm.runInContext(readProjectFile(`frontend/${scriptPath}`), context, {
        filename: scriptPath
    });
}

if (!setupBindings) {
    throw new Error('Vue setup 未执行，无法验证运行时装配');
}

[
    'entryPageSizeOptions',
    'filterByTag',
    'showGroupMode',
    'saveEntry',
    'previewAiOrganize',
    'openBackupCenter',
    'importPlainFile',
    'loadTrash',
    'openToolsModal'
].forEach(name => {
    if (!(name in setupBindings)) {
        throw new Error(`Vue setup 未暴露 ${name}`);
    }
});

if (!Array.isArray(setupBindings.entryPageSizeOptions)) {
    throw new Error('entryPageSizeOptions 未作为可用数组暴露，登录页会无法挂载');
}

console.log('PASS frontend runtime setup');
