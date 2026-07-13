import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/core/widgets/paged_scroll.dart';
import 'package:secretbase/src/core/widgets/page_controls.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/ai/ai_settings_dialog.dart';
import 'package:secretbase/src/features/ai/ai_transport.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/preferences_controller.dart';
import 'package:secretbase/src/state/vault_controller.dart';

enum AiTool {
  parse('parse', '文本解析', Icons.text_snippet_outlined),
  entryTags('entry_tags', '单条目标签', Icons.new_label_outlined),
  groups('groups', '密码组整理', Icons.drive_file_move_outline),
  tagGovernance('tag_governance', '标签治理', Icons.rule_folder_outlined),
  actions('actions', '操作计划', Icons.account_tree_outlined);

  const AiTool(this.key, this.label, this.icon);

  final String key;
  final String label;
  final IconData icon;
}

class AiScreen extends ConsumerStatefulWidget {
  const AiScreen({super.key});

  @override
  ConsumerState<AiScreen> createState() => _AiScreenState();
}

class _AiScreenState extends ConsumerState<AiScreen> {
  final _inputController = TextEditingController();
  final _preferenceController = TextEditingController();
  late Future<AiStatus> _statusFuture;
  AiTool _tool = AiTool.parse;
  String? _entryId;
  String? _entryTitle;
  AiPreview? _preview;
  final Set<String> _selected = {};
  final Set<String> _revealed = {};
  bool _working = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _statusFuture = rust_api.aiStatus();
    _restorePendingPreview();
  }

  @override
  void dispose() {
    _inputController.dispose();
    _preferenceController.dispose();
    super.dispose();
  }

  Future<void> _restorePendingPreview() async {
    try {
      final preview = await rust_api.pendingAiPreview();
      if (preview != null && mounted) _setPreview(preview);
    } catch (_) {
      // 锁定或首次进入时没有待处理建议属于正常状态。
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<AiStatus>(
      future: _statusFuture,
      builder: (context, snapshot) {
        final status = snapshot.data;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _AiHeader(status: status, onSettings: _openSettings),
            const Divider(height: 1),
            if (snapshot.connectionState != ConnectionState.done)
              const Expanded(child: LoadingView(label: '正在读取 AI 设置'))
            else if (snapshot.hasError)
              Expanded(
                child: ErrorView(
                  message: mobileErrorMessage(snapshot.error!),
                  onRetry: () =>
                      setState(() => _statusFuture = rust_api.aiStatus()),
                ),
              )
            else if (status?.configured != true)
              Expanded(
                child: EmptyView(
                  icon: Icons.auto_awesome_outlined,
                  title: '尚未配置 AI 服务',
                  action: FilledButton.icon(
                    onPressed: _openSettings,
                    icon: const Icon(Icons.settings_outlined),
                    label: const Text('配置 AI 服务'),
                  ),
                ),
              )
            else
              Expanded(child: _buildWorkspace(status!)),
          ],
        );
      },
    );
  }

  Widget _buildWorkspace(AiStatus status) {
    return Stack(
      children: [
        ListView(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 90),
          children: [
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 980),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _ToolSelector(selected: _tool, onSelected: _selectTool),
                    const SizedBox(height: 10),
                    _RequestPanel(
                      tool: _tool,
                      inputController: _inputController,
                      preferenceController: _preferenceController,
                      selectedEntryTitle: _entryTitle,
                      working: _working,
                      onPickEntry: _pickEntry,
                      onGenerate: () => _generate(status),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 9),
                      _ErrorBand(message: _error!),
                    ],
                    if (_preview != null) ...[
                      const SizedBox(height: 12),
                      _PreviewPanel(
                        preview: _preview!,
                        selected: _selected,
                        revealed: _revealed,
                        working: _working,
                        onSelectionChanged: (id, value) => setState(() {
                          if (value) {
                            _selected.add(id);
                          } else {
                            _selected.remove(id);
                          }
                        }),
                        onSelectAll: (value) => setState(() {
                          _selected.clear();
                          if (value) {
                            _selected.addAll(
                              _preview!.items.map((item) => item.id),
                            );
                          }
                        }),
                        onReveal: (key) => setState(() {
                          if (!_revealed.add(key)) _revealed.remove(key);
                        }),
                        onApply: _applyPreview,
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
        if (_working)
          const Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: LinearProgressIndicator(),
          ),
      ],
    );
  }

  void _selectTool(AiTool tool) {
    if (_working || tool == _tool) return;
    setState(() {
      _tool = tool;
      _preview = null;
      _selected.clear();
      _revealed.clear();
      _error = null;
      _inputController.clear();
      _preferenceController.clear();
      if (tool != AiTool.entryTags) {
        _entryId = null;
        _entryTitle = null;
      }
    });
  }

  Future<void> _pickEntry() async {
    final selection = await showResponsiveDialog<_EntrySelection>(
      context: context,
      maxWidth: 720,
      builder: (_) => const _AiEntryPickerDialog(),
    );
    if (selection != null && mounted) {
      setState(() {
        _entryId = selection.id;
        _entryTitle = selection.title;
      });
    }
  }

  Future<void> _generate(AiStatus status) async {
    if (_tool == AiTool.entryTags && _entryId == null) {
      setState(() => _error = '请先选择需要整理标签的条目');
      return;
    }
    if ((_tool == AiTool.parse || _tool == AiTool.actions) &&
        _inputController.text.trim().isEmpty) {
      setState(() => _error = _tool == AiTool.parse ? '请输入需要解析的文本' : '请输入操作指令');
      return;
    }
    if (!await _ensurePrivacyConsent()) return;
    setState(() {
      _working = true;
      _error = null;
      _preview = null;
      _selected.clear();
      _revealed.clear();
    });
    try {
      final plan = await rust_api.prepareAiRequest(
        kind: _tool.key,
        input: _inputController.text,
        entryId: _entryId,
        userPrompt: _preferenceController.text,
      );
      if (!mounted || !await _confirmSend(plan.summary, status)) {
        if (mounted) setState(() => _working = false);
        return;
      }
      final response = await AiTransport.send(plan.request);
      final preview = await rust_api.consumeAiResponse(
        token: plan.token,
        content: response,
      );
      if (mounted) {
        setState(() => _working = false);
        _setPreview(preview);
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _working = false;
          _error = _errorMessage(error);
        });
      }
    }
  }

  Future<void> _applyPreview() async {
    final preview = _preview;
    if (preview == null || _selected.isEmpty) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('应用 AI 建议'),
        content: Text('确认应用选中的 ${_selected.length} 项建议？应用前会再次校验密码库版本。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('确认应用'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      final result = await rust_api.applyAiPreview(
        token: preview.token,
        selectedItemIds: _selected.toList(),
        expectedRevision: ref.read(vaultControllerProvider).revision,
      );
      await ref.read(vaultControllerProvider.notifier).refreshStatus();
      ref.invalidate(entryPageProvider);
      ref.invalidate(taxonomyProvider);
      if (mounted) {
        setState(() {
          _working = false;
          _preview = null;
          _selected.clear();
          _revealed.clear();
        });
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(result.message)));
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _working = false;
          _error = _errorMessage(error);
        });
      }
    }
  }

  void _setPreview(AiPreview preview) {
    setState(() {
      _preview = preview;
      _selected
        ..clear()
        ..addAll(preview.items.map((item) => item.id));
      _revealed.clear();
    });
  }

  Future<bool> _ensurePrivacyConsent() async {
    if (ref.read(preferencesProvider).aiPrivacyAccepted) return true;
    final accepted = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('AI 隐私确认'),
        content: const Text(
          'AI 请求会发送到你配置的第三方服务。结构整理不会发送字段值、主密码或备注；文本解析会发送你输入的完整原文。每次请求前仍会显示发送摘要。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('暂不使用'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('同意并继续'),
          ),
        ],
      ),
    );
    if (accepted == true) {
      await ref.read(preferencesProvider.notifier).acceptAiPrivacy();
      return true;
    }
    return false;
  }

  Future<bool> _confirmSend(AiSendSummary summary, AiStatus status) async {
    return await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(summary.title),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('${status.baseUrl} · ${status.model}'),
                const SizedBox(height: 12),
                if (summary.entryCount > 0)
                  Text('涉及条目：${summary.entryCount} 个'),
                if (summary.inputChars > 0)
                  Text('输入长度：${summary.inputChars} 个字符'),
                const SizedBox(height: 8),
                ...summary.categories.map(
                  (category) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.check, size: 17),
                        const SizedBox(width: 7),
                        Expanded(child: Text(category)),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  summary.privacyNote,
                  style: TextStyle(
                    color: summary.includesFieldValues
                        ? Theme.of(context).colorScheme.error
                        : Theme.of(context).colorScheme.primary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('取消'),
              ),
              FilledButton.icon(
                onPressed: () => Navigator.of(context).pop(true),
                icon: const Icon(Icons.send_outlined, size: 18),
                label: const Text('确认发送'),
              ),
            ],
          ),
        ) ??
        false;
  }

  Future<void> _openSettings() async {
    final status = await showAiSettingsDialog(context: context, ref: ref);
    if (status != null && mounted) {
      setState(() {
        _statusFuture = Future.value(status);
        _preview = null;
        _selected.clear();
      });
    }
  }

  String _errorMessage(Object error) {
    if (error is AiTransportException) return error.message;
    return mobileErrorMessage(error);
  }
}

