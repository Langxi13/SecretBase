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
            const headers = {
                'X-SecretBase-Token': api.getToken()
            };
            const options = {
                method,
                headers,
                credentials: 'same-origin'
            };
            if (method !== 'GET') {
                headers['Content-Type'] = 'application/json';
                options.body = JSON.stringify(body || {});
            }

            const response = await fetch(`${api.baseUrl}${path}`, options);
            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new ApiError(error.error, error.message || '导出失败', response.status, error.data || error.details);
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = filename;
            anchor.click();
            URL.revokeObjectURL(url);
            showToast(successMessage, 'success');
        } catch (error) {
            if (!throwOnError) {
                showToast(error.message || '导出失败', 'error');
                return;
            }
            throw error;
        }
    }

    window.SecretBaseDownload = {
        downloadProtectedFile
    };
})();
