const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const lineCount = file => read(file).split('\n').length;
const { readFrontendAssetVersion } = require('./frontend-source');
const assetVersion = readFrontendAssetVersion();

const indexHtml = read('frontend/index.html');
const runtimeConfigJs = read('frontend/secretbase-runtime-config.js');
const appJs = read('frontend/js/app.js');
const stateJs = read('frontend/js/app-state.js');
const aiStateJs = read('frontend/js/ai-state.js');
const syncStateJs = read('frontend/js/sync-state.js');
const syncLifecycleJs = read('frontend/js/sync-lifecycle.js');
const syncSetupValidationJs = read('frontend/js/sync-setup-validation.js');
const inspectorStateJs = read('frontend/js/ai-assistant-inspector-state.js');
const inspectorControllerJs = read('frontend/js/controllers/ai-assistant-inspector-controller.js');
const featureCompositionJs = read('frontend/js/app-feature-composition.js');
const aiFeatureCompositionJs = read('frontend/js/ai-feature-composition.js');
const sessionControllerJs = read('frontend/js/app-session-controller.js');
const sessionSecurityJs = read('frontend/js/app-session-security.js');
const desktopLockCoverJs = read('frontend/js/desktop-lock-cover.js');
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

const localAssetReferences = [
    ...[...indexHtml.matchAll(/<(?:script|link)\b[^>]+(?:src|href)="([^"]+)"/g)]
        .map(match => match[1])
        .filter(asset => asset.startsWith('js/') || asset.startsWith('css/'))
];
const localAssetPaths = localAssetReferences.map(asset => asset.split('?')[0]);
localAssetPaths.forEach(asset => {
    if (!fs.existsSync(path.join(root, 'frontend', asset))) {
        throw new Error(`入口页引用了不存在的本地资源：${asset}`);
    }
});
localAssetReferences.forEach(asset => {
    if (!asset.endsWith(`?v=${assetVersion}`)) {
        throw new Error(`前端资源缓存版本必须统一为 ${assetVersion}：${asset}`);
    }
});
assertIncludes(
    indexHtml,
    `/secretbase-runtime-config.js?v=${assetVersion}`,
    '运行时配置也必须使用独立资源修订号避免缓存旧模式'
);
assertIncludes(
    runtimeConfigJs,
    `assetVersion: '${assetVersion}'`,
    '静态运行时配置必须与资源修订号保持一致'
);

[
    'js/storage.js',
    'js/view-helpers.js',
    'js/tag-view.js',
    'js/backup-view.js',
    'js/ai-view.js',
    'js/download-helper.js',
    'js/controllers/entry-controller.js',
    'js/controllers/group-controller.js',
    'js/sync-lifecycle.js',
    'js/sync-setup-validation.js',
    'js/controllers/sync-management-controller.js',
    'js/controllers/sync-operation-controller.js',
    'js/controllers/sync-controller.js',
    'js/controllers/tag-controller.js',
    'js/controllers/ai-settings-controller.js',
    'js/controllers/ai-controller.js',
    'js/controllers/ai-scope-controller.js',
    'js/controllers/ai-assistant-inspector-controller.js',
    'js/controllers/ai-assistant-local-actions.js',
    'js/ai-assistant-request.js',
    'js/controllers/ai-assistant-controller.js',
    'js/controllers/backup-controller.js',
    'js/controllers/trash-controller.js',
    'js/controllers/transfer-controller.js',
    'js/controllers/maintenance-controller.js',
    'js/controllers/list-controller.js',
    'js/controllers/entry-onboarding-controller.js',
    'js/ai-assistant-inspector-state.js',
    'js/ai-state.js',
    'js/sync-state.js',
    'js/app-state.js',
    'js/app-ui-controller.js',
    'js/app-data-controller.js',
    'js/ai-feature-composition.js',
    'js/app-feature-composition.js',
    'js/desktop-lock-cover.js',
    'js/app-session-lifecycle.js',
    'js/app-session-security.js',
    'js/app-session-settings.js',
    'js/app-session-controller.js',
    'js/app-watchers.js',
    'js/app-template-context.js',
    'js/app.js'
].forEach(asset => {
    assertIncludes(indexHtml, `${asset}?v=${assetVersion}`, `index.html 必须加载 ${asset}`);
});

