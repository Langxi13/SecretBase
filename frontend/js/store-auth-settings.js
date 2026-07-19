/**
 * Store 的认证和设置 API 方法。
 */
(function () {
    function createAuthAndSettingsMethods({ api, normalizeSettings, toBackendSettings }) {
        return {
            async checkAuth() {
                try {
                    const result = await api.get('/auth/status');
                    this.setState({
                        initialized: result.data.initialized,
                        locked: result.data.locked
                    });
                    return result.data;
                } catch (error) {
                    console.error('检查认证状态失败:', error);
                    const isUninitialized = error.status === 404 || (error.data && error.data.initialized === false);
                    if (!isUninitialized) throw error;
                    this.setState({ initialized: false, locked: true });
                    return { initialized: false, locked: true };
                }
            },

            async initPassword(password) {
                const result = await api.post('/auth/init', { password });
                api.setToken(result.data.token);
                this.setState({ locked: false, initialized: true });
                return result;
            },

            async unlock(password) {
                const result = await api.post('/auth/unlock', { password });
                api.setToken(result.data.token);
                this.setState({ locked: false });
                return result;
            },

            async lock() {
                await api.post('/auth/lock');
                api.setToken(null);
                this.setState({ locked: true });
            },

            async loadSettings() {
                try {
                    const result = await api.get('/settings');
                    const settings = normalizeSettings(result.data);
                    this.setState({ settings });
                    return settings;
                } catch (error) {
                    console.error('加载设置失败:', error);
                    return this.state.settings;
                }
            },

            async updateSettings(updates) {
                const result = await api.put('/settings', toBackendSettings(updates));
                const settings = normalizeSettings(result.data);
                this.setState({ settings });
                return { ...result, data: settings };
            }
        };
    }

    window.SecretBaseStoreAuthSettings = {
        createAuthAndSettingsMethods
    };
})();
