/**
 * 回收站分页与恢复/永久删除操作。
 */
(function () {
    function createTrashController(options) {
        const {
            api,
            showToast,
            showConfirmDialog,
            trashItems,
            trashPage,
            trashTotalPages,
            trashTotal,
            trashPageSize,
            loadEntries
        } = options;

        async function loadTrash(page = 1) {
            try {
                const result = await api.get(`/trash?page=${page}&page_size=${trashPageSize.value}`);
                trashItems.value = result.data.items;
                trashPage.value = result.data.pagination.page;
                trashTotalPages.value = result.data.pagination.total_pages;
                trashTotal.value = result.data.pagination.total;
            } catch (error) {
                console.error('加载回收站失败:', error);
            }
        }

        async function goToTrashPage(page) {
            if (page < 1 || page > trashTotalPages.value) return;
            await loadTrash(page);
        }

        async function restoreTrashItem(id) {
            try {
                await api.post(`/trash/${id}/restore`);
                showToast('条目已恢复', 'success');
                await loadTrash();
                await loadEntries();
            } catch (error) {
                showToast('恢复失败', 'error');
            }
        }

        function deleteTrashItem(id) {
            showConfirmDialog('彻底删除', '此操作不可恢复，确认删除？', async () => {
                try {
                    await api.delete(`/trash/${id}`);
                    showToast('已彻底删除', 'success');
                    await loadTrash();
                } catch (error) {
                    showToast('删除失败', 'error');
                }
            });
        }

        function emptyTrashConfirm() {
            showConfirmDialog('清空回收站', '此操作不可恢复，确认清空？', async () => {
                try {
                    await api.post('/trash/empty');
                    showToast('回收站已清空', 'success');
                    await loadTrash();
                } catch (error) {
                    showToast('清空失败', 'error');
                }
            });
        }

        return {
            loadTrash,
            goToTrashPage,
            restoreTrashItem,
            deleteTrashItem,
            emptyTrashConfirm
        };
    }

    window.SecretBaseTrashController = {
        createTrashController
    };
})();
