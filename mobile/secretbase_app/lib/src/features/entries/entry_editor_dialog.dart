import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/vault_controller.dart';

Future<String?> showEntryEditorDialog({
  required BuildContext context,
  required WidgetRef ref,
  EntryRecord? source,
  bool duplicate = false,
}) async {
  final taxonomy = await Future.wait([
    rust_api.listTaxonomy(kind: 'tags'),
    rust_api.listTaxonomy(kind: 'groups'),
  ]);
  if (!context.mounted) return null;
  return showResponsiveDialog<String>(
    context: context,
    dismissible: false,
    maxWidth: 900,
    builder: (_) => EntryEditorDialog(
      source: source,
      duplicate: duplicate,
      availableTags: taxonomy[0],
      availableGroups: taxonomy[1],
      ref: ref,
    ),
  );
}

class EntryEditorDialog extends StatefulWidget {
  const EntryEditorDialog({
    required this.availableTags,
    required this.availableGroups,
    required this.ref,
    this.source,
    this.duplicate = false,
    super.key,
  });

  final EntryRecord? source;
  final bool duplicate;
  final List<TaxonomyRecord> availableTags;
  final List<TaxonomyRecord> availableGroups;
  final WidgetRef ref;

  @override
  State<EntryEditorDialog> createState() => _EntryEditorDialogState();
}

class _EntryEditorDialogState extends State<EntryEditorDialog> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _titleController;
  late final TextEditingController _urlController;
  late final TextEditingController _remarksController;
  late final List<_EditableField> _fields;
  late final Set<String> _tags;
  late final Set<String> _groups;
  late bool _starred;
  bool _saving = false;
  String? _error;

  bool get _isNew => widget.source == null || widget.duplicate;

  @override
  void initState() {
    super.initState();
    final source = widget.source;
    _titleController = TextEditingController(
      text: widget.duplicate && source != null
          ? '${source.title} 副本'
          : source?.title ?? '',
    );
    _urlController = TextEditingController(text: source?.url ?? '');
    _remarksController = TextEditingController(text: source?.remarks ?? '');
    _fields =
        source?.fields.map(_EditableField.fromRecord).toList() ??
        [_EditableField.empty()];
    _tags = {...?source?.tags};
    _groups = {...?source?.groups};
    _starred = source?.starred ?? false;
  }

  @override
  void dispose() {
    _titleController.dispose();
    _urlController.dispose();
    _remarksController.dispose();
    for (final field in _fields) {
      field.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final result = await rust_api.saveEntry(
        id: _isNew ? null : widget.source!.id,
        draft: EntryDraft(
          title: _titleController.text,
          url: _urlController.text,
          starred: _starred,
          tags: _tags.toList(),
          groups: _groups.toList(),
          fields: _fields
              .map(
                (field) => FieldRecord(
                  name: field.name.text,
                  value: field.value.text,
                  copyable: field.copyable,
                  hidden: field.hidden,
                ),
              )
              .toList(),
          remarks: _remarksController.text,
        ),
        expectedRevision: widget.ref.read(vaultControllerProvider).revision,
      );
      await widget.ref.read(vaultControllerProvider.notifier).refreshStatus();
      widget.ref.invalidate(entryPageProvider);
      widget.ref.invalidate(taxonomyProvider);
      if (mounted) Navigator.of(context).pop(result.message);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = isRevisionConflict(error)
            ? '数据已变化，请关闭编辑窗口并刷新后重试'
            : mobileErrorMessage(error);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return DialogFrame(
      title: _isNew ? '新建条目' : '编辑条目',
      canClose: !_saving,
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(18, 18, 18, 24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _buildMainFields(),
                    const SizedBox(height: 24),
                    _SectionTitle(
                      title: '自定义字段',
                      trailing: OutlinedButton.icon(
                        onPressed: _addField,
                        icon: const Icon(Icons.add, size: 18),
                        label: const Text('添加字段'),
                      ),
                    ),
                    const SizedBox(height: 10),
                    ...List.generate(
                      _fields.length,
                      (index) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: _FieldEditor(
                          field: _fields[index],
                          index: index,
                          canDelete: _fields.length > 1,
                          onChanged: () => setState(() {}),
                          onDelete: () => _removeField(index),
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    _TaxonomyEditor(
                      title: '标签',
                      icon: Icons.sell_outlined,
                      selected: _tags,
                      available: widget.availableTags
                          .map((item) => item.name)
                          .toList(),
                      onChanged: (value) => setState(() {
                        _tags
                          ..clear()
                          ..addAll(value);
                      }),
                    ),
                    const SizedBox(height: 18),
                    _TaxonomyEditor(
                      title: '密码组',
                      icon: Icons.folder_outlined,
                      selected: _groups,
                      available: widget.availableGroups
                          .map((item) => item.name)
                          .toList(),
                      onChanged: (value) => setState(() {
                        _groups
                          ..clear()
                          ..addAll(value);
                      }),
                    ),
                    const SizedBox(height: 22),
                    TextFormField(
                      controller: _remarksController,
                      minLines: 3,
                      maxLines: 6,
                      maxLength: 2000,
                      decoration: const InputDecoration(
                        labelText: '备注',
                        alignLabelWithHint: true,
                      ),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 8),
                      _EditorError(message: _error!),
                    ],
                  ],
                ),
              ),
            ),
            const Divider(height: 1),
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 14),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    TextButton(
                      onPressed: _saving
                          ? null
                          : () => Navigator.of(context).pop(),
                      child: const Text('取消'),
                    ),
                    const SizedBox(width: 10),
                    FilledButton.icon(
                      onPressed: _saving ? null : _save,
                      icon: _saving
                          ? const SizedBox(
                              width: 17,
                              height: 17,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.save_outlined, size: 19),
                      label: Text(_saving ? '正在保存' : '保存'),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMainFields() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 640;
        final title = TextFormField(
          controller: _titleController,
          autofocus: _isNew,
          maxLength: 200,
          decoration: const InputDecoration(
            labelText: '条目名称',
            prefixIcon: Icon(Icons.key_outlined),
          ),
          validator: (value) => (value ?? '').trim().isEmpty ? '请输入条目名称' : null,
        );
        final url = TextFormField(
          controller: _urlController,
          keyboardType: TextInputType.url,
          decoration: const InputDecoration(
            labelText: '网址',
            prefixIcon: Icon(Icons.link),
            hintText: 'https://',
          ),
          validator: (value) {
            final url = (value ?? '').trim();
            if (url.isEmpty ||
                url.startsWith('https://') ||
                url.startsWith('http://')) {
              return null;
            }
            return '网址必须以 http:// 或 https:// 开头';
          },
        );
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (wide)
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: title),
                  const SizedBox(width: 14),
                  Expanded(child: url),
                ],
              )
            else ...[
              title,
              const SizedBox(height: 12),
              url,
            ],
            const SizedBox(height: 8),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: const Text('收藏条目'),
              secondary: const Icon(Icons.star_outline),
              value: _starred,
              onChanged: (value) => setState(() => _starred = value),
            ),
          ],
        );
      },
    );
  }

  void _addField() {
    setState(() => _fields.add(_EditableField.empty()));
  }

  void _removeField(int index) {
    final removed = _fields.removeAt(index);
    removed.dispose();
    setState(() {});
  }
}

