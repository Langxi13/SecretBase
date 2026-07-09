const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const lineCount = file => read(file).split('\n').length;

const indexHtml = read('frontend/index.html');
const appJs = read('frontend/js/app.js');
const utilsJs = read('frontend/js/utils.js');

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

function assertLessThan(actual, expected, message) {
    if (!(actual < expected)) {
        throw new Error(`${message}，当前 ${actual}，期望小于 ${expected}`);
    }
}

assertIncludes(indexHtml, 'css/visual-polish.css?v=20260710-ui-v65', '视觉增强样式必须拆到 visual-polish.css 并带版本号');
assertIncludes(indexHtml, 'css/component-polish.css?v=20260710-ui-v65', '组件增强样式必须拆到 component-polish.css 并带版本号');
assertIncludes(indexHtml, 'js/pagination.js?v=20260710-ui-v65', '分页偏好工具必须拆到独立 JS 模块');
assertIncludes(indexHtml, 'js/toast.js?v=20260710-ui-v65', 'Toast 工具必须拆到独立 JS 模块');

assertIncludes(appJs, 'window.SecretBasePagination', 'app.js 必须复用分页偏好工具模块');
assertNotIncludes(appJs, 'function normalizeUniversalPageSize', 'app.js 不应继续内联通用分页归一化函数');
assertNotIncludes(utilsJs, 'function showToast', 'utils.js 不应继续承载 Toast DOM 组件逻辑');

assertLessThan(lineCount('frontend/js/app.js'), 3775, 'app.js 必须从巨型文件中拆出基础工具逻辑');
assertLessThan(lineCount('frontend/css/style.css'), 2050, 'style.css 必须拆出后段视觉覆盖样式');
assertLessThan(lineCount('frontend/css/components.css'), 2050, 'components.css 必须拆出后段组件覆盖样式');

console.log('PASS frontend module split');
