const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const templatePaths = [
    'frontend/templates/app-layout.html',
    'frontend/templates/workspace-list.html',
    'frontend/templates/ai-workspace.html',
    'frontend/templates/ai-entry-inspector.html',
    'frontend/templates/ai-scope-dialog.html',
    'frontend/templates/entry-dialogs.html',
    'frontend/templates/ai-dialog.html',
    'frontend/templates/tag-browser-dialog.html',
    'frontend/templates/settings-dialog.html',
    'frontend/templates/sync-dialogs.html',
    'frontend/templates/desktop-dialog.html',
    'frontend/templates/backup-dialogs.html',
    'frontend/templates/management-dialogs.html',
    'frontend/templates/transfer-dialogs.html'
];
const cssPaths = [
    'frontend/css/base.css',
    'frontend/css/workspace.css',
    'frontend/css/workspace-responsive.css',
    'frontend/css/workspace-polish.css',
    'frontend/css/modals.css',
    'frontend/css/form-controls.css',
    'frontend/css/ai-components.css',
    'frontend/css/ai-workspace.css',
    'frontend/css/ai-entry-inspector.css',
    'frontend/css/ai-plan-review.css',
    'frontend/css/ai-scope-picker.css',
    'frontend/css/ai-send-review.css',
    'frontend/css/management-components.css',
    'frontend/css/sync-components.css',
    'frontend/css/desktop-components.css',
    'frontend/css/component-responsive.css',
    'frontend/css/themes/variables.css',
    'frontend/css/themes/dark.css',
    'frontend/css/themes/light.css',
    'frontend/css/visual-polish.css',
    'frontend/css/component-polish.css',
    'frontend/css/modal-layout.css'
];

function readProjectFile(file) {
    return fs.readFileSync(path.join(root, file), 'utf8');
}

function readFrontendMarkup() {
    return [
        readProjectFile('frontend/index.html'),
        ...templatePaths.map(readProjectFile)
    ].join('\n');
}

function readFrontendCss() {
    return cssPaths.map(readProjectFile).join('\n');
}

function readAppVersion() {
    const source = readProjectFile('backend/version.py');
    const match = source.match(/APP_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"/);
    if (!match) throw new Error('无法读取 backend/version.py 中的 APP_VERSION');
    return match[1];
}

function readFrontendAssetVersion() {
    const source = readProjectFile('backend/version.py');
    const match = source.match(/WEB_ASSET_VERSION\s*=\s*"([^"]+)"/);
    if (!match) throw new Error('无法读取 backend/version.py 中的 WEB_ASSET_VERSION');
    return match[1];
}

module.exports = {
    root,
    templatePaths,
    cssPaths,
    readProjectFile,
    readFrontendMarkup,
    readFrontendCss,
    readAppVersion,
    readFrontendAssetVersion
};
