import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/ai/ai_confirmation_sheets.dart';
import 'package:secretbase/src/features/ai/ai_manager_composer.dart';
import 'package:secretbase/src/features/ai/ai_manager_dialogs.dart';
import 'package:secretbase/src/features/ai/ai_manager_widgets.dart';
import 'package:secretbase/src/features/ai/ai_plan_panel.dart';
import 'package:secretbase/src/features/ai/ai_screen.dart';
import 'package:secretbase/src/features/ai/ai_settings_dialog.dart';
import 'package:secretbase/src/features/ai/ai_transport.dart';
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

  @override
  void initState() {
    super.initState();
    _loadInitial();
  }

  @override
  void dispose() {
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

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AiManagerHeader(
          status: _status,
          onNewConversation: _working ? null : _newConversation,
          onHistory: _working ? null : _openHistory,
          onTools: _working || _preview != null ? null : _openProfessionalTools,
          onSettings: _openSettings,
        ),
        if (_loading)
          const Expanded(child: LoadingView(label: '正在读取 AI 管家'))
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
                      onModeChanged: (value) => setState(() => _mode = value),
                      onScope: _openScope,
                      onPrompt: _usePrompt,
                      onSend: _send,
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
    final hasContent =
        _messages.isNotEmpty ||
        _pendingUserMessage != null ||
        _preview != null ||
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
    if (message.isEmpty || _working) return;
    if (!await _ensurePrivacyConsent()) return;
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
    try {
      final plan = await rust_api.prepareAiAssistantRequest(
        conversationId: _conversationId,
        message: message,
        mode: _mode,
        selectedEntryIds: _scopeEntries.keys.toList(),
      );
      if (!mounted || !await _confirmSend(plan.summary)) {
        if (mounted) {
          setState(() {
            _working = false;
            _pendingUserMessage = null;
          });
        }
        return;
      }
      final response = await AiTransport.send(plan.request);
      final result = await rust_api.consumeAiAssistantResponse(
        token: plan.token,
        content: response,
      );
      final conversation = await rust_api.getAiConversation(
        id: result.conversationId,
      );
      if (!mounted) return;
      setState(() {
        _conversationId = result.conversationId;
        _messages = conversation.messages;
        _working = false;
        _pendingUserMessage = null;
        _messageController.clear();
        _turnWarnings = result.warnings;
        _navigationEntryId = result.navigationEntryId;
        _navigationEntryTitle = result.navigationEntryTitle;
        if (result.preview != null) _setPreview(result.preview!);
      });
      _scrollToBottom();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _working = false;
        _pendingUserMessage = null;
        _error = _errorMessage(error);
      });
      _scrollToBottom();
    }
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
      await ref.read(vaultControllerProvider.notifier).refreshStatus();
      ref.invalidate(entryPageProvider);
      ref.invalidate(taxonomyProvider);
      if (!mounted) return;
      setState(() {
        _working = false;
        _preview = null;
        _selectedPlanItems.clear();
        _revealedDetails.clear();
        _expandedPlanItems.clear();
      });
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(result.message)));
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _working = false;
        _error = _errorMessage(error);
      });
    }
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
    final id = await showAiHistoryDialog(context: context);
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
    final status = await showAiSettingsDialog(context: context, ref: ref);
    if (status != null && mounted) {
      setState(() {
        _status = status;
        _error = null;
      });
    }
  }

  Future<void> _openProfessionalTools() async {
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
