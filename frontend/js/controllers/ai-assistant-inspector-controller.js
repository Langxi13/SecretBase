/**
 * AI 管家计划归一化，以及关联条目的本地详情加载、分页和复制。
 */
(function () {
    const confirmationMessages = new Set([
        '确认', '确认执行', '确认应用', '执行', '执行计划', '应用', '应用计划'
    ]);
    const domainLabels = {
        groups: '密码组',
        tags: '标签',
        entry_structure: '条目结构',
        entry_creation: '条目创建',
        navigation: '条目定位'
    };
    const domainOrder = ['groups', 'tags', 'entry_structure', 'entry_creation', 'navigation', 'other'];

    function normalizeAssistantPlan(data, requestContext, defaultScope, normalizeTargets) {
        const context = requestContext || {};
        const conflicts = Array.isArray(data.conflicts) ? data.conflicts : [];
        const actions = (data.actions || []).map(action => ({
            ...action,
            selected: !action.danger,
            entryTargets: normalizeTargets(action),
            conflicts: conflicts.filter(conflict => (conflict.action_ids || []).includes(action.id)),
            fields: (action.fields || []).map(field => ({
                ...field,
                revealed: !field.hidden
            }))
        }));
        const groupsByDomain = new Map();
        actions.forEach(action => {
            const domain = action.domain || (action.type === 'create_entry' ? 'entry_creation' : 'other');
            if (!groupsByDomain.has(domain)) {
                groupsByDomain.set(domain, {
                    domain,
                    label: domainLabels[domain] || '其他操作',
                    actions: []
                });
            }
            groupsByDomain.get(domain).actions.push(action);
        });
        return {
            ...data,
            requestScope: context.scope || data.requestScope || defaultScope,
            scopeEntryCount: Number(
                context.manifest?.entry_count
                || context.scopeEntryCount
                || data.scopeEntryCount
                || 0
            ),
            warnings: Array.isArray(data.warnings) ? data.warnings.filter(Boolean) : [],
            conflicts,
            actions,
            actionGroups: Array.from(groupsByDomain.values()).sort(
                (left, right) => domainOrder.indexOf(left.domain) - domainOrder.indexOf(right.domain)
            )
        };
    }

    function isAssistantConfirmation(message) {
        const normalized = String(message || '').trim().replace(/[。！!？?]+$/g, '');
        return confirmationMessages.has(normalized);
    }

    function assistantPlanHasSelectedConflicts(plan) {
        const selectedIds = new Set((plan?.actions || []).filter(action => action.selected).map(action => action.id));
        return (plan?.conflicts || []).some(conflict => {
            const actionIds = conflict.action_ids || [];
            return actionIds.length > 0 && actionIds.every(actionId => selectedIds.has(actionId));
        });
    }

    function toggleAssistantPlanGroup(group, selected) {
        (group?.actions || []).forEach(action => {
            action.selected = Boolean(selected);
        });
    }

    window.SecretBaseAiAssistantPlanHelpers = {
        normalizeAssistantPlan,
        isAssistantConfirmation,
        assistantPlanHasSelectedConflicts,
        toggleAssistantPlanGroup
    };
})();

(function () {
    function createAiAssistantInspectorController(options) {
        const {
            store,
            showToast,
            copyToClipboard,
            aiAssistantInspector,
            resetAiAssistantInspector
        } = options;
        let requestId = 0;

        function normalizeAssistantActionTargets(action = {}) {
            const rawTargets = Array.isArray(action.entry_targets) ? action.entry_targets : [];
            const seen = new Set();
            return rawTargets.reduce((targets, target) => {
                const id = String(target?.id || '').trim();
                if (!id || seen.has(id)) return targets;
                seen.add(id);
                targets.push({
                    id,
                    title: String(target?.title || '未命名条目').trim() || '未命名条目'
                });
                return targets;
            }, []);
        }

        function resetAssistantInspector() {
            requestId += 1;
            resetAiAssistantInspector();
        }

        async function loadAssistantInspectorEntry(entryId) {
            const normalizedId = String(entryId || '').trim();
            if (!normalizedId) return;
            const currentRequestId = ++requestId;
            aiAssistantInspector.activeEntryId = normalizedId;
            aiAssistantInspector.loading = true;
            aiAssistantInspector.error = '';
            aiAssistantInspector.entry = null;
            try {
                const entry = await store.getEntry(normalizedId);
                if (currentRequestId !== requestId) return;
                aiAssistantInspector.entry = {
                    ...entry,
                    fields: (entry?.fields || []).map(field => ({
                        ...field,
                        revealed: !field.hidden
                    }))
                };
            } catch (error) {
                if (currentRequestId !== requestId) return;
                aiAssistantInspector.error = error.message || '无法加载条目详情';
            } finally {
                if (currentRequestId === requestId) {
                    aiAssistantInspector.loading = false;
                }
            }
        }

        async function openAssistantActionEntries(action) {
            const targets = Array.isArray(action?.entryTargets)
                ? action.entryTargets
                : normalizeAssistantActionTargets(action);
            if (targets.length === 0) {
                showToast('这项建议不直接关联现有条目', 'info');
                return;
            }
            Object.assign(aiAssistantInspector, {
                open: true,
                loading: false,
                error: '',
                actionTitle: String(action.title || 'AI 建议').trim(),
                actionReason: String(action.reason || '').trim(),
                targets,
                page: 1,
                pageSize: typeof window !== 'undefined'
                    && typeof window.matchMedia === 'function'
                    && window.matchMedia('(max-width: 520px)').matches ? 4 : 8,
                activeEntryId: targets[0].id,
                entry: null
            });
            await loadAssistantInspectorEntry(targets[0].id);
        }

        async function selectAssistantInspectorEntry(entryId) {
            if (entryId === aiAssistantInspector.activeEntryId && aiAssistantInspector.entry) return;
            await loadAssistantInspectorEntry(entryId);
        }

        async function changeAssistantInspectorPage(nextPage) {
            const totalPages = Math.max(
                1,
                Math.ceil(aiAssistantInspector.targets.length / aiAssistantInspector.pageSize)
            );
            const page = Math.min(totalPages, Math.max(1, Number(nextPage) || 1));
            aiAssistantInspector.page = page;
            const firstTarget = aiAssistantInspector.targets[(page - 1) * aiAssistantInspector.pageSize];
            if (firstTarget) await selectAssistantInspectorEntry(firstTarget.id);
        }

        async function copyAssistantInspectorField(field) {
            if (!field || field.value === undefined || field.value === null) return;
            await copyToClipboard(String(field.value));
            showToast(`已复制「${field.name || '字段'}」`, 'success');
        }

        return {
            normalizeAssistantActionTargets,
            resetAssistantInspector,
            openAssistantActionEntries,
            selectAssistantInspectorEntry,
            changeAssistantInspectorPage,
            closeAssistantActionEntries: resetAssistantInspector,
            copyAssistantInspectorField,
            assistantPlanHasSelectedConflicts: window.SecretBaseAiAssistantPlanHelpers.assistantPlanHasSelectedConflicts,
            toggleAssistantPlanGroup: window.SecretBaseAiAssistantPlanHelpers.toggleAssistantPlanGroup
        };
    }

    window.SecretBaseAiAssistantInspectorController = {
        createAiAssistantInspectorController
    };
})();
