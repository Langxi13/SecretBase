/**
 * 工具函数
 */

/**
 * DJB2 哈希算法
 */
function djb2Hash(str) {
    let hash = 5381;
    for (let i = 0; i < str.length; i++) {
        hash = ((hash << 5) + hash) + str.charCodeAt(i);
        hash = hash & hash; // 转换为 32 位整数
    }
    return Math.abs(hash);
}

/**
 * 根据标签名生成颜色
 */
function getTagColor(tagName) {
    const hash = djb2Hash(tagName);
    const hue = hash % 360;
    return `hsl(${hue}, 65%, 55%)`;
}

/**
 * 格式化日期
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;

    // 1 分钟内
    if (diff < 60000) {
        return '刚刚';
    }

    // 1 小时内
    if (diff < 3600000) {
        return `${Math.floor(diff / 60000)} 分钟前`;
    }

    // 24 小时内
    if (diff < 86400000) {
        return `${Math.floor(diff / 3600000)} 小时前`;
    }

    // 7 天内
    if (diff < 604800000) {
        return `${Math.floor(diff / 86400000)} 天前`;
    }

    // 超过 7 天
    return date.toLocaleDateString('zh-CN');
}

/**
 * 防抖函数
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 复制到剪贴板
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (err) {
        // 降级方案
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            return true;
        } catch {
            return false;
        } finally {
            document.body.removeChild(textArea);
        }
    }
}

/**
 * 桌面壳使用系统浏览器打开外部链接，普通 Web 模式继续隔离 opener/referrer。
 */
async function openExternalUrl(url) {
    const desktopApi = window.pywebview && window.pywebview.api;
    if (desktopApi && typeof desktopApi.open_external === 'function') {
        return desktopApi.open_external(url);
    }
    const openedWindow = window.open(url, '_blank', 'noopener,noreferrer');
    if (openedWindow) openedWindow.opener = null;
    return Boolean(openedWindow);
}
