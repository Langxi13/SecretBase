import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/secure_clipboard.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/entries/entry_editor_dialog.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/vault_controller.dart';

Future<String?> showEntryDetailDialog({
  required BuildContext context,
  required WidgetRef ref,
  required String entryId,
}) {
  return showResponsiveDialog<String>(
    context: context,
    maxWidth: 880,
    builder: (_) => EntryDetailDialog(entryId: entryId, ref: ref),
  );
}

class EntryDetailDialog extends StatefulWidget {
  const EntryDetailDialog({
    required this.entryId,
    required this.ref,
    super.key,
  });

  final String entryId;
  final WidgetRef ref;

  @override
  State<EntryDetailDialog> createState() => _EntryDetailDialogState();
}

class _EntryDetailDialogState extends State<EntryDetailDialog> {
  late Future<EntryRecord> _entryFuture;
  final Set<int> _revealedFields = {};
  bool _mutating = false;

  @override
  void initState() {
    super.initState();
    _entryFuture = rust_api.getEntry(id: widget.entryId);
  }

  void _reload() {
    setState(() {
      _revealedFields.clear();
      _entryFuture = rust_api.getEntry(id: widget.entryId);
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<EntryRecord>(
      future: _entryFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const DialogFrame(
            title: '条目详情',
            child: LoadingView(label: '正在读取条目详情'),
          );
        }
        if (snapshot.hasError || snapshot.data == null) {
          return DialogFrame(
            title: '条目详情',
            child: ErrorView(
              message: snapshot.error == null
                  ? '条目不存在'
                  : mobileErrorMessage(snapshot.error!),
              onRetry: _reload,
            ),
          );
        }
        return _buildEntry(snapshot.data!);
      },
    );
  }

