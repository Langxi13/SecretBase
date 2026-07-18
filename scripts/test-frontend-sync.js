const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const index = read('frontend/index.html');
const settings = read('frontend/templates/settings-dialog.html');
const dialogs = read('frontend/templates/sync-dialogs.html');
const controller = read('frontend/js/controllers/sync-controller.js');
const lifecycle = read('frontend/js/sync-lifecycle.js');
const state = read('frontend/js/sync-state.js');
const api = read('frontend/js/api.js');
const styles = read('frontend/css/sync-components.css');

function assertIncludes(content, needle, message) {
    if (!content.includes(needle)) throw new Error(message);
}

function assertNotIncludes(content, needle, message) {
    if (content.includes(needle)) throw new Error(message);
}

[
    'css/sync-components.css',
    'js/sync-lifecycle.js',
    'js/controllers/sync-management-controller.js',
    'js/controllers/sync-controller.js',
    'js/sync-state.js'
].forEach(asset => assertIncludes(index, asset, `入口页必须加载同步资源：${asset}`));

assertIncludes(settings, "activeSettingsTab === 'sync'", '设置必须提供独立同步标签');
assertIncludes(settings, "openSyncSetup('create')", '同步设置必须提供创建空间入口');
assertIncludes(settings, "openSyncSetup('join')", '同步设置必须提供加入空间入口');
assertIncludes(settings, 'syncStatus.pending_join', '待处理加入必须使用独立状态而不是伪装成已配置');
assertIncludes(settings, 'openSyncHistory', '同步设置必须提供历史版本入口');
assertIncludes(settings, "openSyncRecovery('rotate')", '同步设置必须提供密钥轮换入口');
assertIncludes(settings, "openSyncRecovery('compact')", '同步设置必须提供历史压缩入口');
assertIncludes(dialogs, 'syncConflictResolutions[item.conflict_id]', '同步冲突必须逐项选择处理方式');
assertIncludes(dialogs, 'item.local?.field_count', '冲突概况必须显示字段数量');
assertIncludes(dialogs, 'item.changed_sections', '冲突概况必须显示变化区域');
assertNotIncludes(dialogs, 'item.local.fields', '同步冲突界面不得读取本机字段内容');
assertNotIncludes(dialogs, 'item.remote.fields', '同步冲突界面不得读取远端字段内容');
assertNotIncludes(dialogs, 'item.local.value', '同步冲突界面不得渲染本机字段值');
assertNotIncludes(dialogs, 'item.remote.value', '同步冲突界面不得渲染远端字段值');
assertIncludes(dialogs, '当前主密码', '恢复码显示和密钥轮换必须二次验证主密码');
assertIncludes(dialogs, "syncDeleteForm.confirmation !== 'DELETE'", '删除远端数据必须输入 DELETE');
assertIncludes(dialogs, "syncCompactConfirmation !== 'COMPACT'", '历史压缩必须输入 COMPACT');
assertIncludes(lifecycle, 'schedule(5000)', 'Vault 写入后必须使用 5 秒防抖同步');
assertIncludes(lifecycle, 'Date.now() - hiddenAt >= 60000', '回到前台超过 60 秒必须触发同步');
assertIncludes(lifecycle, "window.addEventListener('secretbase:vault-mutated'", '同步生命周期必须监听 Vault 写入事件');
assertIncludes(api, "X-SecretBase-Vault-Changed", 'API 客户端必须识别 Vault 修改响应头');
assertIncludes(api, "startsWith('/sync')", '同步接口必须排除自动同步递归触发');
assertNotIncludes(state, 'SecretBaseStorage', '恢复码和同步凭据不得写入浏览器存储');
assertIncludes(styles, '@media (max-width: 760px)', '同步界面必须提供移动宽度降级');
assertIncludes(styles, 'overflow-wrap: anywhere', '恢复码必须避免长文本撑破布局');

console.log('PASS frontend encrypted sync');
