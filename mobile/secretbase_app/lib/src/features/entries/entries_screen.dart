import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/core/widgets/page_controls.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/entries/entry_card.dart';
import 'package:secretbase/src/features/entries/entry_detail_dialog.dart';
import 'package:secretbase/src/features/entries/entry_editor_dialog.dart';
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/preferences_controller.dart';

class EntryFilterPreset {
  const EntryFilterPreset({this.tag, this.group, this.generation = 0});

  final String? tag;
  final String? group;
  final int generation;
}

class EntriesScreen extends ConsumerStatefulWidget {
  const EntriesScreen({required this.preset, super.key});

  final EntryFilterPreset preset;

  @override
  ConsumerState<EntriesScreen> createState() => _EntriesScreenState();
}

class _EntriesScreenState extends ConsumerState<EntriesScreen> {
  final _searchController = TextEditingController();
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
    }
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _applyPreset(EntryFilterPreset preset) {
    _tag = preset.tag;
    _group = preset.group;
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

    return Scaffold(
      backgroundColor: Colors.transparent,
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _createEntry,
        icon: const Icon(Icons.add),
        label: const Text('新建条目'),
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _EntriesHeader(total: entries.asData?.value.total),
          _FilterBar(
            searchController: _searchController,
            selectedTag: _tag,
            selectedGroup: _group,
            starred: _starred,
            tags: tags,
            groups: groups,
            onSearchChanged: _onSearchChanged,
            onTagChanged: (value) => setState(() {
              _tag = value;
              _page = 1;
            }),
            onGroupChanged: (value) => setState(() {
              _group = value;
              _page = 1;
            }),
            onStarredChanged: (value) => setState(() {
              _starred = value;
              _page = 1;
            }),
            onClear: _hasFilters ? _clearFilters : null,
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
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(14, 14, 14, 96),
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
                      icon: const Icon(Icons.filter_alt_off),
                      label: const Text('清除筛选'),
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
              onPageChanged: (value) => setState(() => _page = value),
              onPageSizeChanged: (value) {
                ref.read(preferencesProvider.notifier).setEntryPageSize(value);
                setState(() => _page = 1);
              },
            );
          }
          final entry = page.items[index];
          return Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 980),
              child: Padding(
                padding: const EdgeInsets.only(bottom: 10),
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
      }
    });
  }

  void _clearFilters() {
    _searchDebounce?.cancel();
    _searchController.clear();
    setState(() {
      _search = '';
      _tag = null;
      _group = null;
      _starred = false;
      _page = 1;
    });
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

class _EntriesHeader extends StatelessWidget {
  const _EntriesHeader({required this.total});

  final int? total;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 17, 20, 13),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '全部条目',
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
            ),
          ),
          if (total != null)
            Text(
              '$total 条',
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
        ],
      ),
    );
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
  final VoidCallback? onClear;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surface,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 980),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  controller: searchController,
                  onChanged: onSearchChanged,
                  decoration: InputDecoration(
                    hintText: '搜索名称、字段、标签或密码组',
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon: searchController.text.isEmpty
                        ? null
                        : IconButton(
                            tooltip: '清空搜索',
                            onPressed: () {
                              searchController.clear();
                              onSearchChanged('');
                            },
                            icon: const Icon(Icons.close),
                          ),
                  ),
                ),
                const SizedBox(height: 9),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    _FilterDropdown(
                      icon: Icons.sell_outlined,
                      label: selectedTag ?? '全部标签',
                      value: selectedTag,
                      items: tags.map((item) => item.name).toList(),
                      onChanged: onTagChanged,
                    ),
                    _FilterDropdown(
                      icon: Icons.folder_outlined,
                      label: selectedGroup ?? '全部密码组',
                      value: selectedGroup,
                      items: groups.map((item) => item.name).toList(),
                      onChanged: onGroupChanged,
                    ),
                    FilterChip(
                      selected: starred,
                      avatar: Icon(
                        starred ? Icons.star_rounded : Icons.star_outline,
                        size: 17,
                      ),
                      label: const Text('仅收藏'),
                      onSelected: onStarredChanged,
                    ),
                    if (onClear != null)
                      TextButton.icon(
                        onPressed: onClear,
                        icon: const Icon(Icons.filter_alt_off, size: 17),
                        label: const Text('清除'),
                      ),
                  ],
                ),
              ],
            ),
          ),
        ),
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
    return PopupMenuButton<String?>(
      tooltip: label,
      initialValue: value,
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
        constraints: const BoxConstraints(maxWidth: 190),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          border: Border.all(
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 17),
            const SizedBox(width: 6),
            Flexible(
              child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis),
            ),
            const SizedBox(width: 5),
            const Icon(Icons.arrow_drop_down, size: 18),
          ],
        ),
      ),
    );
  }
}
