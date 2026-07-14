import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/vault_controller.dart';

Future<String?> showTaxonomyEditorDialog({
  required BuildContext context,
  required WidgetRef ref,
  required String kind,
  TaxonomyRecord? existing,
}) {
  return showResponsiveDialog<String>(
    context: context,
    maxWidth: 600,
    builder: (_) =>
        TaxonomyEditorDialog(ref: ref, kind: kind, existing: existing),
  );
}

class TaxonomyEditorDialog extends StatefulWidget {
  const TaxonomyEditorDialog({
    required this.ref,
    required this.kind,
    this.existing,
    super.key,
  });

  final WidgetRef ref;
  final String kind;
  final TaxonomyRecord? existing;

  @override
  State<TaxonomyEditorDialog> createState() => _TaxonomyEditorDialogState();
}

class _TaxonomyEditorDialogState extends State<TaxonomyEditorDialog> {
  static const _colors = [
    '#087f8c',
    '#315da8',
    '#6b5b95',
    '#26834a',
    '#b54708',
    '#c62828',
    '#9f2d55',
    '#475569',
  ];

  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _nameController;
  late final TextEditingController _descriptionController;
  late String _color;
  bool _saving = false;
  String? _error;

  bool get _isTag => widget.kind == 'tags';

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.existing?.name ?? '');
    _descriptionController = TextEditingController(
      text: widget.existing?.description ?? '',
    );
    _color = widget.existing?.color.toLowerCase() ?? _colors.first;
    if (!_colors.contains(_color)) _color = _colors.first;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final result = await rust_api.saveTaxonomy(
        kind: widget.kind,
        oldName: widget.existing?.name,
        name: _nameController.text,
        description: _descriptionController.text,
        color: _isTag ? _color : null,
        expectedRevision: widget.ref.read(vaultControllerProvider).revision,
      );
      await widget.ref.read(vaultControllerProvider.notifier).refreshStatus();
      widget.ref.invalidate(taxonomyProvider);
      widget.ref.invalidate(entryPageProvider);
      if (mounted) Navigator.of(context).pop(result.message);
    } catch (error) {
      if (mounted) {
        setState(() {
          _saving = false;
          _error = mobileErrorMessage(error);
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final entityName = _isTag ? '标签' : '密码组';
    return DialogFrame(
      title: '${widget.existing == null ? '新建' : '编辑'}$entityName',
      onClose: _saving ? () {} : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextFormField(
                      controller: _nameController,
                      autofocus: true,
                      maxLength: 50,
                      decoration: InputDecoration(
                        labelText: '$entityName名称',
                        prefixIcon: Icon(
                          _isTag ? Icons.sell_outlined : Icons.folder_outlined,
                        ),
                      ),
                      validator: (value) => (value ?? '').trim().isEmpty
                          ? '请输入$entityName名称'
                          : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _descriptionController,
                      minLines: 3,
                      maxLines: 5,
                      maxLength: 500,
                      decoration: const InputDecoration(
                        labelText: '简介',
                        alignLabelWithHint: true,
                      ),
                    ),
                    if (_isTag) ...[
                      const SizedBox(height: 12),
                      Text(
                        '标识颜色',
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 10,
                        runSpacing: 10,
                        children: _colors.map((value) {
                          final color = _parseColor(value);
                          final selected = _color == value;
                          return Semantics(
                            label: selected ? '已选择颜色' : '选择颜色',
                            button: true,
                            child: InkWell(
                              borderRadius: BorderRadius.circular(22),
                              onTap: () => setState(() => _color = value),
                              child: SizedBox(
                                width: 44,
                                height: 44,
                                child: Center(
                                  child: Container(
                                    width: 34,
                                    height: 34,
                                    decoration: BoxDecoration(
                                      color: color,
                                      shape: BoxShape.circle,
                                      border: Border.all(
                                        color: selected
                                            ? Theme.of(
                                                context,
                                              ).colorScheme.onSurface
                                            : Colors.transparent,
                                        width: 3,
                                      ),
                                    ),
                                    child: selected
                                        ? const Icon(
                                            Icons.check,
                                            color: Colors.white,
                                            size: 19,
                                          )
                                        : null,
                                  ),
                                ),
                              ),
                            ),
                          );
                        }).toList(),
                      ),
                    ],
                    if (_error != null) ...[
                      const SizedBox(height: 18),
                      Text(
                        _error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
          const Divider(height: 1),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _saving
                        ? null
                        : () => Navigator.of(context).pop(),
                    child: const Text('取消'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton.icon(
                    onPressed: _saving ? null : _save,
                    icon: const Icon(Icons.save_outlined, size: 18),
                    label: Text(_saving ? '正在保存' : '保存'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  static Color _parseColor(String value) {
    return Color(int.parse(value.substring(1), radix: 16) | 0xFF000000);
  }
}

Future<String?> deleteTaxonomy({
  required BuildContext context,
  required WidgetRef ref,
  required String kind,
  required String name,
}) async {
  final entityName = kind == 'tags' ? '标签' : '密码组';
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text('删除$entityName'),
      content: Text('确认删除“$name”？相关条目只会移除该分类，不会被删除。'),
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
          child: const Text('删除'),
        ),
      ],
    ),
  );
  if (confirmed != true) return null;
  final result = await rust_api.deleteTaxonomy(
    kind: kind,
    name: name,
    expectedRevision: ref.read(vaultControllerProvider).revision,
  );
  await ref.read(vaultControllerProvider.notifier).refreshStatus();
  ref.invalidate(taxonomyProvider);
  ref.invalidate(entryPageProvider);
  return result.message;
}