class _AiHeader extends StatelessWidget {
  const _AiHeader({required this.status, required this.onSettings});

  final AiStatus? status;
  final VoidCallback onSettings;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 10, 9),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '专业工具',
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
            ),
          ),
          if (status?.configured == true)
            Container(
              constraints: const BoxConstraints(maxWidth: 160),
              padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
              decoration: BoxDecoration(
                color: scheme.primaryContainer,
                borderRadius: BorderRadius.circular(5),
              ),
              child: Text(
                status!.model,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: scheme.onPrimaryContainer,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          const SizedBox(width: 5),
          IconButton(
            tooltip: 'AI 服务设置',
            onPressed: onSettings,
            icon: const Icon(Icons.settings_outlined),
          ),
        ],
      ),
    );
  }
}

class _ToolSelector extends StatelessWidget {
  const _ToolSelector({required this.selected, required this.onSelected});

  final AiTool selected;
  final ValueChanged<AiTool> onSelected;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: AiTool.values
          .map(
            (tool) => ChoiceChip(
              selected: tool == selected,
              avatar: Icon(tool.icon, size: 17),
              label: Text(tool.label),
              onSelected: (_) => onSelected(tool),
            ),
          )
          .toList(),
    );
  }
}

class _RequestPanel extends StatelessWidget {
  const _RequestPanel({
    required this.tool,
    required this.inputController,
    required this.preferenceController,
    required this.selectedEntryTitle,
    required this.working,
    required this.onPickEntry,
    required this.onGenerate,
  });

