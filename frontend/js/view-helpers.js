/**
 * SecretBase presentation helpers.
 * These functions are intentionally framework-free so app.js can stay focused on state and workflows.
 */
(function () {
    function getFavicon(url) {
        return window.getFaviconUrl(url);
    }

    function getTagColor(tagName) {
        return window.getTagColor(tagName);
    }

    function groupAccentColor(group) {
        const explicitColor = group && typeof group === 'object' ? String(group.color || '').trim() : '';
        const groupName = group && typeof group === 'object' ? group.name : group;
        const name = String(groupName || '').trim();
        return explicitColor || getTagColor(name || '默认');
    }

    function groupCardStyle(group) {
        return {
            '--group-accent': groupAccentColor(group)
        };
    }

    function entryAccentColor(entry = {}) {
        const entryGroups = Array.isArray(entry.groups) ? entry.groups.filter(Boolean) : [];
        if (entryGroups.length > 0) {
            return groupAccentColor(entryGroups[0]);
        }

        const entryTags = Array.isArray(entry.tags) ? entry.tags.filter(Boolean) : [];
        if (entryTags.length > 0) {
            return getTagColor(entryTags[0]);
        }

        return 'var(--color-primary)';
    }

    function entryCardStyle(entry) {
        return {
            '--entry-accent': entryAccentColor(entry)
        };
    }

    function visibleEntryGroups(entry = {}) {
        const entryGroups = Array.isArray(entry.groups) ? entry.groups.filter(Boolean) : [];
        return entryGroups.slice(0, 2);
    }

    function remainingEntryGroupsCount(entry = {}) {
        const entryGroups = Array.isArray(entry.groups) ? entry.groups.filter(Boolean) : [];
        return Math.max(0, entryGroups.length - visibleEntryGroups(entry).length);
    }

    function groupChipStyle(groupName) {
        return {
            '--chip-accent': groupAccentColor(groupName)
        };
    }

    function formatDate(dateString) {
        return window.formatDate ? window.formatDate(dateString) : dateString;
    }

    function normalizeFieldHidden(field = {}) {
        if (Object.prototype.hasOwnProperty.call(field, 'hidden') && field.hidden !== null) {
            return Boolean(field.hidden);
        }
        return Boolean(field.copyable);
    }

    function normalizeFieldForEdit(field = {}) {
        return {
            name: String(field.name || '').trim(),
            value: String(field.value || ''),
            copyable: Boolean(field.copyable),
            hidden: normalizeFieldHidden(field)
        };
    }

    function formatBytes(size) {
        if (size < 1024) return `${size} B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
        return `${(size / 1024 / 1024).toFixed(1)} MB`;
    }

    function backupTypeLabel(type) {
        if (type === 'manual') return '手动备份';
        if (type === 'auto') return '自动备份';
        return '旧版备份';
    }

    function friendlyApiMessage(error, fallback) {
        if (!error) return fallback;
        if (error.status === 401) return '当前会话已失效，请重新解锁后再操作。';
        if (error.status === 409) return '数据文件已被其他进程修改，请重新解锁或刷新后再操作。';
        if (error.status === 413) return '请求或文件过大，请减小内容后重试。';
        if (error.status === 422) return error.message || '请求内容无效，请检查输入后重试。';
        if (error.status === 423 || error.code === 'VAULT_LOCKED') return '数据文件正在被其他进程使用。请确认没有旧的 SecretBase 进程仍在运行后重试。';
        if (error.status >= 500) return '服务器内部错误，请稍后重试或检查后端日志。';
        return error.message || fallback;
    }

    function aiTagActionLabel(action) {
        const labels = {
            create_tag: '新建标签',
            update_tag: '更新标签',
            delete_tag: '删除标签',
            merge_tags: '合并标签',
            replace_tag: '替换标签',
            assign_tag: '分配标签'
        };
        return labels[action] || action || '标签建议';
    }

    function aiTagActionTitle(suggestion) {
        if (!suggestion) return '标签建议';
        if (suggestion.action === 'merge_tags') {
            return `${aiTagActionLabel(suggestion.action)}：${(suggestion.source_tags || []).join('、')} → ${suggestion.target_tag || ''}`;
        }
        if (suggestion.action === 'update_tag' || suggestion.action === 'replace_tag') {
            return `${aiTagActionLabel(suggestion.action)}：${suggestion.tag || ''} → ${suggestion.new_tag || ''}`;
        }
        return `${aiTagActionLabel(suggestion.action)}：${suggestion.tag || suggestion.target_tag || ''}`;
    }

    function aiActionTypeLabel(type) {
        const labels = {
            create_group: '新建密码组',
            update_group: '更新密码组',
            create_entry: '新建条目',
            create_entry_from_field: '字段拆分为条目',
            update_entry: '更新条目'
        };
        return labels[type] || type || '操作';
    }

    function aiActionEntryLabel(action) {
        if (!action) return '';
        if (action.type === 'create_entry_from_field') {
            return action.source_entry_title || action.source_entry_id || '';
        }
        return action.entry_title || action.entry_id || action.source_entry_title || action.source_entry_id || '';
    }

    function aiActionTitle(action) {
        if (!action) return '操作计划';
        if (action.type === 'create_group') {
            return `${aiActionTypeLabel(action.type)}：${action.group || ''}`;
        }
        if (action.type === 'update_group') {
            const groupChange = action.group_new && action.group_new !== action.group ? ` → ${action.group_new}` : '';
            return `${aiActionTypeLabel(action.type)}：${action.group || ''}${groupChange}`;
        }
        if (action.type === 'create_entry_from_field') {
            const sourceLabel = aiActionEntryLabel(action);
            const fieldLabel = action.field_name ? ` · ${action.field_name}` : '';
            const targetLabel = action.title ? ` → ${action.title}` : '';
            return `${aiActionTypeLabel(action.type)}：${sourceLabel}${fieldLabel}${targetLabel}`;
        }
        if (action.type === 'update_entry') {
            const entryLabel = aiActionEntryLabel(action);
            const titleChange = action.title && action.title !== entryLabel ? ` → ${action.title}` : '';
            return `${aiActionTypeLabel(action.type)}：${entryLabel}${titleChange}`;
        }
        return `${aiActionTypeLabel(action.type)}：${action.title || ''}`;
    }

    function formatAiFailureMessage(error = {}) {
        if (error.status === 401) return '当前 vault 已锁定，请重新解锁后再使用 AI。原文仍保留，可转为手动录入。';
        if (error.status === 502) return 'AI 未配置、网络/API 不可用，或模型返回格式异常。原文仍保留，可转为手动录入。';
        if (error.status >= 500) return 'AI 服务暂时不可用。原文仍保留，可转为手动录入。';
        if (error.status === 413) return '输入内容过长，请分批解析。原文仍保留，可转为手动录入。';
        if (error.status === 422) return '输入内容无法解析为有效请求。请调整文本，或转为手动录入。';
        return `${error.message || 'AI 解析失败'}。原文仍保留，可转为手动录入。`;
    }

    function normalizeEditableAiEntry(entry = {}) {
        const tags = String(entry.tagsText || '')
            .split(/[,，]/)
            .map(tag => tag.trim())
            .filter(Boolean);
        const fields = Array.isArray(entry.fields)
            ? entry.fields
                .map(normalizeFieldForEdit)
                .filter(field => field.name)
            : [];
        return {
            title: String(entry.title || '').trim(),
            url: String(entry.url || '').trim(),
            fields,
            tags: Array.from(new Set(tags)),
            remarks: String(entry.remarks || '').trim()
        };
    }

    function normalizeAiParsedEntries(data = {}) {
        const rawEntries = Array.isArray(data.parsed_entries)
            ? data.parsed_entries
            : data.parsed
                ? [data.parsed]
                : [];
        return rawEntries.map((entry, index) => ({
            aiKey: `${Date.now()}-${index}-${Math.random().toString(16).slice(2)}`,
            selected: true,
            title: String(entry?.title || `AI 解析条目 ${index + 1}`).trim(),
            url: String(entry?.url || '').trim(),
            fields: Array.isArray(entry?.fields) ? entry.fields : [],
            tags: Array.isArray(entry?.tags) ? entry.tags : [],
            tagsText: Array.isArray(entry?.tags) ? entry.tags.join(', ') : '',
            remarks: String(entry?.remarks || '').trim()
        }));
    }

    function normalizeAiWarnings(data = {}, entries = []) {
        const warnings = Array.isArray(data.warnings) ? data.warnings.map(item => String(item || '').trim()).filter(Boolean) : [];
        if (entries.length > 8) warnings.push('解析结果条目较多，建议逐条确认标题、字段和标签后再创建。');
        if (entries.some(entry => !entry.fields || entry.fields.length === 0)) warnings.push('部分条目没有字段，可能需要手动补充账号、密码或备注。');
        return Array.from(new Set(warnings));
    }

    function buildAiRemarks(entryRemarks = '', aiText = '') {
        const parts = [];
        if (entryRemarks) parts.push(entryRemarks);
        if (aiText) parts.push(`AI 原文：\n${aiText}`);
        return parts.join('\n\n');
    }

    window.SecretBaseViewHelpers = {
        getFavicon,
        getTagColor,
        groupAccentColor,
        groupCardStyle,
        entryAccentColor,
        entryCardStyle,
        visibleEntryGroups,
        remainingEntryGroupsCount,
        groupChipStyle,
        formatDate,
        normalizeFieldHidden,
        normalizeFieldForEdit,
        formatBytes,
        backupTypeLabel,
        friendlyApiMessage,
        aiTagActionLabel,
        aiTagActionTitle,
        aiActionTypeLabel,
        aiActionEntryLabel,
        aiActionTitle,
        formatAiFailureMessage,
        normalizeEditableAiEntry,
        normalizeAiParsedEntries,
        normalizeAiWarnings,
        buildAiRemarks
    };
})();
