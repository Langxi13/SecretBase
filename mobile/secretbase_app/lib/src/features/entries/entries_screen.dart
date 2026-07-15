import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/core/widgets/mobile_chrome.dart';
import 'package:secretbase/src/core/widgets/paged_scroll.dart';
import 'package:secretbase/src/core/widgets/page_controls.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/entries/entry_card.dart';
import 'package:secretbase/src/features/entries/entry_detail_dialog.dart';
import 'package:secretbase/src/features/entries/entry_editor_dialog.dart';
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/preferences_controller.dart';

enum EntryFilterOrigin { groups, tags }

class EntryFilterPreset {
  const EntryFilterPreset({
    this.tag,
    this.group,
    this.origin,
    this.generation = 0,
  });

  final String? tag;
  final String? group;
  final EntryFilterOrigin? origin;
  final int generation;
}

class EntriesScreen extends ConsumerStatefulWidget {
  const EntriesScreen({required this.preset, this.onExitPreset, super.key});

  final EntryFilterPreset preset;
  final VoidCallback? onExitPreset;

  @override
  ConsumerState<EntriesScreen> createState() => _EntriesScreenState();
}

class _EntriesScreenState extends ConsumerState<EntriesScreen> {
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();
  Timer? _searchDebounce;
  int _page = 1;
  String _search = '';
  String? _tag;
  String? _group;
  bool _starred = false;

  @override
  void initState() {
    super.initState();
    _applyPreset(widget.preset);
  }

  @override
  void didUpdateWidget(covariant EntriesScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.preset.generation != widget.preset.generation) {
      setState(() => _applyPreset(widget.preset));
      resetPagedScroll(_scrollController);
    }
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _applyPreset(EntryFilterPreset preset) {
    _searchDebounce?.cancel();
    _searchController.clear();
    _search = '';
    _tag = preset.tag;
    _group = preset.group;
    _starred = false;
    _page = 1;
  }

