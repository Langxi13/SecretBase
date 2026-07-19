const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'frontend/js/app-keyboard-controller.js'), 'utf8');
const ref = value => ({ value });
const context = vm.createContext({ console, window: {} });
context.window.window = context.window;
vm.runInContext(source, context, { filename: 'app-keyboard-controller.js' });

function assert(condition, message) {
    if (!condition) throw new Error(message);
}

function createState() {
    const flags = [
        'showConfirm', 'showPrompt', 'showDesktopCloseConfirm', 'showSyncConflicts', 'showSyncHistory',
        'showSyncRecovery', 'showSyncDeleteRemote', 'showSyncConfig', 'showSyncSetup', 'showAiParse',
        'showSettings', 'showAiAssistant', 'showEntryDetail', 'showCreateModal', 'showEditModal',
        'showGroupEntryPicker', 'showGroupModal', 'showTagEditorModal', 'showTagManager', 'showTagBrowser',
        'showTrash', 'showBackupCenter', 'showImportConflicts', 'showImportPreview', 'showImportReport',
        'showTools', 'showChangePassword', 'showDesktopStatus', 'showOnboarding', 'showAdvancedFilters',
        'showTagDropdown'
    ];
    const busy = [
        'confirmSubmitting', 'promptSubmitting', 'desktopCloseSubmitting', 'syncBusy', 'syncConflictsLoading',
        'syncHistoryLoading', 'syncRecoveryBusy', 'syncSetupTesting', 'syncPairingReading', 'syncStatusLoading',
        'aiParsing', 'aiOrganizing', 'aiSettingsSaving', 'aiModelsLoading', 'aiDiagnosticsBusy', 'aiAssistantBusy',
        'settingsSaving', 'transferBusy', 'entrySaving', 'entryEditLoading', 'groupPickerLoading',
        'groupPickerSaving', 'groupSaving', 'tagSaving', 'tagMerging', 'trashLoading', 'trashEmptying',
        'passwordChanging'
    ];
    const state = { locked: ref(false), copyMenuEntryId: ref(null), aiAssistantInspector: { open: false }, aiAssistantScopePicker: { open: false }, restoreWizard: { visible: false, restoring: false }, trashActionIds: ref([]) };
    for (const name of [...flags, ...busy]) state[name] = ref(false);
    return state;
}

function event() {
    return {
        key: 'Escape',
        defaultPrevented: false,
        prevented: false,
        stopped: false,
        preventDefault() { this.defaultPrevented = true; this.prevented = true; },
        stopPropagation() { this.stopped = true; }
    };
}

function actionMap(state) {
    const close = (flag, extra = null) => () => {
        state[flag].value = false;
        if (extra) extra();
    };
    return {
        ai: {
            closeAiParse: close('showAiParse'),
            closeAssistantScopePicker: () => { state.aiAssistantScopePicker.open = false; },
            resetAssistantInspector: () => { state.aiAssistantInspector.open = false; },
            closeAiAssistant: close('showAiAssistant')
        },
        backup: { closeRestoreWizard: () => { state.restoreWizard.visible = false; }, closeBackupCenter: close('showBackupCenter') },
        desktop: { cancelDesktopClose: close('showDesktopCloseConfirm'), closeDesktopStatus: close('showDesktopStatus') },
        entry: { closeEntryDetail: close('showEntryDetail'), closeEntryModal: () => { state.showCreateModal.value = false; state.showEditModal.value = false; } },
        group: { closeGroupEntryPicker: close('showGroupEntryPicker'), closeGroupModal: close('showGroupModal') },
        maintenance: { closeToolsModal: close('showTools') },
        onboarding: { skipOnboarding: close('showOnboarding') },
        settings: { closeSettings: close('showSettings'), closeChangePassword: close('showChangePassword') },
        sync: {
            closeSyncConflicts: close('showSyncConflicts'),
            closeSyncHistory: close('showSyncHistory'),
            closeSyncRecovery: close('showSyncRecovery'),
            closeDeleteRemoteSync: close('showSyncDeleteRemote'),
            closeSyncConfig: close('showSyncConfig'),
            closeSyncSetup: close('showSyncSetup')
        },
        tag: { closeTagEditorModal: close('showTagEditorModal'), closeTagManager: close('showTagManager'), closeTagBrowser: close('showTagBrowser') },
        transfer: { closeImportConflicts: close('showImportConflicts'), closeImportPreview: close('showImportPreview') },
        trash: { closeTrash: close('showTrash') }
    };
}

