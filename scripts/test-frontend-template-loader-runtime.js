const vm = require('vm');
const {
    templatePaths,
    readProjectFile
} = require('./frontend-source');

const templateSources = new Map(
    templatePaths.map(templatePath => [
        templatePath.replace(/^frontend\//, ''),
        readProjectFile(templatePath)
    ])
);
const requestedPaths = [];
let mountedTarget = null;

const root = {
    innerHTML: '',
    removeAttribute() {},
    replaceChildren() {},
    append() {}
};

const sandbox = {
    console,
    Promise,
    Error,
    document: {
        getElementById(id) {
            return id === 'app' ? root : null;
        },
        createElement() {
            return {
                className: '',
                setAttribute() {},
                append() {}
            };
        }
    },
    fetch: async requestPath => {
        const path = String(requestPath).split('?')[0];
        requestedPaths.push(path);
        return {
            ok: templateSources.has(path),
            status: templateSources.has(path) ? 200 : 404,
            async text() {
                return templateSources.get(path) || '';
            }
        };
    }
};
sandbox.window = sandbox;

const context = vm.createContext(sandbox);
vm.runInContext(readProjectFile('frontend/js/template-loader.js'), context, {
    filename: 'template-loader.js'
});

(async () => {
    await context.window.SecretBaseTemplateLoader.mount({
        mount(target) {
            mountedTarget = target;
        }
    });

    const expectedPaths = templatePaths.map(templatePath => templatePath.replace(/^frontend\//, ''));
    if (requestedPaths.join('|') !== expectedPaths.join('|')) {
        throw new Error(`模板请求顺序错误：${requestedPaths.join(', ')}`);
    }
    if (mountedTarget !== root) {
        throw new Error('模板合并后 Vue 没有挂载到 #app');
    }
    if (!root.innerHTML.includes('v-if="showAiParse"') || !root.innerHTML.includes('v-if="showImportPreview"')) {
        throw new Error('模板加载器没有合并完整页面片段');
    }

    console.log('PASS frontend template loader runtime');
})().catch(error => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
});
