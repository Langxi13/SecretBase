/**
 * Store 的条目读写与批量操作方法。
 * 写操作只提交并返回结果，页面状态刷新由调用方统一负责。
 */
(function () {
    function createEntryMethods({ api, showToast, normalizePagination, buildEntrySearchParams }) {
        return {
            async loadEntries(page = 1, { shouldCommit } = {}) {
                try {
                    const pageSize = this.state.settings.pageSize || 20;
                    const params = buildEntrySearchParams({
                        page,
                        pageSize,
                        filters: this.state.filters
                    });
                    const result = await api.get(`/entries?${params}`);
                    const pagination = normalizePagination(result.data.pagination);
                    if (typeof shouldCommit === 'function' && !shouldCommit()) {
                        return { ...result.data, pagination };
                    }
                    this.setState({
                        entries: result.data.items,
                        pagination
                    });
                    return { ...result.data, pagination };
                } catch (error) {
                    console.error('加载条目失败:', error);
                    throw error;
                }
            },

            async getEntry(id) {
                try {
                    const result = await api.get(`/entries/${id}`);
                    return result.data;
                } catch (error) {
                    console.error('获取条目失败:', error);
                    showToast(error.message || '获取条目失败', 'error');
                    return null;
                }
            },

            async createEntry(entryData) {
                try {
                    const result = await api.post('/entries', entryData);
                    showToast('条目创建成功', 'success');
                    return result.data;
                } catch (error) {
                    console.error('创建条目失败:', error);
                    showToast(error.message || '创建条目失败', 'error');
                    return null;
                }
            },

            async updateEntry(id, updates) {
                try {
                    const result = await api.put(`/entries/${id}`, updates);
                    showToast('条目更新成功', 'success');
                    return result.data;
                } catch (error) {
                    console.error('更新条目失败:', error);
                    showToast(error.message || '更新条目失败', 'error');
                    return null;
                }
            },

            async deleteEntry(id) {
                try {
                    await api.delete(`/entries/${id}`);
                    showToast('条目已移至回收站', 'success');
                    return true;
                } catch (error) {
                    console.error('删除条目失败:', error);
                    showToast('删除条目失败', 'error');
                    return false;
                }
            },

            async batchDelete(ids) {
                try {
                    const result = await api.post('/entries/batch-delete', { ids });
                    showToast(result.message || '批量删除成功', 'success');
                    return result.data;
                } catch (error) {
                    console.error('批量删除失败:', error);
                    showToast(error.message || '批量删除失败', 'error');
                    return null;
                }
            },

            async batchStar(ids, starred) {
                try {
                    const result = await api.post('/entries/batch-star', { ids, starred });
                    showToast(result.message || '批量更新成功', 'success');
                    return result.data;
                } catch (error) {
                    console.error('批量星标失败:', error);
                    showToast(error.message || '批量星标失败', 'error');
                    return null;
                }
            },

            async batchUpdateTags(ids, addTags = [], removeTags = []) {
                try {
                    const result = await api.post('/entries/batch-update-tags', {
                        ids,
                        add_tags: addTags,
                        remove_tags: removeTags
                    });
                    showToast(result.message || '批量标签更新成功', 'success');
                    return result.data;
                } catch (error) {
                    console.error('批量更新标签失败:', error);
                    showToast(error.message || '批量更新标签失败', 'error');
                    return null;
                }
            },

            async toggleStar(entry) {
                return this.updateEntry(entry.id, { starred: !entry.starred });
            }
        };
    }

    window.SecretBaseStoreEntryMethods = {
        createEntryMethods
    };
})();
