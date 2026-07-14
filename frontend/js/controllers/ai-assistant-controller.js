/**
 * 对话式 AI 管家：发送清单、历史、计划审核与撤销。
 */
(function () {
    function createAiAssistantController(options) {
        const {
            api,
            store,
            showToast,
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
            searchQuery,
            selectedSearchScopes,
            sortBy,
            sortOrder,
            selectedEntryIds,
            selectedEntry,
            currentPage,
            loadEntries,
            loadTags,
            loadGroups,
            openSettings,
            selectSettingsTab
        } = options;

        function currentFilters() {
            if (aiAssistantScope.value === 'all') return {};
            const filters = {
                ...store.state.filters,
                search: searchQuery.value,
                searchScopes: [...selectedSearchScopes.value],
                sortBy: sortBy.value,
                sortOrder: sortOrder.value
            };
            if (aiAssistantScope.value === 'selection') {
                filters.entryIds = [...selectedEntryIds.value];
            }
            return filters;
        }

        async function loadConversations() {
            const result = await api.get('/ai/assistant/conversations');
            aiAssistantConversations.value = result.data?.conversations || [];
            return aiAssistantConversations.value;
        }

        async function createConversation() {
            const result = await api.post('/ai/assistant/conversations', { title: '' });
            aiAssistantConversationId.value = result.data.id;
            aiAssistantMessages.value = [];
            aiAssistantPlan.value = null;
            aiAssistantLastResult.value = null;
            await loadConversations();
            return result.data;
        }

        async function loadConversation(conversationId, preserveReview = false) {
            if (!conversationId) return;
            const result = await api.get(`/ai/assistant/conversations/${encodeURIComponent(conversationId)}`);
            aiAssistantConversationId.value = conversationId;
            aiAssistantMessages.value = result.data?.messages || [];
            aiAssistantPrepared.value = null;
            if (!preserveReview) {
                aiAssistantPlan.value = null;
                aiAssistantLastResult.value = null;
            }
        }

        async function ensureConversation() {
            const conversations = await loadConversations();
            const target = aiAssistantConversationId.value
                ? conversations.find(item => item.id === aiAssistantConversationId.value)
                : conversations[0];
            if (target) {
                await loadConversation(target.id);
            } else {
                await createConversation();
            }
        }

        async function openAiAssistant() {
            showAiAssistant.value = true;
            aiAssistantError.value = '';
            aiAssistantPrepared.value = null;
            try {
                const status = await api.get('/ai/status');
                aiStatus.value = status.data;
                await ensureConversation();
            } catch (error) {
                aiAssistantError.value = error.message || '无法加载 AI 管家';
            }
        }

        function closeAiAssistant() {
            if (aiAssistantBusy.value) {
                showToast('AI 请求正在处理中，请稍候', 'warning');
                return;
            }
            showAiAssistant.value = false;
            aiAssistantPrepared.value = null;
            aiAssistantPlan.value = null;
            aiAssistantLastResult.value = null;
            aiAssistantStage.value = '';
        }

        async function deleteAssistantConversation(conversationId) {
            if (!window.confirm('确认删除这段本机加密保存的 AI 对话？')) return;
            try {
                await api.delete(`/ai/assistant/conversations/${encodeURIComponent(conversationId)}`);
                if (aiAssistantConversationId.value === conversationId) {
                    aiAssistantConversationId.value = '';
                    aiAssistantMessages.value = [];
                }
                await ensureConversation();
            } catch (error) {
                showToast(error.message || '删除 AI 对话失败', 'error');
            }
        }

        async function clearAssistantHistory() {
            if (!window.confirm('确认清除本机全部 AI 对话历史？此操作不影响密码库。')) return;
            try {
                await api.delete('/ai/assistant/conversations');
                aiAssistantConversationId.value = '';
                aiAssistantMessages.value = [];
                await createConversation();
                showToast('AI 对话历史已清除', 'success');
            } catch (error) {
                showToast(error.message || '清除 AI 对话历史失败', 'error');
            }
        }

        function refreshAssistantContext(conversationId) {
            Promise.allSettled([
                loadConversation(conversationId, true),
                loadConversations()
            ]).then(results => {
                if (results.some(result => result.status === 'rejected')) {
                    showToast('AI 回复已完成，但对话历史刷新失败', 'warning');
                }
            });
        }

        async function requestSendPreview(draft) {
            const result = await api.post('/ai/assistant/turns/preview', {
                mode: draft.mode,
                scope: draft.scope,
                filters: draft.filters
            }, { timeoutMs: 20000 });
            const data = result.data || {};
            return {
                ...draft,
                previewToken: data.preview_token,
                manifest: data.manifest || {}
            };
        }

        function applyAssistantTurnResult(data) {
            aiAssistantConversationId.value = data.conversation_id || aiAssistantConversationId.value;
            aiAssistantPrepared.value = null;
            aiAssistantInput.value = '';
            aiAssistantMode.value = 'assistant';
            if (data.plan_token) {
                aiAssistantPlan.value = {
                    ...data,
                    actions: (data.actions || []).map(action => ({
                        ...action,
                        selected: true,
                        fields: (action.fields || []).map(field => ({
                            ...field,
                            revealed: !field.hidden
                        }))
                    }))
                };
            } else {
                aiAssistantPlan.value = null;
            }
            aiAssistantLastResult.value = data.navigation
                ? { navigation: data.navigation }
                : (data.message ? { message: data.message } : null);
            refreshAssistantContext(aiAssistantConversationId.value);
        }

        async function restorePreparedReview(draft) {
            aiAssistantStage.value = '正在恢复发送确认';
            try {
                aiAssistantPrepared.value = await requestSendPreview(draft);
            } catch (_error) {
                aiAssistantPrepared.value = null;
            }
        }

        async function submitPreparedTurn() {
            const prepared = aiAssistantPrepared.value;
            if (!prepared?.previewToken || aiAssistantBusy.value) return;
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
            try {
                const preparedResult = await api.post('/ai/assistant/turns/prepare', {
                    preview_token: prepared.previewToken,
                    conversation_id: aiAssistantConversationId.value || null,
                    message: prepared.originalMessage
                }, { timeoutMs: 20000 });
                const turn = preparedResult.data || {};
                aiAssistantConversationId.value = turn.conversation_id || aiAssistantConversationId.value;
                if (turn.local_result) {
                    aiAssistantPrepared.value = null;
                    aiAssistantInput.value = '';
                    aiAssistantMode.value = 'assistant';
                    aiAssistantLastResult.value = {
                        navigation: turn.local_result.navigation || null,
                        localAction: turn.local_result.local_action || null,
                        message: turn.local_result.message || ''
                    };
                    refreshAssistantContext(aiAssistantConversationId.value);
                    return;
                }
                if (!turn.turn_token) throw new Error('AI 请求令牌生成失败');

                aiAssistantStage.value = 'AI 正在分析并校验计划';
                const result = await api.post('/ai/assistant/turns/submit', {
                    turn_token: turn.turn_token,
                    acknowledge_risk: true
                }, { timeoutMs: 150000 });
                applyAssistantTurnResult(result.data || {});
            } catch (error) {
                aiAssistantError.value = error.message || 'AI 请求失败';
                await restorePreparedReview(draft);
            } finally {
                aiAssistantBusy.value = false;
                aiAssistantStage.value = '';
            }
        }

        async function sendAssistantMessage() {
            const message = aiAssistantInput.value.trim();
            if (!message || aiAssistantBusy.value || aiAssistantPrepared.value) return;
            if (!aiStatus.value?.configured) {
                aiAssistantError.value = '请先配置 AI 服务。';
                return;
            }
            if (aiAssistantScope.value === 'selection' && selectedEntryIds.value.length === 0) {
                aiAssistantError.value = '选择范围模式下，请先在条目列表勾选至少一个条目。';
                return;
            }
            aiAssistantBusy.value = true;
            aiAssistantStage.value = '正在核对发送范围';
            aiAssistantError.value = '';
            aiAssistantPlan.value = null;
            aiAssistantLastResult.value = null;
            const draft = {
                originalMessage: message,
                mode: aiAssistantMode.value,
                scope: aiAssistantScope.value,
                filters: currentFilters()
            };
            try {
                aiAssistantPrepared.value = await requestSendPreview(draft);
            } catch (error) {
                aiAssistantError.value = error.message || '无法核对 AI 发送范围';
            } finally {
                aiAssistantBusy.value = false;
                aiAssistantStage.value = '';
            }
        }

        function cancelPreparedTurn() {
            aiAssistantPrepared.value = null;
            aiAssistantStage.value = '';
        }

        async function applyAssistantPlan() {
            if (aiAssistantBusy.value) return;
            const plan = aiAssistantPlan.value;
            const selectedIds = (plan?.actions || []).filter(action => action.selected).map(action => action.id);
            if (!plan?.plan_token || selectedIds.length === 0) {
                showToast('请选择要应用的 AI 操作', 'warning');
                return;
            }
            aiAssistantBusy.value = true;
            aiAssistantStage.value = '正在本地应用已确认的操作';
            aiAssistantError.value = '';
            try {
                const result = await api.post('/ai/assistant/plans/apply', {
                    plan_token: plan.plan_token,
                    selected_ids: selectedIds,
                    expected_revision: plan.source_revision
                });
                aiAssistantLastResult.value = {
                    message: result.message,
                    undoToken: result.data?.undo_token || '',
                    revision: result.data?.revision || 0,
                    emptyGroups: result.data?.empty_groups || []
                };
                aiAssistantPlan.value = null;
                await Promise.all([
                    loadEntries(currentPage.value),
                    loadTags(),
                    loadGroups(),
                    loadConversation(aiAssistantConversationId.value, true),
                    loadConversations()
                ]);
                showToast(result.message || 'AI 操作已应用', 'success');
            } catch (error) {
                aiAssistantError.value = error.message || '应用 AI 计划失败';
            } finally {
                aiAssistantBusy.value = false;
                aiAssistantStage.value = '';
            }
        }

        async function undoAssistantPlan() {
            if (aiAssistantBusy.value) return;
            const resultState = aiAssistantLastResult.value;
            if (!resultState?.undoToken || !resultState.revision) return;
            aiAssistantBusy.value = true;
            aiAssistantStage.value = '正在恢复 AI 操作前的加密快照';
            try {
                const result = await api.post('/ai/assistant/plans/undo', {
                    undo_token: resultState.undoToken,
                    expected_revision: resultState.revision
                });
                aiAssistantLastResult.value = { message: result.message };
                await Promise.all([
                    loadEntries(currentPage.value), loadTags(), loadGroups(),
                    loadConversation(aiAssistantConversationId.value, true), loadConversations()
                ]);
                showToast('已撤销本次 AI 操作', 'success');
            } catch (error) {
                aiAssistantError.value = error.message || '撤销 AI 操作失败';
            } finally {
                aiAssistantBusy.value = false;
                aiAssistantStage.value = '';
            }
        }

        async function deleteAssistantEmptyGroup(groupName) {
            if (!window.confirm(`确认删除已经为空的密码组「${groupName}」？`)) return;
            try {
                const result = await api.delete(`/groups/${encodeURIComponent(groupName)}/empty`);
                aiAssistantLastResult.value.emptyGroups = (aiAssistantLastResult.value.emptyGroups || [])
                    .filter(name => name !== groupName);
                aiAssistantLastResult.value.undoToken = '';
                await loadGroups();
                showToast(result.message || '空密码组已删除', 'success');
            } catch (error) {
                showToast(error.message || '删除空密码组失败', 'error');
            }
        }

        async function openAssistantNavigation(navigation = null) {
            const target = navigation || aiAssistantLastResult.value?.navigation;
            if (!target?.entry_id) return;
            try {
                selectedEntry.value = await store.getEntry(target.entry_id);
                showAiAssistant.value = false;
            } catch (error) {
                showToast(error.message || '无法打开目标条目', 'error');
            }
        }

        function secureRandomText(length, alphabet) {
            const result = [];
            const values = new Uint32Array(32);
            const limit = Math.floor(0x100000000 / alphabet.length) * alphabet.length;
            while (result.length < length) {
                window.crypto.getRandomValues(values);
                for (const value of values) {
                    if (value < limit) result.push(alphabet[value % alphabet.length]);
                    if (result.length === length) break;
                }
            }
            return result.join('');
        }

        function generateAssistantSecret() {
            const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*_-+=';
            const requestedLength = Number(aiAssistantLastResult.value?.localAction?.length);
            const length = Number.isInteger(requestedLength) && requestedLength >= 12 && requestedLength <= 64
                ? requestedLength
                : 20;
            const secret = secureRandomText(length, alphabet);
            aiAssistantLastResult.value = {
                message: `已在本机生成 ${length} 位随机密码，内容不会发送给 AI。`,
                generatedSecret: secret
            };
            window.setTimeout(() => {
                if (aiAssistantLastResult.value?.generatedSecret === secret) {
                    aiAssistantLastResult.value = { message: '本地生成的密码已从 AI 面板清除。' };
                }
            }, 60000);
        }

        async function copyAssistantSecret() {
            const secret = aiAssistantLastResult.value?.generatedSecret;
            if (!secret) return;
            await copyToClipboard(secret);
            showToast('本地生成的密码已复制', 'success');
        }

        function useAssistantQuickReply(text) {
            aiAssistantInput.value = text;
            sendAssistantMessage();
        }

        async function openProfessionalAiTools() {
            showAiParse.value = true;
            try {
                const result = await api.get('/ai/status');
                aiStatus.value = result.data;
            } catch (error) {
                aiAssistantError.value = error.message || '无法加载 AI 状态';
            }
        }

        async function openAssistantSettings() {
            await openSettings();
            selectSettingsTab('ai');
        }

        return {
            openAiAssistant,
            closeAiAssistant,
            createAssistantConversation: createConversation,
            loadAssistantConversation: loadConversation,
            deleteAssistantConversation,
            clearAssistantHistory,
            sendAssistantMessage,
            submitPreparedTurn,
            cancelPreparedTurn,
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
