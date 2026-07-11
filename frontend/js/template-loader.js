/**
 * 加载拆分后的 Vue 模板片段。
 *
 * 保持当前无构建链的部署方式：模板仍由同源静态目录提供，
 * 但入口页不再承担全部页面和弹窗的标记。
 */
(function () {
    const TEMPLATE_VERSION = '20260711-ui-v77';
    const templatePaths = [
        'templates/app-layout.html',
        'templates/workspace-list.html',
        'templates/entry-dialogs.html',
        'templates/ai-dialog.html',
        'templates/tag-browser-dialog.html',
        'templates/settings-dialog.html',
        'templates/desktop-dialog.html',
        'templates/backup-dialogs.html',
        'templates/management-dialogs.html',
        'templates/transfer-dialogs.html'
    ];

    async function loadTemplate(path) {
        const response = await fetch(`${path}?v=${TEMPLATE_VERSION}`, {
            credentials: 'same-origin'
        });
        if (!response.ok) {
            throw new Error(`模板加载失败：${path}（${response.status}）`);
        }
        return response.text();
    }

    function renderLoadError(root) {
        root.replaceChildren();

        const screen = document.createElement('div');
        screen.className = 'loading-screen template-load-error';
        screen.setAttribute('role', 'alert');

        const title = document.createElement('h1');
        title.textContent = '页面加载失败';
        const message = document.createElement('p');
        message.textContent = '请刷新页面后重试。';

        screen.append(title, message);
        root.append(screen);
    }

    async function mount(app) {
        const root = document.getElementById('app');
        if (!root) {
            throw new Error('未找到应用挂载节点');
        }

        try {
            const templates = await Promise.all(templatePaths.map(loadTemplate));
            root.innerHTML = templates.join('\n');
            root.removeAttribute('aria-busy');
            app.mount(root);
        } catch (error) {
            console.error('SecretBase 模板加载失败:', error);
            root.removeAttribute('aria-busy');
            renderLoadError(root);
        }
    }

    window.SecretBaseTemplateLoader = {
        mount,
        templatePaths
    };
})();
