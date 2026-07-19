/**
 * 根应用键盘交互。
 *
 * Escape 只处理当前最上层且可安全关闭的界面；写入、确认和敏感请求期间
 * 保持原状态，避免快捷键造成半完成操作。
 */
(function () {
    function createAppKeyboardController({ state, ui, actions, backupBusy }) {
        function isBusy(...refs) {
            return refs.some(item => Boolean(item?.value));
        }

        function handleDocumentKeydown(event) {
            if (event?.key !== 'Escape' || event.defaultPrevented || state.locked.value) return false;
            const close = action => {
                if (typeof action !== 'function') return false;
                const result = action();
                if (result !== false) {
                    event.preventDefault();
                    event.stopPropagation();
                    return true;
                }
                return false;
            };

            if (state.showConfirm.value) {
                return state.confirmSubmitting.value ? false : close(ui.cancelConfirmAction);
            }
            if (state.showPrompt.value) {
                return state.promptSubmitting.value ? false : close(ui.cancelPrompt);
            }
            if (state.showDesktopCloseConfirm.value) {
                return state.desktopCloseSubmitting.value ? false : close(actions.desktop.cancelDesktopClose);
            }

            if (state.showSyncConflicts.value) {
                return isBusy(state.syncBusy, state.syncConflictsLoading) ? false : close(actions.sync.closeSyncConflicts);
            }
            if (state.showSyncHistory.value) {
                return isBusy(state.syncBusy, state.syncHistoryLoading) ? false : close(actions.sync.closeSyncHistory);
            }
            if (state.showSyncRecovery.value) {
                return state.syncRecoveryBusy.value ? false : close(actions.sync.closeSyncRecovery);
            }
            if (state.showSyncDeleteRemote.value) {
                return state.syncBusy.value ? false : close(actions.sync.closeDeleteRemoteSync);
            }
            if (state.showSyncConfig.value) {
                return state.syncBusy.value ? false : close(actions.sync.closeSyncConfig);
            }
            if (state.showSyncSetup.value) {
                return isBusy(state.syncBusy, state.syncSetupTesting, state.syncPairingReading)
                    ? false
                    : close(actions.sync.closeSyncSetup);
            }

            // 这些界面可能从设置页打开，Escape 应先关闭最上层弹窗。
            if (state.showChangePassword.value) {
                return state.passwordChanging.value ? false : close(actions.settings.closeChangePassword);
            }
            if (state.showImportConflicts.value) {
                return state.transferBusy.value ? false : close(actions.transfer.closeImportConflicts);
            }
            if (state.showImportPreview.value) {
                return state.transferBusy.value ? false : close(actions.transfer.closeImportPreview);
            }
            if (state.showImportReport.value) {
                return close(() => { state.showImportReport.value = false; });
            }
            if (state.restoreWizard?.visible) {
                return state.restoreWizard.restoring ? false : close(actions.backup.closeRestoreWizard);
            }
            if (state.showBackupCenter.value) {
                return backupBusy.value ? false : close(actions.backup.closeBackupCenter);
            }
            if (state.showDesktopStatus.value) {
                return close(actions.desktop.closeDesktopStatus);
            }

            if (state.aiAssistantScopePicker?.open) {
                return close(actions.ai.closeAssistantScopePicker);
            }

            if (state.showAiParse.value) {
                return isBusy(state.aiParsing, state.aiOrganizing) ? false : close(actions.ai.closeAiParse);
            }
            if (state.showSettings.value) {
                return isBusy(
                    state.settingsSaving,
                    state.transferBusy,
                    state.aiSettingsSaving,
                    state.syncBusy,
                    state.syncConflictsLoading,
                    state.syncRecoveryBusy
                ) ? false : close(actions.settings.closeSettings);
            }
            if (state.aiAssistantInspector?.open) {
                return close(actions.ai.resetAssistantInspector);
            }
            if (state.showAiAssistant.value) {
                return state.aiAssistantBusy.value ? false : close(actions.ai.closeAiAssistant);
            }

            if (state.showEntryDetail.value) return close(actions.entry.closeEntryDetail);
            if (state.showCreateModal.value || state.showEditModal.value) {
                return isBusy(state.entrySaving, state.entryEditLoading) ? false : close(actions.entry.closeEntryModal);
            }
            if (state.showGroupEntryPicker.value) {
                return isBusy(state.groupPickerLoading, state.groupPickerSaving)
                    ? false
                    : close(actions.group.closeGroupEntryPicker);
            }
            if (state.showGroupModal.value) {
                return state.groupSaving.value ? false : close(actions.group.closeGroupModal);
            }
            if (state.showTagEditorModal.value) {
                return state.tagSaving.value ? false : close(actions.tag.closeTagEditorModal);
            }
            if (state.showTagManager.value) {
                return isBusy(state.tagSaving, state.tagMerging) ? false : close(actions.tag.closeTagManager);
            }
            if (state.showTagBrowser.value) return close(actions.tag.closeTagBrowser);
            if (state.showTrash.value) {
                return isBusy(state.trashLoading, state.trashEmptying) || state.trashActionIds.value.length > 0
                    ? false
                    : close(actions.trash.closeTrash);
            }
            if (state.showTools.value) return close(actions.maintenance.closeToolsModal);
            if (state.showOnboarding.value) return close(actions.onboarding.skipOnboarding);
            if (state.showAdvancedFilters.value) {
                state.showAdvancedFilters.value = false;
                event.preventDefault();
                event.stopPropagation();
                return true;
            }
            if (state.showTagDropdown.value || state.copyMenuEntryId.value) {
                state.showTagDropdown.value = false;
                state.copyMenuEntryId.value = null;
                event.preventDefault();
                event.stopPropagation();
                return true;
            }
            return false;
        }

        return { handleDocumentKeydown };
    }

    window.SecretBaseAppKeyboardController = { createAppKeyboardController };
})();
