/**
 * Tag browser and tag manager computed state.
 */
(function () {
    function createTagView(options) {
        const {
            computed,
            tags,
            activeTagName,
            tagBrowserSort,
            tagBrowserQuery,
            tagBrowserPage,
            tagBrowserPageSize,
            tagManagerPage,
            tagManagerPageSize,
            selectedManagedTagNames
        } = options;

        const sidebarTagLimit = 6;
        const tagNameCollator = new Intl.Collator('zh-CN', { numeric: true, sensitivity: 'base' });
        const tagBrowserSortOptions = [
            { value: 'count_desc', label: '条目数量多到少' },
            { value: 'count_asc', label: '条目数量少到多' },
            { value: 'name_asc', label: '名称 A-Z / 中文升序' },
            { value: 'name_desc', label: '名称 Z-A / 中文降序' }
        ];

        const sortedTagBrowserTags = computed(() => {
            const sorted = [...tags.value];
            sorted.sort((left, right) => {
                const nameCompare = tagNameCollator.compare(left.name || '', right.name || '');
                if (tagBrowserSort.value === 'count_asc') {
                    return (left.count || 0) - (right.count || 0) || nameCompare;
                }
                if (tagBrowserSort.value === 'name_asc') {
                    return nameCompare || (right.count || 0) - (left.count || 0);
                }
                if (tagBrowserSort.value === 'name_desc') {
                    return -nameCompare || (right.count || 0) - (left.count || 0);
                }
                return (right.count || 0) - (left.count || 0) || nameCompare;
            });
            return sorted;
        });

        const visibleSidebarTags = computed(() => {
            if (tags.value.length <= sidebarTagLimit) return tags.value;
            const activeTag = tags.value.find(tag => tag.name === activeTagName.value);
            const baseTags = tags.value
                .filter(tag => tag.name !== activeTagName.value)
                .slice(0, activeTag ? sidebarTagLimit - 1 : sidebarTagLimit);
            return activeTag ? [activeTag, ...baseTags] : baseTags;
        });

        const hiddenSidebarTagCount = computed(() => Math.max(0, tags.value.length - visibleSidebarTags.value.length));

        const filteredTagBrowserTags = computed(() => {
            const query = tagBrowserQuery.value.trim().toLowerCase();
            if (!query) return sortedTagBrowserTags.value;
            return sortedTagBrowserTags.value.filter(tag => String(tag.name || '').toLowerCase().includes(query));
        });

        const tagBrowserTotalPages = computed(() => Math.max(1, Math.ceil(filteredTagBrowserTags.value.length / tagBrowserPageSize.value)));

        const paginatedTagBrowserTags = computed(() => {
            const start = (tagBrowserPage.value - 1) * tagBrowserPageSize.value;
            return filteredTagBrowserTags.value.slice(start, start + tagBrowserPageSize.value);
        });

        const tagManagerTotalPages = computed(() => Math.max(1, Math.ceil(tags.value.length / tagManagerPageSize.value)));

        const paginatedManagedTags = computed(() => {
            const start = (tagManagerPage.value - 1) * tagManagerPageSize.value;
            return sortedTagBrowserTags.value.slice(start, start + tagManagerPageSize.value);
        });

        const allManagedPageTagsSelected = computed(() => {
            const pageTags = paginatedManagedTags.value;
            return pageTags.length > 0 && pageTags.every(tag => selectedManagedTagNames.value.includes(tag.name));
        });

        return {
            tagBrowserSortOptions,
            sortedTagBrowserTags,
            visibleSidebarTags,
            hiddenSidebarTagCount,
            filteredTagBrowserTags,
            tagBrowserTotalPages,
            paginatedTagBrowserTags,
            tagManagerTotalPages,
            paginatedManagedTags,
            allManagedPageTagsSelected
        };
    }

    window.SecretBaseTagView = {
        createTagView
    };
})();