class _EditableField {
  _EditableField({
    required this.name,
    required this.value,
    required this.copyable,
    required this.hidden,
  });

  factory _EditableField.empty() => _EditableField(
    name: TextEditingController(),
    value: TextEditingController(),
    copyable: true,
    hidden: false,
  );

  factory _EditableField.fromRecord(FieldRecord record) => _EditableField(
    name: TextEditingController(text: record.name),
    value: TextEditingController(text: record.value),
    copyable: record.copyable,
    hidden: record.hidden,
  );

  final TextEditingController name;
  final TextEditingController value;
  bool copyable;
  bool hidden;

  void dispose() {
    name.dispose();
    value.dispose();
  }
}

class _FieldEditor extends StatelessWidget {
  const _FieldEditor({
    required this.field,
    required this.index,
    required this.canDelete,
    required this.onChanged,
    required this.onDelete,
  });

  final _EditableField field;
  final int index;
  final bool canDelete;
  final VoidCallback onChanged;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          LayoutBuilder(
            builder: (context, constraints) {
              final wide = constraints.maxWidth >= 580;
              final name = TextFormField(
                controller: field.name,
                decoration: InputDecoration(labelText: '字段 ${index + 1} 名称'),
                validator: (value) =>
                    (value ?? '').trim().isEmpty ? '请输入字段名称' : null,
              );
              final value = TextFormField(
                controller: field.value,
                minLines: 1,
                maxLines: 3,
                decoration: const InputDecoration(labelText: '字段值'),
              );
              if (wide) {
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(width: 210, child: name),
                    const SizedBox(width: 12),
                    Expanded(child: value),
                  ],
                );
              }
              return Column(
                children: [name, const SizedBox(height: 10), value],
              );
            },
          ),
          const SizedBox(height: 8),
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 12,
            runSpacing: 2,
            children: [
              _CompactCheckbox(
                label: '可复制',
                value: field.copyable,
                onChanged: (value) {
                  field.copyable = value;
                  onChanged();
                },
              ),
              _CompactCheckbox(
                label: '默认隐藏',
                value: field.hidden,
                onChanged: (value) {
                  field.hidden = value;
                  onChanged();
                },
              ),
              if (canDelete)
                TextButton.icon(
                  onPressed: onDelete,
                  style: TextButton.styleFrom(
                    foregroundColor: scheme.error,
                    visualDensity: VisualDensity.compact,
                  ),
                  icon: const Icon(Icons.delete_outline, size: 17),
                  label: const Text('删除字段'),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _CompactCheckbox extends StatelessWidget {
  const _CompactCheckbox({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(4),
      onTap: () => onChanged(!value),
      child: SizedBox(
        height: 32,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Checkbox(
              value: value,
              onChanged: (next) => onChanged(next ?? false),
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              visualDensity: VisualDensity.compact,
            ),
            const SizedBox(width: 3),
            Text(label, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(width: 5),
          ],
        ),
      ),
    );
  }
}

class _TaxonomyEditor extends StatelessWidget {
  const _TaxonomyEditor({
    required this.title,
    required this.icon,
    required this.selected,
    required this.available,
    required this.onChanged,
  });

  final String title;
  final IconData icon;
  final Set<String> selected;
  final List<String> available;
  final ValueChanged<Set<String>> onChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _SectionTitle(
          title: title,
          trailing: Wrap(
            spacing: 8,
            children: [
              OutlinedButton.icon(
                onPressed: () => _select(context),
                icon: Icon(icon, size: 18),
                label: Text('选择$title'),
              ),
              IconButton.outlined(
                tooltip: '新建$title',
                onPressed: () => _create(context),
                icon: const Icon(Icons.add),
              ),
            ],
          ),
        ),
        const SizedBox(height: 9),
        if (selected.isEmpty)
          Text(
            '尚未选择',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          )
        else
          Wrap(
            spacing: 7,
            runSpacing: 7,
            children: selected
                .map(
                  (name) => InputChip(
                    avatar: Icon(icon, size: 15),
                    label: Text(name),
                    onDeleted: () => onChanged({...selected}..remove(name)),
                  ),
                )
                .toList(),
          ),
      ],
    );
  }

  Future<void> _select(BuildContext context) async {
    final result = await showResponsiveDialog<Set<String>>(
      context: context,
      maxWidth: 620,
      builder: (_) => _TaxonomySelectionDialog(
        title: '选择$title',
        icon: icon,
        available: {...available, ...selected}.toList()..sort(),
        selected: selected,
      ),
    );
    if (result != null) onChanged(result);
  }

  Future<void> _create(BuildContext context) async {
    final controller = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('新建$title'),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLength: 50,
          decoration: InputDecoration(labelText: '$title名称'),
          onSubmitted: (value) => Navigator.of(context).pop(value),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(controller.text),
            child: const Text('添加'),
          ),
        ],
      ),
    );
    controller.dispose();
    final name = result?.trim() ?? '';
    if (name.isNotEmpty) onChanged({...selected, name});
  }
}

