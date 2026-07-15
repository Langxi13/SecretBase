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

class GroupsScreen extends ConsumerStatefulWidget {
  const GroupsScreen({required this.onOpenGroup, super.key});

  final ValueChanged<String> onOpenGroup;

  @override
  ConsumerState<GroupsScreen> createState() => _GroupsScreenState();
}

class _GroupsScreenState extends ConsumerState<GroupsScreen> {
  bool _reordering = false;
  bool _savingOrder = false;
  final _scrollController = ScrollController();
  int _page = 1;
  List<TaxonomyRecord> _ordered = [];

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final groups = ref.watch(taxonomyProvider('groups'));
    final pageSize = ref.watch(
      preferencesProvider.select((preferences) => preferences.groupPageSize),
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _GroupsHeader(
          reordering: _reordering,
          saving: _savingOrder,
          hasGroups: groups.asData?.value.isNotEmpty ?? false,
          groupCount: groups.asData?.value.length ?? 0,
          onCreate: _create,
          onRestoreDefault: _restoreDefault,
          onToggleOrder: () =>
              _toggleOrdering(groups.asData?.value ?? const []),
          onSaveOrder: _saveOrder,
        ),
        Expanded(
          child: groups.when(
            loading: () => const LoadingView(label: '正在加载密码组'),
            error: (error, stackTrace) => ErrorView(
              message: mobileErrorMessage(error),
              onRetry: () => ref.invalidate(taxonomyProvider('groups')),
            ),
            data: (items) {
              if (items.isEmpty) {
                return EmptyView(
                  icon: Icons.folder_outlined,
                  title: '还没有密码组',
                  action: FilledButton.icon(
                    onPressed: _create,
                    icon: const Icon(Icons.create_new_folder_outlined),
                    label: const Text('新建密码组'),
                  ),
                );
              }
              if (_reordering) return _buildReorderList();
              return _buildGrid(items, pageSize);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildGrid(List<TaxonomyRecord> groups, int pageSize) {
    final totalPages = math.max(1, (groups.length + pageSize - 1) ~/ pageSize);
    final currentPage = _page.clamp(1, totalPages);
    if (currentPage != _page) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) setState(() => _page = currentPage);
      });
    }
    final start = (currentPage - 1) * pageSize;
    final pageItems = groups.skip(start).take(pageSize).toList();

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(taxonomyProvider('groups'));
        await ref.read(taxonomyProvider('groups').future);
      },
      child: CustomScrollView(
        controller: _scrollController,
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
            sliver: SliverGrid(
              gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                maxCrossAxisExtent: 430,
                mainAxisExtent: 132,
                crossAxisSpacing: 9,
                mainAxisSpacing: 9,
              ),
              delegate: SliverChildBuilderDelegate((context, index) {
                final group = pageItems[index];
                return _GroupCard(
                  group: group,
                  onOpen: () => widget.onOpenGroup(group.name),
                  onEdit: () => _edit(group),
                  onDelete: () => _delete(group),
                );
              }, childCount: pageItems.length),
            ),
          ),
          SliverToBoxAdapter(
            child: PageControls(
              page: currentPage,
              totalPages: totalPages,
              pageSize: pageSize,
              onPageChanged: (value) {
                setState(() => _page = value);
                resetPagedScroll(_scrollController);
              },
              onPageSizeChanged: (value) {
                ref.read(preferencesProvider.notifier).setGroupPageSize(value);
                setState(() => _page = 1);
                resetPagedScroll(_scrollController);
              },
            ),
          ),
          const SliverToBoxAdapter(child: SizedBox(height: 78)),
        ],
      ),
    );
  }

  Widget _buildReorderList() {
    return ReorderableListView.builder(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 86),
      buildDefaultDragHandles: false,
      itemCount: _ordered.length,
      onReorderItem: (oldIndex, newIndex) {
        setState(() {
          final item = _ordered.removeAt(oldIndex);
          _ordered.insert(newIndex, item);
        });
      },
      itemBuilder: (context, index) {
        final item = _ordered[index];
        return Padding(
          key: ValueKey(item.name),
          padding: const EdgeInsets.only(bottom: 6),
          child: Material(
            color: Theme.of(context).colorScheme.surface,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
              side: BorderSide(
                color: Theme.of(context).colorScheme.outlineVariant,
              ),
            ),
            child: ListTile(
              leading: CircleAvatar(radius: 15, child: Text('${index + 1}')),
              title: Text(
                item.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              subtitle: Text('${item.count} 个条目'),
              trailing: ReorderableDragStartListener(
                index: index,
                child: const Tooltip(
                  message: '拖动调整顺序',
                  child: Padding(
                    padding: EdgeInsets.all(10),
                    child: Icon(Icons.drag_handle),
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  void _toggleOrdering(List<TaxonomyRecord> groups) {
    setState(() {
      if (_reordering) {
        _reordering = false;
        _ordered = [];
      } else {
        _ordered = [...groups];
        _reordering = true;
      }
    });
  }

  Future<void> _saveOrder() async {
    if (_savingOrder) return;
    setState(() => _savingOrder = true);
    try {
      final result = await rust_api.saveGroupOrder(
        names: _ordered.map((item) => item.name).toList(),
        expectedRevision: ref.read(vaultControllerProvider).revision,
      );
      await ref.read(vaultControllerProvider.notifier).refreshStatus();
      ref.invalidate(taxonomyProvider('groups'));
      if (mounted) {
        setState(() {
          _savingOrder = false;
          _reordering = false;
          _ordered = [];
        });
        _showMessage(result.message);
      }
    } catch (error) {
      if (mounted) {
        setState(() => _savingOrder = false);
        _showMessage(mobileErrorMessage(error));
      }
    }
  }

  Future<void> _restoreDefault() async {
    if (_savingOrder) return;
    setState(() => _savingOrder = true);
    try {
      final result = await rust_api.saveGroupOrder(
        names: const [],
        expectedRevision: ref.read(vaultControllerProvider).revision,
      );
      await ref.read(vaultControllerProvider.notifier).refreshStatus();
      ref.invalidate(taxonomyProvider('groups'));
      if (mounted) _showMessage(result.message);
    } catch (error) {
      if (mounted) _showMessage(mobileErrorMessage(error));
    } finally {
      if (mounted) setState(() => _savingOrder = false);
    }
  }

  Future<void> _create() async {
    final message = await showTaxonomyEditorDialog(
      context: context,
      ref: ref,
      kind: 'groups',
    );
    if (message != null && mounted) _showMessage(message);
  }

  Future<void> _edit(TaxonomyRecord group) async {
    final message = await showTaxonomyEditorDialog(
      context: context,
      ref: ref,
      kind: 'groups',
      existing: group,
    );
    if (message != null && mounted) _showMessage(message);
  }

  Future<void> _delete(TaxonomyRecord group) async {
    try {
      final message = await deleteTaxonomy(
        context: context,
        ref: ref,
        kind: 'groups',
        name: group.name,
      );
      if (message != null && mounted) _showMessage(message);
    } catch (error) {
      if (mounted) _showMessage(mobileErrorMessage(error));
    }
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }
}

class _GroupsHeader extends StatelessWidget {
  const _GroupsHeader({
    required this.reordering,
    required this.saving,
    required this.hasGroups,
    required this.groupCount,
    required this.onCreate,
    required this.onRestoreDefault,
    required this.onToggleOrder,
    required this.onSaveOrder,
  });

  final bool reordering;
  final bool saving;
  final bool hasGroups;
  final int groupCount;
  final VoidCallback onCreate;
  final VoidCallback onRestoreDefault;
  final VoidCallback onToggleOrder;
  final VoidCallback onSaveOrder;

  @override
  Widget build(BuildContext context) {
    return MobilePageHeader(
      title: reordering ? '调整密码组顺序' : '密码组',
      subtitle: reordering ? '拖动右侧把手后保存' : '共 $groupCount 个密码组',
      actions: reordering
          ? [
              IconButton(
                tooltip: '取消排序',
                onPressed: saving ? null : onToggleOrder,
                icon: const Icon(Icons.close),
              ),
              IconButton.filled(
                tooltip: saving ? '正在保存' : '保存排序',
                onPressed: saving ? null : onSaveOrder,
                icon: saving
                    ? const SizedBox(
                        width: 17,
                        height: 17,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.check),
              ),
            ]
          : [
              if (hasGroups)
                IconButton(
                  tooltip: '调整顺序',
                  onPressed: saving ? null : onToggleOrder,
                  icon: const Icon(Icons.swap_vert),
                ),
              if (saving)
                const Padding(
                  padding: EdgeInsets.all(12),
                  child: SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                )
              else
                PopupMenuButton<String>(
                  tooltip: '更多操作',
                  onSelected: (value) {
                    if (value == 'restore') onRestoreDefault();
                  },
                  itemBuilder: (context) => const [
                    PopupMenuItem(
                      value: 'restore',
                      child: ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(Icons.restart_alt),
                        title: Text('恢复默认排序'),
                      ),
                    ),
                  ],
                ),
              IconButton.filled(
                tooltip: '新建密码组',
                onPressed: saving ? null : onCreate,
                icon: const Icon(Icons.create_new_folder_outlined),
              ),
            ],
    );
  }
}

class _GroupCard extends StatelessWidget {
  const _GroupCard({
    required this.group,
    required this.onOpen,
    required this.onEdit,
    required this.onDelete,
  });

  final TaxonomyRecord group;
  final VoidCallback onOpen;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final accent = _parseColor(group.color, scheme.tertiary);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onOpen,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(11, 10, 7, 9),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Container(
                    width: 34,
                    height: 34,
                    decoration: BoxDecoration(
                      color: accent.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(7),
                    ),
                    child: Icon(Icons.folder, size: 19, color: accent),
                  ),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          group.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.titleSmall
                              ?.copyWith(fontWeight: FontWeight.w800),
                        ),
                        Text(
                          '${group.count} 个条目',
                          style: Theme.of(context).textTheme.bodySmall
                              ?.copyWith(color: scheme.onSurfaceVariant),
                        ),
                      ],
                    ),
                  ),
                  MobileManageButton(
                    label: '编辑/删除',
                    tooltip: '管理密码组',
                    onPressed: () => _showActions(context),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Expanded(
                child: Text(
                  group.description.isEmpty ? '暂无简介' : group.description,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: group.description.isEmpty
                        ? scheme.onSurfaceVariant
                        : scheme.onSurface,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _showActions(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return showMobileActionSheet(
      context: context,
      title: group.name,
      actions: [
        MobileAction(
          label: '查看组内条目',
          subtitle: '切换到已筛选的全部条目视图',
          icon: Icons.arrow_forward,
          color: scheme.primary,
          onPressed: onOpen,
        ),
        MobileAction(
          label: '编辑密码组',
          icon: Icons.edit_outlined,
          color: scheme.tertiary,
          onPressed: onEdit,
        ),
        MobileAction(
          label: '删除密码组',
          subtitle: '移除组关系，不会删除其中的条目',
          icon: Icons.delete_outline,
          color: scheme.error,
          onPressed: onDelete,
        ),
      ],
    );
  }

  static Color _parseColor(String value, Color fallback) {
    if (!RegExp(r'^#[0-9a-fA-F]{6}$').hasMatch(value)) return fallback;
    return Color(int.parse(value.substring(1), radix: 16) | 0xFF000000);
  }
}