  @override
  Widget build(BuildContext context) {
    final pageSize = ref.watch(
      preferencesProvider.select((preferences) => preferences.entryPageSize),
    );
    final query = EntryQuery(
      page: _page,
      pageSize: pageSize,
      search: _search,
      tag: _tag,
      group: _group,
      starred: _starred ? true : null,
      deleted: false,
    );
    final entries = ref.watch(entryPageProvider(query));
    final tags =
        ref.watch(taxonomyProvider('tags')).asData?.value ??
        const <TaxonomyRecord>[];
    final groups =
        ref.watch(taxonomyProvider('groups')).asData?.value ??
        const <TaxonomyRecord>[];
    final compactFab = MediaQuery.sizeOf(context).width < 600;
    final origin = widget.preset.origin;
    final pageTitle = origin == EntryFilterOrigin.groups
        ? (_group ?? '密码组条目')
        : origin == EntryFilterOrigin.tags
        ? (_tag ?? '标签条目')
        : '全部条目';
    final total = entries.asData?.value.total;
    final subtitlePrefix = origin == EntryFilterOrigin.groups
        ? '密码组'
        : origin == EntryFilterOrigin.tags
        ? '标签'
        : null;
    final pageSubtitle = total == null
        ? '正在统计条目'
        : subtitlePrefix == null
        ? '共 $total 条'
        : '$subtitlePrefix · 共 $total 条';

    return Scaffold(
      backgroundColor: Colors.transparent,
      floatingActionButton: compactFab
          ? FloatingActionButton(
              tooltip: '新建条目',
              onPressed: _createEntry,
              child: const Icon(Icons.add),
            )
          : FloatingActionButton.extended(
              onPressed: _createEntry,
              icon: const Icon(Icons.add),
              label: const Text('新建条目'),
            ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          MobilePageHeader(
            title: pageTitle,
            subtitle: pageSubtitle,
            leading: _canReturnToOrigin
                ? IconButton(
                    tooltip: _returnLabel,
                    onPressed: _exitPreset,
                    icon: const Icon(Icons.arrow_back),
                  )
                : null,
          ),
          _FilterBar(
            searchController: _searchController,
            selectedTag: _tag,
            selectedGroup: _group,
            starred: _starred,
            tags: tags,
            groups: groups,
            onSearchChanged: _onSearchChanged,
            onTagChanged: (value) {
              setState(() {
                _tag = value;
                _page = 1;
              });
              resetPagedScroll(_scrollController);
            },
            onGroupChanged: (value) {
              setState(() {
                _group = value;
                _page = 1;
              });
              resetPagedScroll(_scrollController);
            },
            onStarredChanged: (value) {
              setState(() {
                _starred = value;
                _page = 1;
              });
              resetPagedScroll(_scrollController);
            },
            onClear: _hasFilters ? _clearFilters : null,
            clearTooltip: _canReturnToOrigin ? _returnLabel : '清除筛选',
            clearIcon: _canReturnToOrigin
                ? Icons.arrow_back
                : Icons.filter_alt_off,
          ),
          Expanded(
            child: entries.when(
              loading: () => const LoadingView(label: '正在加载条目'),
              error: (error, stackTrace) => ErrorView(
                message: mobileErrorMessage(error),
                onRetry: () => ref.invalidate(entryPageProvider(query)),
              ),
              data: (page) => _buildList(page, query),
            ),
          ),
        ],
      ),
    );
  }

  bool get _hasFilters =>
      _search.isNotEmpty || _tag != null || _group != null || _starred;

  Widget _buildList(EntryPage page, EntryQuery query) {
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(entryPageProvider(query));
        await ref.read(entryPageProvider(query).future);
      },
      child: ListView.builder(
        controller: _scrollController,
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 90),
        itemCount: page.items.isEmpty ? 1 : page.items.length + 1,
        itemBuilder: (context, index) {
          if (page.items.isEmpty) {
            return EmptyView(
              icon: _hasFilters
                  ? Icons.filter_alt_off_outlined
                  : Icons.key_outlined,
              title: _hasFilters ? '没有匹配的条目' : '还没有条目',
              subtitle: _hasFilters ? '调整当前筛选条件后重试' : null,
              action: _hasFilters
                  ? OutlinedButton.icon(
                      onPressed: _clearFilters,
                      icon: Icon(
                        _canReturnToOrigin
                            ? Icons.arrow_back
                            : Icons.filter_alt_off,
                      ),
                      label: Text(_canReturnToOrigin ? _returnLabel : '清除筛选'),
                    )
                  : FilledButton.icon(
                      onPressed: _createEntry,
                      icon: const Icon(Icons.add),
                      label: const Text('新建条目'),
                    ),
            );
          }
          if (index == page.items.length) {
            return PageControls(
              page: page.page,
              totalPages: page.totalPages,
              pageSize: page.pageSize,
              onPageChanged: (value) {
                setState(() => _page = value);
                resetPagedScroll(_scrollController);
              },
              onPageSizeChanged: (value) {
                ref.read(preferencesProvider.notifier).setEntryPageSize(value);
                setState(() => _page = 1);
                resetPagedScroll(_scrollController);
              },
            );
          }
          final entry = page.items[index];
          return Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 980),
              child: Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: EntryCard(
                  entry: entry,
                  onTap: () => _openEntry(entry.id),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 320), () {
      if (mounted) {
        setState(() {
          _search = value.trim();
          _page = 1;
        });
        resetPagedScroll(_scrollController);
      }
    });
  }

  void _clearFilters() {
    if (_canReturnToOrigin) {
      _exitPreset();
      return;
    }
    _searchDebounce?.cancel();
    _searchController.clear();
    setState(() {
      _search = '';
      _tag = null;
      _group = null;
      _starred = false;
      _page = 1;
    });
    resetPagedScroll(_scrollController);
  }

  bool get _canReturnToOrigin =>
      widget.preset.origin != null && widget.onExitPreset != null;

  String get _returnLabel => switch (widget.preset.origin) {
    EntryFilterOrigin.groups => '返回密码组',
    EntryFilterOrigin.tags => '返回标签',
    null => '返回',
  };

  void _exitPreset() {
    widget.onExitPreset?.call();
  }

  Future<void> _createEntry() async {
    try {
      final message = await showEntryEditorDialog(context: context, ref: ref);
      if (message != null && mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(message)));
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(mobileErrorMessage(error))));
      }
    }
  }

  Future<void> _openEntry(String id) async {
    final message = await showEntryDetailDialog(
      context: context,
      ref: ref,
      entryId: id,
    );
    if (message != null && mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
    }
  }
}

class _FilterBar extends StatelessWidget {
  const _FilterBar({
    required this.searchController,
    required this.selectedTag,
    required this.selectedGroup,
    required this.starred,
    required this.tags,
    required this.groups,
    required this.onSearchChanged,
    required this.onTagChanged,
    required this.onGroupChanged,
    required this.onStarredChanged,
    this.clearTooltip = '清除筛选',
    this.clearIcon = Icons.filter_alt_off,
    this.onClear,
  });

