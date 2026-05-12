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
            sessionStorage.setItem('token', token);
        } else {
            sessionStorage.removeItem('token');
        }
        localStorage.removeItem('token');
    }

    /**
     * 获取认证 token
     */
    getToken() {
        if (!this.token) {
            this.token = sessionStorage.getItem('token');
            localStorage.removeItem('token');
        }
        return this.token;
    }

    /**
     * 发送请求
     */
    async request(method, path, data = null) {
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

        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(`${this.baseUrl}${path}`, options);
        const result = await response.json();

        if (!response.ok) {
            this.notifyUnauthorized(response.status, result.message);
            throw new ApiError(result.error, result.message, response.status, result.data || result.details);
        }

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
    post(path, data) {
        return this.request('POST', path, data);
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

        const response = await fetch(`${this.baseUrl}${path}`, {
            method: 'POST',
            headers,
            credentials: 'same-origin',
            body: formData
        });

        const result = await response.json();
        if (!response.ok) {
            this.notifyUnauthorized(response.status, result.message);
            throw new ApiError(result.error, result.message, response.status, result.data || result.details);
        }

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
