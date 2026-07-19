/**
 * 根应用中不属于某个业务领域的轻量交互。
 */
(function () {
    function createAppUiController({ state, store, viewHelpers }) {
        let confirmCallback = null;
        let confirmGeneration = 0;
        let promptResolver = null;

        function resetSearchScopes() {
            state.selectedSearchScopes.value = [...state.defaultSearchScopes];
            store.setFilter('searchScopes', state.selectedSearchScopes.value);
        }

        function resetEntryForm() {
            state.entryForm.id = null;
            state.entryForm.title = '';
            state.entryForm.url = '';
            state.entryForm.starred = false;
            state.entryForm.tags = [];
            state.entryForm.groups = [];
            state.entryForm.fields = [];
            state.entryForm.remarks = '';
            state.newTag.value = '';
            state.newGroup.value = '';
            state.newGroupDescription.value = '';
            state.selectedTemplate.value = '';
        }

        function showConfirmDialog(title, message, callback) {
            confirmGeneration += 1;
            state.confirmTitle.value = title;
            state.confirmMessage.value = message;
            state.confirmSubmitting.value = false;
            if (state.confirmError) state.confirmError.value = '';
            confirmCallback = callback;
            state.showConfirm.value = true;
        }

        async function confirmAction() {
            if (state.confirmSubmitting.value) return;
            const generation = confirmGeneration;
            const callback = confirmCallback;
            state.confirmSubmitting.value = true;
            if (state.confirmError) state.confirmError.value = '';
            let completed = false;
            try {
                if (callback) {
                    completed = (await callback()) !== false;
                } else {
                    completed = true;
                }
                if (generation === confirmGeneration && !completed && state.confirmError && !state.confirmError.value) {
                    state.confirmError.value = '操作未完成，请检查提示后重试。';
                }
            } catch (error) {
                if (generation === confirmGeneration && state.confirmError) {
                    state.confirmError.value = error?.message || '操作未完成，请重试';
                }
            } finally {
                if (generation !== confirmGeneration || callback !== confirmCallback) return;
                state.confirmSubmitting.value = false;
                if (completed) {
                    state.showConfirm.value = false;
                    confirmCallback = null;
                }
            }
        }

        function cancelConfirmAction() {
            if (state.confirmSubmitting.value) return;
            confirmGeneration += 1;
            state.showConfirm.value = false;
            if (state.confirmError) state.confirmError.value = '';
            confirmCallback = null;
        }

        function resolvePrompt(value) {
            const resolver = promptResolver;
            promptResolver = null;
            if (state.showPrompt) state.showPrompt.value = false;
            if (state.promptSubmitting) state.promptSubmitting.value = false;
            if (state.promptError) state.promptError.value = '';
            if (state.promptValue) state.promptValue.value = '';
            if (resolver) resolver(value);
        }

        function showPromptDialog(options = {}) {
            if (promptResolver) promptResolver(null);
            if (!state.showPrompt || !state.promptTitle) return Promise.resolve(null);
            state.promptTitle.value = String(options.title || '请输入');
            state.promptMessage.value = String(options.message || '');
            state.promptValue.value = String(options.value || '');
            state.promptPlaceholder.value = String(options.placeholder || '');
            state.promptType.value = options.type === 'password' ? 'password' : 'text';
            state.promptConfirmLabel.value = String(options.confirmLabel || '确定');
            state.promptMaxLength.value = Math.min(10000, Math.max(1, Number(options.maxLength) || 200));
            state.promptRequired.value = options.required !== false;
            state.promptObscured.value = true;
            state.promptError.value = '';
            state.promptSubmitting.value = false;
            state.showPrompt.value = true;
            return new Promise(resolve => {
                promptResolver = resolve;
            });
        }

        function submitPrompt() {
            if (state.promptSubmitting.value) return;
            const value = String(state.promptValue.value || '');
            if (state.promptRequired.value && !value.trim()) {
                state.promptError.value = '请输入内容';
                return;
            }
            state.promptSubmitting.value = true;
            resolvePrompt(value);
        }

        function cancelPrompt() {
            if (state.promptSubmitting.value) return;
            resolvePrompt(null);
        }

        function togglePromptVisibility() {
            state.promptObscured.value = !state.promptObscured.value;
        }

        function clearPendingDialogs() {
            confirmGeneration += 1;
            confirmCallback = null;
            state.showConfirm.value = false;
            state.confirmSubmitting.value = false;
            if (state.confirmError) state.confirmError.value = '';
            resetEntryForm();
            resolvePrompt(null);
        }

        return {
            resetSearchScopes,
            resetEntryForm,
            showConfirmDialog,
            confirmAction,
            cancelConfirmAction,
            showPromptDialog,
            submitPrompt,
            cancelPrompt,
            togglePromptVisibility,
            clearPendingDialogs,
            getEntryIconText: viewHelpers.getEntryIconText,
            getTagColor: viewHelpers.getTagColor,
            groupCardStyle: viewHelpers.groupCardStyle,
            entryCardStyle: viewHelpers.entryCardStyle,
            visibleEntryGroups: viewHelpers.visibleEntryGroups,
            remainingEntryGroupsCount: viewHelpers.remainingEntryGroupsCount,
            groupChipStyle: viewHelpers.groupChipStyle,
            formatDate: viewHelpers.formatDate,
            formatBytes: viewHelpers.formatBytes,
            aiTagActionLabel: viewHelpers.aiTagActionLabel,
            aiTagActionTitle: viewHelpers.aiTagActionTitle,
            aiActionTypeLabel: viewHelpers.aiActionTypeLabel,
            aiActionEntryLabel: viewHelpers.aiActionEntryLabel,
            aiActionTitle: viewHelpers.aiActionTitle
        };
    }

    window.SecretBaseAppUiController = {
        createAppUiController
    };
})();