const state = createState();
const actions = actionMap(state);
const ui = {
    cancelConfirmAction: () => { state.showConfirm.value = false; },
    cancelPrompt: () => { state.showPrompt.value = false; }
};
const keyboard = context.window.SecretBaseAppKeyboardController.createAppKeyboardController({
    state,
    ui,
    actions,
    backupBusy: ref(false)
});

state.showConfirm.value = true;
let current = event();
assert(keyboard.handleDocumentKeydown(current) === true && !state.showConfirm.value && current.prevented, 'Escape 应关闭确认弹窗');

state.showConfirm.value = true;
state.confirmSubmitting.value = true;
current = event();
assert(keyboard.handleDocumentKeydown(current) === false && state.showConfirm.value, '确认提交期间 Escape 不得关闭确认弹窗');
state.confirmSubmitting.value = false;
state.showConfirm.value = false;

state.showSettings.value = true;
state.showAiAssistant.value = true;
current = event();
assert(keyboard.handleDocumentKeydown(current) === true && !state.showSettings.value && state.showAiAssistant.value, 'Escape 应先关闭最上层设置');
current = event();
assert(keyboard.handleDocumentKeydown(current) === true && !state.showAiAssistant.value, '再次 Escape 应关闭底层 AI 面板');

state.showSettings.value = true;
state.showChangePassword.value = true;
current = event();
assert(keyboard.handleDocumentKeydown(current) === true && !state.showChangePassword.value && state.showSettings.value, 'Escape 应先关闭设置中的修改密码弹窗');
state.showSettings.value = false;

state.showSettings.value = true;
state.showBackupCenter.value = true;
current = event();
assert(keyboard.handleDocumentKeydown(current) === true && !state.showBackupCenter.value && state.showSettings.value, 'Escape 应先关闭设置中的备份中心');
state.showSettings.value = false;

state.showSettings.value = true;
state.showImportPreview.value = true;
current = event();
assert(keyboard.handleDocumentKeydown(current) === true && !state.showImportPreview.value && state.showSettings.value, 'Escape 应先关闭设置中的导入预览');
state.showSettings.value = false;

state.showSettings.value = true;
state.showDesktopStatus.value = true;
current = event();
assert(keyboard.handleDocumentKeydown(current) === true && !state.showDesktopStatus.value && state.showSettings.value, 'Escape 应先关闭顶层桌面状态弹窗');
state.showSettings.value = false;

state.showSettings.value = true;
state.aiModelsLoading.value = true;
current = event();
assert(keyboard.handleDocumentKeydown(current) === true && !state.showSettings.value, '只读模型加载期间 Escape 仍应允许关闭设置');
state.aiModelsLoading.value = false;

state.showGroupEntryPicker.value = true;
state.groupPickerLoading.value = true;
current = event();
assert(keyboard.handleDocumentKeydown(current) === false && state.showGroupEntryPicker.value, '密码组条目读取期间不得关闭弹窗');
state.groupPickerLoading.value = false;
current = event();
assert(keyboard.handleDocumentKeydown(current) === true && !state.showGroupEntryPicker.value, '密码组条目读取完成后可用 Escape 关闭');

state.showCreateModal.value = true;
state.entrySaving.value = true;
current = event();
assert(keyboard.handleDocumentKeydown(current) === false && state.showCreateModal.value, '条目写入期间不得关闭编辑器');
state.entrySaving.value = false;
state.showCreateModal.value = false;

state.showAdvancedFilters.value = true;
current = event();
assert(keyboard.handleDocumentKeydown(current) === true && !state.showAdvancedFilters.value, 'Escape 应收起高级筛选面板');

console.log('PASS frontend keyboard interaction');
