import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/core/widgets/mobile_chrome.dart';
import 'package:secretbase/src/core/widgets/paged_scroll.dart';
import 'package:secretbase/src/core/widgets/page_controls.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/taxonomy/taxonomy_editor_dialog.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/preferences_controller.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class TagsScreen extends ConsumerStatefulWidget {
  const TagsScreen({required this.onOpenTag, super.key});

  final ValueChanged<String> onOpenTag;

  @override
  ConsumerState<TagsScreen> createState() => _TagsScreenState();
}

class _TagsScreenState extends ConsumerState<TagsScreen> {
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();
  final Set<String> _selected = {};
  int _page = 1;
  String _search = '';
  bool _selectionMode = false;
  bool _deleting = false;

  @override
  void dispose() {
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tags = ref.watch(taxonomyProvider('tags'));
    final pageSize = ref.watch(
      preferencesProvider.select((preferences) => preferences.taxonomyPageSize),
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _TagsHeader(
          selectionMode: _selectionMode,
          selectedCount: _selected.length,
          totalCount: tags.asData?.value.length ?? 0,
          deleting: _deleting,
          onCreate: _create,
          onToggleSelection: _toggleSelectionMode,
          onDeleteSelected: _deleteSelected,
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 7, 12, 8),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 920),
              child: TextField(
                controller: _searchController,
                onChanged: (value) {
                  setState(() {
                    _search = value.trim();
                    _page = 1;
                  });
                  resetPagedScroll(_scrollController);
                },
                decoration: InputDecoration(
                  isDense: true,
                  hintText: '筛选标签',
                  prefixIcon: const Icon(Icons.search, size: 20),
                  prefixIconConstraints: const BoxConstraints(
                    minWidth: 40,
                    minHeight: 40,
                  ),
                  suffixIcon: _search.isEmpty
                      ? null
                      : IconButton(
                          tooltip: '清空筛选',
                          onPressed: () {
                            _searchController.clear();
                            setState(() {
                              _search = '';
                              _page = 1;
                            });
                            resetPagedScroll(_scrollController);
                          },
                          icon: const Icon(Icons.close),
                        ),
                ),
              ),
            ),
          ),
        ),
        Expanded(
          child: tags.when(
            loading: () => const LoadingView(label: '正在加载标签'),
            error: (error, stackTrace) => ErrorView(
              message: mobileErrorMessage(error),
              onRetry: () => ref.invalidate(taxonomyProvider('tags')),
            ),
            data: (items) => _buildPage(items, pageSize),
          ),
        ),
      ],
    );
  }

  Widget _buildPage(List<TaxonomyRecord> items, int pageSize) {
    final filtered = items.where((item) {
      final query = _search.toLowerCase();
      return query.isEmpty ||
          item.name.toLowerCase().contains(query) ||
          item.description.toLowerCase().contains(query);
    }).toList();
    final totalPages = math.max(
      1,
      (filtered.length + pageSize - 1) ~/ pageSize,
    );
    final currentPage = _page.clamp(1, totalPages);
    if (currentPage != _page) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) setState(() => _page = currentPage);
      });
    }
    final start = (currentPage - 1) * pageSize;
    final pageItems = filtered.skip(start).take(pageSize).toList();

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(taxonomyProvider('tags'));
        await ref.read(taxonomyProvider('tags').future);
      },
      child: ListView.builder(
        controller: _scrollController,
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(12, 3, 12, 84),
        itemCount: pageItems.isEmpty ? 1 : pageItems.length + 1,
        itemBuilder: (context, index) {
          if (pageItems.isEmpty) {
            return EmptyView(
              icon: Icons.sell_outlined,
              title: _search.isEmpty ? '还没有标签' : '没有匹配的标签',
              action: _search.isEmpty
                  ? FilledButton.icon(
                      onPressed: _create,
                      icon: const Icon(Icons.add),
                      label: const Text('新建标签'),
                    )
                  : null,
            );
          }
          if (index == pageItems.length) {
            return PageControls(
              page: currentPage,
              totalPages: totalPages,
              pageSize: pageSize,
              onPageChanged: (value) {
                setState(() => _page = value);
                resetPagedScroll(_scrollController);
              },
              onPageSizeChanged: (value) {
                ref
                    .read(preferencesProvider.notifier)
                    .setTaxonomyPageSize(value);
                setState(() => _page = 1);
                resetPagedScroll(_scrollController);
              },
            );
          }
          final tag = pageItems[index];
          return Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 920),
              child: Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _TagRow(
                  tag: tag,
                  selectionMode: _selectionMode,
                  selected: _selected.contains(tag.name),
                  onSelected: (value) => setState(() {
                    if (value) {
                      _selected.add(tag.name);
                    } else {
                      _selected.remove(tag.name);
                    }
                  }),
                  onOpen: () => widget.onOpenTag(tag.name),
                  onEdit: () => _edit(tag),
                  onDelete: () => _deleteOne(tag),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  void _toggleSelectionMode() {
    setState(() {
      _selectionMode = !_selectionMode;
      if (!_selectionMode) _selected.clear();
    });
  }

  Future<void> _create() async {
    final message = await showTaxonomyEditorDialog(
      context: context,
      ref: ref,
      kind: 'tags',
    );
    if (message != null && mounted) _showMessage(message);
  }

  Future<void> _edit(TaxonomyRecord tag) async {
    final message = await showTaxonomyEditorDialog(
      context: context,
      ref: ref,
      kind: 'tags',
      existing: tag,
    );
    if (message != null && mounted) _showMessage(message);
  }

  Future<void> _deleteOne(TaxonomyRecord tag) async {
    try {
      final message = await deleteTaxonomy(
        context: context,
        ref: ref,
        kind: 'tags',
        name: tag.name,
      );
      if (message != null && mounted) _showMessage(message);
    } catch (error) {
      if (mounted) _showMessage(mobileErrorMessage(error));
    }
  }

  Future<void> _deleteSelected() async {
    if (_selected.isEmpty) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('批量删除标签'),
        content: Text('确认删除选中的 ${_selected.length} 个标签？条目本身不会被删除。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('取消'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('批量删除'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _deleting = true);
    try {
      final result = await rust_api.deleteTaxonomies(
        kind: 'tags',
        names: _selected.toList(),
        expectedRevision: ref.read(vaultControllerProvider).revision,
      );
      await ref.read(vaultControllerProvider.notifier).refreshStatus();
      ref.invalidate(taxonomyProvider);
      ref.invalidate(entryPageProvider);
      if (mounted) {
        setState(() {
          _deleting = false;
          _selectionMode = false;
          _selected.clear();
        });
        _showMessage(result.message);
      }
    } catch (error) {
      if (mounted) {
        setState(() => _deleting = false);
        _showMessage(mobileErrorMessage(error));
      }
    }
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }
}

class _TagsHeader extends StatelessWidget {
  const _TagsHeader({
    required this.selectionMode,
    required this.selectedCount,
    required this.totalCount,
    required this.deleting,
    required this.onCreate,
    required this.onToggleSelection,
    required this.onDeleteSelected,
  });

  final bool selectionMode;
  final int selectedCount;
  final int totalCount;
  final bool deleting;
  final VoidCallback onCreate;
  final VoidCallback onToggleSelection;
  final VoidCallback onDeleteSelected;

  @override
  Widget build(BuildContext context) {
    return MobilePageHeader(
      title: selectionMode ? '批量管理标签' : '标签管理',
      subtitle: selectionMode ? '已选择 $selectedCount 个' : '共 $totalCount 个标签',
      actions: selectionMode
          ? [
              IconButton(
                tooltip: '取消批量管理',
                onPressed: deleting ? null : onToggleSelection,
                icon: const Icon(Icons.close),
              ),
              IconButton.filled(
                tooltip: deleting ? '正在删除' : '删除所选标签',
                onPressed: selectedCount == 0 || deleting
                    ? null
                    : onDeleteSelected,
                style: IconButton.styleFrom(
                  backgroundColor: Theme.of(context).colorScheme.error,
                  foregroundColor: Theme.of(context).colorScheme.onError,
                ),
                icon: deleting
                    ? const SizedBox(
                        width: 17,
                        height: 17,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.delete_outline),
              ),
            ]
          : [
              IconButton(
                tooltip: '批量管理',
                onPressed: onToggleSelection,
                icon: const Icon(Icons.checklist),
              ),
              IconButton.filled(
                tooltip: '新建标签',
                onPressed: onCreate,
                icon: const Icon(Icons.add),
              ),
            ],
    );
  }
}

class _TagRow extends StatelessWidget {
  const _TagRow({
    required this.tag,
    required this.selectionMode,
    required this.selected,
    required this.onSelected,
    required this.onOpen,
    required this.onEdit,
    required this.onDelete,
  });

  final TaxonomyRecord tag;
  final bool selectionMode;
  final bool selected;
  final ValueChanged<bool> onSelected;
  final VoidCallback onOpen;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final color = _parseColor(tag.color);
    final scheme = Theme.of(context).colorScheme;
    return Card(
      color: selected ? scheme.primaryContainer : scheme.surface,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: selectionMode ? () => onSelected(!selected) : onOpen,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(10, 7, 6, 7),
          child: Row(
            children: [
              if (selectionMode) ...[
                Checkbox(
                  value: selected,
                  onChanged: (value) => onSelected(value ?? false),
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  visualDensity: VisualDensity.compact,
                ),
                const SizedBox(width: 5),
              ],
              Container(
                width: 8,
                height: 38,
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            tag.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.titleSmall
                                ?.copyWith(fontWeight: FontWeight.w800),
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          '${tag.count} 条',
                          style: Theme.of(context).textTheme.labelMedium
                              ?.copyWith(color: scheme.onSurfaceVariant),
                        ),
                      ],
                    ),
                    if (tag.description.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        tag.description,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (!selectionMode)
                MobileManageButton(
                  label: '编辑/删除',
                  tooltip: '管理标签',
                  onPressed: () => _showActions(context),
                ),
            ],
          ),
        ),
      ),
    );
  }

  static Color _parseColor(String value) {
    final normalized = RegExp(r'^#[0-9a-fA-F]{6}$').hasMatch(value)
        ? value.substring(1)
        : '087f8c';
    return Color(int.parse(normalized, radix: 16) | 0xFF000000);
  }

  Future<void> _showActions(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return showMobileActionSheet(
      context: context,
      title: tag.name,
      actions: [
        MobileAction(
          label: '查看标签条目',
          subtitle: '切换到已筛选的全部条目视图',
          icon: Icons.arrow_forward,
          color: scheme.primary,
          onPressed: onOpen,
        ),
        MobileAction(
          label: '编辑标签',
          icon: Icons.edit_outlined,
          color: scheme.tertiary,
          onPressed: onEdit,
        ),
        MobileAction(
          label: '删除标签',
          icon: Icons.delete_outline,
          color: scheme.error,
          onPressed: onDelete,
        ),
      ],
    );
  }
}
