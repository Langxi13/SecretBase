const vm = require('vm');
const { readProjectFile, templatePaths } = require('./frontend-source');

function fakeElement(tag) {
    return {
        tagName: tag.toUpperCase(),
        style: {},
        content: { firstChild: null },
        children: [],
        textContent: '',
        set innerHTML(value) {
            this.rawHtml = value;
            const attribute = value.match(/^<div foo="([\s\S]*)">$/);
            if (attribute) {
                const decoded = attribute[1].replace(/&quot;/g, '"').replace(/&amp;/g, '&');
                this.children = [{ getAttribute: () => decoded }];
            } else {
                this.textContent = value
                    .replace(/<[^>]*>/g, '')
                    .replace(/&lt;/g, '<')
                    .replace(/&gt;/g, '>')
                    .replace(/&amp;/g, '&');
            }
        },
        get innerHTML() {
            return this.rawHtml || '';
        }
    };
}

const document = {
    createElement: fakeElement,
    createElementNS(_namespace, tag) { return fakeElement(tag); },
    createTextNode() { return {}; },
    createComment() { return {}; },
    querySelector() { return null; }
};
const sandbox = {
    console,
    document,
    window: null,
    globalThis: null,
    location: {},
    navigator: { userAgent: '' },
    setTimeout,
    clearTimeout,
    MutationObserver: class MutationObserver { observe() {} }
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

const context = vm.createContext(sandbox);
vm.runInContext(readProjectFile('frontend/vendor/vue/vue.global.prod.js'), context, {
    filename: 'vue.global.prod.js'
});
const template = templatePaths.map(readProjectFile).join('\n');
const render = context.Vue.compile(template, {
    onError(error) { throw error; }
});
if (typeof render !== 'function') {
    throw new Error('Vue 模板未编译为 render 函数');
}

console.log('PASS frontend Vue template compilation');
