const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const lineCount = file => read(file).split('\n').length;

const indexHtml = read('frontend/index.html');
const appJs = read('frontend/js/app.js');
const stateJs = read('frontend/js/app-state.js');
const aiStateJs = read('frontend/js/ai-state.js');
const featureCompositionJs = read('frontend/js/app-feature-composition.js');
const aiFeatureCompositionJs = read('frontend/js/ai-feature-composition.js');
const sessionControllerJs = read('frontend/js/app-session-controller.js');
const dataControllerJs = read('frontend/js/app-data-controller.js');
const templateContextJs = read('frontend/js/app-template-context.js');

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

function assertBefore(content, earlier, later, message) {
    if (content.indexOf(earlier) === -1 || content.indexOf(later) === -1 || content.indexOf(earlier) >= content.indexOf(later)) {
        throw new Error(message);
    }
}

const localAssetPaths = [
    ...[...indexHtml.matchAll(/<(?:script|link)\b[^>]+(?:src|href)="([^"]+)"/g)]
        .map(match => match[1].split('?')[0])
        .filter(asset => asset.startsWith('js/') || asset.startsWith('css/'))
];
localAssetPaths.forEach(asset => {
    if (!fs.existsSync(path.join(root, 'frontend', asset))) {
        throw new Error(`入口页引用了不存在的本地资源：${asset}`);
    }
});

[
    'js/view-helpers.js?v=20260714-ai-v3',
    'js/tag-view.js?v=20260714-ai-v3',
    'js/backup-view.js?v=20260714-ai-v3',
    'js/ai-view.js?v=20260714-ai-v3',
    'js/download-helper.js?v=20260714-ai-v3',
    'js/controllers/entry-controller.js?v=20260714-ai-v3',
    'js/controllers/group-controller.js?v=20260714-ai-v3',
    'js/controllers/tag-controller.js?v=20260714-ai-v3',
    'js/controllers/ai-settings-controller.js?v=20260714-ai-v3',
    'js/controllers/ai-controller.js?v=20260714-ai-v3',
    'js/controllers/ai-assistant-controller.js?v=20260714-ai-v3',
    'js/controllers/backup-controller.js?v=20260714-ai-v3',
    'js/controllers/trash-controller.js?v=20260714-ai-v3',
    'js/controllers/transfer-controller.js?v=20260714-ai-v3',
    'js/controllers/maintenance-controller.js?v=20260714-ai-v3',
    'js/controllers/list-controller.js?v=20260714-ai-v3',
    'js/ai-state.js?v=20260714-ai-v3',
    'js/app-state.js?v=20260714-ai-v3',
    'js/app-ui-controller.js?v=20260714-ai-v3',
    'js/app-data-controller.js?v=20260714-ai-v3',
    'js/ai-feature-composition.js?v=20260714-ai-v3',
    'js/app-feature-composition.js?v=20260714-ai-v3',
    'js/app-session-controller.js?v=20260714-ai-v3',
    'js/app-watchers.js?v=20260714-ai-v3',
    'js/app-template-context.js?v=20260714-ai-v3',
    'js/app.js?v=20260714-ai-v3'
].forEach(asset => {
    assertIncludes(indexHtml, asset, `index.html 必须加载 ${asset}`);
});

assertBefore(indexHtml, 'js/store-state.js', 'js/store.js', 'Store 状态和领域方法必须先于 store.js 加载');
assertBefore(indexHtml, 'js/store-taxonomy-methods.js', 'js/store.js', '密码组和标签 Store 方法必须先于 store.js 加载');
assertBefore(indexHtml, 'js/ai-state.js', 'js/app-state.js', 'AI 状态模块必须先于根状态模块加载');
assertBefore(indexHtml, 'js/app-state.js', 'js/app.js', '根状态模块必须先于 app.js 加载');
assertBefore(indexHtml, 'js/ai-feature-composition.js', 'js/app-feature-composition.js', 'AI 领域装配必须先于根领域装配加载');
assertBefore(indexHtml, 'js/app-feature-composition.js', 'js/app.js', '领域装配模块必须先于 app.js 加载');
assertBefore(indexHtml, 'js/app-template-context.js', 'js/app.js', '模板上下文模块必须先于 app.js 加载');

