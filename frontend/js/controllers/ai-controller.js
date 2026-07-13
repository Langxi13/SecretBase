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

        async function openAiParse() {
            showAiParse.value = true;
            aiMode.value = 'parse';
            aiStatus.value = null;
            aiStatusError.value = '';
            aiFailureMessage.value = '';
            aiOrganizeError.value = '';
            aiActionError.value = '';
            try {
                const result = await api.get('/ai/status');
                aiStatus.value = result.data;
            } catch (error) {
                aiStatusError.value = error.message || '无法获取 AI 配置状态，可继续手动录入';
            }
        }

        async function manualEntryFromAi(showMessage = true) {
            resetEntryForm();
            entryForm.remarks = aiText.value;
            aiResult.value = null;
            showAiParse.value = false;
            await nextTick();
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
            aiMode.value = mode;
            aiFailureMessage.value = '';
            aiOrganizeError.value = '';
            aiActionError.value = '';
        }

        function clearAiOrganize() {
            aiOrganizeResult.value = null;
            aiOrganizeError.value = '';
        }

        function clearAiActions() {
            aiActionResult.value = null;
            aiActionError.value = '';
        }

        function setAiOrganizeMode(mode) {
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
            if (!canPreviewAiOrganize.value) {
                if (!aiStatus.value?.configured) {
                    aiOrganizeError.value = 'AI 未配置，请先到设置页填写接入信息。';
                }
                return;
            }
            aiOrganizing.value = true;
            aiOrganizeError.value = '';
            aiOrganizeResult.value = null;
            try {
                const result = isAiTagGovernanceMode.value
                    ? await api.post('/ai/tags/preview', {
                        filters: currentAiOrganizeFilters(),
                        user_prompt: currentAiOrganizePrompt.value
                    })
                    : await api.post('/ai/organize/preview', {
                        filters: currentAiOrganizeFilters(),
                        organize_tags: aiOrganizeOptions.organizeTags,
                        organize_groups: aiOrganizeOptions.organizeGroups,
                        user_prompt: currentAiOrganizePrompt.value
                    });
                aiOrganizeResult.value = result.data;
            } catch (error) {
                aiOrganizeError.value = error.message || 'AI 整理建议生成失败';
                showToast(aiOrganizeError.value, 'warning');
            } finally {
                aiOrganizing.value = false;
            }
        }

        function removeAiOrganizeItem(suggestion, key, value) {
            if (!Array.isArray(suggestion[key])) return;
            suggestion[key] = suggestion[key].filter(item => item !== value);
        }

        async function applyAiOrganize() {
            const suggestions = (aiOrganizeResult.value?.suggestions || []).filter(item => item.selected);
            if (suggestions.length === 0) {
                showToast('请选择要应用的整理建议', 'warning');
                return;
            }
            aiOrganizing.value = true;
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
                showToast(result.message || 'AI 整理已应用', 'success');
                aiOrganizeResult.value = null;
                await Promise.all([loadEntries(currentPage.value), loadTags(), loadGroups()]);
            } catch (error) {
                aiOrganizeError.value = error.message || '应用 AI 整理失败';
                showToast(aiOrganizeError.value, 'error');
            } finally {
                aiOrganizing.value = false;
            }
        }

        async function previewAiActions() {
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
            aiActionError.value = '';
            aiActionResult.value = null;
            try {
                const result = await api.post('/ai/actions/preview', {
                    instruction,
                    filters: currentAiOrganizeFilters()
                });
                aiActionResult.value = result.data;
            } catch (error) {
                aiActionError.value = error.message || 'AI 操作计划生成失败';
                showToast(aiActionError.value, 'warning');
            } finally {
                aiOrganizing.value = false;
            }
        }

        async function applyAiActions() {
            const actions = (aiActionResult.value?.actions || []).filter(action => action.selected);
            if (actions.length === 0) {
                showToast('请选择要应用的操作计划', 'warning');
                return;
            }
            aiOrganizing.value = true;
            aiActionError.value = '';
            try {
                const result = await api.post('/ai/actions/apply', {
                    plan_token: aiActionResult.value.plan_token,
                    selected_ids: actions.map(item => item.id),
                    expected_revision: aiActionResult.value.source_revision
                });
                showToast(result.message || 'AI 操作计划已应用', 'success');
                aiActionResult.value = null;
                await Promise.all([loadEntries(currentPage.value), loadTags(), loadGroups()]);
            } catch (error) {
                aiActionError.value = error.message || '应用 AI 操作计划失败';
                showToast(aiActionError.value, 'error');
            } finally {
                aiOrganizing.value = false;
            }
        }

        async function openAiSettingsFromParse() {
            showAiParse.value = false;
            await openSettings();
            selectSettingsTab('ai');
        }

        async function parseAiText() {
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
            aiResult.value = null;
            aiFailureMessage.value = '';
            try {
                const result = await api.post('/ai/parse', { text });
                const parsedEntries = viewHelpers.normalizeAiParsedEntries(result.data);
                aiResult.value = {
                    entries: parsedEntries,
                    entryCount: parsedEntries.length,
                    warnings: viewHelpers.normalizeAiWarnings(result.data, parsedEntries)
                };
                lastAiParseText.value = text;
                aiNow.value = Date.now();
                aiCooldownUntil.value = aiNow.value + 5000;
            } catch (error) {
                if (error.status === 429) {
                    aiFailureMessage.value = error.message || '请求过于频繁，请等待冷却结束后再试。你也可以直接转为手动录入。';
                } else {
                    aiFailureMessage.value = viewHelpers.formatAiFailureMessage(error);
                }
                showToast(aiFailureMessage.value, 'warning');
            } finally {
                aiParsing.value = false;
            }
        }

        async function applyAiResult() {
            const entriesToApply = (aiResult.value?.entries || [])
                .filter(entry => entry.selected)
                .map(viewHelpers.normalizeEditableAiEntry)
                .filter(entry => entry.title);
            if (entriesToApply.length === 0) return;

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

            try {
                for (const entry of entriesToApply) {
                    await api.post('/entries', {
                        title: entry.title,
                        url: entry.url || '',
                        starred: false,
                        tags: entry.tags || [],
                        groups: entry.groups || [],
                        fields: entry.fields || [],
                        remarks: buildAiRemarks(entry.remarks)
                    });
                }
                showToast(`已创建 ${entriesToApply.length} 条 AI 解析条目`, 'success');
                showAiParse.value = false;
                aiResult.value = null;
                aiText.value = '';
                await loadEntries(1);
                await Promise.all([loadTags(), loadGroups()]);
            } catch (error) {
                showToast(error.message || 'AI 多条目创建失败，请检查解析结果', 'error');
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
            manualEntryFromAi,
            clearAiParse,
            setAiMode,
            clearAiOrganize,
            clearAiActions,
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
            removeAiEntryField
        };
    }

    window.SecretBaseAiController = {
        createAiController
    };
})();
