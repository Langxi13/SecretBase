/**
 * API 客户端封装
 */
class ApiClient {
    constructor() {
        this.baseUrl = this.resolveBaseUrl();
        this.token = null;
        this.sessionEpoch = 0;
        this.activeControllers = new Set();
    }

    /**
     * Invalidates requests that belong to a locked or replaced session.
     * Aborting here prevents late responses from repopulating sensitive UI.
     */
    invalidateSession() {
        this.sessionEpoch += 1;
        for (const controller of this.activeControllers) {
            try {
                controller.abort();
            } catch (_) {
                // An already completed controller can safely be ignored.
            }
        }
        this.activeControllers.clear();
    }

    defaultTimeoutMs(path) {
        const value = String(path || '');
        if (value.startsWith('/sync/') || value.startsWith('/backups') || value.startsWith('/import')) {
            return 120000;
        }
        if (value.startsWith('/ai/')) {
            if (
                value === '/ai/status'
                || value === '/ai/providers'
                || value === '/ai/models'
                || value.endsWith('/diagnostics/status')
                || value.endsWith('/diagnostics/preview')
            ) {
                return 20000;
            }
            // AI 解析和整理由后端统一受 AI_CHAT_TIMEOUT_SECONDS 控制，
            // 前端必须覆盖该上游时限，不能用普通列表请求的 45 秒默认值。
            return 150000;
        }
        return 45000;
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

    getSessionEpoch() {
        return this.sessionEpoch;
    }

    isSessionCurrent(epoch) {
        return epoch === this.sessionEpoch;
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

        const timeoutMs = Number(requestOptions.timeoutMs || this.defaultTimeoutMs(path));
        const externalSignal = requestOptions.signal || null;
        let abortedByCaller = Boolean(externalSignal?.aborted);
        let externalAbortListener = null;
        const controller = timeoutMs > 0 && typeof AbortController !== 'undefined'
            ? new AbortController()
            : null;
        const timeoutId = controller
            ? window.setTimeout(() => controller.abort(), timeoutMs)
            : null;
        const requestEpoch = this.sessionEpoch;
        if (controller) {
            options.signal = controller.signal;
            this.activeControllers.add(controller);
            if (externalSignal) {
                externalAbortListener = () => {
                    abortedByCaller = true;
                    controller.abort();
                };
                if (externalSignal.aborted) {
                    externalAbortListener();
                } else {
                    externalSignal.addEventListener('abort', externalAbortListener, { once: true });
                }
            }
        } else if (externalSignal) {
            options.signal = externalSignal;
        }

        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }

        let response;
        let parsed;
        try {
            response = await fetch(`${this.baseUrl}${path}`, options);
            parsed = await this.parseResponse(response);
            if (requestEpoch !== this.sessionEpoch) {
                throw new ApiError('SESSION_INVALIDATED', '当前会话已结束，请重新解锁后重试', 401);
            }
        } catch (error) {
            if (error?.code === 'SESSION_INVALIDATED') throw error;
            if (error?.name === 'AbortError' && requestEpoch !== this.sessionEpoch) {
                throw new ApiError('SESSION_INVALIDATED', '当前会话已结束，请重新解锁后重试', 401);
            }
            if (error?.name === 'AbortError') {
                if (abortedByCaller || externalSignal?.aborted) {
                    throw new ApiError('REQUEST_CANCELLED', '已取消本次请求', 499);
                }
                throw new ApiError('REQUEST_TIMEOUT', '请求处理超时，请稍后重试', 408);
            }
            throw new ApiError('NETWORK_ERROR', '网络连接失败，请检查连接后重试', 0);
        } finally {
            if (timeoutId !== null) window.clearTimeout(timeoutId);
            if (externalSignal && externalAbortListener) {
                externalSignal.removeEventListener('abort', externalAbortListener);
            }
            if (controller) this.activeControllers.delete(controller);
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
    get(path, requestOptions = {}) {
        return this.request('GET', path, null, requestOptions);
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
    put(path, data, requestOptions = {}) {
        return this.request('PUT', path, data, requestOptions);
    }

    /**
     * DELETE 请求
     */
    delete(path, requestOptions = {}) {
        return this.request('DELETE', path, null, requestOptions);
    }

    /**
     * 文件上传
     */
    async upload(path, file, additionalData = {}, requestOptions = {}) {
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

        const timeoutMs = Number(requestOptions.timeoutMs || 120000);
        const controller = timeoutMs > 0 && typeof AbortController !== 'undefined'
            ? new AbortController()
            : null;
        const timeoutId = controller
            ? window.setTimeout(() => controller.abort(), timeoutMs)
            : null;
        const requestEpoch = this.sessionEpoch;
        if (controller) this.activeControllers.add(controller);
        let response;
        let parsed;
        try {
            const fetchOptions = {
                method: 'POST',
                headers,
                credentials: 'same-origin',
                body: formData
            };
            if (controller) fetchOptions.signal = controller.signal;
            response = await fetch(`${this.baseUrl}${path}`, fetchOptions);
            parsed = await this.parseResponse(response);
            if (requestEpoch !== this.sessionEpoch) {
                throw new ApiError('SESSION_INVALIDATED', '当前会话已结束，请重新解锁后重试', 401);
            }
        } catch (error) {
            if (error?.code === 'SESSION_INVALIDATED') throw error;
            if (error?.name === 'AbortError' && requestEpoch !== this.sessionEpoch) {
                throw new ApiError('SESSION_INVALIDATED', '当前会话已结束，请重新解锁后重试', 401);
            }
            if (error?.name === 'AbortError') {
                throw new ApiError('REQUEST_TIMEOUT', '请求处理超时，请稍后重试', 408);
            }
            throw new ApiError('NETWORK_ERROR', '网络连接失败，请检查连接后重试', 0);
        } finally {
            if (timeoutId !== null) window.clearTimeout(timeoutId);
            if (controller) this.activeControllers.delete(controller);
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
     * 下载二进制响应。与普通请求共用会话代际和超时边界，锁定后不会继续
     * 把迟到的受保护文件交给页面。
     */
    async download(path, data = null, requestOptions = {}) {
        const headers = {};
        const token = this.getToken();
        if (token) headers['X-SecretBase-Token'] = token;
        const method = String(requestOptions.method || (data ? 'POST' : 'GET')).toUpperCase();
        const options = {
            method,
            headers,
            credentials: 'same-origin'
        };
        if (data && method !== 'GET') {
            headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(data);
        }

        const timeoutMs = Number(requestOptions.timeoutMs || 120000);
        const controller = timeoutMs > 0 && typeof AbortController !== 'undefined'
            ? new AbortController()
            : null;
        const timeoutId = controller
            ? window.setTimeout(() => controller.abort(), timeoutMs)
            : null;
        const requestEpoch = this.sessionEpoch;
        if (controller) {
            options.signal = controller.signal;
            this.activeControllers.add(controller);
        }

        try {
            const response = await fetch(`${this.baseUrl}${path}`, options);
            if (requestEpoch !== this.sessionEpoch) {
                throw new ApiError('SESSION_INVALIDATED', '当前会话已结束，请重新解锁后重试', 401);
            }
            if (!response.ok) {
                const parsed = await this.parseResponse(response);
                const result = this.responseError(response, parsed);
                this.notifyUnauthorized(response.status, result.message);
                throw new ApiError(result.error, result.message, response.status, result.data || result.details);
            }
            const blob = await response.blob();
            if (requestEpoch !== this.sessionEpoch) {
                throw new ApiError('SESSION_INVALIDATED', '当前会话已结束，请重新解锁后重试', 401);
            }
            return blob;
        } catch (error) {
            if (error?.code === 'SESSION_INVALIDATED') throw error;
            if (error?.name === 'AbortError' && requestEpoch !== this.sessionEpoch) {
                throw new ApiError('SESSION_INVALIDATED', '当前会话已结束，请重新解锁后重试', 401);
            }
            if (error?.name === 'AbortError') {
                throw new ApiError('REQUEST_TIMEOUT', '请求处理超时，请稍后重试', 408);
            }
            if (error instanceof ApiError) throw error;
            throw new ApiError('NETWORK_ERROR', '网络连接失败，请检查连接后重试', 0);
        } finally {
            if (timeoutId !== null) window.clearTimeout(timeoutId);
            if (controller) this.activeControllers.delete(controller);
        }
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
