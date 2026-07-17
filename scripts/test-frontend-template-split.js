const fs = require('fs');
const path = require('path');
const {
    root,
    templatePaths,
    readProjectFile,
    readFrontendMarkup,
    readAppVersion
} = require('./frontend-source');
const appVersion = readAppVersion();
const templateLineLimits = {
    'frontend/templates/settings-dialog.html': 450
};

function assertIncludes(content, needle, message) {
    if (!content.includes(needle)) {
        throw new Error(message);
    }
}

function assertLessThan(actual, expected, message) {
    if (!(actual < expected)) {
        throw new Error(`${message}，当前 ${actual}，期望小于 ${expected}`);
    }
}

const indexHtml = readProjectFile('frontend/index.html');
const appJs = readProjectFile('frontend/js/app.js');
const loaderJs = readProjectFile('frontend/js/template-loader.js');
const fullMarkup = readFrontendMarkup();

assertIncludes(indexHtml, `js/template-loader.js?v=${appVersion}`, '入口页必须在 app.js 前加载模板加载器');
assertIncludes(loaderJs, 'SECRETBASE_RUNTIME_CONFIG?.version', '模板缓存版本必须复用统一应用版本');
assertIncludes(loaderJs, "'templates/ai-scope-dialog.html'", '模板加载器必须加载 AI 范围选择弹窗');
assertIncludes(loaderJs, "'templates/sync-dialogs.html'", '模板加载器必须加载同步弹窗');
assertIncludes(appJs, 'window.SecretBaseTemplateLoader.mount(app)', 'Vue 应用必须由模板加载器挂载');
assertIncludes(loaderJs, 'Promise.all(templatePaths.map(loadTemplate))', '模板加载器必须并行读取全部片段');
assertIncludes(loaderJs, "credentials: 'same-origin'", '模板请求必须保持同源凭据策略');
assertIncludes(loaderJs, 'renderLoadError', '模板加载失败必须展示可见的恢复提示');
assertLessThan(indexHtml.split('\n').length, 95, 'index.html 必须保持为轻量入口页');

templatePaths.forEach(templatePath => {
    const source = readProjectFile(templatePath);
    const lineLimit = templateLineLimits[templatePath] || 400;
    if (!source.trim()) {
        throw new Error(`模板片段不能为空：${templatePath}`);
    }
    assertLessThan(source.split('\n').length, lineLimit, `模板片段必须保持在可维护体量：${templatePath}`);
    assertIncludes(loaderJs, templatePath.replace(/^frontend\//, ''), `模板加载器必须加载 ${templatePath}`);
});

assertIncludes(fullMarkup, 'v-if="showAiParse"', '组合后的模板必须保留 AI 弹窗');
assertIncludes(fullMarkup, 'v-if="showTagManager"', '组合后的模板必须保留标签管理');
assertIncludes(fullMarkup, 'v-if="showImportPreview"', '组合后的模板必须保留导入预览');

const missingTemplates = templatePaths.filter(templatePath => !fs.existsSync(path.join(root, templatePath)));
if (missingTemplates.length > 0) {
    throw new Error(`模板文件缺失：${missingTemplates.join(', ')}`);
}

console.log('PASS frontend template split');