  final AiTool tool;
  final TextEditingController inputController;
  final TextEditingController preferenceController;
  final String? selectedEntryTitle;
  final bool working;
  final VoidCallback onPickEntry;
  final VoidCallback onGenerate;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.surface,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(tool.icon, color: scheme.primary),
              const SizedBox(width: 9),
              Text(
                tool.label,
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
              ),
            ],
          ),
          const SizedBox(height: 10),
          if (tool == AiTool.entryTags) ...[
            OutlinedButton.icon(
              onPressed: working ? null : onPickEntry,
              icon: const Icon(Icons.key_outlined),
              label: Text(selectedEntryTitle ?? '选择条目'),
            ),
            const SizedBox(height: 9),
          ],
          if (tool == AiTool.parse)
            TextField(
              controller: inputController,
              enabled: !working,
              minLines: 6,
              maxLines: 12,
              maxLength: 6000,
              decoration: const InputDecoration(
                labelText: '待解析文本',
                alignLabelWithHint: true,
              ),
            )
          else if (tool == AiTool.actions)
            TextField(
              controller: inputController,
              enabled: !working,
              minLines: 4,
              maxLines: 8,
              maxLength: 2000,
              decoration: const InputDecoration(
                labelText: '操作指令',
                alignLabelWithHint: true,
              ),
            ),
          if (tool != AiTool.parse) ...[
            if (tool == AiTool.actions) const SizedBox(height: 10),
            TextField(
              controller: preferenceController,
              enabled: !working,
              minLines: 2,
              maxLines: 5,
              maxLength: 1000,
              decoration: InputDecoration(
                labelText: tool == AiTool.actions ? '补充偏好（可选）' : '整理偏好（可选）',
                alignLabelWithHint: true,
              ),
            ),
          ],
          const SizedBox(height: 4),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton.icon(
              onPressed: working ? null : onGenerate,
              icon: const Icon(Icons.auto_awesome, size: 18),
              label: Text(working ? '正在处理' : '生成建议'),
            ),
          ),
        ],
      ),
    );
  }
}