  final TextEditingController searchController;
  final String? selectedTag;
  final String? selectedGroup;
  final bool starred;
  final List<TaxonomyRecord> tags;
  final List<TaxonomyRecord> groups;
  final ValueChanged<String> onSearchChanged;
  final ValueChanged<String?> onTagChanged;
  final ValueChanged<String?> onGroupChanged;
  final ValueChanged<bool> onStarredChanged;
  final String clearTooltip;
  final IconData clearIcon;
  final VoidCallback? onClear;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surface,
      child: Container(
        decoration: BoxDecoration(
          border: Border(bottom: BorderSide(color: scheme.outlineVariant)),
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 7, 12, 8),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 980),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ValueListenableBuilder<TextEditingValue>(
                    valueListenable: searchController,
                    builder: (context, value, child) => TextField(
                      controller: searchController,
                      onChanged: onSearchChanged,
                      decoration: InputDecoration(
                        isDense: true,
                        hintText: '搜索条目、字段或分类',
                        prefixIcon: const Icon(Icons.search, size: 20),
                        prefixIconConstraints: const BoxConstraints(
                          minWidth: 40,
                          minHeight: 40,
                        ),
                        suffixIconConstraints: const BoxConstraints(
                          minWidth: 40,
                          minHeight: 40,
                        ),
                        suffixIcon: value.text.isEmpty
                            ? null
                            : IconButton(
                                tooltip: '清空搜索',
                                onPressed: () {
                                  searchController.clear();
                                  onSearchChanged('');
                                },
                                icon: const Icon(Icons.close, size: 18),
                              ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 7),
                  Row(
                    children: [
                      Expanded(
                        child: _FilterDropdown(
                          icon: Icons.sell_outlined,
                          label: selectedTag ?? '标签',
                          value: selectedTag,
                          items: tags.map((item) => item.name).toList(),
                          onChanged: onTagChanged,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: _FilterDropdown(
                          icon: Icons.folder_outlined,
                          label: selectedGroup ?? '密码组',
                          value: selectedGroup,
                          items: groups.map((item) => item.name).toList(),
                          onChanged: onGroupChanged,
                        ),
                      ),
                      const SizedBox(width: 6),
                      _FavoriteFilterButton(
                        selected: starred,
                        onChanged: onStarredChanged,
                      ),
                      if (onClear != null) ...[
                        const SizedBox(width: 4),
                        IconButton.outlined(
                          tooltip: clearTooltip,
                          onPressed: onClear,
                          icon: Icon(clearIcon, size: 18),
                          style: IconButton.styleFrom(
                            fixedSize: const Size(38, 38),
                            minimumSize: const Size(38, 38),
                            padding: EdgeInsets.zero,
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _FavoriteFilterButton extends StatelessWidget {
  const _FavoriteFilterButton({
    required this.selected,
    required this.onChanged,
  });

  final bool selected;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return IconButton(
      tooltip: selected ? '显示全部条目' : '仅显示收藏',
      isSelected: selected,
      onPressed: () => onChanged(!selected),
      icon: const Icon(Icons.star_outline, size: 19),
      selectedIcon: const Icon(Icons.star_rounded, size: 19),
      color: scheme.onSurfaceVariant,
      style: IconButton.styleFrom(
        foregroundColor: selected ? scheme.onSecondaryContainer : null,
        backgroundColor: selected
            ? scheme.secondaryContainer
            : scheme.surfaceContainerLow,
        side: BorderSide(
          color: selected ? scheme.secondary : scheme.outlineVariant,
        ),
        fixedSize: const Size(38, 38),
        minimumSize: const Size(38, 38),
        padding: EdgeInsets.zero,
      ),
    );
  }
}

class _FilterDropdown extends StatelessWidget {
  const _FilterDropdown({
    required this.icon,
    required this.label,
    required this.value,
    required this.items,
    required this.onChanged,
  });

  final IconData icon;
  final String label;
  final String? value;
  final List<String> items;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final accent = icon == Icons.sell_outlined
        ? scheme.primary
        : scheme.tertiary;
    return PopupMenuButton<String?>(
      tooltip: label,
      initialValue: value,
      position: PopupMenuPosition.under,
      onSelected: onChanged,
      itemBuilder: (context) => [
        PopupMenuItem<String?>(
          value: null,
          child: Text(icon == Icons.sell_outlined ? '全部标签' : '全部密码组'),
        ),
        ...items.map(
          (item) => PopupMenuItem<String?>(value: item, child: Text(item)),
        ),
      ],
      child: Container(
        height: 38,
        padding: const EdgeInsets.symmetric(horizontal: 8),
        decoration: BoxDecoration(
          color: value == null
              ? scheme.surfaceContainerLow
              : accent.withValues(alpha: 0.1),
          border: Border.all(
            color: value == null
                ? scheme.outlineVariant
                : accent.withValues(alpha: 0.55),
          ),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Row(
          children: [
            Icon(icon, size: 16, color: value == null ? null : accent),
            const SizedBox(width: 5),
            Flexible(
              child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis),
            ),
            const SizedBox(width: 2),
            const Icon(Icons.arrow_drop_down, size: 17),
          ],
        ),
      ),
    );
  }
}
