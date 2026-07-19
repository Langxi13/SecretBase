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
            trashActionIds = { value: [] },
            trashEmptying = { value: false },
            showTrash = { value: false },
            loadEntries,
            trashLoading,
            trashError,
            locked
        } = options;
        let requestSequence = 0;

        function setItemBusy(id, busy) {
            if (busy) {
                trashActionIds.value = Array.from(new Set([...trashActionIds.value, id]));
            } else {
                trashActionIds.value = trashActionIds.value.filter(itemId => itemId !== id);
            }
        }

        function pageAfterRemoval(count = 1) {
            const nextTotal = Math.max(0, trashTotal.value - count);
            const nextTotalPages = Math.max(1, Math.ceil(nextTotal / trashPageSize.value));
            return Math.min(trashPage.value, nextTotalPages);
        }

        async function loadTrash(page = 1) {
            if (locked?.value) return false;
            const request = ++requestSequence;
            trashLoading.value = true;
            trashError.value = '';
            try {
                const result = await api.get(`/trash?page=${page}&page_size=${trashPageSize.value}`);
                if (request !== requestSequence || locked?.value) return false;
                trashItems.value = result.data.items;
                trashPage.value = result.data.pagination.page;
                trashTotalPages.value = result.data.pagination.total_pages;
                trashTotal.value = result.data.pagination.total;
                return true;
            } catch (error) {
                if (request !== requestSequence || error?.code === 'SESSION_INVALIDATED') return false;
                console.error('加载回收站失败:', error);
                trashError.value = error.message || '回收站加载失败，请重试。';
                return false;
            } finally {
                if (request === requestSequence) trashLoading.value = false;
            }
        }

        async function goToTrashPage(page) {
            if (trashLoading.value || page < 1 || page > trashTotalPages.value) return;
            await loadTrash(page);
        }

        function closeTrash() {
            if (trashLoading.value || trashEmptying.value || trashActionIds.value.length > 0) return;
            requestSequence += 1;
            showTrash.value = false;
            trashLoading.value = false;
            trashError.value = '';
        }

        async function restoreTrashItem(id) {
            if (trashActionIds.value.includes(id)) return;
            setItemBusy(id, true);
            try {
                await api.post(`/trash/${id}/restore`);
                const refreshed = await loadTrash(pageAfterRemoval());
                const entriesRefreshed = await loadEntries();
                showToast(
                    refreshed && entriesRefreshed !== false
                        ? '条目已恢复'
                        : '条目已恢复，但列表刷新不完整，请稍后重试。',
                    refreshed && entriesRefreshed !== false ? 'success' : 'warning'
                );
            } catch (error) {
                if (error?.code === 'SESSION_INVALIDATED') return;
                showToast(error.message || '恢复失败', 'error');
            } finally {
                setItemBusy(id, false);
            }
        }

        function deleteTrashItem(id) {
            showConfirmDialog('彻底删除', '此操作不可恢复，确认删除？', async () => {
                setItemBusy(id, true);
                try {
                    await api.delete(`/trash/${id}`);
                    const refreshed = await loadTrash(pageAfterRemoval());
                    showToast(
                        refreshed ? '已彻底删除' : '已彻底删除，但列表刷新不完整，请稍后重试。',
                        refreshed ? 'success' : 'warning'
                    );
                } catch (error) {
                    throw new Error(error.message || '删除失败');
                } finally {
                    setItemBusy(id, false);
                }
            });
        }

        function emptyTrashConfirm() {
            showConfirmDialog('清空回收站', '此操作不可恢复，确认清空？', async () => {
                trashEmptying.value = true;
                try {
                    await api.post('/trash/empty');
                    const refreshed = await loadTrash(1);
                    showToast(
                        refreshed ? '回收站已清空' : '回收站已清空，但列表刷新不完整，请稍后重试。',
                        refreshed ? 'success' : 'warning'
                    );
                } catch (error) {
                    throw new Error(error.message || '清空失败');
                } finally {
                    trashEmptying.value = false;
                }
            });
        }

        return {
            loadTrash,
            closeTrash,
            retryTrash: () => loadTrash(trashPage.value),
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