class _PreviewPanel extends StatelessWidget {
  const _PreviewPanel({
    required this.preview,
    required this.selected,
    required this.revealed,
    required this.working,
    required this.onSelectionChanged,
    required this.onSelectAll,
    required this.onReveal,
    required this.onApply,
  });

  final AiPreview preview;
  final Set<String> selected;
  final Set<String> revealed;
  final bool working;
  final void Function(String id, bool value) onSelectionChanged;
  final ValueChanged<bool> onSelectAll;
  final ValueChanged<String> onReveal;
  final VoidCallback onApply;

  @override
  Widget build(BuildContext context) {
    final allSelected =
        preview.items.isNotEmpty && selected.length == preview.items.length;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                preview.title,
                style: Theme.of(
                  context,
                ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
              ),
            ),
            Checkbox(
              value: allSelected,
              onChanged: preview.items.isEmpty
                  ? null
                  : (value) => onSelectAll(value ?? false),
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              visualDensity: VisualDensity.compact,
            ),
            const SizedBox(width: 4),
            Text('全选', style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
        const SizedBox(height: 5),
        Text(
          preview.privacyNote,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        if (preview.warnings.isNotEmpty) ...[
          const SizedBox(height: 10),
          _WarningBand(warnings: preview.warnings),
        ],
        const SizedBox(height: 10),
        if (preview.items.isEmpty)
          const EmptyView(icon: Icons.task_alt_outlined, title: '没有需要应用的建议')
        else
          ...preview.items.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 9),
              child: _PreviewItemCard(
                item: item,
                selected: selected.contains(item.id),
                revealed: revealed,
                onSelected: (value) => onSelectionChanged(item.id, value),
                onReveal: onReveal,
              ),
            ),
          ),
        if (preview.items.isNotEmpty)
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton.icon(
              onPressed: selected.isEmpty || working ? null : onApply,
              icon: const Icon(Icons.done_all, size: 18),
              label: Text('应用所选（${selected.length}）'),
            ),
          ),
      ],
    );
  }
}

class _PreviewItemCard extends StatelessWidget {
  const _PreviewItemCard({
    required this.item,
    required this.selected,
    required this.revealed,
    required this.onSelected,
    required this.onReveal,
  });

  final AiPreviewItem item;
  final bool selected;
  final Set<String> revealed;
  final ValueChanged<bool> onSelected;
  final ValueChanged<String> onReveal;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(10, 11, 12, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Checkbox(
                  value: selected,
                  onChanged: (value) => onSelected(value ?? false),
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  visualDensity: VisualDensity.compact,
                ),
                const SizedBox(width: 7),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.title,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      if (item.subtitle.isNotEmpty) ...[
                        const SizedBox(height: 2),
                        Text(
                          item.subtitle,
                          style: Theme.of(context).textTheme.bodySmall
                              ?.copyWith(
                                color: Theme.of(
                                  context,
                                ).colorScheme.onSurfaceVariant,
                              ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
            if (item.details.isNotEmpty) ...[
              const SizedBox(height: 9),
              const Divider(height: 1),
              const SizedBox(height: 5),
              ...List.generate(item.details.length, (index) {
                final detail = item.details[index];
                final key = '${item.id}:$index';
                return _AiDetailRow(
                  detail: detail,
                  revealed: revealed.contains(key),
                  onReveal: detail.sensitive ? () => onReveal(key) : null,
                );
              }),
            ],
          ],
        ),
      ),
    );
  }
}

