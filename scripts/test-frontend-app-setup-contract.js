const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const appJs = fs.readFileSync(path.join(root, 'frontend/js/app.js'), 'utf8');
const indexHtml = fs.readFileSync(path.join(root, 'frontend/index.html'), 'utf8');

function assertIncludes(content, needle, message) {
    if (!content.includes(needle)) {
        throw new Error(message);
    }
}

function assertMatches(content, pattern, message) {
    if (!pattern.test(content)) {
        throw new Error(message);
    }
}

assertIncludes(indexHtml, 'entryPageSizeOptions', '条目分页下拉框必须使用 setup 暴露的选项');
assertIncludes(appJs, 'entryPageSizeOptions,', 'setup return 必须暴露条目分页选项');
assertMatches(
    appJs,
    /const\s+entryPageSizeOptions\s*=\s*\[6,\s*12,\s*20,\s*30,\s*50,\s*100\]/,
    'entryPageSizeOptions 必须在 setup 内声明，否则 Vue 初始化会 ReferenceError'
);
assertIncludes(appJs, 'if (api.getToken())', '条目分页自定义必须用 api token 判断解锁状态，不能读取不存在的 store.state.token');
assertMatches(
    appJs,
    /async function updateEntryPageSize\(val\)\s*\{[\s\S]*?await store\.updateSettings\(\{ pageSize: size \}\)[\s\S]*?await loadEntries\(1\)/,
    '条目分页自定义保存后必须通过 loadEntries(1) 刷新 Vue 列表状态'
);
assertMatches(
    appJs,
    /async function applySettings\(settings\)[\s\S]*?await store\.updateSettings\(\{ pageSize: savedEntryPageSize \}\)/,
    '启动或解锁恢复条目分页偏好时必须等待设置同步完成，避免首次加载仍用旧分页'
);
assertMatches(
    appJs,
    /await applySettings\(settings\)/,
    '初始化流程必须等待分页偏好应用后再加载条目'
);
assertMatches(
    appJs,
    /await applySettings\(await store\.loadSettings\(\)\)/,
    '初始化和解锁流程必须等待分页偏好应用后再加载条目'
);
assertIncludes(indexHtml, 'updateEntryPageSize(settingsForm.pageSize)', '全部条目分页控件必须继续支持自定义每页数量');
assertIncludes(indexHtml, 'entryPageSizeOptions', '全部条目分页控件必须继续支持常用每页数量下拉');
if (/<div class="setting-item">\s*<label>每页条目数<\/label>/.test(indexHtml)) {
    throw new Error('系统设置通用页不应再保留“每页条目数”，分页数量应在各分页区自定义');
}

const returnIndex = appJs.lastIndexOf('return {');
const returnEndIndex = appJs.indexOf('\n        };', returnIndex);
const setupPrefix = appJs.slice(0, returnIndex);
const returnBlock = appJs.slice(returnIndex, returnEndIndex);
const returnedNames = [...returnBlock.matchAll(/^\s*([A-Za-z_$][\w$]*),\s*$/gm)].map(match => match[1]);
const destructuredConstNames = new Set();
[...setupPrefix.matchAll(/const\s+\{([\s\S]*?)\}\s*=/g)].forEach(match => {
    match[1]
        .split(',')
        .map(name => name.trim())
        .filter(Boolean)
        .forEach(name => {
            const localName = name.includes(':') ? name.split(':').pop().trim() : name;
            if (/^[A-Za-z_$][\w$]*$/.test(localName)) {
                destructuredConstNames.add(localName);
            }
        });
});
const missingReturnedNames = returnedNames.filter(name => {
    const declarationPatterns = [
        new RegExp(`\\bconst\\s+${name}\\b`),
        new RegExp(`\\blet\\s+${name}\\b`),
        new RegExp(`\\bvar\\s+${name}\\b`),
        new RegExp(`\\bfunction\\s+${name}\\b`),
        new RegExp(`\\basync\\s+function\\s+${name}\\b`)
    ];
    return !destructuredConstNames.has(name) && !declarationPatterns.some(pattern => pattern.test(setupPrefix));
});

if (missingReturnedNames.length > 0) {
    throw new Error(`setup return 包含未声明变量：${missingReturnedNames.join(', ')}`);
}

console.log('PASS frontend app setup contract');