  Widget _buildEntry(EntryRecord entry) {
    return DialogFrame(
      title: entry.title,
      canClose: !_mutating,
      actions: [
        if (!entry.deleted) ...[
          IconButton(
            tooltip: '在此基础上新建',
            onPressed: _mutating ? null : () => _duplicate(entry),
            icon: const Icon(Icons.copy_all_outlined),
          ),
        ],
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_mutating) const LinearProgressIndicator(minHeight: 2),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(14, 14, 14, 22),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _EntryHeading(
                    entry: entry,
                    onCopyUrl: () => _copy(entry.url),
                  ),
                  if (entry.fields.isNotEmpty) ...[
                    const SizedBox(height: 18),
                    const _DetailSectionTitle(
                      icon: Icons.view_list_outlined,
                      title: '自定义字段',
                    ),
                    const SizedBox(height: 9),
                    Container(
                      decoration: BoxDecoration(
                        border: Border.all(
                          color: Theme.of(context).colorScheme.outlineVariant,
                        ),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Column(
                        children: List.generate(entry.fields.length, (index) {
                          final field = entry.fields[index];
                          return Column(
                            children: [
                              if (index > 0) const Divider(height: 1),
                              _FieldDetailRow(
                                field: field,
                                revealed: _revealedFields.contains(index),
                                onReveal: field.hidden
                                    ? () => setState(() {
                                        if (!_revealedFields.add(index)) {
                                          _revealedFields.remove(index);
                                        }
                                      })
                                    : null,
                                onCopy: field.copyable
                                    ? () => _copy(field.value)
                                    : null,
                              ),
                            ],
                          );
                        }),
                      ),
                    ),
                  ],
                  if (entry.tags.isNotEmpty || entry.groups.isNotEmpty) ...[
                    const SizedBox(height: 18),
                    const _DetailSectionTitle(
                      icon: Icons.category_outlined,
                      title: '分类',
                    ),
                    const SizedBox(height: 9),
                    Wrap(
                      spacing: 7,
                      runSpacing: 7,
                      children: [
                        ...entry.groups.map(
                          (name) => Chip(
                            avatar: const Icon(Icons.folder_outlined, size: 16),
                            label: Text(name),
                          ),
                        ),
                        ...entry.tags.map(
                          (name) => Chip(
                            avatar: const Icon(Icons.sell_outlined, size: 15),
                            label: Text(name),
                          ),
                        ),
                      ],
                    ),
                  ],
                  if (entry.remarks.isNotEmpty) ...[
                    const SizedBox(height: 18),
                    const _DetailSectionTitle(
                      icon: Icons.notes_outlined,
                      title: '备注',
                    ),
                    const SizedBox(height: 9),
                    SelectableText(
                      entry.remarks,
                      style: Theme.of(
                        context,
                      ).textTheme.bodyLarge?.copyWith(height: 1.55),
                    ),
                  ],
                  const SizedBox(height: 18),
                  _Metadata(entry: entry),
                ],
              ),
            ),
          ),
          const Divider(height: 1),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 11, 16, 13),
              child: entry.deleted
                  ? Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: _mutating ? null : () => _purge(entry),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: Theme.of(
                                context,
                              ).colorScheme.error,
                            ),
                            icon: const Icon(Icons.delete_forever_outlined),
                            label: const Text('彻底删除'),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: FilledButton.icon(
                            onPressed: _mutating ? null : () => _restore(entry),
                            icon: const Icon(Icons.restore),
                            label: const Text('恢复条目'),
                          ),
                        ),
                      ],
                    )
                  : Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        TextButton.icon(
                          onPressed: _mutating ? null : () => _trash(entry),
                          style: TextButton.styleFrom(
                            foregroundColor: Theme.of(
                              context,
                            ).colorScheme.error,
                          ),
                          icon: const Icon(Icons.delete_outline),
                          label: const Text('移入回收站'),
                        ),
                        FilledButton.icon(
                          onPressed: _mutating ? null : () => _edit(entry),
                          icon: const Icon(Icons.edit_outlined),
                          label: const Text('编辑'),
                        ),
                      ],
                    ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _copy(String value) async {
    if (value.isEmpty) return;
    await copySensitiveValue(widget.ref, value);
    if (mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('已复制，将按设置自动清理剪贴板')));
    }
  }

  Future<void> _edit(EntryRecord entry) async {
    final message = await showEntryEditorDialog(
      context: context,
      ref: widget.ref,
      source: entry,
    );
    if (message != null && mounted) {
      _reload();
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
    }
  }

  Future<void> _duplicate(EntryRecord entry) async {
    final message = await showEntryEditorDialog(
      context: context,
      ref: widget.ref,
      source: entry,
      duplicate: true,
    );
    if (message != null && mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
    }
  }

  Future<void> _trash(EntryRecord entry) async {
    final confirmed = await _confirm(
      title: '移入回收站',
      message: '确认将“${entry.title}”移入回收站？',
      action: '移入回收站',
    );
    if (confirmed) {
      await _runMutation(
        () => rust_api.trashEntry(
          id: entry.id,
          expectedRevision: widget.ref.read(vaultControllerProvider).revision,
        ),
      );
    }
  }

  Future<void> _restore(EntryRecord entry) async {
    await _runMutation(
      () => rust_api.restoreEntry(
        id: entry.id,
        expectedRevision: widget.ref.read(vaultControllerProvider).revision,
      ),
    );
  }

  Future<void> _purge(EntryRecord entry) async {
    final confirmed = await _confirm(
      title: '彻底删除条目',
      message: '此操作无法撤销。确认彻底删除“${entry.title}”？',
      action: '彻底删除',
      destructive: true,
    );
    if (confirmed) {
      await _runMutation(
        () => rust_api.purgeEntry(
          id: entry.id,
          expectedRevision: widget.ref.read(vaultControllerProvider).revision,
        ),
      );
    }
  }

  Future<void> _runMutation(
    Future<OperationResult> Function() operation,
  ) async {
    if (_mutating) return;
    setState(() => _mutating = true);
    try {
      final result = await operation();
      await widget.ref.read(vaultControllerProvider.notifier).refreshStatus();
      widget.ref.invalidate(entryPageProvider);
      widget.ref.invalidate(taxonomyProvider);
      if (mounted) Navigator.of(context).pop(result.message);
    } catch (error) {
      if (!mounted) return;
      setState(() => _mutating = false);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(mobileErrorMessage(error))));
    }
  }

  Future<bool> _confirm({
    required String title,
    required String message,
    required String action,
    bool destructive = false,
  }) async {
    return await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(title),
            content: Text(message),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('取消'),
              ),
              FilledButton(
                style: destructive
                    ? FilledButton.styleFrom(
                        backgroundColor: Theme.of(context).colorScheme.error,
                      )
                    : null,
                onPressed: () => Navigator.of(context).pop(true),
                child: Text(action),
              ),
            ],
          ),
        ) ??
        false;
  }
}