assertBefore(indexHtml, 'js/storage.js', 'js/api.js', '安全存储适配必须先于 API 客户端加载');
assertBefore(indexHtml, 'js/store-state.js', 'js/store.js', 'Store 状态和领域方法必须先于 store.js 加载');
assertBefore(indexHtml, 'js/store-taxonomy-methods.js', 'js/store.js', '密码组和标签 Store 方法必须先于 store.js 加载');
assertBefore(indexHtml, 'js/ai-assistant-inspector-state.js', 'js/ai-state.js', '建议详情状态必须先于 AI 聚合状态加载');
assertBefore(indexHtml, 'js/ai-state.js', 'js/app-state.js', 'AI 状态模块必须先于根状态模块加载');
assertBefore(indexHtml, 'js/sync-state.js', 'js/app-state.js', '同步状态模块必须先于根状态模块加载');
assertBefore(indexHtml, 'js/sync-lifecycle.js', 'js/controllers/sync-controller.js', '同步生命周期必须先于控制器加载');
assertBefore(indexHtml, 'js/sync-setup-validation.js', 'js/controllers/sync-controller.js', '同步表单校验必须先于同步主控制器加载');
assertBefore(indexHtml, 'js/controllers/sync-management-controller.js', 'js/controllers/sync-controller.js', '同步管理控制器必须先于同步主控制器加载');
assertBefore(indexHtml, 'js/controllers/sync-operation-controller.js', 'js/controllers/sync-controller.js', '同步操作控制器必须先于同步主控制器加载');
assertBefore(indexHtml, 'js/controllers/ai-assistant-inspector-controller.js', 'js/controllers/ai-assistant-controller.js', 'AI 管家支持模块必须先于主控制器加载');
assertBefore(indexHtml, 'js/controllers/ai-assistant-local-actions.js', 'js/controllers/ai-assistant-controller.js', 'AI 本地操作模块必须先于主控制器加载');
assertBefore(indexHtml, 'js/ai-assistant-request.js', 'js/controllers/ai-assistant-controller.js', 'AI 请求生命周期模块必须先于主控制器加载');
assertBefore(indexHtml, 'js/app-state.js', 'js/app.js', '根状态模块必须先于 app.js 加载');
assertBefore(indexHtml, 'js/app-session-lifecycle.js', 'js/app-session-controller.js', '会话生命周期必须先于会话控制器加载');
assertBefore(indexHtml, 'js/app-session-security.js', 'js/app-session-controller.js', '会话安全清理必须先于会话控制器加载');
assertBefore(indexHtml, 'js/app-session-settings.js', 'js/app-session-controller.js', '会话设置模块必须先于会话控制器加载');
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
assertIncludes(stateJs, 'window.SecretBaseSyncState.createSyncState', '根状态模块必须装配独立同步状态');
assertIncludes(aiStateJs, 'function createAiState', 'AI 状态必须由独立模块创建');
assertIncludes(syncStateJs, 'function createSyncState', '同步状态必须由独立模块创建');
assertIncludes(syncLifecycleJs, 'function createSyncLifecycle', '同步生命周期必须由独立模块创建');
assertIncludes(syncSetupValidationJs, 'function createSyncSetupValidation', '同步表单校验必须由独立模块创建');
assertIncludes(inspectorStateJs, 'function createAiAssistantInspectorState', '建议详情状态必须由独立模块创建');
assertIncludes(inspectorControllerJs, 'function normalizeAssistantPlan', 'AI 计划归一化必须由管家支持模块负责');
assertIncludes(inspectorControllerJs, 'function createAiAssistantInspectorController', '建议详情加载必须由独立控制器负责');
assertNotIncludes(stateJs, 'async function', '状态模块不应承载异步领域行为');
assertIncludes(dataControllerJs, 'function createAppDataController', '跨领域加载行为必须从根入口拆出');
assertIncludes(sessionControllerJs, 'function createAppSessionController', '认证与生命周期必须从根入口拆出');
assertIncludes(desktopLockCoverJs, 'scheduleRelease', '桌面保护层必须提供隐藏窗口可恢复的释放调度');

