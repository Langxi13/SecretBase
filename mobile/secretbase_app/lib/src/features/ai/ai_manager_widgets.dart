import 'package:flutter/material.dart';
import 'package:secretbase/src/rust/mobile/models.dart';

class AiManagerHeader extends StatelessWidget {
  const AiManagerHeader({
    required this.status,
    required this.onNewConversation,
    required this.onHistory,
    required this.onTools,
    required this.onSettings,
    super.key,
  });

  final AiStatus? status;
  final VoidCallback? onNewConversation;
  final VoidCallback? onHistory;
  final VoidCallback? onTools;
  final VoidCallback? onSettings;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 8, 6, 8),
      child: Row(
        children: [
          Expanded(
            child: Row(
              children: [
                Text(
                  'AI 管家',
                  style: Theme.of(
                    context,
                  ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
                ),
                if (status?.configured == true && width >= 620) ...[
                  const SizedBox(width: 10),
                  Flexible(
                    child: Container(
                      constraints: const BoxConstraints(maxWidth: 190),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.primaryContainer,
                        borderRadius: BorderRadius.circular(5),
                      ),
                      child: Text(
                        status!.model,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: Theme.of(
                            context,
                          ).colorScheme.onPrimaryContainer,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
          IconButton(
            tooltip: '新对话',
            onPressed: onNewConversation,
            icon: const Icon(Icons.add_comment_outlined),
          ),
          IconButton(
            tooltip: '对话历史',
            onPressed: onHistory,
            icon: const Icon(Icons.history),
          ),
          IconButton(
            tooltip: '专业工具',
            onPressed: onTools,
            icon: const Icon(Icons.tune),
          ),
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

class AiManagerWelcome extends StatelessWidget {
  const AiManagerWelcome({required this.onPrompt, super.key});

  final ValueChanged<String> onPrompt;

  @override
  Widget build(BuildContext context) {
    final prompts = [
      (Icons.new_label_outlined, '整理缺失或不合理的标签'),
      (Icons.folder_copy_outlined, '按用途给条目整理密码组'),
      (Icons.merge_type, '检查相似标签并给出合并建议'),
      (Icons.view_list_outlined, '检查字段名和隐藏、复制设置'),
    ];
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 42, 20, 24),
      child: Column(
        children: [
          Icon(
            Icons.auto_awesome,
            size: 44,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 14),
          Text(
            '需要整理什么？',
            style: Theme.of(
              context,
            ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 22),
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 8,
            runSpacing: 8,
            children: prompts
                .map(
                  (item) => OutlinedButton.icon(
                    onPressed: () => onPrompt(item.$2),
                    icon: Icon(item.$1, size: 18),
                    label: Text(item.$2),
                  ),
                )
                .toList(),
          ),
        ],
      ),
    );
  }
}

class AiManagerMessageBubble extends StatelessWidget {
  const AiManagerMessageBubble({required this.message, super.key})
    : pendingContent = null,
      pending = false;

  const AiManagerMessageBubble.pending({required String content, super.key})
    : message = null,
      pendingContent = content,
      pending = true;

  final AiConversationMessage? message;
  final String? pendingContent;
  final bool pending;

  @override
  Widget build(BuildContext context) {
    final user = pending || message?.role == 'user';
    final content = pendingContent ?? message?.content ?? '';
    final scheme = Theme.of(context).colorScheme;
    return Align(
      alignment: user ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 720),
        margin: EdgeInsets.fromLTRB(user ? 54 : 12, 4, user ? 12 : 54, 4),
        padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 10),
        decoration: BoxDecoration(
          color: user ? scheme.primaryContainer : scheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(7),
          border: Border.all(
            color: user ? scheme.primaryContainer : scheme.outlineVariant,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (!user) ...[
              Icon(Icons.auto_awesome, size: 17, color: scheme.primary),
              const SizedBox(width: 8),
            ],
            Flexible(
              child: Text(
                content,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: user ? scheme.onPrimaryContainer : scheme.onSurface,
                  height: 1.45,
                ),
              ),
            ),
            if (pending) ...[
              const SizedBox(width: 8),
              const SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class AiManagerComposer extends StatelessWidget {
  const AiManagerComposer({
    required this.controller,
    required this.mode,
    required this.selectedEntryCount,
    required this.working,
    required this.onModeChanged,
    required this.onScope,
    required this.onSend,
    super.key,
  });

  final TextEditingController controller;
  final String mode;
  final int selectedEntryCount;
  final bool working;
  final ValueChanged<String> onModeChanged;
  final VoidCallback onScope;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 9, 12, 11),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 8,
              runSpacing: 7,
              children: [
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(
                      value: 'assistant',
                      icon: Icon(Icons.auto_awesome_outlined, size: 17),
                      label: Text('管家'),
                    ),
                    ButtonSegment(
                      value: 'sensitive_create',
                      icon: Icon(Icons.add_box_outlined, size: 17),
                      label: Text('AI 新建'),
                    ),
                  ],
                  selected: {mode},
                  onSelectionChanged: working
                      ? null
                      : (values) => onModeChanged(values.first),
                  showSelectedIcon: false,
                ),
                if (mode == 'assistant')
                  OutlinedButton.icon(
                    onPressed: working ? null : onScope,
                    icon: const Icon(Icons.filter_alt_outlined, size: 18),
                    label: Text(
                      selectedEntryCount == 0
                          ? '全部条目'
                          : '指定 $selectedEntryCount 项',
                    ),
                  ),
              ],
            ),
            if (mode == 'sensitive_create') ...[
              const SizedBox(height: 6),
              Text(
                'AI 新建会发送你输入的完整原文，已有条目字段值仍不会发送。',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.error,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
            const SizedBox(height: 8),
            TextField(
              controller: controller,
              enabled: !working,
              minLines: 1,
              maxLines: mode == 'sensitive_create' ? 7 : 5,
              maxLength: 6000,
              decoration: InputDecoration(
                hintText: mode == 'sensitive_create'
                    ? '粘贴需要创建为新条目的原文'
                    : '输入整理、定位或结构调整需求',
                counterText: '',
                suffixIcon: IconButton(
                  tooltip: '发送',
                  onPressed: working ? null : onSend,
                  icon: const Icon(Icons.send),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class AiManagerInlineNotice extends StatelessWidget {
  const AiManagerInlineNotice({
    required this.icon,
    required this.message,
    required this.error,
    super.key,
  });

  final IconData icon;
  final String message;
  final bool error;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 5, 12, 9),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: error ? scheme.errorContainer : scheme.secondaryContainer,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18),
          const SizedBox(width: 8),
          Expanded(child: Text(message)),
        ],
      ),
    );
  }
}

class AiProfessionalToolsAppBar extends StatelessWidget
    implements PreferredSizeWidget {
  const AiProfessionalToolsAppBar({super.key});

  @override
  Size get preferredSize => const Size.fromHeight(48);

  @override
  Widget build(BuildContext context) {
    return AppBar(toolbarHeight: 48, title: const Text('AI 专业工具'));
  }
}
