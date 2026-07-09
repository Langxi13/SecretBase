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
            showTools.value = false;
            await loadEntries(1);
            showToast(`已定位 ${ids.length} 条${label || '条目'}`, 'success');
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
            const tagName = window.prompt('给无标签条目添加标签', '待整理');
            if (!tagName || !tagName.trim()) return;
            const result = await store.batchUpdateTags(ids, [tagName.trim()], []);
            if (result) {
                await Promise.all([loadEntries(1), loadTags(), loadMaintenanceReport()]);
            }
        }

        async function openToolsModal() {
            showTools.value = true;
            await Promise.all([loadHealthReport(), loadMaintenanceReport(), loadSecurityReport()]);
        }

        async function loadHealthReport() {
            try {
                const result = await api.get('/tools/health-report');
                healthReport.value = result.data;
            } catch (error) {
                showToast(error.message || '健康报告加载失败', 'error');
            }
        }

        async function loadMaintenanceReport() {
            try {
                const result = await api.get('/tools/maintenance-report');
                maintenanceReport.value = result.data;
            } catch (error) {
                showToast(error.message || '维护报告加载失败', 'error');
            }
        }

        async function loadSecurityReport() {
            try {
                const result = await api.get('/tools/security-report');
                securityReport.value = result.data;
            } catch (error) {
                showToast(friendlyApiMessage(error, '安全自检加载失败'), 'error');
            }
        }

        function deleteSampleEntries() {
            const ids = (maintenanceReport.value?.sample_items || []).map(item => item.id);
            if (ids.length === 0) return;
            showConfirmDialog('删除示例数据', `确认删除 ${ids.length} 条示例数据？`, async () => {
                await store.batchDelete(ids);
                await loadAllData();
                await loadMaintenanceReport();
                showToast('示例数据已移至回收站', 'success');
            });
        }

        return {
            openToolsModal,
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
