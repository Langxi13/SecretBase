const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const toastJs = fs.readFileSync(path.join(root, 'frontend/js/toast.js'), 'utf8');
const indexHtml = fs.readFileSync(path.join(root, 'frontend/index.html'), 'utf8');
const transferHtml = fs.readFileSync(path.join(root, 'frontend/templates/transfer-dialogs.html'), 'utf8');
const utilsJs = fs.readFileSync(path.join(root, 'frontend/js/utils.js'), 'utf8');

function assertIncludes(content, needle, message) {
    if (!content.includes(needle)) {
        throw new Error(message);
    }
}

function assertNotIncludes(content, needle, message) {
    if (content.includes(needle)) {
        throw new Error(message);
    }
}

assertIncludes(toastJs, 'function showToast', 'Toast DOM 组件逻辑必须由 toast.js 承载');
assertNotIncludes(toastJs, 'innerHTML', 'Toast 不能用 innerHTML 拼接消息，避免错误内容注入 HTML');
assertIncludes(toastJs, 'messageElement.textContent = String(message)', 'Toast 消息必须通过 textContent 写入');
assertIncludes(indexHtml, 'id="toast-container"', 'Toast 容器必须位于网页根层，避免随业务弹窗模板消失');
if (transferHtml.includes('id="toast-container"')) {
    throw new Error('导入导出模板不得重复声明 Toast 容器');
}
assertIncludes(toastJs, "document.body.appendChild(container)", 'Toast 容器缺失时必须自动恢复，不能静默丢失错误');
assertIncludes(toastJs, "type === 'error' ? 'alert' : 'status'", 'Toast 必须为错误和普通状态提供可访问语义');
assertNotIncludes(utilsJs, 'function showToast', 'utils.js 不应继续承载 Toast DOM 组件逻辑');

let container = null;
const createElement = tagName => ({
    tagName,
    className: '',
    textContent: '',
    attributes: {},
    children: [],
    classList: { add() {} },
    appendChild(child) { this.children.push(child); },
    setAttribute(name, value) { this.attributes[name] = value; },
    remove() {}
});
const context = vm.createContext({
    document: {
        getElementById: id => id === 'toast-container' ? container : null,
        createElement,
        body: {
            appendChild(element) { container = element; }
        }
    },
    setTimeout() { return 1; }
});
vm.runInContext(toastJs, context, { filename: 'toast.js' });
context.showToast('同步失败，请重试', 'error');
if (!container || container.children.length !== 1) {
    throw new Error('Toast 容器缺失时必须自动创建并展示错误');
}
const renderedToast = container.children[0];
if (renderedToast.attributes.role !== 'alert' || renderedToast.children[1].textContent !== '同步失败，请重试') {
    throw new Error('错误 Toast 必须保留可访问语义和纯文本消息');
}

console.log('PASS frontend toast security');
