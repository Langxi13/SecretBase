/**
 * API 客户端封装
 */
class ApiClient {
    constructor() {
        this.baseUrl = this.resolveBaseUrl();
        this.token = null;
    }

    /**
     * 解析 API 地址：Windows 本地开发直连后端，Ubuntu 生产走 nginx /api 代理。
     */
    resolveBaseUrl() {
        const runtimeConfig = window.SECRETBASE_RUNTIME_CONFIG || {};
        if (Object.prototype.hasOwnProperty.call(runtimeConfig, 'apiBaseUrl')
            && runtimeConfig.apiBaseUrl !== null
            && runtimeConfig.apiBaseUrl !== undefined) {
            return this.normalizeBaseUrl(runtimeConfig.apiBaseUrl);
        }

        if (Object.prototype.hasOwnProperty.call(window, 'SECRETBASE_API_BASE_URL')) {
            return this.normalizeBaseUrl(window.SECRETBASE_API_BASE_URL);
        }

        const { protocol, hostname, port } = window.location;
        const isLocalDev = protocol === 'file:'
            || hostname === 'localhost'
            || hostname === '127.0.0.1'
            || hostname === '';

        if (isLocalDev && port !== '10004') {
            return 'http://127.0.0.1:10004';
        }

        return '/api';
    }

    normalizeBaseUrl(url) {
        return String(url).replace(/\/+$/, '');
    }

    /**
     * 设置认证 token
     */
    setToken(token) {
        this.token = token;
        if (token) {
            window.SecretBaseStorage.setSession('token', token);
        } else {
            window.SecretBaseStorage.removeSession('token');
        }
        window.SecretBaseStorage.removeLocal('token');
    }

    /**
     * 获取认证 token
     */
    getToken() {
        if (!this.token) {
            this.token = window.SecretBaseStorage.getSession('token');
            window.SecretBaseStorage.removeLocal('token');
        }
        return this.token;
    }

    async parseResponse(response) {
        let text;
        try {
            text = await response.text();
        } catch (error) {
            return { valid: false, data: null };
        }
        if (!text.trim()) {
            return { valid: response.status === 204, data: {} };
        }
        try {
            const data = JSON.parse(text);
            return {
                valid: data !== null && typeof data === 'object' && !Array.isArray(data),
                data
            };
        } catch (error) {
            return { valid: false, data: null };
        }
    }

    responseError(response, parsed) {
        if (parsed.valid && response.ok) return parsed.data;
        if (parsed.valid) {
            return {
                ...parsed.data,
                error: parsed.data.error || 'HTTP_ERROR',
                message: parsed.data.message || `请求失败（HTTP ${response.status}）`
            };
        }
        return {
            error: 'HTTP_ERROR',
            message: `请求失败（HTTP ${response.status}）`
        };
    }

    notifyVaultMutation(response, path) {
        if (String(path || '').startsWith('/sync')) return;
        if (response.headers?.get?.('X-SecretBase-Vault-Changed') !== '1') return;
        window.dispatchEvent(new CustomEvent('secretbase:vault-mutated', {
            detail: {
                path,
                revision: response.headers.get('X-SecretBase-Vault-Revision') || ''
            }
        }));
    }

    /**
     * 发送请求
     */
    async request(method, path, data = null, requestOptions = {}) {
        const headers = {
            'Content-Type': 'application/json'
        };

        const token = this.getToken();
        if (token) {
            headers['X-SecretBase-Token'] = token;
        }

        const options = {
            method,
            headers,
            credentials: 'same-origin'
        };

        const timeoutMs = Number(requestOptions.timeoutMs || 0);
        const controller = timeoutMs > 0 && typeof AbortController !== 'undefined'
            ? new AbortController()
            : null;
        const timeoutId = controller
            ? window.setTimeout(() => controller.abort(), timeoutMs)
            : null;
        if (controller) options.signal = controller.signal;

        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }

        let response;
        let parsed;
        try {
            response = await fetch(`${this.baseUrl}${path}`, options);
            parsed = await this.parseResponse(response);
        } catch (error) {
            if (error?.name === 'AbortError') {
                throw new ApiError('REQUEST_TIMEOUT', '请求处理超时，请稍后重试', 408);
            }
            throw new ApiError('NETWORK_ERROR', '网络连接失败，请检查连接后重试', 0);
        } finally {
            if (timeoutId !== null) window.clearTimeout(timeoutId);
        }

        const result = this.responseError(response, parsed);
        if (!response.ok) {
            this.notifyUnauthorized(response.status, result.message);
            throw new ApiError(result.error, result.message, response.status, result.data || result.details);
        }
        if (!parsed.valid) {
            throw new ApiError('INVALID_RESPONSE', '服务器返回了无法识别的响应', response.status);
        }

        this.notifyVaultMutation(response, path);
        return result;
    }

    /**
     * GET 请求
     */
    get(path) {
        return this.request('GET', path);
    }

    /**
     * POST 请求
     */
    post(path, data, requestOptions = {}) {
        return this.request('POST', path, data, requestOptions);
    }

    /**
     * PUT 请求
     */
    put(path, data) {
        return this.request('PUT', path, data);
    }

    /**
     * DELETE 请求
     */
    delete(path) {
        return this.request('DELETE', path);
    }

    /**
     * 文件上传
     */
    async upload(path, file, additionalData = {}) {
        const formData = new FormData();
        formData.append('file', file);

        for (const [key, value] of Object.entries(additionalData)) {
            formData.append(key, value);
        }

        const headers = {};
        const token = this.getToken();
        if (token) {
            headers['X-SecretBase-Token'] = token;
        }

        let response;
        let parsed;
        try {
            response = await fetch(`${this.baseUrl}${path}`, {
                method: 'POST',
                headers,
                credentials: 'same-origin',
                body: formData
            });
            parsed = await this.parseResponse(response);
        } catch (error) {
            throw new ApiError('NETWORK_ERROR', '网络连接失败，请检查连接后重试', 0);
        }

        const result = this.responseError(response, parsed);
        if (!response.ok) {
            this.notifyUnauthorized(response.status, result.message);
            throw new ApiError(result.error, result.message, response.status, result.data || result.details);
        }
        if (!parsed.valid) {
            throw new ApiError('INVALID_RESPONSE', '服务器返回了无法识别的响应', response.status);
        }

        this.notifyVaultMutation(response, path);
        return result;
    }

    notifyUnauthorized(status, message = '') {
        if (status === 401) {
            window.dispatchEvent(new CustomEvent('secretbase:unauthorized', { detail: { message } }));
        }
    }
}

/**
 * API 错误类
 */
class ApiError extends Error {
    constructor(code, message, status, data = null) {
        super(message);
        this.code = code;
        this.status = status;
        this.data = data;
    }
}

// 创建全局 API 实例
const api = new ApiClient();
