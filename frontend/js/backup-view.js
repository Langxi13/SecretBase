/**
 * Backup center computed state.
 */
(function () {
    function createBackupView(options) {
        const {
            computed,
            backups,
            backupPages,
            backupPageSize,
            settingsForm,
            backupListLoading,
            creatingBackup,
            restoringBackupFilename,
            downloadingBackupFilename
        } = options;

        const backupBusy = computed(() => (
            backupListLoading.value ||
            creatingBackup.value ||
            Boolean(restoringBackupFilename.value) ||
            Boolean(downloadingBackupFilename.value)
        ));

        const sortedBackups = computed(() => {
            return [...backups.value].sort((a, b) => new Date(b.modified_at || 0) - new Date(a.modified_at || 0));
        });

        const backupSummary = computed(() => {
            const manualCount = backups.value.filter(backup => backup.type === 'manual').length;
            const autoCount = backups.value.filter(backup => backup.type === 'auto').length;
            const recent = sortedBackups.value[0] || null;
            return {
                manualCount,
                autoCount,
                retention: settingsForm.autoBackupRetention,
                recent
            };
        });

        const backupGroups = computed(() => {
            const definitions = [
                {
                    type: 'manual',
                    title: '手动备份',
                    hint: '由你主动创建，不会被自动备份轮转清理。'
                },
                {
                    type: 'auto',
                    title: '自动备份',
                    hint: '写入或恢复前自动创建，会按保留数量清理旧文件。'
                },
                {
                    type: 'legacy',
                    title: '旧版备份',
                    hint: '旧目录中的兼容备份。刷新后通常会迁移到自动备份。'
                }
            ];
            return definitions
                .map(group => ({
                    ...group,
                    items: backups.value.filter(backup => (backup.type || 'legacy') === group.type)
                }))
                .filter(group => group.type !== 'legacy' || group.items.length > 0)
                .map(group => {
                    const totalPages = Math.max(1, Math.ceil(group.items.length / backupPageSize.value));
                    const current = Math.min(backupPages[group.type] || 1, totalPages);
                    const start = (current - 1) * backupPageSize.value;
                    const pagedItems = group.items.slice(start, start + backupPageSize.value);
                    return {
                        ...group,
                        page: current,
                        totalPages,
                        pagedItems,
                        emptySlots: Math.max(0, backupPageSize.value - pagedItems.length)
                    };
                });
        });

        return {
            backupBusy,
            sortedBackups,
            backupSummary,
            backupGroups
        };
    }

    window.SecretBaseBackupView = {
        createBackupView
    };
})();