assertIncludes(appJs, 'window.SecretBaseAppState.createAppState', 'app.js 必须从独立状态模块创建共享状态');
assertIncludes(appJs, 'window.SecretBaseFeatureComposition.createFeatureComposition', 'app.js 必须委托领域装配模块');
assertIncludes(appJs, 'window.SecretBaseAppSessionController.createAppSessionController', 'app.js 必须委托会话控制器');
assertIncludes(appJs, 'window.SecretBaseTemplateContext.createTemplateContext', 'app.js 必须通过模板上下文模块暴露绑定');
assertIncludes(templateContextJs, 'Object.assign', '模板上下文必须将状态、视图和操作平铺给 Vue');
assertIncludes(stateJs, 'function createAppState', '共享响应式状态必须在独立模块中创建');
assertIncludes(stateJs, 'window.SecretBaseAiState.createAiState', '根状态模块必须装配独立 AI 状态');
assertIncludes(aiStateJs, 'function createAiState', 'AI 状态必须由独立模块创建');
assertNotIncludes(stateJs, 'async function', '状态模块不应承载异步领域行为');
assertIncludes(dataControllerJs, 'function createAppDataController', '跨领域加载行为必须从根入口拆出');
assertIncludes(sessionControllerJs, 'function createAppSessionController', '认证与生命周期必须从根入口拆出');

assertIncludes(appJs, 'const viewHelpers = window.SecretBaseViewHelpers', '根入口必须装配视图辅助模块');
assertIncludes(featureCompositionJs, 'viewHelpers,', '领域装配层必须接收视图辅助模块依赖');
assertIncludes(featureCompositionJs, 'window.SecretBaseTagView.createTagView', '装配层必须复用标签视图模块');
assertIncludes(featureCompositionJs, 'window.SecretBaseBackupView.createBackupView', '装配层必须复用备份视图模块');
assertIncludes(featureCompositionJs, 'window.SecretBaseAiFeatureComposition.createAiFeatureComposition', '根装配层必须委托独立 AI 领域装配');
assertIncludes(aiFeatureCompositionJs, 'window.SecretBaseAiView.createAiView', 'AI 领域装配必须复用 AI 视图模块');
assertIncludes(aiFeatureCompositionJs, 'window.SecretBaseAiSettingsController.createAiSettingsController', 'AI 领域装配必须装配厂商设置控制器');
assertIncludes(aiFeatureCompositionJs, 'window.SecretBaseAiController.createAiController', 'AI 领域装配必须装配专业工具控制器');
assertIncludes(aiFeatureCompositionJs, 'window.SecretBaseAiAssistantController.createAiAssistantController', 'AI 领域装配必须装配对话管家控制器');
assertIncludes(appJs, 'openExternalUrl,', '根入口必须显式传递外部链接能力');
assertIncludes(featureCompositionJs, 'openExternalUrl,', '领域装配不得隐式依赖全局外部链接函数');
[
    'window.SecretBaseEntryController.createEntryController',
    'window.SecretBaseGroupController.createGroupController',
    'window.SecretBaseTagController.createTagController',
    'window.SecretBaseBackupController.createBackupController',
    'window.SecretBaseTrashController.createTrashController',
    'window.SecretBaseTransferController.createTransferController',
    'window.SecretBaseMaintenanceController.createMaintenanceController',
    'window.SecretBaseListController.createListController'
].forEach(namespace => {
    assertIncludes(featureCompositionJs, namespace, `领域装配模块必须装配 ${namespace}`);
});

assertNotIncludes(appJs, 'function entryAccentColor', '条目强调色逻辑不应继续内联在 app.js');
assertNotIncludes(appJs, 'function normalizeFieldForEdit', '字段编辑归一化不应继续内联在 app.js');
assertNotIncludes(appJs, 'const sortedTagBrowserTags = computed', '标签排序视图不应继续内联在 app.js');
assertNotIncludes(appJs, 'const backupGroups = computed', '备份分组视图不应继续内联在 app.js');
assertNotIncludes(appJs, 'const aiOrganizeSummary = computed', 'AI 整理摘要不应继续内联在 app.js');

assertLessThan(lineCount('frontend/js/app.js'), 140, 'app.js 必须保持为轻量装配入口');
assertLessThan(lineCount('frontend/js/app-state.js'), 500, '共享状态模块必须保持可审阅体量');
assertLessThan(lineCount('frontend/js/ai-state.js'), 220, 'AI 状态模块必须保持可审阅体量');
assertLessThan(lineCount('frontend/js/ai-feature-composition.js'), 220, 'AI 领域装配模块必须保持单一职责体量');
assertLessThan(lineCount('frontend/js/app-feature-composition.js'), 550, '领域装配模块必须只承担依赖连接');
assertLessThan(lineCount('frontend/js/app-session-controller.js'), 300, '会话控制器必须保持单一职责体量');
[
    'entry-controller.js',
    'group-controller.js',
    'tag-controller.js',
    'ai-settings-controller.js',
    'ai-controller.js',
    'ai-assistant-controller.js',
    'backup-controller.js',
    'trash-controller.js',
    'transfer-controller.js',
    'maintenance-controller.js',
    'list-controller.js'
].forEach(file => {
    assertLessThan(lineCount(`frontend/js/controllers/${file}`), 550, `${file} 必须保持单一职责体量`);
});

console.log('PASS frontend feature modules');
