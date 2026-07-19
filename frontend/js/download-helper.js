/**
 * 受保护下载请求的通用实现。
 */
(function () {
    async function downloadProtectedFile({
        api,
        showToast,
        path,
        body,
        filename,
        method = 'POST',
        throwOnError = false,
        successMessage = '备份已下载'
    }) {
        try {
            const sessionEpoch = typeof api.getSessionEpoch === 'function'
                ? api.getSessionEpoch()
                : null;
            const desktopApi = window.pywebview && window.pywebview.api;
            if (desktopApi && typeof desktopApi.save_download === 'function') {
                const result = await desktopApi.save_download({
                    path,
                    body: body || {},
                    filename,
                    method,
                    token: api.getToken()
                });
                if (typeof api.isSessionCurrent === 'function' && !api.isSessionCurrent(sessionEpoch)) {
                    throw new ApiError('SESSION_INVALIDATED', '当前会话已结束，请重新解锁后重试', 401);
                }
                if (result && result.status === 'cancelled') return false;
                if (result && result.status === 'error') {
                    throw new ApiError(result.error || 'DOWNLOAD_ERROR', result.message || '下载失败', 0);
                }
                showToast(successMessage, 'success');
                return true;
            }

            const blob = typeof api.download === 'function'
                ? await api.download(path, method === 'GET' ? null : (body || {}), {
                    method,
                    timeoutMs: 120000
                })
                : await downloadWithLegacyFetch(api, path, body, method);
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = filename;
            anchor.click();
            URL.revokeObjectURL(url);
            showToast(successMessage, 'success');
            return true;
        } catch (error) {
            if (!throwOnError) {
                showToast(error.message || '导出失败', 'error');
                return false;
            }
            throw error;
        }
    }

    async function downloadWithLegacyFetch(api, path, body, method) {
        const headers = { 'X-SecretBase-Token': api.getToken() };
        const options = { method, headers, credentials: 'same-origin' };
        if (method !== 'GET') {
            headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(body || {});
        }
        const response = await fetch(`${api.baseUrl}${path}`, options);
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new ApiError(error.error, error.message || '导出失败', response.status, error.data || error.details);
        }
        return response.blob();
    }

    window.SecretBaseDownload = {
        downloadProtectedFile
    };
})();
