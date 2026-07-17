/**
 * WebDAV 端到端加密同步的独立响应式状态。
 */
(function () {
    function createSyncState({ ref, reactive }) {
        const syncStatus = reactive({
            configured: false,
            pending_join: false,
            phase: 'disabled',
            message: '尚未配置 WebDAV 同步',
            last_error: '',
            pending_conflicts: 0,
            auto_sync: true,
            host: '',
            base_url: '',
            username_mask: '',
            device_name: '',
            vault_id: '',
            last_synced_at: '',
            generation: 0
        });
        const syncStatusLoading = ref(false);
        const syncBusy = ref(false);
        const syncError = ref('');
        const showSyncSetup = ref(false);
        const syncSetupMode = ref('create');
        const syncSetupTesting = ref(false);
        const syncSetupMessage = ref('');
        const syncSetupForm = reactive({
            baseUrl: '',
            username: '',
            password: '',
            deviceName: '',
            autoSync: true,
            recoveryCode: '',
            mergeExisting: false
        });
        const showSyncConfig = ref(false);
        const syncConfigForm = reactive({
            baseUrl: '',
            username: '',
            password: '',
            deviceName: '',
            autoSync: true
        });
        const showSyncConflicts = ref(false);
        const syncConflictToken = ref('');
        const syncConflicts = ref([]);
        const syncConflictResolutions = reactive({});
        const showSyncHistory = ref(false);
        const syncHistory = ref([]);
        const syncHistoryLoading = ref(false);
        const syncCurrentSnapshotId = ref('');
        const showSyncRecovery = ref(false);
        const syncRecoveryMode = ref('reveal');
        const syncMasterPassword = ref('');
        const syncRecoveryMaterial = ref(null);
        const syncRecoveryBusy = ref(false);
        const showSyncDeleteRemote = ref(false);
        const syncDeleteForm = reactive({ password: '', confirmation: '' });

        return {
            syncStatus,
            syncStatusLoading,
            syncBusy,
            syncError,
            showSyncSetup,
            syncSetupMode,
            syncSetupTesting,
            syncSetupMessage,
            syncSetupForm,
            showSyncConfig,
            syncConfigForm,
            showSyncConflicts,
            syncConflictToken,
            syncConflicts,
            syncConflictResolutions,
            showSyncHistory,
            syncHistory,
            syncHistoryLoading,
            syncCurrentSnapshotId,
            showSyncRecovery,
            syncRecoveryMode,
            syncMasterPassword,
            syncRecoveryMaterial,
            syncRecoveryBusy,
            showSyncDeleteRemote,
            syncDeleteForm
        };
    }

    window.SecretBaseSyncState = { createSyncState };
})();
