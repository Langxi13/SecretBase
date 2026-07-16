/**
 * 浏览器存储的安全适配层。
 *
 * Safari 隐私模式、禁用站点数据或受限 WebView 可能在访问 storage 属性时
 * 直接抛出 SecurityError。偏好持久化失败不应阻止密码库登录和当前会话使用。
 */
(function exposeSafeStorage() {
    function storageFor(name) {
        try {
            return window[name] || null;
        } catch (error) {
            return null;
        }
    }

    function get(name, key) {
        try {
            return storageFor(name)?.getItem(key) ?? null;
        } catch (error) {
            return null;
        }
    }

    function set(name, key, value) {
        try {
            const storage = storageFor(name);
            if (!storage) return false;
            storage.setItem(key, String(value));
            return true;
        } catch (error) {
            return false;
        }
    }

    function remove(name, key) {
        try {
            const storage = storageFor(name);
            if (!storage) return false;
            storage.removeItem(key);
            return true;
        } catch (error) {
            return false;
        }
    }

    window.SecretBaseStorage = Object.freeze({
        getLocal: key => get('localStorage', key),
        setLocal: (key, value) => set('localStorage', key, value),
        removeLocal: key => remove('localStorage', key),
        getSession: key => get('sessionStorage', key),
        setSession: (key, value) => set('sessionStorage', key, value),
        removeSession: key => remove('sessionStorage', key)
    });
})();
