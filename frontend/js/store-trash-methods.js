/**
 * Store 的回收站 API 方法。
 */
(function () {
    function createTrashMethods({ api, showToast }) {
        return {
            async loadTrash(page = 1) {
                try {
                    const result = await api.get(`/trash?page=${page}&page_size=${this.state.settings.pageSize}`);
                    this.setState({ trash: result.data.items });
                    return result.data;
                } catch (error) {
                    console.error('加载回收站失败:', error);
                    return { items: [], pagination: { page: 1, total: 0, totalPages: 0 } };
                }
            },

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
            },

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
            },

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
        };
    }

    window.SecretBaseStoreTrashMethods = {
        createTrashMethods
    };
})();
