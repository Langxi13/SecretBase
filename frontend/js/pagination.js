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
        return normalizeUniversalPageSize(window.SecretBaseStorage.getLocal(key), fallback);
    }

    function savePageSizePreference(key, value) {
        window.SecretBaseStorage.setLocal(key, normalizeUniversalPageSize(value));
    }

    function createVisiblePages(current, total) {
        const pages = [];
        if (total <= 7) {
            for (let i = 1; i <= total; i++) pages.push(i);
        } else {
            pages.push(1);
            if (current > 3) pages.push('...');
            for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
                pages.push(i);
            }
            if (current < total - 2) pages.push('...');
            pages.push(total);
        }
        return pages;
    }

    window.SecretBasePagination = {
        normalizeUniversalPageSize,
        loadPageSizePreference,
        savePageSizePreference,
        createVisiblePages
    };
})();
