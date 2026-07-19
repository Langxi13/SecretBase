import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/ai/ai_confirmation_sheets.dart';
import 'package:secretbase/src/features/ai/ai_activity_controller.dart';
import 'package:secretbase/src/features/ai/ai_manager_composer.dart';
import 'package:secretbase/src/features/ai/ai_manager_dialogs.dart';
import 'package:secretbase/src/features/ai/ai_manager_widgets.dart';
import 'package:secretbase/src/features/ai/ai_plan_panel.dart';
import 'package:secretbase/src/features/ai/ai_screen.dart';
import 'package:secretbase/src/features/ai/ai_settings_dialog.dart';
import 'package:secretbase/src/features/ai/ai_transport.dart';
import 'package:secretbase/src/features/ai/ai_undo_controller.dart';
import 'package:secretbase/src/features/entries/entry_detail_dialog.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/preferences_controller.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class AiManagerScreen extends ConsumerStatefulWidget {
  const AiManagerScreen({super.key});

  @override
  ConsumerState<AiManagerScreen> createState() => _AiManagerScreenState();
}

class _AiManagerScreenState extends ConsumerState<AiManagerScreen> {
  final _messageController = TextEditingController();
  final _scrollController = ScrollController();
  AiStatus? _status;
  String? _conversationId;
  List<AiConversationMessage> _messages = [];
  final Map<String, String> _scopeEntries = {};
  AiPreview? _preview;
  final Set<String> _selectedPlanItems = {};
  final Set<String> _revealedDetails = {};
  final Set<String> _expandedPlanItems = {};
  String _mode = 'assistant';
  String? _pendingUserMessage;
  String? _navigationEntryId;
  String? _navigationEntryTitle;
  List<String> _turnWarnings = [];
  bool _loading = true;
  bool _working = false;
  String? _error;
  AiTransportOperation? _transportOperation;
  int? _activityToken;
  int _requestGeneration = 0;

