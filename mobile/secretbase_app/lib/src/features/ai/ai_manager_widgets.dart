import 'package:flutter/material.dart';
import 'package:secretbase/src/core/widgets/mobile_chrome.dart';
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
    final compact = MediaQuery.sizeOf(context).width < 560;
    return MobilePageHeader(
      title: 'AI 管家',
      subtitle: status?.configured == true ? status!.model : '尚未配置 AI 服务',
      actions: [
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
        if (!compact) ...[
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
        ] else
          PopupMenuButton<String>(
            tooltip: '更多 AI 功能',
            onSelected: (value) {
              if (value == 'tools') onTools?.call();
              if (value == 'settings') onSettings?.call();
            },
            itemBuilder: (context) => [
              PopupMenuItem(
                value: 'tools',
                enabled: onTools != null,
                child: const ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(Icons.tune),
                  title: Text('专业工具'),
                ),
              ),
              PopupMenuItem(
                value: 'settings',
                enabled: onSettings != null,
                child: const ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(Icons.settings_outlined),
                  title: Text('服务设置'),
                ),
              ),
            ],
          ),
      ],
    );
  }
}

class AiManagerWelcome extends StatelessWidget {
  const AiManagerWelcome({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 54, 24, 24),
      child: Column(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.primaryContainer,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              Icons.auto_awesome,
              size: 28,
              color: Theme.of(context).colorScheme.onPrimaryContainer,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            '今天想整理什么？',
            style: Theme.of(
              context,
            ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          Text(
            '输入你的整理需求，发送前会先展示本轮数据清单。',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              height: 1.5,
            ),
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
        margin: EdgeInsets.fromLTRB(user ? 42 : 12, 4, user ? 12 : 42, 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        decoration: BoxDecoration(
          color: user ? scheme.primaryContainer : scheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(8),
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
        borderRadius: BorderRadius.circular(8),
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

class AiUndoBanner extends StatelessWidget {
  const AiUndoBanner({required this.state, required this.onUndo, super.key});

  final AiUndoState state;
  final VoidCallback? onUndo;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 5, 12, 9),
      padding: const EdgeInsets.fromLTRB(10, 8, 8, 8),
      decoration: BoxDecoration(
        color: scheme.tertiaryContainer,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: scheme.tertiary.withValues(alpha: 0.24)),
      ),
      child: Row(
        children: [
          Icon(Icons.restore, size: 19, color: scheme.onTertiaryContainer),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '已应用 ${state.appliedCount} 项 AI 操作',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: scheme.onTertiaryContainer,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(width: 6),
          TextButton.icon(
            onPressed: onUndo,
            icon: onUndo == null
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.undo, size: 17),
            label: const Text('撤回'),
          ),
        ],
      ),
    );
  }
}
