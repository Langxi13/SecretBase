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
 * 获取网站 favicon
 */
function getFaviconUrl(url) {
    if (!url) return '';
    try {
        const domain = new URL(url).hostname;
        // 使用多个 favicon 服务作为备选
        return `https://favicon.im/${domain}`;
    } catch {
        return '';
    }
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
 * 显示 Toast 提示
 */
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-message">${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/**
 * 生成 UUID
 */
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}
