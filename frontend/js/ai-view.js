/**
 * AI assistant computed summaries.
 */
(function () {
    function createAiView(options) {
        const {
            computed,
            aiText,
            aiParsing,
            aiStatus,
            aiCooldownUntil,
            aiNow,
            lastAiParseText,
            aiResult,
            aiOrganizing,
            aiOrganizeOptions,
            aiActionInstruction,
            aiOrganizeResult,
            isAiTagGovernanceMode,
            groups,
            aiActionResult
        } = options;

        const aiSoftInputChars = 3000;
        const aiMaxInputChars = 6000;

        const aiCooldownSeconds = computed(() => Math.max(0, Math.ceil((aiCooldownUntil.value - aiNow.value) / 1000)));

        const aiTextLength = computed(() => aiText.value.length);

        const aiInputWarning = computed(() => {
            const text = aiText.value.trim();
            if (aiText.value.length > aiMaxInputChars) return `内容过长，请分批解析，单次最多 ${aiMaxInputChars} 字符。`;
            if (text.split(/\n+/).filter(Boolean).length > 60) return '内容行数较多，建议按系统或账号分批解析，避免 AI 合并或误分条目。';
            if (aiText.value.length > aiSoftInputChars) return '内容较长，建议分批解析并逐条检查结果。';
            return '';
        });

        const canParseAi = computed(() => {
            const text = aiText.value.trim();
            return Boolean(text)
                && Boolean(aiStatus.value?.configured)
                && aiText.value.length <= aiMaxInputChars
                && !aiParsing.value
                && aiCooldownSeconds.value === 0
                && text !== lastAiParseText.value;
        });

        const selectedAiEntryCount = computed(() => {
            return aiResult.value?.entries?.filter(entry => entry.selected).length || 0;
        });

        const selectedAiOrganizeCount = computed(() => {
            return aiOrganizeResult.value?.suggestions?.filter(item => item.selected).length || 0;
        });

        const aiOrganizeSummary = computed(() => {
            const suggestions = (aiOrganizeResult.value?.suggestions || []).filter(item => item.selected);
            if (isAiTagGovernanceMode.value) {
                const affectedEntries = new Set();
                const summary = {
                    affected_entries: 0,
                    total_actions: suggestions.length,
                    create_tag: 0,
                    update_tag: 0,
                    delete_tag: 0,
                    merge_tags: 0,
                    replace_tag: 0,
                    assign_tag: 0
                };
                suggestions.forEach(item => {
                    (item.entry_ids || []).forEach(entryId => affectedEntries.add(entryId));
                    if (Object.prototype.hasOwnProperty.call(summary, item.action)) {
                        summary[item.action] += 1;
                    }
                });
                summary.affected_entries = affectedEntries.size;
                return summary;
            }

            const existingGroupNames = new Set(groups.value.map(group => group.name));
            const uniqueAddGroups = new Set();
            let addGroupAssignments = 0;
            const summary = {
                affected_entries: suggestions.length,
                add_tags: 0,
                remove_tags: 0,
                add_groups: 0,
                add_group_assignments: 0,
                assigned_groups: 0,
                remove_groups: 0
            };
            suggestions.forEach(item => {
                summary.add_tags += (item.add_tags || []).length;
                summary.remove_tags += (item.remove_tags || []).length;
                summary.remove_groups += (item.remove_groups || []).length;
                (item.add_groups || []).forEach(group => {
                    uniqueAddGroups.add(group);
                    addGroupAssignments += 1;
                });
            });
            const uniqueNewGroups = [...uniqueAddGroups].filter(group => !existingGroupNames.has(group));
            summary.add_groups = uniqueNewGroups.length;
            summary.add_group_assignments = addGroupAssignments;
            summary.assigned_groups = uniqueAddGroups.size;
            return summary;
        });

        const selectedAiOrganizeChangeCount = computed(() => {
            return (aiOrganizeResult.value?.suggestions || [])
                .filter(item => item.selected)
                .reduce((total, item) => {
                    if (isAiTagGovernanceMode.value) {
                        return total + (item.action ? 1 : 0);
                    }
                    return total
                        + (item.add_tags || []).length
                        + (item.remove_tags || []).length
                        + (item.add_groups || []).length
                        + (item.remove_groups || []).length;
                }, 0);
        });

        const selectedAiActionCount = computed(() => {
            return aiActionResult.value?.actions?.filter(action => action.selected).length || 0;
        });

        const aiActionSummary = computed(() => {
            const actions = (aiActionResult.value?.actions || []).filter(action => action.selected);
            return actions.reduce((summary, action) => {
                summary.total_actions += 1;
                if (Object.prototype.hasOwnProperty.call(summary, action.type)) {
                    summary[action.type] += 1;
                }
                return summary;
            }, {
                total_actions: 0,
                create_group: 0,
                update_group: 0,
                create_entry: 0,
                create_entry_from_field: 0,
                update_entry: 0
            });
        });

        const canPreviewAiOrganize = computed(() => {
            return Boolean(aiStatus.value?.configured)
                && !aiOrganizing.value
                && (isAiTagGovernanceMode.value || aiOrganizeOptions.organizeTags || aiOrganizeOptions.organizeGroups);
        });

        const canPreviewAiActions = computed(() => {
            return Boolean(aiStatus.value?.configured)
                && !aiOrganizing.value
                && Boolean(aiActionInstruction.value.trim());
        });

        return {
            aiSoftInputChars,
            aiMaxInputChars,
            aiCooldownSeconds,
            aiTextLength,
            aiInputWarning,
            canParseAi,
            selectedAiEntryCount,
            selectedAiOrganizeCount,
            aiOrganizeSummary,
            selectedAiOrganizeChangeCount,
            selectedAiActionCount,
            aiActionSummary,
            canPreviewAiOrganize,
            canPreviewAiActions
        };
    }

    window.SecretBaseAiView = {
        createAiView
    };
})();
