/**
 * AI 管家对话历史与会话加载。
 *
 * 该模块只负责历史记录和会话上下文，不处理发送、计划应用或敏感内容。
 */
(function () {
    function createAiAssistantHistoryController(options) {
        const {
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
            getAssistantEpoch,
            resetPendingMessage
        } = options;

        async function scrollAssistantToBottom() {
            await nextTick();
            if (typeof document === 'undefined') return;
            const thread = document.querySelector('.ai-chat-thread');
            if (thread) thread.scrollTop = thread.scrollHeight;
        }

        function collapseHistoryOnNarrowScreen() {
            if (
                typeof window !== 'undefined'
                && typeof window.matchMedia === 'function'
                && window.matchMedia('(max-width: 820px)').matches
            ) {
                aiAssistantHistoryOpen.value = false;
            }
        }

        async function loadConversations(epoch = getAssistantEpoch()) {
            const result = await api.get('/ai/assistant/conversations');
            if (!isCurrentAssistantSession(epoch)) return aiAssistantConversations.value;
            aiAssistantConversations.value = result.data?.conversations || [];
            return aiAssistantConversations.value;
        }

        async function createConversation(epoch = getAssistantEpoch()) {
            const result = await api.post('/ai/assistant/conversations', { title: '' });
            if (!isCurrentAssistantSession(epoch)) return result.data;
            resetAssistantScopeForConversation();
            aiAssistantConversationId.value = result.data.id;
            aiAssistantMessages.value = [];
            resetPendingMessage();
            aiAssistantPlan.value = null;
            aiAssistantLastResult.value = null;
            resetAssistantInspector();
            await loadConversations(epoch);
            if (!isCurrentAssistantSession(epoch)) return result.data;
            await refreshAssistantScopeCatalog({ silent: true });
            collapseHistoryOnNarrowScreen();
            return result.data;
        }

        async function loadConversation(conversationId, preserveReview = false, epoch = getAssistantEpoch()) {
            if (!conversationId) return;
            const changedConversation = conversationId !== aiAssistantConversationId.value;
            if (changedConversation) resetAssistantScopeForConversation();
            const result = await api.get(`/ai/assistant/conversations/${encodeURIComponent(conversationId)}`);
            if (!isCurrentAssistantSession(epoch)) return;
            aiAssistantConversationId.value = conversationId;
            aiAssistantMessages.value = result.data?.messages || [];
            resetPendingMessage();
            aiAssistantPrepared.value = null;
            if (!preserveReview) {
                aiAssistantPlan.value = null;
                aiAssistantLastResult.value = null;
                resetAssistantInspector();
            }
            if (changedConversation) {
                await refreshAssistantScopeCatalog({ silent: true });
                if (!isCurrentAssistantSession(epoch)) return;
            }
            collapseHistoryOnNarrowScreen();
            scrollAssistantToBottom();
        }

        async function ensureConversation(epoch = getAssistantEpoch()) {
            const conversations = await loadConversations(epoch);
            if (!isCurrentAssistantSession(epoch)) return;
            const target = aiAssistantConversationId.value
                ? conversations.find(item => item.id === aiAssistantConversationId.value)
                : conversations[0];
            if (target) await loadConversation(target.id, false, epoch);
            else await createConversation(epoch);
        }

        function deleteAssistantConversation(conversationId) {
            showConfirmDialog('删除 AI 对话', '确认删除这段本机加密保存的 AI 对话？此操作不会修改密码库。', async () => {
                const epoch = getAssistantEpoch();
                try {
                    await api.delete(`/ai/assistant/conversations/${encodeURIComponent(conversationId)}`);
                    if (!isCurrentAssistantSession(epoch)) return;
                    if (aiAssistantConversationId.value === conversationId) {
                        aiAssistantConversationId.value = '';
                        aiAssistantMessages.value = [];
                    }
                    await ensureConversation(epoch);
                } catch (error) {
                    if (!isCurrentAssistantSession(epoch)) return;
                    throw new Error(error.message || '删除 AI 对话失败');
                }
            });
        }

        function clearAssistantHistory() {
            showConfirmDialog('清除 AI 对话历史', '确认清除本机全部 AI 对话历史？此操作不可撤销，但不会修改密码库。', async () => {
                const epoch = getAssistantEpoch();
                try {
                    await api.delete('/ai/assistant/conversations');
                    if (!isCurrentAssistantSession(epoch)) return;
                    aiAssistantConversationId.value = '';
                    aiAssistantMessages.value = [];
                    await createConversation(epoch);
                    if (!isCurrentAssistantSession(epoch)) return;
                    showToast('AI 对话历史已清除', 'success');
                } catch (error) {
                    if (!isCurrentAssistantSession(epoch)) return;
                    throw new Error(error.message || '清除 AI 对话历史失败');
                }
            });
        }

        function refreshAssistantContext(conversationId, epoch = getAssistantEpoch()) {
            Promise.allSettled([
                loadConversation(conversationId, true, epoch),
                loadConversations(epoch)
            ]).then(results => {
                if (!isCurrentAssistantSession(epoch)) return;
                if (results.some(result => result.status === 'rejected')) {
                    showToast('AI 回复已完成，但对话历史刷新失败', 'warning');
                }
            });
        }

        return {
            scrollAssistantToBottom,
            loadConversations,
            createConversation,
            loadConversation,
            ensureConversation,
            deleteAssistantConversation,
            clearAssistantHistory,
            refreshAssistantContext
        };
    }

    window.SecretBaseAiAssistantHistoryController = {
        createAiAssistantHistoryController
    };
})();
