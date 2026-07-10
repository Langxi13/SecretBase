const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const downloadHelper = fs.readFileSync(path.join(root, 'frontend/js/download-helper.js'), 'utf8');
const utils = fs.readFileSync(path.join(root, 'frontend/js/utils.js'), 'utf8');
const entryController = fs.readFileSync(path.join(root, 'frontend/js/controllers/entry-controller.js'), 'utf8');
const entryDialogs = fs.readFileSync(path.join(root, 'frontend/templates/entry-dialogs.html'), 'utf8');

if (!utils.includes('desktopApi.open_external(url)')) throw new Error('桌面外部链接必须通过原生桥打开');
if (!entryController.includes('openExternalUrl(url)')) throw new Error('条目控制器必须复用外部链接桥');
if (!entryDialogs.includes('@click.prevent="openUrl(selectedEntry.url)"')) throw new Error('详情链接不得让 WebView 直接导航');

const calls = [];
const toasts = [];
const sandbox = {
    window: {
        pywebview: {
            api: {
                async save_download(payload) {
                    calls.push(payload);
                    return { status: 'saved' };
                }
            }
        }
    },
    fetch() {
        throw new Error('桌面保存不应回退到浏览器 fetch 下载');
    },
    ApiError: class ApiError extends Error {}
};
sandbox.window.window = sandbox.window;
vm.runInContext(downloadHelper, vm.createContext(sandbox));

(async () => {
    const result = await sandbox.window.SecretBaseDownload.downloadProtectedFile({
        api: { getToken: () => 'desktop-token', baseUrl: '' },
        showToast: (...args) => toasts.push(args),
        path: '/export/encrypted',
        body: {},
        filename: 'backup.enc'
    });
    if (result !== true) throw new Error('桌面保存成功应返回 true');
    if (calls.length !== 1 || calls[0].token !== 'desktop-token') throw new Error('桌面保存参数不完整');
    if (toasts.length !== 1 || toasts[0][1] !== 'success') throw new Error('桌面保存成功提示缺失');
    console.log('PASS frontend desktop bridge');
})().catch(error => {
    console.error(error);
    process.exit(1);
});
