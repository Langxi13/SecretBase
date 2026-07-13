import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/taxonomy/taxonomy_editor_dialog.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart';
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
  List<TaxonomyRecord> _ordered = [];

  @override
  Widget build(BuildContext context) {
    final groups = ref.watch(taxonomyProvider('groups'));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _GroupsHeader(
          reordering: _reordering,
          saving: _savingOrder,
          hasGroups: groups.asData?.value.isNotEmpty ?? false,
          onCreate: _create,
          onRestoreDefault: _restoreDefault,
          onToggleOrder: () =>
              _toggleOrdering(groups.asData?.value ?? const []),
          onSaveOrder: _saveOrder,
        ),
        const Divider(height: 1),
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
              return _buildGrid(items);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildGrid(List<TaxonomyRecord> groups) {
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(taxonomyProvider('groups'));
        await ref.read(taxonomyProvider('groups').future);
      },
      child: GridView.builder(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(14, 14, 14, 90),
        gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
          maxCrossAxisExtent: 430,
          mainAxisExtent: 178,
          crossAxisSpacing: 11,
          mainAxisSpacing: 11,
        ),
        itemCount: groups.length,
        itemBuilder: (context, index) {
          final group = groups[index];
          return _GroupCard(
            group: group,
            onOpen: () => widget.onOpenGroup(group.name),
            onEdit: () => _edit(group),
            onDelete: () => _delete(group),
          );
        },
      ),
    );
  }

  Widget _buildReorderList() {
    return ReorderableListView.builder(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 90),
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
          padding: const EdgeInsets.only(bottom: 8),
          child: Material(
            color: Theme.of(context).colorScheme.surface,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(6),
              side: BorderSide(
                color: Theme.of(context).colorScheme.outlineVariant,
              ),
            ),
            child: ListTile(
              leading: CircleAvatar(radius: 17, child: Text('${index + 1}')),
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
    required this.onCreate,
    required this.onRestoreDefault,
    required this.onToggleOrder,
    required this.onSaveOrder,
  });

  final bool reordering;
  final bool saving;
  final bool hasGroups;
  final VoidCallback onCreate;
  final VoidCallback onRestoreDefault;
  final VoidCallback onToggleOrder;
  final VoidCallback onSaveOrder;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 14, 14, 12),
      child: Row(
        children: [
          Expanded(
            child: Text(
              reordering ? '调整密码组顺序' : '密码组',
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
            ),
          ),
          if (reordering) ...[
            TextButton(
              onPressed: saving ? null : onToggleOrder,
              child: const Text('取消'),
            ),
            const SizedBox(width: 6),
            FilledButton.icon(
              onPressed: saving ? null : onSaveOrder,
              icon: const Icon(Icons.save_outlined, size: 17),
              label: Text(saving ? '保存中' : '保存顺序'),
            ),
          ] else ...[
            if (hasGroups)
              IconButton(
                tooltip: '调整顺序',
                onPressed: onToggleOrder,
                icon: const Icon(Icons.swap_vert),
              ),
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
            const SizedBox(width: 4),
            FilledButton.icon(
              onPressed: onCreate,
              icon: const Icon(Icons.create_new_folder_outlined, size: 18),
              label: const Text('新建密码组'),
            ),
          ],
        ],
      ),
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
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onOpen,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Container(
                    width: 38,
                    height: 38,
                    decoration: BoxDecoration(
                      color: scheme.tertiaryContainer,
                      borderRadius: BorderRadius.circular(7),
                    ),
                    child: Icon(
                      Icons.folder,
                      color: scheme.onTertiaryContainer,
                    ),
                  ),
                  const SizedBox(width: 11),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          group.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.titleMedium
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
                ],
              ),
              const SizedBox(height: 12),
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
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  _SmallAction(
                    tooltip: '查看条目',
                    icon: Icons.arrow_forward,
                    color: scheme.primary,
                    onPressed: onOpen,
                  ),
                  const SizedBox(width: 7),
                  _SmallAction(
                    tooltip: '编辑密码组',
                    icon: Icons.edit_outlined,
                    color: scheme.tertiary,
                    onPressed: onEdit,
                  ),
                  const SizedBox(width: 7),
                  _SmallAction(
                    tooltip: '删除密码组',
                    icon: Icons.delete_outline,
                    color: scheme.error,
                    onPressed: onDelete,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SmallAction extends StatelessWidget {
  const _SmallAction({
    required this.tooltip,
    required this.icon,
    required this.color,
    required this.onPressed,
  });

  final String tooltip;
  final IconData icon;
  final Color color;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: tooltip,
      onPressed: onPressed,
      icon: Icon(icon, size: 17),
      color: color,
      style: IconButton.styleFrom(
        backgroundColor: color.withValues(alpha: 0.09),
        fixedSize: const Size(32, 32),
        minimumSize: const Size(32, 32),
        padding: EdgeInsets.zero,
      ),
    );
  }
}
