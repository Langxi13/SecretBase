/**
 * 分页偏好工具
 */
(function exposePaginationTools() {
    function normalizeUniversalPageSize(value, fallback = 12, min = 1, max = 500) {
        const numericValue = Number(value);
        if (Number.isFinite(numericValue) && numericValue >= min && numericValue <= max) {
            return Math.round(numericValue);
        }
        return fallback;
    }

    function loadPageSizePreference(key, fallback = 12) {
        try {
            return normalizeUniversalPageSize(localStorage.getItem(key), fallback);
        } catch (error) {
            return fallback;
        }
    }

    function savePageSizePreference(key, value) {
        try {
            localStorage.setItem(key, String(normalizeUniversalPageSize(value)));
        } catch (error) {
            // 本地偏好保存失败不影响分页功能
        }
    }

    window.SecretBasePagination = {
        normalizeUniversalPageSize,
        loadPageSizePreference,
        savePageSizePreference
    };
})();
