const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const toastJs = fs.readFileSync(path.join(root, 'frontend/js/toast.js'), 'utf8');
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
assertNotIncludes(utilsJs, 'function showToast', 'utils.js 不应继续承载 Toast DOM 组件逻辑');

console.log('PASS frontend toast security');
