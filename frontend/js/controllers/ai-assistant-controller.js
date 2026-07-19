/**
 * 对话式 AI 管家：发送清单、历史、计划审核与撤销。
 */
(function () {
    function createAiAssistantController(options) {
        const {
            nextTick,
            api,
            store,
            showToast,
            showConfirmDialog = (_title, _message, callback) => callback?.(),
            copyToClipboard,
            showAiAssistant,
            showAiParse,
            aiStatus,
            aiAssistantMode,
            aiAssistantScope,
            aiAssistantInput,
            aiAssistantBusy,
            aiAssistantStage,
            aiAssistantError,
            aiAssistantConversations,
            aiAssistantConversationId,
            aiAssistantMessages,
            aiAssistantPrepared,
            aiAssistantPlan,
            aiAssistantLastResult,
            aiAssistantHistoryOpen,
            selectedEntry,
            currentPage,
            assistantFiltersForScope,
            assistantScopeCount,
            refreshAssistantScopeCatalog,
            closeAssistantScopePicker,
            resetAssistantScopeForConversation,
            loadEntries,
            loadTags,
            loadGroups,
            openSettings,
            selectSettingsTab,
            openEntryDetail = () => false,
            normalizeAssistantActionTargets,
            resetAssistantInspector,
            assistantPlanHasSelectedConflicts
        } = options;
        let pendingMessageId = '';
        let assistantEpoch = 0;
        const requestLifecycle = window.SecretBaseAiAssistantRequest.createAiAssistantRequestLifecycle();
        const planHelpers = window.SecretBaseAiAssistantPlanHelpers;
        const isCurrentAssistantSession = epoch => epoch === assistantEpoch;
        function invalidateAssistantRequests() {
            requestLifecycle.abort();
            assistantEpoch += 1;
            clearPendingUserMessage();
            return assistantEpoch;
        }
        function beginAssistantRequest() {
            return requestLifecycle.begin();
        }
        const finishAssistantRequest = controller => requestLifecycle.finish(controller);
        function normalizePlan(data, requestContext = {}) {
            return planHelpers.normalizeAssistantPlan(
                data, requestContext, aiAssistantScope.value, normalizeAssistantActionTargets
            );
        }
        function showPendingUserMessage(content) {
            clearPendingUserMessage();
            pendingMessageId = `pending-${Date.now()}`;
            aiAssistantMessages.value = [...aiAssistantMessages.value, {
                id: pendingMessageId,
                role: 'user',
                content,
                pending: true
            }];
            scrollAssistantToBottom();
        }
        function clearPendingUserMessage() {
            if (!pendingMessageId) return;
            aiAssistantMessages.value = aiAssistantMessages.value.filter(message => message.id !== pendingMessageId);
            pendingMessageId = '';
        }
        const resetPendingMessage = () => { clearPendingUserMessage(); pendingMessageId = ''; };
        const history = window.SecretBaseAiAssistantHistoryController.createAiAssistantHistoryController({
            nextTick,
            api,
            showToast,
            showConfirmDialog,
            aiAssistantHistoryOpen,
            aiAssistantConversations,
            aiAssistantConversationId,
            aiAssistantMessages,
            aiAssistantPrepared,
            aiAssistantPlan,
            aiAssistantLastResult,
            resetAssistantScopeForConversation,
            refreshAssistantScopeCatalog,
            closeAssistantScopePicker,
            resetAssistantInspector,
            isCurrentAssistantSession,
            getAssistantEpoch: () => assistantEpoch,
            resetPendingMessage
        });
        const {
            scrollAssistantToBottom,
            loadConversations,
            createConversation,
            loadConversation,
            ensureConversation,
            deleteAssistantConversation,
            clearAssistantHistory,
            refreshAssistantContext
        } = history;
        const localActions = window.SecretBaseAiAssistantLocalActions.createAiAssistantLocalActions({
            aiAssistantLastResult,
            copyToClipboard,
            showToast,
            getAssistantEpoch: () => assistantEpoch,
            isCurrentAssistantSession
        });
        const { generateAssistantSecret, copyAssistantSecret } = localActions;
        async function openAiAssistant() {
            const epoch = ++assistantEpoch;
            showAiAssistant.value = true;
            aiAssistantError.value = '';
            aiAssistantPrepared.value = null;
            try {
                const status = await api.get('/ai/status');
                if (!isCurrentAssistantSession(epoch)) return;
                aiStatus.value = status.data;
                await ensureConversation(epoch);
                if (!isCurrentAssistantSession(epoch)) return;
                await refreshAssistantScopeCatalog({ silent: true });
                if (!isCurrentAssistantSession(epoch)) return;
                scrollAssistantToBottom();
            } catch (error) {
                if (!isCurrentAssistantSession(epoch)) return;
                aiAssistantError.value = error.message || '无法加载 AI 管家';
            }
        }
        function closeAiAssistant() {
            if (aiAssistantBusy.value) {
                showToast('AI 请求正在处理中，请稍候', 'warning');
                return;
            }
            invalidateAssistantRequests();
            showAiAssistant.value = false;
            aiAssistantPrepared.value = null;
            closeAssistantScopePicker();
            clearPendingUserMessage();
            aiAssistantPlan.value = null;
            aiAssistantLastResult.value = null;
            resetAssistantInspector();
            aiAssistantStage.value = '';
        }
        function disposeAiAssistant() {
            invalidateAssistantRequests();
            showAiAssistant.value = false;
            aiAssistantBusy.value = false;
            aiAssistantStage.value = '';
            aiAssistantError.value = '';
            aiAssistantPrepared.value = null;
            aiAssistantPlan.value = null;
            aiAssistantLastResult.value = null;
            aiAssistantConversationId.value = '';
            aiAssistantMessages.value = [];
            closeAssistantScopePicker();
            resetAssistantScopeForConversation();
            resetAssistantInspector();
        }
        async function requestSendPreview(draft, epoch = assistantEpoch, signal = null) {
            const result = await api.post('/ai/assistant/turns/preview', {
                mode: draft.mode,
                scope: draft.scope,
                filters: draft.filters
            }, { timeoutMs: 20000, signal });
            if (!isCurrentAssistantSession(epoch)) return null;
            const data = result.data || {};
            return {
                ...draft,
                previewToken: data.preview_token,
                manifest: data.manifest || {}
            };
        }
        function applyAssistantTurnResult(data, requestContext = {}, epoch = assistantEpoch) {
            if (!isCurrentAssistantSession(epoch)) return;
            clearPendingUserMessage();
            aiAssistantConversationId.value = data.conversation_id || aiAssistantConversationId.value;
            aiAssistantPrepared.value = null;
            aiAssistantInput.value = '';
            aiAssistantMode.value = 'assistant';
            const warnings = Array.isArray(data.warnings) ? data.warnings.filter(Boolean) : [];
            if (data.plan_token) {
                aiAssistantPlan.value = normalizePlan({ ...data, warnings }, requestContext);
            } else {
                aiAssistantPlan.value = null;
            }
            resetAssistantInspector();
            aiAssistantLastResult.value = data.navigation
                ? { navigation: data.navigation, warnings, privacyNote: data.privacy_note || '' }
                : (data.message || warnings.length
                    ? {
                        message: data.message || 'AI 回复已保留，但没有生成可执行计划。',
                        warnings,
                        privacyNote: data.privacy_note || ''
                    }
                    : null);
            refreshAssistantContext(aiAssistantConversationId.value, epoch);
        }
        async function restorePreparedReview(draft, epoch = assistantEpoch) {
            if (!isCurrentAssistantSession(epoch)) return;
            aiAssistantStage.value = '正在恢复发送确认';
            try {
                const prepared = await requestSendPreview(draft, epoch);
                if (isCurrentAssistantSession(epoch)) aiAssistantPrepared.value = prepared;
            } catch (_error) {
                if (isCurrentAssistantSession(epoch)) aiAssistantPrepared.value = null;
            }
        }
        async function refreshAssistantAfterMutation(epoch) {
            const results = await Promise.allSettled([
                loadEntries(currentPage.value),
                loadTags(),
                loadGroups(),
                loadConversation(aiAssistantConversationId.value, true, epoch),
                loadConversations(epoch),
                refreshAssistantScopeCatalog({ silent: true })
            ]);
            if (!isCurrentAssistantSession(epoch)) return null;
            return results.every(result => (
                result.status === 'fulfilled' && result.value !== false
            ));
        }
        function mutationRefreshMessage(successMessage, refreshed) {
            return refreshed === false ? `${successMessage}，但界面刷新不完整，请稍后点击重试。` : successMessage;
        }
        async function submitPreparedTurn() {
            const prepared = aiAssistantPrepared.value;
            if (!prepared?.previewToken || aiAssistantBusy.value) return;
            const epoch = assistantEpoch;
            const requestController = beginAssistantRequest();
            const draft = {
                originalMessage: prepared.originalMessage,
                mode: prepared.mode,
                scope: prepared.scope,
                filters: prepared.filters
            };
            aiAssistantBusy.value = true;
            aiAssistantStage.value = '正在提交已确认的发送内容';
            aiAssistantError.value = '';
            aiAssistantPrepared.value = null;
            showPendingUserMessage(prepared.originalMessage);
            try {
                const preparedResult = await api.post('/ai/assistant/turns/prepare', {
                    preview_token: prepared.previewToken,
                    conversation_id: aiAssistantConversationId.value || null,
                    message: prepared.originalMessage
                }, { timeoutMs: 20000, signal: requestController?.signal || null });
                if (!isCurrentAssistantSession(epoch)) return;
                const turn = preparedResult.data || {};
                aiAssistantConversationId.value = turn.conversation_id || aiAssistantConversationId.value;
                if (turn.local_result) {
                    clearPendingUserMessage();
                    aiAssistantPrepared.value = null;
                    aiAssistantInput.value = '';
                    aiAssistantMode.value = 'assistant';
                    aiAssistantLastResult.value = {
                        navigation: turn.local_result.navigation || null,
                        localAction: turn.local_result.local_action || null,
                        message: turn.local_result.message || '',
                        privacyNote: turn.local_result.privacy_note || ''
                    };
                    refreshAssistantContext(aiAssistantConversationId.value);
                    return;
                }
                if (!turn.turn_token) throw new Error('AI 请求令牌生成失败');
                aiAssistantStage.value = 'AI 正在分析并校验计划';
                const result = await api.post('/ai/assistant/turns/submit', {
                    turn_token: turn.turn_token,
                    acknowledge_risk: true
                }, { timeoutMs: 150000, signal: requestController?.signal || null });
                if (!isCurrentAssistantSession(epoch)) return;
                applyAssistantTurnResult(result.data || {}, prepared, epoch);
            } catch (error) {
                if (!isCurrentAssistantSession(epoch)) return;
                if (error?.code === 'REQUEST_CANCELLED') {
                    clearPendingUserMessage();
                    aiAssistantError.value = '已取消本次 AI 请求。';
                    return;
                }
                clearPendingUserMessage();
                aiAssistantError.value = error.message || 'AI 请求失败';
                await restorePreparedReview(draft, epoch);
            } finally {
                finishAssistantRequest(requestController);
                if (isCurrentAssistantSession(epoch)) {
                    aiAssistantBusy.value = false;
                    aiAssistantStage.value = '';
                }
            }
        }
        async function sendAssistantMessage() {
            const message = aiAssistantInput.value.trim();
            if (!message || aiAssistantBusy.value || aiAssistantPrepared.value) return;
            if (planHelpers.isAssistantConfirmation(message)) {
                aiAssistantInput.value = '';
                if (aiAssistantPlan.value) {
                    await applyAssistantPlan();
                } else {
                    aiAssistantError.value = '当前没有可执行计划，请先让 AI 生成建议，再确认应用。';
                }
                return;
            }
            if (!aiStatus.value?.configured) {
                aiAssistantError.value = '请先配置 AI 服务。';
                return;
            }
            if (aiAssistantScope.value === 'selection' && assistantScopeCount('selection') === 0) {
                aiAssistantError.value = '自定义选择范围下，请先选择至少一个条目。';
                return;
            }
            const epoch = assistantEpoch;
            const requestController = beginAssistantRequest();
            aiAssistantBusy.value = true;
            aiAssistantStage.value = '正在核对发送范围';
            aiAssistantError.value = '';
            aiAssistantPlan.value = null;
            aiAssistantLastResult.value = null;
            resetAssistantInspector();
            const draft = {
                originalMessage: message,
                mode: aiAssistantMode.value,
                scope: aiAssistantScope.value,
                filters: assistantFiltersForScope()
            };
            try {
                const prepared = await requestSendPreview(draft, epoch, requestController?.signal || null);
                if (isCurrentAssistantSession(epoch)) aiAssistantPrepared.value = prepared;
            } catch (error) {
                if (isCurrentAssistantSession(epoch)) {
                    aiAssistantError.value = error?.code === 'REQUEST_CANCELLED'
                        ? '已取消本次 AI 请求。'
                        : (error.message || '无法核对 AI 发送范围');
                }
            } finally {
                finishAssistantRequest(requestController);
                if (isCurrentAssistantSession(epoch)) {
                    aiAssistantBusy.value = false;
                    aiAssistantStage.value = '';
                }
            }
        }
        function cancelPreparedTurn() {
            invalidateAssistantRequests();
            aiAssistantPrepared.value = null;
            aiAssistantStage.value = '';
        }
        function cancelAssistantRequest() {
            if (!aiAssistantBusy.value && !requestLifecycle.hasActive()) return false;
            invalidateAssistantRequests();
            aiAssistantBusy.value = false;
            aiAssistantStage.value = '';
            aiAssistantPrepared.value = null;
            aiAssistantError.value = '已取消本次 AI 请求。';
            return true;
        }
        async function applyAssistantPlan() {
            if (aiAssistantBusy.value) return;
            const plan = aiAssistantPlan.value;
            const selectedIds = (plan?.actions || []).filter(action => action.selected).map(action => action.id);
            if (!plan?.plan_token || selectedIds.length === 0) {
                showToast('请选择要应用的 AI 操作', 'warning');
                return;
            }
            if (assistantPlanHasSelectedConflicts(plan)) {
                showToast('当前选中操作存在冲突，请取消冲突项后再应用', 'warning');
                return;
            }
            const epoch = assistantEpoch;
            aiAssistantBusy.value = true;
            aiAssistantStage.value = '正在本地应用已确认的操作';
            aiAssistantError.value = '';
            try {
                const result = await api.post('/ai/assistant/plans/apply', {
                    plan_token: plan.plan_token,
                    selected_ids: selectedIds,
                    expected_revision: plan.source_revision
                });
                if (!isCurrentAssistantSession(epoch)) return;
                aiAssistantLastResult.value = {
                    message: result.message,
                    undoToken: result.data?.undo_token || '',
                    revision: result.data?.revision || 0,
                    emptyGroups: result.data?.empty_groups || []
                };
                aiAssistantPlan.value = null;
                resetAssistantInspector();
                const refreshed = await refreshAssistantAfterMutation(epoch);
                if (!isCurrentAssistantSession(epoch)) return;
                showToast(
                    mutationRefreshMessage(result.message || 'AI 操作已应用', refreshed),
                    refreshed === false ? 'warning' : 'success'
                );
            } catch (error) {
                if (isCurrentAssistantSession(epoch)) {
                    aiAssistantError.value = error.message || '应用 AI 计划失败';
                }
            } finally {
                if (isCurrentAssistantSession(epoch)) {
                    aiAssistantBusy.value = false;
                    aiAssistantStage.value = '';
                }
            }
        }
        async function undoAssistantPlan() {
            if (aiAssistantBusy.value) return;
            const resultState = aiAssistantLastResult.value;
            if (!resultState?.undoToken || !resultState.revision) return;
            const epoch = assistantEpoch;
            aiAssistantBusy.value = true;
            aiAssistantStage.value = '正在恢复 AI 操作前的加密快照';
            try {
                const result = await api.post('/ai/assistant/plans/undo', {
                    undo_token: resultState.undoToken,
                    expected_revision: resultState.revision
                });
                if (!isCurrentAssistantSession(epoch)) return;
                aiAssistantLastResult.value = { message: result.message };
                aiAssistantPlan.value = null;
                resetAssistantInspector();
                const refreshed = await refreshAssistantAfterMutation(epoch);
                if (!isCurrentAssistantSession(epoch)) return;
                showToast(
                    mutationRefreshMessage('已撤销本次 AI 操作', refreshed),
                    refreshed === false ? 'warning' : 'success'
                );
            } catch (error) {
                if (isCurrentAssistantSession(epoch)) {
                    aiAssistantError.value = error.message || '撤销 AI 操作失败';
                }
            } finally {
                if (isCurrentAssistantSession(epoch)) {
                    aiAssistantBusy.value = false;
                    aiAssistantStage.value = '';
                }
            }
        }
        function deleteAssistantEmptyGroup(groupName) {
            showConfirmDialog('删除空密码组', `确认删除已经为空的密码组「${groupName}」？`, async () => {
                const epoch = assistantEpoch;
                try {
                    const result = await api.delete(`/groups/${encodeURIComponent(groupName)}/empty`);
                    if (!isCurrentAssistantSession(epoch)) return;
                    aiAssistantLastResult.value.emptyGroups = (aiAssistantLastResult.value.emptyGroups || [])
                        .filter(name => name !== groupName);
                    aiAssistantLastResult.value.undoToken = '';
                    const refreshed = await Promise.allSettled([
                        loadGroups(),
                        refreshAssistantScopeCatalog({ silent: true })
                    ]);
                    if (!isCurrentAssistantSession(epoch)) return;
                    const refreshOk = refreshed.every(item => (
                        item.status === 'fulfilled' && item.value !== false
                    ));
                    showToast(
                        mutationRefreshMessage(result.message || '空密码组已删除', refreshOk),
                        refreshOk ? 'success' : 'warning'
                    );
                } catch (error) {
                    if (!isCurrentAssistantSession(epoch)) return;
                    throw new Error(error.message || '删除空密码组失败');
                }
            });
        }
        async function openAssistantNavigation(navigation = null) {
            const target = navigation || aiAssistantLastResult.value?.navigation;
            if (!target?.entry_id) return;
            try {
                const entry = await store.getEntry(target.entry_id);
                if (!entry) {
                    showToast('目标条目已不存在或无法读取', 'warning');
                    return;
                }
                const opened = await openEntryDetail(entry);
                if (opened === false) {
                    showToast('无法打开条目详情，请重试', 'warning');
                    return;
                }
                showAiAssistant.value = false;
            } catch (error) {
                showToast(error.message || '无法打开目标条目', 'error');
            }
        }
        function useAssistantQuickReply(text) {
            aiAssistantInput.value = text;
            sendAssistantMessage();
        }
        async function openProfessionalAiTools() {
            if (aiAssistantBusy.value || aiAssistantPrepared.value) {
                showToast('当前 AI 请求或发送确认正在处理中，请稍候', 'warning');
                return false;
            }
            const epoch = assistantEpoch;
            showAiParse.value = true;
            try {
                const result = await api.get('/ai/status');
                if (isCurrentAssistantSession(epoch)) aiStatus.value = result.data;
            } catch (error) {
                if (isCurrentAssistantSession(epoch)) {
                    aiAssistantError.value = error.message || '无法加载 AI 状态';
                }
            }
        }
        async function openAssistantSettings() {
            if (aiAssistantBusy.value || aiAssistantPrepared.value) {
                showToast('当前 AI 请求或发送确认正在处理中，请稍候', 'warning');
                return false;
            }
            const epoch = assistantEpoch;
            await openSettings();
            if (isCurrentAssistantSession(epoch)) selectSettingsTab('ai');
        }
        return {
            openAiAssistant,
            closeAiAssistant,
            disposeAiAssistant,
            createAssistantConversation: createConversation,
            loadAssistantConversation: loadConversation,
            deleteAssistantConversation,
            clearAssistantHistory,
            sendAssistantMessage,
            submitPreparedTurn,
            cancelPreparedTurn,
            cancelAssistantRequest,
            applyAssistantPlan,
            undoAssistantPlan,
            deleteAssistantEmptyGroup,
            openAssistantNavigation,
            generateAssistantSecret,
            copyAssistantSecret,
            useAssistantQuickReply,
            openProfessionalAiTools,
            openAssistantSettings
        };
    }
    window.SecretBaseAiAssistantController = {
        createAiAssistantController
    };
})();
