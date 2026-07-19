import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/core/widgets/mobile_chrome.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/ai/ai_confirmation_sheets.dart';
import 'package:secretbase/src/features/ai/ai_activity_controller.dart';
import 'package:secretbase/src/features/ai/ai_entry_picker_dialog.dart';
import 'package:secretbase/src/features/ai/ai_manager_widgets.dart';
import 'package:secretbase/src/features/ai/ai_plan_panel.dart';
import 'package:secretbase/src/features/ai/ai_settings_dialog.dart';
import 'package:secretbase/src/features/ai/ai_transport.dart';
import 'package:secretbase/src/features/ai/ai_undo_controller.dart';
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
  const AiScreen({this.onBack, super.key});

  final VoidCallback? onBack;

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
  final Set<String> _expanded = {};
  bool _working = false;
  String? _error;
  AiTransportOperation? _transportOperation;
  int? _activityToken;
  int _requestGeneration = 0;

  @override
  void initState() {
    super.initState();
    _statusFuture = rust_api.aiStatus();
    _restorePendingPreview();
  }

  @override
  void dispose() {
    _requestGeneration += 1;
    _transportOperation?.cancel();
    _transportOperation = null;
    if (_working) unawaited(rust_api.cancelAiPending().catchError((_) {}));
    final activityToken = _activityToken;
    if (activityToken != null) {
      ref.read(aiActivityControllerProvider.notifier).finish(activityToken);
      _activityToken = null;
    }
    _inputController.dispose();
    _preferenceController.dispose();
    super.dispose();
  }

  Future<void> _restorePendingPreview() async {
    try {
      final preview = await rust_api.pendingAiPreview();
      if (preview != null && preview.kind != 'assistant' && mounted) {
        _setPreview(preview);
      }
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
            _AiHeader(
              status: status,
              onBack: widget.onBack,
              onSettings: _working || _preview != null ? null : _openSettings,
            ),
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
    final undo = ref.watch(aiUndoControllerProvider);
    final anotherRequestActive = ref.watch(aiActivityControllerProvider);
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
                    if (undo.pending != null) ...[
                      AiUndoBanner(
                        state: undo.pending!,
                        onUndo: _working || undo.working
                            ? null
                            : _undoLastOperation,
                      ),
                      const SizedBox(height: 2),
                    ],
                    _ToolSelector(
                      selected: _tool,
                      enabled:
                          !_working &&
                          !anotherRequestActive &&
                          _preview == null,
                      onSelected: _selectTool,
                    ),
                    const SizedBox(height: 10),
                    _RequestPanel(
                      tool: _tool,
                      inputController: _inputController,
                      preferenceController: _preferenceController,
                      selectedEntryTitle: _entryTitle,
                      working: _working || anotherRequestActive,
                      reviewing: _preview != null,
                      cancelable: _working,
                      onPickEntry: _pickEntry,
                      onGenerate: () => _generate(status),
                      onCancel: () => unawaited(_cancelRequest()),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 9),
                      _ErrorBand(message: _error!),
                    ],
                    if (_preview != null) ...[
                      const SizedBox(height: 12),
                      AiPlanPanel(
                        preview: _preview!,
                        selected: _selected,
                        revealed: _revealed,
                        expanded: _expanded,
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
                        onExpanded: (id) => setState(() {
                          if (!_expanded.add(id)) _expanded.remove(id);
                        }),
                        onApply: _applyPreview,
                        onDiscard: _discardPreview,
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
    if (_working || _preview != null || tool == _tool) return;
    setState(() {
      _tool = tool;
      _preview = null;
      _selected.clear();
      _revealed.clear();
      _expanded.clear();
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
    if (_working || _preview != null) return;
    final selection = await showAiEntryPickerDialog(context);
    if (selection != null && mounted) {
      setState(() {
        _entryId = selection.id;
        _entryTitle = selection.title;
      });
    }
  }

  Future<void> _generate(AiStatus status) async {
    if (_working || _preview != null) return;
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
    final activity = ref.read(aiActivityControllerProvider.notifier);
    final activityToken = activity.acquire();
    if (activityToken == null) {
      setState(() => _error = '另一个 AI 请求正在处理中，请等待完成');
      return;
    }
    final generation = ++_requestGeneration;
    _activityToken = activityToken;
    setState(() {
      _working = true;
      _error = null;
      _preview = null;
      _selected.clear();
      _revealed.clear();
      _expanded.clear();
    });
    AiTransportOperation? operation;
    try {
      final plan = await rust_api.prepareAiRequest(
        kind: _tool.key,
        input: _inputController.text,
        entryId: _entryId,
        userPrompt: _preferenceController.text,
      );
      if (!_isCurrentRequest(generation)) {
        unawaited(rust_api.cancelAiPending().catchError((_) {}));
        return;
      }
      if (!await _confirmSend(plan.summary, status)) {
        unawaited(rust_api.cancelAiPending().catchError((_) {}));
        if (_isCurrentRequest(generation)) setState(() => _working = false);
        return;
      }
      if (!_isCurrentRequest(generation)) return;
      operation = AiTransport.start(plan.request);
      _transportOperation = operation;
      final response = await operation.future;
      if (!_isCurrentRequest(generation)) return;
      final preview = await rust_api.consumeAiResponse(
        token: plan.token,
        content: response,
      );
      if (_isCurrentRequest(generation)) {
        setState(() => _working = false);
        _setPreview(preview);
      }
    } catch (error) {
      unawaited(rust_api.cancelAiPending().catchError((_) {}));
      if (_isCurrentRequest(generation)) {
        setState(() {
          _working = false;
          _error = _errorMessage(error);
        });
      }
    } finally {
      if (identical(_transportOperation, operation)) _transportOperation = null;
      if (_activityToken == activityToken) _activityToken = null;
      activity.finish(activityToken);
    }
  }

  bool _isCurrentRequest(int generation) =>
      mounted && _working && generation == _requestGeneration;

  Future<void> _cancelRequest() async {
    if (!_working) return;
    _requestGeneration += 1;
    _transportOperation?.cancel();
    _transportOperation = null;
    unawaited(rust_api.cancelAiPending().catchError((_) {}));
    final activityToken = _activityToken;
    if (activityToken != null) {
      ref.read(aiActivityControllerProvider.notifier).finish(activityToken);
      _activityToken = null;
    }
    if (!mounted) return;
    setState(() {
      _working = false;
      _error = 'AI 请求已取消';
    });
  }

  Future<void> _applyPreview() async {
    final preview = _preview;
    if (preview == null || _selected.isEmpty) return;
    final confirmed = await showAiApplyConfirmationSheet(
      context: context,
      selectedCount: _selected.length,
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
      ref.read(aiUndoControllerProvider.notifier).record(result);
      var refreshed = true;
      try {
        await ref.read(vaultControllerProvider.notifier).refreshStatus();
      } catch (_) {
        refreshed = false;
      }
      ref.invalidate(entryPageProvider);
      ref.invalidate(taxonomyProvider);
      if (mounted) {
        setState(() {
          _working = false;
          _preview = null;
          _selected.clear();
          _revealed.clear();
          _expanded.clear();
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              refreshed ? result.message : '${result.message}，但界面刷新不完整，请稍后重试。',
            ),
          ),
        );
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

  Future<void> _undoLastOperation() async {
    if (_working) return;
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      final message = await ref.read(aiUndoControllerProvider.notifier).undo();
      if (!mounted) return;
      setState(() {
        _working = false;
        _preview = null;
        _selected.clear();
        _revealed.clear();
        _expanded.clear();
      });
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _working = false;
        _error = _errorMessage(error);
      });
    }
  }

  Future<void> _discardPreview() async {
    if (_preview == null || _working) return;
    final confirmed = await showAiDiscardConfirmationSheet(context: context);
    if (confirmed != true) return;
    try {
      await rust_api.cancelAiPending();
    } catch (_) {
      // 锁定流程可能已经清理运行时状态，仍允许用户关闭本地预览。
    }
    if (!mounted) return;
    setState(() {
      _preview = null;
      _selected.clear();
      _revealed.clear();
      _expanded.clear();
      _error = null;
    });
  }

  void _setPreview(AiPreview preview) {
    setState(() {
      _preview = preview;
      _selected
        ..clear()
        ..addAll(
          preview.items
              .where((item) => !aiPreviewItemIsHighImpact(item))
              .map((item) => item.id),
        );
      _revealed.clear();
      _expanded.clear();
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
    return showAiSendConfirmationSheet(
      context: context,
      status: status,
      summary: summary,
    );
  }

  Future<void> _openSettings() async {
    if (_working || _preview != null) return;
    final status = await showAiSettingsDialog(context: context, ref: ref);
    if (status != null && mounted) {
      setState(() {
        _statusFuture = Future.value(status);
        _preview = null;
        _selected.clear();
        _revealed.clear();
        _expanded.clear();
      });
    }
  }

  String _errorMessage(Object error) {
    if (error is AiTransportException) return error.message;
    return mobileErrorMessage(error);
  }
}

class _AiHeader extends StatelessWidget {
  const _AiHeader({
    required this.status,
    required this.onBack,
    required this.onSettings,
  });

  final AiStatus? status;
  final VoidCallback? onBack;
  final VoidCallback? onSettings;

  @override
  Widget build(BuildContext context) {
    return MobilePageHeader(
      title: '专业工具',
      subtitle: status?.configured == true ? status!.model : '尚未配置 AI 服务',
      leading: onBack == null
          ? null
          : IconButton(
              tooltip: '返回 AI 管家',
              onPressed: onBack,
              icon: const Icon(Icons.arrow_back),
            ),
      actions: [
        IconButton(
          tooltip: 'AI 服务设置',
          onPressed: onSettings,
          icon: const Icon(Icons.settings_outlined),
        ),
      ],
    );
  }
}

class _ToolSelector extends StatelessWidget {
  const _ToolSelector({
    required this.selected,
    required this.enabled,
    required this.onSelected,
  });

  final AiTool selected;
  final bool enabled;
  final ValueChanged<AiTool> onSelected;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < 600) {
          return DropdownButtonFormField<AiTool>(
            initialValue: selected,
            decoration: const InputDecoration(
              labelText: '选择专业工具',
              prefixIcon: Icon(Icons.tune),
            ),
            items: AiTool.values
                .map(
                  (tool) => DropdownMenuItem(
                    value: tool,
                    child: Row(
                      children: [
                        Icon(tool.icon, size: 18),
                        const SizedBox(width: 8),
                        Text(tool.label),
                      ],
                    ),
                  ),
                )
                .toList(),
            onChanged: enabled
                ? (value) {
                    if (value != null) onSelected(value);
                  }
                : null,
          );
        }
        return Wrap(
          spacing: 6,
          runSpacing: 6,
          children: AiTool.values
              .map(
                (tool) => ChoiceChip(
                  selected: tool == selected,
                  avatar: Icon(tool.icon, size: 17),
                  label: Text(tool.label),
                  onSelected: enabled ? (_) => onSelected(tool) : null,
                ),
              )
              .toList(),
        );
      },
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
    required this.reviewing,
    required this.cancelable,
    required this.onPickEntry,
    required this.onGenerate,
    required this.onCancel,
  });

  final AiTool tool;
  final TextEditingController inputController;
  final TextEditingController preferenceController;
  final String? selectedEntryTitle;
  final bool working;
  final bool reviewing;
  final bool cancelable;
  final VoidCallback onPickEntry;
  final VoidCallback onGenerate;
  final VoidCallback? onCancel;

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
              onPressed: working || reviewing ? null : onPickEntry,
              icon: const Icon(Icons.key_outlined),
              label: Text(selectedEntryTitle ?? '选择条目'),
            ),
            const SizedBox(height: 9),
          ],
          if (tool == AiTool.parse)
            TextField(
              controller: inputController,
              enabled: !working && !reviewing,
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
              enabled: !working && !reviewing,
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
              enabled: !working && !reviewing,
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
            child: cancelable
                ? OutlinedButton.icon(
                    onPressed: onCancel,
                    icon: const Icon(Icons.stop_rounded, size: 18),
                    label: const Text('取消请求'),
                  )
                : FilledButton.icon(
                    onPressed: working || reviewing ? null : onGenerate,
                    icon: const Icon(Icons.auto_awesome, size: 18),
                    label: Text(
                      reviewing
                          ? '请先处理建议'
                          : working
                          ? '已有请求处理中'
                          : '生成建议',
                    ),
                  ),
          ),
        ],
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
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(message, style: TextStyle(color: scheme.onErrorContainer)),
    );
  }
}
