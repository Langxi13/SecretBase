/**
 * 状态管理
 */
class Store {
    constructor() {
        this.state = {
            initialized: false,
            locked: true,
            entries: [],
            tags: [],
            trash: [],
            settings: {
                theme: 'system',
                pageSize: 20,
                autoLockMinutes: 5
            },
            pagination: {
                page: 1,
                pageSize: 20,
                total: 0,
                totalPages: 0
            },
            filters: {
                search: '',
                entryIds: [],
                tag: null,
                searchScopes: [],
                tags: [],
                untagged: false,
                createdFrom: '',
                createdTo: '',
                updatedFrom: '',
                updatedTo: '',
                hasUrl: '',
                hasRemarks: '',
                starred: false,
                sortBy: 'updated_at',
                sortOrder: 'desc'
            }
        };

        this.listeners = [];
    }

    /**
     * 订阅状态变化
     */
    subscribe(listener) {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter(l => l !== listener);
        };
    }

    /**
     * 通知状态变化
     */
    notify() {
        this.listeners.forEach(listener => listener(this.state));
    }

    normalizeSettings(settings = {}) {
        return {
            theme: settings.theme || 'system',
            pageSize: settings.pageSize ?? settings.page_size ?? 20,
            autoLockMinutes: settings.autoLockMinutes ?? settings.auto_lock_minutes ?? 5,
            language: settings.language || 'zh-CN'
        };
    }

    toBackendSettings(settings = {}) {
        return {
            theme: settings.theme,
            page_size: settings.pageSize ?? settings.page_size,
            auto_lock_minutes: settings.autoLockMinutes ?? settings.auto_lock_minutes,
            language: settings.language
        };
    }

    normalizePagination(pagination = {}) {
        return {
            page: pagination.page ?? 1,
            pageSize: pagination.pageSize ?? pagination.page_size ?? 20,
            total: pagination.total ?? 0,
            totalPages: pagination.totalPages ?? pagination.total_pages ?? 0
        };
    }

    /**
     * 更新状态
     */
    setState(updates) {
        Object.assign(this.state, updates);
        this.notify();
    }

    /**
     * 检查认证状态
     */
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
            return { initialized: false, locked: true };
        }
    }

    /**
     * 初始化主密码
     */
    async initPassword(password) {
        const result = await api.post('/auth/init', { password });
        api.setToken(result.data.token);
        this.setState({ locked: false, initialized: true });
        return result;
    }

    /**
     * 解锁
     */
    async unlock(password) {
        const result = await api.post('/auth/unlock', { password });
        api.setToken(result.data.token);
        this.setState({ locked: false });
        return result;
    }

    /**
     * 锁定
     */
    async lock() {
        await api.post('/auth/lock');
        api.setToken(null);
        this.setState({ locked: true });
    }

    /**
     * 加载设置
     */
    async loadSettings() {
        try {
            const result = await api.get('/settings');
            const settings = this.normalizeSettings(result.data);
            this.setState({ settings });
            return settings;
        } catch (error) {
            console.error('加载设置失败:', error);
            return this.state.settings;
        }
    }

    /**
     * 更新设置
     */
    async updateSettings(updates) {
        const result = await api.put('/settings', this.toBackendSettings(updates));
        const settings = this.normalizeSettings(result.data);
        this.setState({ settings });
        return { ...result, data: settings };
    }

    /**
     * 加载条目列表
     */
    async loadEntries(page = 1) {
        try {
            const pageSize = this.state.settings.pageSize || 20;
            const params = new URLSearchParams({
                page: page.toString(),
                page_size: pageSize.toString()
            });

            if (this.state.filters.search) {
                params.append('search', this.state.filters.search);
                params.append('search_scopes', (this.state.filters.searchScopes || []).join(','));
            }
            if (this.state.filters.entryIds?.length) {
                params.append('ids', this.state.filters.entryIds.join(','));
            }
            if (this.state.filters.tag) {
                params.append('tag', this.state.filters.tag);
            }
            if (this.state.filters.tags?.length) {
                params.append('tags', this.state.filters.tags.join(','));
            }
            if (this.state.filters.untagged) {
                params.append('untagged', 'true');
            }
            if (this.state.filters.createdFrom) {
                params.append('created_from', this.state.filters.createdFrom);
            }
            if (this.state.filters.createdTo) {
                params.append('created_to', this.state.filters.createdTo);
            }
            if (this.state.filters.updatedFrom) {
                params.append('updated_from', this.state.filters.updatedFrom);
            }
            if (this.state.filters.updatedTo) {
                params.append('updated_to', this.state.filters.updatedTo);
            }
            if (this.state.filters.hasUrl === 'yes') {
                params.append('has_url', 'true');
            } else if (this.state.filters.hasUrl === 'no') {
                params.append('has_url', 'false');
            }
            if (this.state.filters.hasRemarks === 'yes') {
                params.append('has_remarks', 'true');
            } else if (this.state.filters.hasRemarks === 'no') {
                params.append('has_remarks', 'false');
            }
            if (this.state.filters.starred) {
                params.append('starred', 'true');
            }
            params.append('sort_by', this.state.filters.sortBy || 'updated_at');
            params.append('sort_order', this.state.filters.sortOrder || 'desc');

            const result = await api.get(`/entries?${params}`);
            
            const pagination = this.normalizePagination(result.data.pagination);

            this.setState({
                entries: result.data.items,
                pagination
            });

            return { ...result.data, pagination };
        } catch (error) {
            console.error('加载条目失败:', error);
            showToast(error.message || '加载条目失败', 'error');
            return {
                items: this.state.entries,
                pagination: this.state.pagination
            };
        }
    }

    /**
     * 获取条目详情
     */
    async getEntry(id) {
        try {
            const result = await api.get(`/entries/${id}`);
            return result.data;
        } catch (error) {
            console.error('获取条目失败:', error);
            showToast('获取条目失败', 'error');
            return null;
        }
    }

    /**
     * 创建条目
     */
    async createEntry(entryData) {
        try {
            const result = await api.post('/entries', entryData);
            showToast('条目创建成功', 'success');
            await this.loadEntries(this.state.pagination.page);
            return result.data;
        } catch (error) {
            console.error('创建条目失败:', error);
            showToast('创建条目失败', 'error');
            return null;
        }
    }

    /**
     * 更新条目
     */
    async updateEntry(id, updates) {
        try {
            const result = await api.put(`/entries/${id}`, updates);
            showToast('条目更新成功', 'success');
            await this.loadEntries(this.state.pagination.page);
            return result.data;
        } catch (error) {
            console.error('更新条目失败:', error);
            showToast('更新条目失败', 'error');
            return null;
        }
    }

    /**
     * 删除条目
     */
    async deleteEntry(id) {
        try {
            await api.delete(`/entries/${id}`);
            showToast('条目已移至回收站', 'success');
            await this.loadEntries(this.state.pagination.page);
            return true;
        } catch (error) {
            console.error('删除条目失败:', error);
            showToast('删除条目失败', 'error');
            return false;
        }
    }

    async batchDelete(ids) {
        try {
            const result = await api.post('/entries/batch-delete', { ids });
            showToast(result.message || '批量删除成功', 'success');
            await this.loadEntries(1);
            return result.data;
        } catch (error) {
            console.error('批量删除失败:', error);
            showToast(error.message || '批量删除失败', 'error');
            return null;
        }
    }

    async batchStar(ids, starred) {
        try {
            const result = await api.post('/entries/batch-star', { ids, starred });
            showToast(result.message || '批量更新成功', 'success');
            await this.loadEntries(this.state.pagination.page);
            return result.data;
        } catch (error) {
            console.error('批量星标失败:', error);
            showToast(error.message || '批量星标失败', 'error');
            return null;
        }
    }

    async batchUpdateTags(ids, addTags = [], removeTags = []) {
        try {
            const result = await api.post('/entries/batch-update-tags', {
                ids,
                add_tags: addTags,
                remove_tags: removeTags
            });
            showToast(result.message || '批量标签更新成功', 'success');
            await this.loadEntries(this.state.pagination.page);
            await this.loadTags();
            return result.data;
        } catch (error) {
            console.error('批量更新标签失败:', error);
            showToast(error.message || '批量更新标签失败', 'error');
            return null;
        }
    }

    /**
     * 切换星标
     */
    async toggleStar(entry) {
        return this.updateEntry(entry.id, { starred: !entry.starred });
    }

    /**
     * 加载标签
     */
    async loadTags() {
        try {
            const result = await api.get('/tags');
            this.setState({ tags: result.data.tags });
            return result.data.tags;
        } catch (error) {
            console.error('加载标签失败:', error);
            return [];
        }
    }

    /**
     * 加载回收站
     */
    async loadTrash(page = 1) {
        try {
            const result = await api.get(`/trash?page=${page}&page_size=${this.state.settings.pageSize}`);
            this.setState({ trash: result.data.items });
            return result.data;
        } catch (error) {
            console.error('加载回收站失败:', error);
            return { items: [], pagination: { page: 1, total: 0, totalPages: 0 } };
        }
    }

    /**
     * 恢复条目
     */
    async restoreEntry(id) {
        try {
            await api.post(`/trash/${id}/restore`);
            showToast('条目已恢复', 'success');
            await this.loadTrash();
            return true;
        } catch (error) {
            console.error('恢复条目失败:', error);
            showToast('恢复条目失败', 'error');
            return false;
        }
    }

    /**
     * 彻底删除
     */
    async permanentlyDelete(id) {
        try {
            await api.delete(`/trash/${id}`);
            showToast('条目已彻底删除', 'success');
            await this.loadTrash();
            return true;
        } catch (error) {
            console.error('彻底删除失败:', error);
            showToast('彻底删除失败', 'error');
            return false;
        }
    }

    /**
     * 清空回收站
     */
    async emptyTrash() {
        try {
            await api.post('/trash/empty');
            showToast('回收站已清空', 'success');
            await this.loadTrash();
            return true;
        } catch (error) {
            console.error('清空回收站失败:', error);
            showToast('清空回收站失败', 'error');
            return false;
        }
    }

    /**
     * 设置筛选条件
     */
    setFilter(key, value) {
        this.state.filters[key] = value;
        this.notify();
    }

    /**
     * 清除筛选条件
     */
    clearFilters() {
        this.state.filters = {
            search: '',
            entryIds: [],
            tag: null,
            searchScopes: [],
            tags: [],
            untagged: false,
            createdFrom: '',
            createdTo: '',
            updatedFrom: '',
            updatedTo: '',
            hasUrl: '',
            hasRemarks: '',
            starred: false,
            sortBy: 'updated_at',
            sortOrder: 'desc'
        };
        this.notify();
    }
}

// 创建全局 Store 实例
const store = new Store();
