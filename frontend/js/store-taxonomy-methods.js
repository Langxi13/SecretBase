/**
 * Store 的标签和密码组 API 方法。
 * 写操作只提交并返回结果，页面状态刷新由调用方统一负责。
 */
(function () {
    function createTaxonomyMethods({ api, showToast }) {
        return {
            async loadTags({ shouldCommit } = {}) {
                try {
                    const result = await api.get('/tags');
                    if (typeof shouldCommit === 'function' && !shouldCommit()) {
                        return result.data.tags;
                    }
                    this.setState({ tags: result.data.tags });
                    return result.data.tags;
                } catch (error) {
                    console.error('加载标签失败:', error);
                    throw error;
                }
            },

            async createTag(tagData) {
                try {
                    const result = await api.post('/tags', tagData);
                    showToast(result.message || '标签已创建', 'success');
                    return result.data;
                } catch (error) {
                    console.error('创建标签失败:', error);
                    showToast(error.message || '创建标签失败', 'error');
                    return null;
                }
            },

            async updateTag(tagName, tagData) {
                try {
                    const result = await api.put(`/tags/${encodeURIComponent(tagName)}`, tagData);
                    showToast(result.message || '标签已更新', 'success');
                    return result.data;
                } catch (error) {
                    console.error('更新标签失败:', error);
                    showToast(error.message || '更新标签失败', 'error');
                    return null;
                }
            },

            async deleteTag(tagName) {
                try {
                    const result = await api.delete(`/tags/${encodeURIComponent(tagName)}`);
                    showToast(result.message || '标签已删除', 'success');
                    return result.data;
                } catch (error) {
                    console.error('删除标签失败:', error);
                    showToast(error.message || '删除标签失败', 'error');
                    return null;
                }
            },

            async batchDeleteTags(tagNames) {
                try {
                    const result = await api.post('/tags/batch-delete', { names: tagNames });
                    showToast(result.message || '标签已批量删除', 'success');
                    return result.data;
                } catch (error) {
                    console.error('批量删除标签失败:', error);
                    showToast(error.message || '批量删除标签失败', 'error');
                    return null;
                }
            },

            async loadGroups({ shouldCommit } = {}) {
                try {
                    const result = await api.get('/groups');
                    if (typeof shouldCommit === 'function' && !shouldCommit()) {
                        return result.data.groups;
                    }
                    this.setState({ groups: result.data.groups });
                    return result.data.groups;
                } catch (error) {
                    console.error('加载密码组失败:', error);
                    throw error;
                }
            },

            async createGroup(groupData) {
                try {
                    const result = await api.post('/groups', groupData);
                    showToast(result.message || '密码组已创建', 'success');
                    return result.data;
                } catch (error) {
                    console.error('创建密码组失败:', error);
                    showToast(error.message || '创建密码组失败', 'error');
                    return null;
                }
            },

            async updateGroup(groupName, groupData) {
                try {
                    const result = await api.put(`/groups/${encodeURIComponent(groupName)}`, groupData);
                    showToast(result.message || '密码组已更新', 'success');
                    return result.data;
                } catch (error) {
                    console.error('更新密码组失败:', error);
                    showToast(error.message || '更新密码组失败', 'error');
                    return null;
                }
            },

            async updateGroupOrder(names) {
                try {
                    const result = await api.post('/groups/order', { names });
                    showToast(result.message || '密码组排序已更新', 'success');
                    const groups = result.data.groups || [];
                    this.setState({ groups });
                    return groups;
                } catch (error) {
                    console.error('更新密码组排序失败:', error);
                    showToast(error.message || '更新密码组排序失败', 'error');
                    return null;
                }
            },

            async deleteGroup(groupName) {
                try {
                    const result = await api.delete(`/groups/${encodeURIComponent(groupName)}`);
                    showToast(result.message || '密码组已删除', 'success');
                    return result.data;
                } catch (error) {
                    console.error('删除密码组失败:', error);
                    showToast(error.message || '删除密码组失败', 'error');
                    return null;
                }
            },

            async assignEntriesToGroup(groupName, ids) {
                try {
                    const result = await api.post(`/groups/${encodeURIComponent(groupName)}/entries`, { ids });
                    showToast(result.message || '已加入密码组', 'success');
                    return result.data;
                } catch (error) {
                    console.error('批量加入密码组失败:', error);
                    showToast(error.message || '批量加入密码组失败', 'error');
                    return null;
                }
            }
        };
    }

    window.SecretBaseStoreTaxonomyMethods = {
        createTaxonomyMethods
    };
})();
