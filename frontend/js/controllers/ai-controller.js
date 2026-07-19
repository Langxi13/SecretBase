/**
 * AI 解析、整理建议与自然语言操作计划。
 */
(function () {
    function createAiController(options) {
        const {
            api,
            store,
            showToast,
            nextTick,
            viewHelpers,
            showAiParse,
            aiMode,
            aiText,
            aiResult,
            aiParsing,
            aiStatus,
            aiStatusError,
            aiFailureMessage,
            aiOrganizing,
            aiRequestCancelable = { value: false },
            aiOrganizeError,
            aiOrganizeResult,
            aiOrganizeMode,
            aiOrganizeOptions,
            currentAiOrganizePrompt,
            aiActionInstruction,
            aiActionResult,
            aiActionError,
            aiCooldownUntil,
            aiNow,
            lastAiParseText,
            isAiTagGovernanceMode,
            canPreviewAiOrganize,
            canPreviewAiActions,
            canParseAi,
            aiCooldownSeconds,
            aiMaxInputChars,
            searchQuery,
            selectedSearchScopes,
            sortBy,
            sortOrder,
            currentPage,
            entryForm,
            showCreateModal,
            resetEntryForm,
            loadEntries,
            loadTags,
            loadGroups,
            openSettings,
            selectSettingsTab
        } = options;
        let aiRequestEpoch = 0;
        const requestLifecycle = window.SecretBaseAiAssistantRequest.createAiAssistantRequestLifecycle();

        function isCurrentAiSession(epoch) {
            return epoch === aiRequestEpoch;
        }

        function disposeAiTools() {
            requestLifecycle.abort();
            aiRequestEpoch += 1;
            aiParsing.value = false;
            aiOrganizing.value = false;
            aiRequestCancelable.value = false;
            aiFailureMessage.value = '';
            aiStatusError.value = '';
            aiOrganizeError.value = '';
            aiActionError.value = '';
        }

        function cancelAiRequest() {
            if (!aiRequestCancelable.value) return false;
            requestLifecycle.abort();
            aiRequestEpoch += 1;
            aiParsing.value = false;
            aiOrganizing.value = false;
            aiRequestCancelable.value = false;
            aiFailureMessage.value = '已取消本次 AI 请求。';
            aiOrganizeError.value = '已取消本次 AI 请求。';
            aiActionError.value = '已取消本次 AI 请求。';
            showToast('已取消本次 AI 请求', 'info');
            return true;
        }

        function beginCancelableRequest() {
            aiRequestCancelable.value = true;
            return requestLifecycle.begin();
        }

        function finishCancelableRequest(controller) {
            requestLifecycle.finish(controller);
            if (!requestLifecycle.hasActive()) aiRequestCancelable.value = false;
        }

        function closeAiParse() {
            if (aiParsing.value || aiOrganizing.value) return;
            disposeAiTools();
            showAiParse.value = false;
        }

        async function openAiParse() {
            if (aiParsing.value || aiOrganizing.value) return false;
            const epoch = ++aiRequestEpoch;
            showAiParse.value = true;
            aiMode.value = 'parse';
            aiStatus.value = null;
            aiStatusError.value = '';
            aiFailureMessage.value = '';
            aiOrganizeError.value = '';
            aiActionError.value = '';
            try {
                const result = await api.get('/ai/status');
                if (isCurrentAiSession(epoch)) aiStatus.value = result.data;
            } catch (error) {
                if (isCurrentAiSession(epoch)) {
                    aiStatusError.value = error.message || '无法获取 AI 配置状态，可继续手动录入';
                }
            }
        }

        async function manualEntryFromAi(showMessage = true) {
            const epoch = aiRequestEpoch;
            resetEntryForm();
            entryForm.remarks = aiText.value;
            aiResult.value = null;
            showAiParse.value = false;
            await nextTick();
            if (!isCurrentAiSession(epoch)) return;
            showCreateModal.value = true;
            if (showMessage) {
                showToast('已将原文转入备注，可继续手动录入', 'warning');
            }
        }

        function clearAiParse() {
            aiText.value = '';
            aiResult.value = null;
            aiFailureMessage.value = '';
            lastAiParseText.value = '';
            aiCooldownUntil.value = 0;
            aiNow.value = Date.now();
        }

        function setAiMode(mode) {
            if (aiParsing.value || aiOrganizing.value) return;
            aiMode.value = mode;
            aiFailureMessage.value = '';
            aiOrganizeError.value = '';
            aiActionError.value = '';
        }

        function clearAiOrganize() {
            if (aiOrganizing.value) return;
            aiOrganizeResult.value = null;
            aiOrganizeError.value = '';
        }

        function clearAiActions() {
            if (aiOrganizing.value) return;
            aiActionResult.value = null;
            aiActionError.value = '';
        }

        function setAiOrganizeMode(mode) {
            if (aiOrganizing.value) return;
            aiOrganizeMode.value = mode;
            aiOrganizeOptions.organizeTags = mode === 'tags';
            aiOrganizeOptions.organizeGroups = mode === 'groups';
            clearAiOrganize();
        }

        function currentAiOrganizeFilters() {
            return {
                ...store.state.filters,
                search: searchQuery.value,
                searchScopes: [...selectedSearchScopes.value],
                sortBy: sortBy.value,
                sortOrder: sortOrder.value
            };
        }

        async function previewAiOrganize() {
            if (aiOrganizing.value || aiParsing.value) return;
            if (!canPreviewAiOrganize.value) {
                if (!aiStatus.value?.configured) {
                    aiOrganizeError.value = 'AI 未配置，请先到设置页填写接入信息。';
                }
                return;
            }
            aiOrganizing.value = true;
            const requestController = beginCancelableRequest();
            const epoch = aiRequestEpoch;
            aiOrganizeError.value = '';
            aiOrganizeResult.value = null;
            try {
                const result = isAiTagGovernanceMode.value
                    ? await api.post('/ai/tags/preview', {
                        filters: currentAiOrganizeFilters(),
                        user_prompt: currentAiOrganizePrompt.value
                    }, { signal: requestController?.signal || null })
                    : await api.post('/ai/organize/preview', {
                        filters: currentAiOrganizeFilters(),
                        organize_tags: aiOrganizeOptions.organizeTags,
                        organize_groups: aiOrganizeOptions.organizeGroups,
                        user_prompt: currentAiOrganizePrompt.value
                    }, { signal: requestController?.signal || null });
                if (isCurrentAiSession(epoch)) aiOrganizeResult.value = result.data;
            } catch (error) {
                if (isCurrentAiSession(epoch)) {
                    aiOrganizeError.value = error.message || 'AI 整理建议生成失败';
                    showToast(aiOrganizeError.value, 'warning');
                }
            } finally {
                finishCancelableRequest(requestController);
                if (isCurrentAiSession(epoch)) aiOrganizing.value = false;
            }
        }

        function removeAiOrganizeItem(suggestion, key, value) {
            if (!Array.isArray(suggestion[key])) return;
            suggestion[key] = suggestion[key].filter(item => item !== value);
        }

        async function refreshAiDataAfterMutation() {
            const results = await Promise.allSettled([
                loadEntries(currentPage.value),
                loadTags(),
                loadGroups()
            ]);
            return results.every(result => (
                result.status === 'fulfilled' && result.value !== false
            ));
        }

        async function applyAiOrganize() {
            const suggestions = (aiOrganizeResult.value?.suggestions || []).filter(item => item.selected);
            if (suggestions.length === 0) {
                showToast('请选择要应用的整理建议', 'warning');
                return;
            }
            aiOrganizing.value = true;
            aiRequestCancelable.value = false;
            const epoch = aiRequestEpoch;
            aiOrganizeError.value = '';
            try {
                const result = isAiTagGovernanceMode.value
                    ? await api.post('/ai/tags/apply', {
                        plan_token: aiOrganizeResult.value.plan_token,
                        selected_ids: suggestions.map(item => item.id),
                        expected_revision: aiOrganizeResult.value.source_revision
                    })
                    : await api.post('/ai/organize/apply', {
                        plan_token: aiOrganizeResult.value.plan_token,
                        selected_ids: suggestions.map(item => item.id),
                        expected_revision: aiOrganizeResult.value.source_revision
                    });
                if (!isCurrentAiSession(epoch)) return;
                aiOrganizeResult.value = null;
                const refreshed = await refreshAiDataAfterMutation();
                if (!isCurrentAiSession(epoch)) return;
                const message = refreshed
                    ? (result.message || 'AI 整理已应用')
                    : `${result.message || 'AI 整理已应用'}，但界面刷新不完整，请稍后重试。`;
                showToast(message, refreshed ? 'success' : 'warning');
            } catch (error) {
                if (isCurrentAiSession(epoch)) {
                    aiOrganizeError.value = error.message || '应用 AI 整理失败';
                    showToast(aiOrganizeError.value, 'error');
                }
            } finally {
                if (isCurrentAiSession(epoch)) aiOrganizing.value = false;
            }
        }

        async function previewAiActions() {
            if (aiOrganizing.value || aiParsing.value) return;
            const instruction = aiActionInstruction.value.trim();
            if (!instruction) {
                aiActionError.value = '请输入希望 AI 执行的整理指令。';
                return;
            }
            if (!aiStatus.value?.configured) {
                aiActionError.value = 'AI 未配置，请先到设置页填写接入信息。';
                return;
            }
            aiOrganizing.value = true;
            const requestController = beginCancelableRequest();
            const epoch = aiRequestEpoch;
            aiActionError.value = '';
            aiActionResult.value = null;
            try {
                const result = await api.post('/ai/actions/preview', {
                    instruction,
                    filters: currentAiOrganizeFilters()
                }, { signal: requestController?.signal || null });
                if (isCurrentAiSession(epoch)) aiActionResult.value = result.data;
            } catch (error) {
                if (isCurrentAiSession(epoch)) {
                    aiActionError.value = error.message || 'AI 操作计划生成失败';
                    showToast(aiActionError.value, 'warning');
                }
            } finally {
                finishCancelableRequest(requestController);
                if (isCurrentAiSession(epoch)) aiOrganizing.value = false;
            }
        }

        async function applyAiActions() {
            const actions = (aiActionResult.value?.actions || []).filter(action => action.selected);
            if (actions.length === 0) {
                showToast('请选择要应用的操作计划', 'warning');
                return;
            }
            aiOrganizing.value = true;
            aiRequestCancelable.value = false;
            const epoch = aiRequestEpoch;
            aiActionError.value = '';
            try {
                const result = await api.post('/ai/actions/apply', {
                    plan_token: aiActionResult.value.plan_token,
                    selected_ids: actions.map(item => item.id),
                    expected_revision: aiActionResult.value.source_revision
                });
                if (!isCurrentAiSession(epoch)) return;
                aiActionResult.value = null;
                const refreshed = await refreshAiDataAfterMutation();
                if (!isCurrentAiSession(epoch)) return;
                const message = refreshed
                    ? (result.message || 'AI 操作计划已应用')
                    : `${result.message || 'AI 操作计划已应用'}，但界面刷新不完整，请稍后重试。`;
                showToast(message, refreshed ? 'success' : 'warning');
            } catch (error) {
                if (isCurrentAiSession(epoch)) {
                    aiActionError.value = error.message || '应用 AI 操作计划失败';
                    showToast(aiActionError.value, 'error');
                }
            } finally {
                if (isCurrentAiSession(epoch)) aiOrganizing.value = false;
            }
        }

        async function openAiSettingsFromParse() {
            const epoch = aiRequestEpoch;
            showAiParse.value = false;
            await openSettings();
            if (isCurrentAiSession(epoch)) selectSettingsTab('ai');
        }

        async function parseAiText() {
            if (aiParsing.value || aiOrganizing.value) return;
            const text = aiText.value.trim();
            if (!text) return;
            if (!aiStatus.value?.configured) {
                aiFailureMessage.value = 'AI 未配置，请先到设置页填写 Base URL、API Key 并选择模型后再使用智能解析。';
                showToast(aiFailureMessage.value, 'warning');
                return;
            }
            if (aiText.value.length > aiMaxInputChars) {
                aiFailureMessage.value = `内容过长，请分批解析，单次最多 ${aiMaxInputChars} 字符。原文仍保留，可转为手动录入。`;
                showToast(aiFailureMessage.value, 'warning');
                return;
            }
            if (!canParseAi.value) {
                if (aiCooldownSeconds.value > 0) {
                    showToast(`请等待 ${aiCooldownSeconds.value} 秒后再解析`, 'warning');
                } else if (text === lastAiParseText.value) {
                    showToast('内容未变化，不能重复智能解析', 'warning');
                } else if (!aiStatus.value?.configured) {
                    showToast('请先配置 AI 接入信息后再解析', 'warning');
                }
                return;
            }

            aiParsing.value = true;
            const requestController = beginCancelableRequest();
            const epoch = aiRequestEpoch;
            aiResult.value = null;
            aiFailureMessage.value = '';
            try {
                const result = await api.post('/ai/parse', { text }, { signal: requestController?.signal || null });
                const parsedEntries = viewHelpers.normalizeAiParsedEntries(result.data);
                if (!isCurrentAiSession(epoch)) return;
                aiResult.value = {
                    entries: parsedEntries,
                    entryCount: parsedEntries.length,
                    warnings: viewHelpers.normalizeAiWarnings(result.data, parsedEntries)
                };
                lastAiParseText.value = text;
                aiNow.value = Date.now();
                aiCooldownUntil.value = aiNow.value + 5000;
            } catch (error) {
                if (!isCurrentAiSession(epoch)) return;
                if (error.status === 429) {
                    aiFailureMessage.value = error.message || '请求过于频繁，请等待冷却结束后再试。你也可以直接转为手动录入。';
                } else {
                    aiFailureMessage.value = viewHelpers.formatAiFailureMessage(error);
                }
                showToast(aiFailureMessage.value, 'warning');
            } finally {
                finishCancelableRequest(requestController);
                if (isCurrentAiSession(epoch)) aiParsing.value = false;
            }
        }

        async function applyAiResult() {
            const entriesToApply = (aiResult.value?.entries || [])
                .filter(entry => entry.selected)
                .map(viewHelpers.normalizeEditableAiEntry)
                .filter(entry => entry.title);
            if (entriesToApply.length === 0) return;
            const epoch = aiRequestEpoch;

            const buildAiRemarks = entryRemarks => viewHelpers.buildAiRemarks(entryRemarks, aiText.value);
            if (entriesToApply.length === 1) {
                const entry = entriesToApply[0];
                resetEntryForm();
                entryForm.title = entry.title;
                entryForm.url = entry.url || '';
                entryForm.fields = entry.fields || [];
                entryForm.tags = entry.tags || [];
                entryForm.groups = entry.groups || [];
                entryForm.remarks = buildAiRemarks(entry.remarks);
                showAiParse.value = false;
                showCreateModal.value = true;
                aiResult.value = null;
                aiText.value = '';
                return;
            }

            let createdCount = 0;
            try {
                for (const entry of entriesToApply) {
                    if (!isCurrentAiSession(epoch)) return;
                    await api.post('/entries', {
                        title: entry.title,
                        url: entry.url || '',
                        starred: false,
                        tags: entry.tags || [],
                        groups: entry.groups || [],
                        fields: entry.fields || [],
                        remarks: buildAiRemarks(entry.remarks)
                    });
                    createdCount += 1;
                }
                if (!isCurrentAiSession(epoch)) return;
                showAiParse.value = false;
                aiResult.value = null;
                aiText.value = '';
                const refreshed = await Promise.allSettled([
                    loadEntries(1),
                    loadTags(),
                    loadGroups()
                ]);
                const refreshOk = refreshed.every(item => (
                    item.status === 'fulfilled' && item.value !== false
                ));
                showToast(
                    refreshOk
                        ? `已创建 ${createdCount} 条 AI 解析条目`
                        : `已创建 ${createdCount} 条 AI 解析条目，但界面刷新不完整，请稍后重试。`,
                    refreshOk ? 'success' : 'warning'
                );
            } catch (error) {
                if (isCurrentAiSession(epoch)) {
                    if (createdCount > 0) {
                        showAiParse.value = false;
                        aiResult.value = null;
                        aiText.value = '';
                        showToast(
                            `已创建 ${createdCount} 条 AI 解析条目，后续条目创建失败，请检查列表后再继续。`,
                            'warning'
                        );
                    } else {
                        showToast(error.message || 'AI 多条目创建失败，请检查解析结果', 'error');
                    }
                }
            }
        }

        function toggleAiEntrySelection(entry) {
            entry.selected = !entry.selected;
        }

        function addAiEntryField(entry) {
            if (!Array.isArray(entry.fields)) entry.fields = [];
            entry.fields.push({ name: '', value: '', copyable: true, hidden: false });
        }

        function removeAiEntryField(entry, index) {
            if (!Array.isArray(entry.fields)) return;
            entry.fields.splice(index, 1);
        }

        return {
            openAiParse,
            closeAiParse,
            manualEntryFromAi,
            clearAiParse,
            setAiMode,
            clearAiOrganize,
            clearAiActions,
            cancelAiRequest,
            setAiOrganizeMode,
            previewAiOrganize,
            removeAiOrganizeItem,
            applyAiOrganize,
            previewAiActions,
            applyAiActions,
            openAiSettingsFromParse,
            parseAiText,
            applyAiResult,
            toggleAiEntrySelection,
            addAiEntryField,
            removeAiEntryField,
            disposeAiTools
        };
    }

    window.SecretBaseAiController = {
        createAiController
    };
})();