class _EntryHeading extends StatelessWidget {
  const _EntryHeading({required this.entry, required this.onCopyUrl});

  final EntryRecord entry;
  final VoidCallback onCopyUrl;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(
                entry.starred ? Icons.star_rounded : Icons.key_outlined,
                color: entry.starred ? scheme.secondary : scheme.primary,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  entry.starred ? '已收藏条目' : '条目概览',
                  style: Theme.of(
                    context,
                  ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
          if (entry.url.isNotEmpty) ...[
            const SizedBox(height: 11),
            Row(
              children: [
                Expanded(
                  child: SelectableText(
                    entry.url,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: scheme.primary,
                      height: 1.4,
                    ),
                  ),
                ),
                IconButton(
                  tooltip: '复制网址',
                  onPressed: onCopyUrl,
                  icon: const Icon(Icons.copy_outlined, size: 19),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _FieldDetailRow extends StatelessWidget {
  const _FieldDetailRow({
    required this.field,
    required this.revealed,
    this.onReveal,
    this.onCopy,
  });

  final FieldRecord field;
  final bool revealed;
  final VoidCallback? onReveal;
  final VoidCallback? onCopy;

  @override
  Widget build(BuildContext context) {
    final visible = !field.hidden || revealed;
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 520;
          final value = SelectableText(
            visible ? field.value : '••••••',
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              fontFamily: visible ? 'monospace' : null,
              fontWeight: visible ? FontWeight.w500 : FontWeight.w800,
            ),
          );
          final actions = Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (onReveal != null)
                IconButton(
                  tooltip: visible ? '隐藏字段值' : '显示字段值',
                  visualDensity: VisualDensity.compact,
                  onPressed: onReveal,
                  icon: Icon(
                    visible
                        ? Icons.visibility_off_outlined
                        : Icons.visibility_outlined,
                    size: 19,
                  ),
                ),
              if (onCopy != null)
                IconButton(
                  tooltip: '复制字段值',
                  visualDensity: VisualDensity.compact,
                  onPressed: onCopy,
                  icon: const Icon(Icons.copy_outlined, size: 19),
                ),
            ],
          );
          if (compact) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  field.name,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: scheme.onSurfaceVariant,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 7),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: value),
                    actions,
                  ],
                ),
              ],
            );
          }
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 180,
                child: Text(
                  field.name,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: scheme.onSurfaceVariant,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const SizedBox(width: 20),
              Expanded(child: value),
              actions,
            ],
          );
        },
      ),
    );
  }
}

class _DetailSectionTitle extends StatelessWidget {
  const _DetailSectionTitle({required this.icon, required this.title});

  final IconData icon;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 20, color: Theme.of(context).colorScheme.primary),
        const SizedBox(width: 8),
        Text(
          title,
          style: Theme.of(
            context,
          ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
        ),
      ],
    );
  }
}

class _Metadata extends StatelessWidget {
  const _Metadata({required this.entry});

  final EntryRecord entry;

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.bodySmall?.copyWith(
      color: Theme.of(context).colorScheme.onSurfaceVariant,
    );
    return Wrap(
      spacing: 18,
      runSpacing: 7,
      children: [
        Text('创建：${_format(entry.createdAt)}', style: style),
        Text('更新：${_format(entry.updatedAt)}', style: style),
        if (entry.deletedAt != null)
          Text('删除：${_format(entry.deletedAt!)}', style: style),
      ],
    );
  }

  static String _format(String value) {
    final date = DateTime.tryParse(value)?.toLocal();
    return date == null ? value : DateFormat('yyyy-MM-dd HH:mm').format(date);
  }
}