class _AiDetailRow extends StatelessWidget {
  const _AiDetailRow({
    required this.detail,
    required this.revealed,
    this.onReveal,
  });

  final AiPreviewDetail detail;
  final bool revealed;
  final VoidCallback? onReveal;

  @override
  Widget build(BuildContext context) {
    final color = switch (detail.changeType) {
      'add' => const Color(0xFF18794E),
      'remove' => Theme.of(context).colorScheme.error,
      'update' => Theme.of(context).colorScheme.tertiary,
      _ => Theme.of(context).colorScheme.onSurfaceVariant,
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final labelWidth = (constraints.maxWidth * 0.28).clamp(80.0, 150.0);
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: labelWidth,
                child: Text(
                  detail.label,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Text(
                  detail.sensitive && !revealed ? '••••••' : detail.value,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
              if (onReveal != null)
                IconButton(
                  tooltip: revealed ? '隐藏内容' : '显示内容',
                  visualDensity: VisualDensity.compact,
                  onPressed: onReveal,
                  icon: Icon(
                    revealed
                        ? Icons.visibility_off_outlined
                        : Icons.visibility_outlined,
                    size: 18,
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _WarningBand extends StatelessWidget {
  const _WarningBand({required this.warnings});

  final List<String> warnings;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: scheme.secondaryContainer,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: warnings
            .map(
              (warning) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text(
                  warning,
                  style: TextStyle(color: scheme.onSecondaryContainer),
                ),
              ),
            )
            .toList(),
      ),
    );
  }
}

class _ErrorBand extends StatelessWidget {
  const _ErrorBand({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(message, style: TextStyle(color: scheme.onErrorContainer)),
    );
  }
}

class _EntrySelection {
  const _EntrySelection(this.id, this.title);

  final String id;
  final String title;
}

class _AiEntryPickerDialog extends ConsumerStatefulWidget {
  const _AiEntryPickerDialog();

  @override
  ConsumerState<_AiEntryPickerDialog> createState() =>
      _AiEntryPickerDialogState();
}

class _AiEntryPickerDialogState extends ConsumerState<_AiEntryPickerDialog> {
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();
  Timer? _debounce;
  int _page = 1;
  String _search = '';

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
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
      deleted: false,
    );
    final entries = ref.watch(entryPageProvider(query));
    return DialogFrame(
      title: '选择条目',
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _searchController,
              onChanged: (value) {
                _debounce?.cancel();
                _debounce = Timer(const Duration(milliseconds: 280), () {
                  if (mounted) {
                    setState(() {
                      _search = value.trim();
                      _page = 1;
                    });
                    resetPagedScroll(_scrollController);
                  }
                });
              },
              decoration: const InputDecoration(
                isDense: true,
                hintText: '搜索条目名称',
                prefixIcon: Icon(Icons.search, size: 20),
                prefixIconConstraints: BoxConstraints(
                  minWidth: 40,
                  minHeight: 40,
                ),
              ),
            ),
          ),
          Expanded(
            child: entries.when(
              loading: () => const LoadingView(),
              error: (error, stackTrace) => ErrorView(
                message: mobileErrorMessage(error),
                onRetry: () => ref.invalidate(entryPageProvider(query)),
              ),
              data: (page) => ListView.builder(
                controller: _scrollController,
                itemCount: page.items.isEmpty ? 1 : page.items.length + 1,
                itemBuilder: (context, index) {
                  if (page.items.isEmpty) {
                    return const EmptyView(
                      icon: Icons.search_off,
                      title: '没有匹配的条目',
                    );
                  }
                  if (index == page.items.length) {
                    return PageControls(
                      page: page.page,
                      totalPages: page.totalPages,
                      pageSize: pageSize,
                      showPageSize: false,
                      onPageChanged: (value) {
                        setState(() => _page = value);
                        resetPagedScroll(_scrollController);
                      },
                      onPageSizeChanged: (_) {},
                    );
                  }
                  final entry = page.items[index];
                  return ListTile(
                    leading: const Icon(Icons.key_outlined),
                    title: Text(entry.title),
                    subtitle: entry.url.isEmpty ? null : Text(entry.url),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(
                      context,
                    ).pop(_EntrySelection(entry.id, entry.title)),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}