class _TaxonomySelectionDialog extends StatefulWidget {
  const _TaxonomySelectionDialog({
    required this.title,
    required this.icon,
    required this.available,
    required this.selected,
  });

  final String title;
  final IconData icon;
  final List<String> available;
  final Set<String> selected;

  @override
  State<_TaxonomySelectionDialog> createState() =>
      _TaxonomySelectionDialogState();
}

class _TaxonomySelectionDialogState extends State<_TaxonomySelectionDialog> {
  late final Set<String> _selected = {...widget.selected};
  String _search = '';

  @override
  Widget build(BuildContext context) {
    final items = widget.available
        .where((name) => name.toLowerCase().contains(_search.toLowerCase()))
        .toList();
    return DialogFrame(
      title: widget.title,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(14),
            child: TextField(
              onChanged: (value) => setState(() => _search = value.trim()),
              decoration: const InputDecoration(
                hintText: '筛选已有名称',
                prefixIcon: Icon(Icons.search),
              ),
            ),
          ),
          Expanded(
            child: items.isEmpty
                ? const Center(child: Text('没有匹配项'))
                : ListView.builder(
                    itemCount: items.length,
                    itemBuilder: (context, index) {
                      final name = items[index];
                      return CheckboxListTile(
                        value: _selected.contains(name),
                        secondary: Icon(widget.icon, size: 20),
                        title: Text(name),
                        controlAffinity: ListTileControlAffinity.trailing,
                        onChanged: (checked) => setState(() {
                          if (checked ?? false) {
                            _selected.add(name);
                          } else {
                            _selected.remove(name);
                          }
                        }),
                      );
                    },
                  ),
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('取消'),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: () => Navigator.of(context).pop(_selected),
                  child: Text('确认（${_selected.length}）'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title, required this.trailing});

  final String title;
  final Widget trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(
          child: Text(
            title,
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
          ),
        ),
        trailing,
      ],
    );
  }
}

class _EditorError extends StatelessWidget {
  const _EditorError({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(message, style: TextStyle(color: scheme.onErrorContainer)),
    );
  }
}