  @override
  void initState() {
    super.initState();
    _loadInitial();
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
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _loadInitial() async {
    try {
      final status = await rust_api.aiStatus();
      final conversations = await rust_api.listAiConversations();
      AiConversation? conversation;
      if (conversations.isNotEmpty) {
        conversation = await rust_api.getAiConversation(
          id: conversations.first.id,
        );
      }
      final pendingPreview = await rust_api.pendingAiPreview();
      if (!mounted) return;
      setState(() {
        _status = status;
        _conversationId = conversation?.id;
        _messages = conversation?.messages ?? [];
        _loading = false;
        if (pendingPreview != null) _setPreview(pendingPreview);
      });
      _scrollToBottom();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = mobileErrorMessage(error);
      });
    }
  }

  Future<void> _retryInitial() async {
    if (_loading || _working) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    await _loadInitial();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AiManagerHeader(
          status: _status,
          onNewConversation: _working || _preview != null
              ? null
              : _newConversation,
          onHistory: _working || _preview != null ? null : _openHistory,
          onTools: _working || _preview != null ? null : _openProfessionalTools,
          onSettings: _working || _preview != null ? null : _openSettings,
        ),
        if (_loading)
          const Expanded(child: LoadingView(label: '正在读取 AI 管家'))
        else if (_error != null && _status == null)
          Expanded(
            child: ErrorView(message: _error!, onRetry: _retryInitial),
          )
        else if (_status?.configured != true)
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
          Expanded(
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 980),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(child: _buildConversation()),
                    const Divider(height: 1),
                    AiManagerComposer(
                      controller: _messageController,
                      mode: _mode,
                      selectedEntryCount: _scopeEntries.length,
                      working: _working,
                      reviewing: _preview != null,
                      onModeChanged: (value) => setState(() => _mode = value),
                      onScope: _openScope,
                      onPrompt: _usePrompt,
                      onTools: _working ? () {} : _openProfessionalTools,
                      onSend: _send,
                      onCancel: () => unawaited(_cancelRequest()),
                    ),
                  ],
                ),
              ),
            ),
          ),
        if (_working) const LinearProgressIndicator(minHeight: 2),
      ],
    );
  }

  Widget _buildConversation() {
    final undo = ref.watch(aiUndoControllerProvider);
    final hasContent =
        _messages.isNotEmpty ||
        _pendingUserMessage != null ||
        _preview != null ||
        undo.pending != null ||
        _error != null;
    if (!hasContent) {
      return const AiManagerWelcome();
    }
    final children = <Widget>[
      for (final message in _messages) AiManagerMessageBubble(message: message),
      if (_pendingUserMessage != null)
        AiManagerMessageBubble.pending(content: _pendingUserMessage!),
      if (_navigationEntryId != null)
        Align(
          alignment: Alignment.centerLeft,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 2, 12, 8),
            child: OutlinedButton.icon(
              onPressed: _working ? null : _openLocatedEntry,
              icon: const Icon(Icons.open_in_new, size: 18),
              label: Text('打开「${_navigationEntryTitle ?? '条目'}」'),
            ),
          ),
        ),
      if (_turnWarnings.isNotEmpty)
        AiManagerInlineNotice(
          icon: Icons.warning_amber_rounded,
          message: _turnWarnings.join('\n'),
          error: true,
        ),
      if (_error != null)
        AiManagerInlineNotice(
          icon: Icons.error_outline,
          message: _error!,
          error: true,
        ),
      if (undo.pending != null)
        AiUndoBanner(
          state: undo.pending!,
          onUndo: _working || undo.working ? null : _undoLastOperation,
        ),
      if (_preview != null)
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 4, 12, 14),
          child: AiPlanPanel(
            preview: _preview!,
            selected: _selectedPlanItems,
            revealed: _revealedDetails,
            expanded: _expandedPlanItems,
            working: _working,
            onSelectionChanged: (id, value) => setState(() {
              if (value) {
                _selectedPlanItems.add(id);
              } else {
                _selectedPlanItems.remove(id);
              }
            }),
            onSelectAll: (value) => setState(() {
              _selectedPlanItems.clear();
              if (value) {
                _selectedPlanItems.addAll(
                  _preview!.items.map((item) => item.id),
                );
              }
            }),
            onReveal: (key) => setState(() {
              if (!_revealedDetails.add(key)) _revealedDetails.remove(key);
            }),
            onExpanded: (id) => setState(() {
              if (!_expandedPlanItems.add(id)) {
                _expandedPlanItems.remove(id);
              }
            }),
            onApply: _applyPreview,
            onDiscard: _discardPreview,
          ),
        ),
    ];
    return ListView(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(vertical: 10),
      children: children,
    );
  }

  void _usePrompt(String prompt) {
    _messageController.text = prompt;
    _messageController.selection = TextSelection.collapsed(
      offset: prompt.length,
    );
  }

  Future<void> _send() async {
    final message = _messageController.text.trim();
    if (message.isEmpty || _working || _preview != null) return;
    if (!await _ensurePrivacyConsent()) return;
    final activity = ref.read(aiActivityControllerProvider.notifier);
    final activityToken = activity.acquire();
    if (activityToken == null) {
      setState(() => _error = '已有 AI 请求正在处理中，请稍后再试');
      return;
    }
    final generation = ++_requestGeneration;
    _activityToken = activityToken;
    setState(() {
      _working = true;
      _pendingUserMessage = message;
      _error = null;
      _turnWarnings = [];
      _navigationEntryId = null;
      _navigationEntryTitle = null;
      _preview = null;
      _selectedPlanItems.clear();
      _revealedDetails.clear();
      _expandedPlanItems.clear();
    });
    _scrollToBottom();
    AiTransportOperation? operation;
    try {
      final plan = await rust_api.prepareAiAssistantRequest(
        conversationId: _conversationId,
        message: message,
        mode: _mode,
        selectedEntryIds: _scopeEntries.keys.toList(),
      );
      if (!_isCurrentRequest(generation)) {
        unawaited(rust_api.cancelAiPending().catchError((_) {}));
        return;
      }
      if (!await _confirmSend(plan.summary)) {
        unawaited(rust_api.cancelAiPending().catchError((_) {}));
        if (_isCurrentRequest(generation)) {
          setState(() {
            _working = false;
            _pendingUserMessage = null;
          });
        }
        return;
      }
      if (!_isCurrentRequest(generation)) return;
      operation = AiTransport.start(plan.request);
      _transportOperation = operation;
      final response = await operation.future;
      if (!_isCurrentRequest(generation)) return;
      final result = await rust_api.consumeAiAssistantResponse(
        token: plan.token,
        content: response,
      );
      AiConversation? conversation;
      String? historyRefreshError;
      try {
        conversation = await rust_api.getAiConversation(
          id: result.conversationId,
        );
      } catch (error) {
        historyRefreshError = mobileErrorMessage(error);
      }
      if (!_isCurrentRequest(generation)) return;
      setState(() {
        _conversationId = result.conversationId;
        if (conversation != null) _messages = conversation.messages;
        _working = false;
        _pendingUserMessage = null;
        _messageController.clear();
        _turnWarnings = result.warnings;
        _error = historyRefreshError == null
            ? null
            : 'AI 已完成，但对话历史刷新失败，请稍后重新打开本页。';
        _navigationEntryId = result.navigationEntryId;
        _navigationEntryTitle = result.navigationEntryTitle;
        if (result.preview != null) _setPreview(result.preview!);
      });
      _scrollToBottom();
    } catch (error) {
      unawaited(rust_api.cancelAiPending().catchError((_) {}));
      if (!_isCurrentRequest(generation)) return;
      setState(() {
        _working = false;
        _pendingUserMessage = null;
        _error = _errorMessage(error);
      });
      _scrollToBottom();
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
      _pendingUserMessage = null;
      _error = 'AI 请求已取消';
    });
  }

  Future<void> _applyPreview() async {
    final preview = _preview;
    if (preview == null || _selectedPlanItems.isEmpty || _working) return;
    final confirmed = await showAiApplyConfirmationSheet(
      context: context,
      selectedCount: _selectedPlanItems.length,
    );
    if (confirmed != true) return;
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      final result = await rust_api.applyAiPreview(
        token: preview.token,
        selectedItemIds: _selectedPlanItems.toList(),
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
      AiConversation? conversation;
      if (_conversationId != null) {
        try {
          conversation = await rust_api.getAiConversation(id: _conversationId!);
        } catch (_) {
          refreshed = false;
        }
      }
      if (!mounted) return;
      setState(() {
        _working = false;
        if (conversation != null) _messages = conversation.messages;
        _preview = null;
        _selectedPlanItems.clear();
        _revealedDetails.clear();
        _expandedPlanItems.clear();
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            refreshed ? result.message : '${result.message}，但界面刷新不完整，请稍后重试。',
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _working = false;
        _error = _errorMessage(error);
      });
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
      AiConversation? conversation;
      var refreshed = true;
      if (_conversationId != null) {
        try {
          conversation = await rust_api.getAiConversation(id: _conversationId!);
        } catch (_) {
          refreshed = false;
        }
      }
      if (!mounted) return;
      setState(() {
        _working = false;
        _preview = null;
        _selectedPlanItems.clear();
        _revealedDetails.clear();
        _expandedPlanItems.clear();
        if (conversation != null) _messages = conversation.messages;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(refreshed ? message : '$message，但对话历史刷新不完整，请稍后重试。'),
        ),
      );
      _scrollToBottom();
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
      _selectedPlanItems.clear();
      _revealedDetails.clear();
      _expandedPlanItems.clear();
      _error = null;
    });
  }

  void _setPreview(AiPreview preview) {
    _preview = preview;
    _selectedPlanItems
      ..clear()
      ..addAll(
        preview.items
            .where((item) => !aiPreviewItemIsHighImpact(item))
            .map((item) => item.id),
      );
    _revealedDetails.clear();
    _expandedPlanItems.clear();
  }

  Future<void> _newConversation() async {
    if (_working || _preview != null) return;
    try {
      final conversation = await rust_api.createAiConversation(title: '新对话');
      if (!mounted) return;
      setState(() {
        _conversationId = conversation.id;
        _messages = [];
        _preview = null;
        _selectedPlanItems.clear();
        _revealedDetails.clear();
        _expandedPlanItems.clear();
        _scopeEntries.clear();
        _navigationEntryId = null;
        _navigationEntryTitle = null;
        _turnWarnings = [];
        _error = null;
      });
    } catch (error) {
      if (mounted) setState(() => _error = mobileErrorMessage(error));
    }
  }

  Future<void> _openHistory() async {
    if (_working || _preview != null) return;
    final id = await showAiHistoryDialog(
      context: context,
      currentConversationId: _conversationId,
    );
    if (id == null) return;
    if (id.isEmpty) {
      if (!mounted) return;
      setState(() {
        _conversationId = null;
        _messages = [];
        _preview = null;
        _selectedPlanItems.clear();
        _revealedDetails.clear();
        _expandedPlanItems.clear();
        _scopeEntries.clear();
        _navigationEntryId = null;
        _navigationEntryTitle = null;
        _turnWarnings = [];
        _error = null;
      });
      return;
    }
    try {
      final conversation = await rust_api.getAiConversation(id: id);
      if (!mounted) return;
      setState(() {
        _conversationId = conversation.id;
        _messages = conversation.messages;
        _preview = null;
        _selectedPlanItems.clear();
        _revealedDetails.clear();
        _expandedPlanItems.clear();
        _scopeEntries.clear();
        _navigationEntryId = null;
        _navigationEntryTitle = null;
        _turnWarnings = [];
        _error = null;
      });
      _scrollToBottom();
    } catch (error) {
      if (mounted) setState(() => _error = mobileErrorMessage(error));
    }
  }

  Future<void> _openScope() async {
    if (_working || _preview != null) return;
    final selection = await showAiScopeDialog(
      context: context,
      selected: _scopeEntries,
    );
    if (selection == null || !mounted) return;
    setState(() {
      _scopeEntries
        ..clear()
        ..addAll(selection.entries);
    });
  }

  Future<void> _openLocatedEntry() async {
    final id = _navigationEntryId;
    if (id == null) return;
    await showEntryDetailDialog(context: context, ref: ref, entryId: id);
  }

  Future<void> _openSettings() async {
    if (_working || _preview != null) return;
    final status = await showAiSettingsDialog(context: context, ref: ref);
    if (status != null && mounted) {
      setState(() {
        _status = status;
        _error = null;
      });
    }
  }

  Future<void> _openProfessionalTools() async {
    if (_working || _preview != null) return;
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (routeContext) => Scaffold(
          body: SafeArea(
            child: AiScreen(onBack: () => Navigator.of(routeContext).pop()),
          ),
        ),
      ),
    );
  }

  Future<bool> _ensurePrivacyConsent() async {
    if (ref.read(preferencesProvider).aiPrivacyAccepted) return true;
    final accepted = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('AI 隐私确认'),
        content: const Text(
          '普通管家不会发送已有字段值、完整网址、备注、主密码或真实条目 ID。只有你主动切换到“AI 新建”时，输入的完整原文才会发送到所配置的第三方服务。',
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

  Future<bool> _confirmSend(AiSendSummary summary) async {
    return showAiSendConfirmationSheet(
      context: context,
      status: _status,
      summary: summary,
    );
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_scrollController.hasClients) return;
      unawaited(
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOut,
        ),
      );
    });
  }

  String _errorMessage(Object error) {
    if (error is AiTransportException) return error.message;
    return mobileErrorMessage(error);
  }
}
