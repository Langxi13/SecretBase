/** 在其他前端资源加载前，从地址栏清除意外遗留的认证字段。 */
(function () {
    const sensitiveKeys = [
        'init_password',
        'init_confirm_password',
        'unlock_password',
        'password',
        'old_password',
        'new_password'
    ];
    const url = new URL(window.location.href);
    let changed = false;

    sensitiveKeys.forEach(key => {
        if (url.searchParams.has(key)) {
            url.searchParams.delete(key);
            changed = true;
        }
    });

    if (changed) {
        const query = url.searchParams.toString();
        const safeUrl = `${url.pathname}${query ? `?${query}` : ''}${url.hash}`;
        window.history.replaceState(null, document.title, safeUrl);
    }
})();
