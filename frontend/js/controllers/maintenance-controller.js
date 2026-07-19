/**
 * 工具中心：健康报告、维护报告、安全报告与报告项定位。
 */
(function () {
    function createMaintenanceController(options) {
        const {
            api,
            store,
            showToast,
            showConfirmDialog,
            showPromptDialog = async () => null,
            friendlyApiMessage,
            showTools,
            healthReport,
            maintenanceReport,
            securityReport,
            searchQuery,
            filter,
            activeTagName,
            activeGroupName,
            listContextNotice,
            advancedFilters,
            showAdvancedFilters,
            resetAdvancedFilterForm,
            clearAdvancedFilters,
            applyAdvancedFilters,
            loadEntries,
            loadTags,
            loadAllData
        } = options;
        let reportRequestEpoch = 0;

        function isCurrentReportRequest(epoch) {
            return epoch === reportRequestEpoch;
        }

        function reportItemIds(items = []) {
            return Array.from(new Set(items.map(item => item.id).filter(Boolean)));
        }

        async function focusReportItems(items, label) {
            const ids = reportItemIds(items);
            if (ids.length === 0) {
                showToast('没有可定位的条目', 'warning');
                return;
            }
            store.clearFilters();
            resetAdvancedFilterForm();
            searchQuery.value = '';
            filter.value = 'all';
            activeTagName.value = '';
            activeGroupName.value = '';
            listContextNotice.value = `工具定位：${label || '条目'}（${ids.length} 条）`;
            store.setFilter('entryIds', ids);
            const loaded = await loadEntries(1);
            if (!loaded) {
                showToast(`定位${label || '条目'}失败，请重试加载`, 'error');
                return false;
            }
            showTools.value = false;
            showToast(`已定位 ${ids.length} 条${label || '条目'}`, 'success');
            return true;
        }

        async function focusReportGroups(groups, label) {
            await focusReportItems(groups.flatMap(group => group), label);
        }

        async function focusUntaggedItems() {
            showTools.value = false;
            await clearAdvancedFilters();
            advancedFilters.untagged = true;
            showAdvancedFilters.value = true;
            listContextNotice.value = '维护工具：无标签条目';
            await applyAdvancedFilters();
        }

        async function addTagToUntaggedItems() {
            const items = maintenanceReport.value?.untagged_items || [];
            const ids = reportItemIds(items);
            if (ids.length === 0) return;
            const tagName = await showPromptDialog({
                title: '批量添加标签',
                message: `将给 ${ids.length} 个无标签条目添加同一个标签。`,
                value: '待整理',
                placeholder: '标签名称',
                confirmLabel: '添加标签',
                maxLength: 50
            });
            if (!tagName || !tagName.trim()) return;
            try {
                const result = await store.batchUpdateTags(ids, [tagName.trim()], []);
                if (result) {
                    const refreshed = await Promise.allSettled([loadEntries(1), loadTags(), loadMaintenanceReport()]);
                    if (refreshed.some(item => item.status === 'rejected' || item.value === false)) {
                        showToast('标签已添加，但工具报告刷新不完整，请稍后重试。', 'warning');
                    }
                }
            } catch (error) {
                showToast(error.message || '批量添加标签失败，请重试', 'error');
            }
        }

        async function openToolsModal() {
            const epoch = ++reportRequestEpoch;
            showTools.value = true;
            await Promise.all([loadHealthReport(epoch), loadMaintenanceReport(epoch), loadSecurityReport(epoch)]);
        }

        function closeToolsModal() {
            reportRequestEpoch += 1;
            showTools.value = false;
        }

        function disposeMaintenance() {
            closeToolsModal();
        }

        async function loadHealthReport(epoch = reportRequestEpoch) {
            try {
                const result = await api.get('/tools/health-report');
                if (!isCurrentReportRequest(epoch) || !showTools.value) return false;
                healthReport.value = result.data;
                return true;
            } catch (error) {
                if (isCurrentReportRequest(epoch) && showTools.value) showToast(error.message || '健康报告加载失败', 'error');
                return false;
            }
        }

        async function loadMaintenanceReport(epoch = reportRequestEpoch) {
            try {
                const result = await api.get('/tools/maintenance-report');
                if (!isCurrentReportRequest(epoch) || !showTools.value) return false;
                maintenanceReport.value = result.data;
                return true;
            } catch (error) {
                if (isCurrentReportRequest(epoch) && showTools.value) showToast(error.message || '维护报告加载失败', 'error');
                return false;
            }
        }

        async function loadSecurityReport(epoch = reportRequestEpoch) {
            try {
                const result = await api.get('/tools/security-report');
                if (!isCurrentReportRequest(epoch) || !showTools.value) return false;
                securityReport.value = result.data;
                return true;
            } catch (error) {
                if (isCurrentReportRequest(epoch) && showTools.value) showToast(friendlyApiMessage(error, '安全自检加载失败'), 'error');
                return false;
            }
        }

        function deleteSampleEntries() {
            const ids = (maintenanceReport.value?.sample_items || []).map(item => item.id);
            if (ids.length === 0) return;
            showConfirmDialog('删除示例数据', `确认删除 ${ids.length} 条示例数据？`, async () => {
                const result = await store.batchDelete(ids);
                if (!result) return false;
                await loadAllData();
                const refreshed = await loadMaintenanceReport();
                showToast(
                    refreshed ? '示例数据已移至回收站' : '示例数据已移至回收站，但报告刷新不完整，请稍后重试。',
                    refreshed ? 'success' : 'warning'
                );
            });
        }

        return {
            openToolsModal,
            closeToolsModal,
            disposeMaintenance,
            loadHealthReport,
            loadMaintenanceReport,
            loadSecurityReport,
            focusReportItems,
            focusReportGroups,
            focusUntaggedItems,
            addTagToUntaggedItems,
            deleteSampleEntries
        };
    }

    window.SecretBaseMaintenanceController = {
        createMaintenanceController
    };
})();