assertIncludes(appJs, 'const viewHelpers = window.SecretBaseViewHelpers', '根入口必须装配视图辅助模块');
assertIncludes(featureCompositionJs, 'viewHelpers,', '领域装配层必须接收视图辅助模块依赖');
assertIncludes(featureCompositionJs, 'window.SecretBaseTagView.createTagView', '装配层必须复用标签视图模块');
assertIncludes(featureCompositionJs, 'window.SecretBaseBackupView.createBackupView', '装配层必须复用备份视图模块');
assertIncludes(featureCompositionJs, 'window.SecretBaseAiFeatureComposition.createAiFeatureComposition', '根装配层必须委托独立 AI 领域装配');
assertIncludes(aiFeatureCompositionJs, 'window.SecretBaseAiView.createAiView', 'AI 领域装配必须复用 AI 视图模块');
assertIncludes(aiFeatureCompositionJs, 'window.SecretBaseAiSettingsController.createAiSettingsController', 'AI 领域装配必须装配厂商设置控制器');
assertIncludes(aiFeatureCompositionJs, 'window.SecretBaseAiController.createAiController', 'AI 领域装配必须装配专业工具控制器');
assertIncludes(aiFeatureCompositionJs, 'window.SecretBaseAiAssistantInspectorController.createAiAssistantInspectorController', 'AI 领域装配必须装配建议详情控制器');
assertIncludes(aiFeatureCompositionJs, 'window.SecretBaseAiAssistantController.createAiAssistantController', 'AI 领域装配必须装配对话管家控制器');
assertIncludes(sessionSecurityJs, 'createSessionSecurityController', '会话安全清理必须独立装配');
assertIncludes(appJs, 'openExternalUrl,', '根入口必须显式传递外部链接能力');
assertIncludes(featureCompositionJs, 'openExternalUrl,', '领域装配不得隐式依赖全局外部链接函数');
[
    'window.SecretBaseEntryController.createEntryController',
    'window.SecretBaseGroupController.createGroupController',
    'window.SecretBaseSyncController.createSyncController',
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
assertLessThan(lineCount('frontend/js/sync-state.js'), 120, '同步状态模块必须保持轻量');
assertLessThan(lineCount('frontend/js/sync-lifecycle.js'), 140, '同步生命周期模块必须保持轻量');
assertLessThan(lineCount('frontend/js/sync-setup-validation.js'), 140, '同步表单校验模块必须保持轻量');
assertLessThan(lineCount('frontend/js/controllers/sync-controller.js'), 600, '同步控制器必须保持可审阅体量');
assertLessThan(lineCount('frontend/js/controllers/sync-operation-controller.js'), 420, '同步操作控制器必须保持可审阅体量');
assertLessThan(lineCount('frontend/js/ai-assistant-inspector-state.js'), 120, '建议详情状态模块必须保持轻量');
assertLessThan(lineCount('frontend/js/ai-feature-composition.js'), 220, 'AI 领域装配模块必须保持单一职责体量');
assertLessThan(lineCount('frontend/js/app-feature-composition.js'), 550, '领域装配模块必须只承担依赖连接');
assertLessThan(lineCount('frontend/js/app-session-controller.js'), 300, '会话控制器必须保持单一职责体量');
assertLessThan(lineCount('frontend/js/app-session-security.js'), 240, '会话安全清理模块必须保持可审阅体量');
[
    'entry-controller.js',
    'group-controller.js',
    'tag-controller.js',
    'ai-settings-controller.js',
    'ai-controller.js',
    'ai-scope-controller.js',
    'ai-assistant-inspector-controller.js',
    'ai-assistant-local-actions.js',
    '../ai-assistant-request.js',
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
