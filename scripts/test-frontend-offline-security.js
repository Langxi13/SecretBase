const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

function assertIncludes(content, needle, message) {
    if (!content.includes(needle)) throw new Error(message);
}

function assertNotIncludes(content, needle, message) {
    if (content.includes(needle)) throw new Error(message);
}

const indexHtml = read('frontend/index.html');
const appLayout = read('frontend/templates/app-layout.html');
const workspaceList = read('frontend/templates/workspace-list.html');
const utilsJs = read('frontend/js/utils.js');
const viewHelpersJs = read('frontend/js/view-helpers.js');
const entryControllerJs = read('frontend/js/controllers/entry-controller.js');
const earlySecurityJs = read('frontend/js/early-security.js');
const vendorPath = path.join(root, 'frontend/vendor/vue/vue.global.prod.js');
const vendorBytes = fs.readFileSync(vendorPath);

assertIncludes(indexHtml, '<meta name="referrer" content="no-referrer">', '入口页必须禁止发送敏感来源地址');
assertIncludes(indexHtml, 'js/early-security.js', '入口页必须优先清理遗留敏感查询参数');
assertIncludes(indexHtml, 'vendor/vue/vue.global.prod.js?v=3.5.39', 'Vue 必须固定为本地 vendored 版本');
assertNotIncludes(indexHtml, 'https://unpkg.com', '本地模式不应从 CDN 执行 Vue 代码');
assertNotIncludes(indexHtml, 'fonts.googleapis.com', '本地模式不应依赖 Google Fonts');
if (indexHtml.indexOf('js/early-security.js') >= indexHtml.indexOf('vendor/vue/vue.global.prod.js')) {
    throw new Error('敏感查询参数清理脚本必须先于 Vue 执行');
}

assertIncludes(appLayout, '<form method="post" action="/" @submit.prevent="initPassword">', '初始化表单必须用 POST 作为无脚本降级');
assertIncludes(appLayout, '<form method="post" action="/" @submit.prevent="unlock">', '解锁表单必须用 POST 作为无脚本降级');

assertNotIncludes(utilsJs, 'favicon.im', '条目列表不得向第三方 favicon 服务泄露域名');
assertNotIncludes(workspaceList, '<img', '条目图标必须使用本地生成的占位图标');
assertIncludes(workspaceList, 'getEntryIconText(entry)', '条目图标必须从本地条目元数据生成');
assertIncludes(viewHelpersJs, 'function getEntryIconText', '视图辅助模块必须提供本地图标文本');
assertIncludes(utilsJs, "'_blank', 'noopener,noreferrer'", '浏览器模式打开外部网址必须隔离 opener 和 referrer');
assertIncludes(entryControllerJs, 'openExternalUrl(url)', '条目网址必须通过桌面兼容的外部链接方法打开');

const normalizedVendorBytes = Buffer.from(vendorBytes.toString('utf8').replace(/\r\n/g, '\n'), 'utf8');
const vendorHash = crypto.createHash('sha256').update(normalizedVendorBytes).digest('hex');
if (vendorHash !== '349cb8e0ede3449b4962458daa03418518af50b4a9959a552cce35a8bec92805') {
    throw new Error(`Vue vendored 文件校验失败：${vendorHash}`);
}

let replacedUrl = '';
const sandbox = {
    URL,
    document: { title: 'SecretBase' },
    history: {
        replaceState(_state, _title, url) {
            replacedUrl = url;
        }
    },
    location: {
        href: 'http://127.0.0.1:12345/?init_password=hidden&theme=dark#vault'
    }
};
sandbox.window = sandbox;
vm.runInContext(earlySecurityJs, vm.createContext(sandbox));
if (replacedUrl !== '/?theme=dark#vault') {
    throw new Error(`敏感查询参数清理结果错误：${replacedUrl}`);
}

console.log('PASS frontend offline security');
