import 'package:flutter/material.dart';

const aiQuickPrompts = [
  ('分类', Icons.category_outlined, '统计当前范围内未分组和未加标签的条目'),
  ('标签', Icons.sell_outlined, '检查当前范围内重复、近义、过细或无效的标签，只生成标签管理计划'),
  ('密码组', Icons.folder_outlined, '检查当前范围内密码组的分类是否合理，只生成密码组管理计划'),
  ('字段', Icons.view_stream_outlined, '检查当前范围内字段命名是否统一，只生成字段结构调整计划'),
];

class AiManagerComposer extends StatelessWidget {
  const AiManagerComposer({
    required this.controller,
    required this.mode,
    required this.selectedEntryCount,
    required this.working,
    required this.onModeChanged,
    required this.onScope,
    required this.onPrompt,
    required this.onTools,
    required this.onSend,
    super.key,
  });

  final TextEditingController controller;
  final String mode;
  final int selectedEntryCount;
  final bool working;
  final ValueChanged<String> onModeChanged;
  final VoidCallback onScope;
  final ValueChanged<String> onPrompt;
  final VoidCallback onTools;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final sensitive = mode == 'sensitive_create';
    return SafeArea(
      top: false,
      child: Material(
        color: scheme.surfaceContainerLowest,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(10, 7, 10, 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _ComposerContextLine(
                sensitive: sensitive,
                selectedEntryCount: selectedEntryCount,
              ),
              const SizedBox(height: 6),
              Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  IconButton.outlined(
                    tooltip: '更多 AI 操作',
                    onPressed: () => _openActions(context),
                    icon: const Icon(Icons.add_rounded),
                    style: IconButton.styleFrom(
                      fixedSize: const Size(42, 42),
                      minimumSize: const Size(42, 42),
                      shape: const CircleBorder(),
                    ),
                  ),
                  const SizedBox(width: 7),
                  Expanded(
                    child: TextField(
                      controller: controller,
                      enabled: !working,
                      minLines: 1,
                      maxLines: sensitive ? 6 : 4,
                      maxLength: 6000,
                      textInputAction: TextInputAction.newline,
                      decoration: InputDecoration(
                        hintText: sensitive ? '描述需要新建的条目' : '向 AI 管家描述整理需求',
                        counterText: '',
                      ),
                    ),
                  ),
                  const SizedBox(width: 7),
                  IconButton.filled(
                    tooltip: '预览发送',
                    onPressed: working ? null : onSend,
                    icon: const Icon(Icons.arrow_upward_rounded),
                    style: IconButton.styleFrom(
                      fixedSize: const Size(44, 44),
                      minimumSize: const Size(44, 44),
                      shape: const CircleBorder(),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _openActions(BuildContext context) async {
    final panel = AiComposerActionPanel(
      mode: mode,
      selectedEntryCount: selectedEntryCount,
      working: working,
      onModeChanged: onModeChanged,
      onScope: onScope,
      onPrompt: onPrompt,
      onTools: onTools,
    );
    if (MediaQuery.sizeOf(context).width >= 600) {
      await showDialog<void>(
        context: context,
        builder: (context) => Dialog(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: panel,
          ),
        ),
      );
      return;
    }
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (context) => panel,
    );
  }
}

class _ComposerContextLine extends StatelessWidget {
  const _ComposerContextLine({
    required this.sensitive,
    required this.selectedEntryCount,
  });

  final bool sensitive;
  final int selectedEntryCount;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final scope = selectedEntryCount == 0 ? '全部条目' : '已选 $selectedEntryCount 条';
    return Row(
      children: [
        Icon(
          sensitive ? Icons.warning_amber_rounded : Icons.shield_outlined,
          size: 15,
          color: sensitive ? scheme.error : scheme.primary,
        ),
        const SizedBox(width: 5),
        Expanded(
          child: Text(
            sensitive ? 'AI 新建 · 本轮完整输入 · 发送前确认' : '管家 · $scope · 不含已有字段值',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: sensitive ? scheme.error : scheme.onSurfaceVariant,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }
}

class AiComposerActionPanel extends StatelessWidget {
  const AiComposerActionPanel({
    required this.mode,
    required this.selectedEntryCount,
    required this.working,
    required this.onModeChanged,
    required this.onScope,
    required this.onPrompt,
    required this.onTools,
    super.key,
  });

  final String mode;
  final int selectedEntryCount;
  final bool working;
  final ValueChanged<String> onModeChanged;
  final VoidCallback onScope;
  final ValueChanged<String> onPrompt;
  final VoidCallback onTools;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 18),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '更多操作',
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 12),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 8,
            crossAxisSpacing: 8,
            childAspectRatio: 2.55,
            children: aiQuickPrompts
                .map(
                  (prompt) => _PanelActionButton(
                    label: prompt.$1,
                    icon: prompt.$2,
                    enabled: !working,
                    onPressed: () =>
                        _closeThen(context, () => onPrompt(prompt.$3)),
                  ),
                )
                .toList(),
          ),
          const SizedBox(height: 14),
          Text(
            '输入模式',
            style: Theme.of(
              context,
            ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 7),
          Row(
            children: [
              Expanded(
                child: _ModeButton(
                  label: '管家',
                  icon: Icons.auto_awesome_outlined,
                  selected: mode == 'assistant',
                  enabled: !working,
                  onPressed: () =>
                      _closeThen(context, () => onModeChanged('assistant')),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _ModeButton(
                  label: 'AI 新建',
                  icon: Icons.add_box_outlined,
                  selected: mode == 'sensitive_create',
                  enabled: !working,
                  onPressed: () => _closeThen(
                    context,
                    () => onModeChanged('sensitive_create'),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          _PanelListAction(
            icon: Icons.filter_alt_outlined,
            title: '分析范围',
            subtitle: selectedEntryCount == 0
                ? '全部条目'
                : '已选择 $selectedEntryCount 条',
            enabled: !working && mode == 'assistant',
            onTap: () => _closeThen(context, onScope),
          ),
          _PanelListAction(
            icon: Icons.tune,
            title: '专业工具',
            subtitle: working ? '可查看；当前请求完成前不能发起新请求' : '打开五项独立整理工具',
            enabled: true,
            onTap: () => _closeThen(context, onTools),
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: mode == 'sensitive_create'
                  ? scheme.errorContainer
                  : scheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              mode == 'sensitive_create'
                  ? 'AI 新建会发送你本轮输入的完整原文；已有字段值仍不会发送。'
                  : '普通管家只使用条目结构信息，不发送已有字段值、备注或完整网址。',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }

  void _closeThen(BuildContext context, VoidCallback callback) {
    Navigator.of(context).pop();
    WidgetsBinding.instance.addPostFrameCallback((_) => callback());
  }
}

class _PanelActionButton extends StatelessWidget {
  const _PanelActionButton({
    required this.label,
    required this.icon,
    required this.enabled,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final bool enabled;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: enabled ? onPressed : null,
      icon: Icon(icon, size: 19),
      label: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis),
    );
  }
}

class _ModeButton extends StatelessWidget {
  const _ModeButton({
    required this.label,
    required this.icon,
    required this.selected,
    required this.enabled,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final bool enabled;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return selected
        ? FilledButton.tonalIcon(
            onPressed: enabled ? onPressed : null,
            icon: Icon(icon, size: 18),
            label: Text(label),
          )
        : OutlinedButton.icon(
            onPressed: enabled ? onPressed : null,
            icon: Icon(icon, size: 18),
            label: Text(label),
          );
  }
}

class _PanelListAction extends StatelessWidget {
  const _PanelListAction({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.enabled,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      enabled: enabled,
      leading: Icon(icon),
      title: Text(title),
      subtitle: Text(subtitle, maxLines: 2, overflow: TextOverflow.ellipsis),
      trailing: const Icon(Icons.chevron_right),
      onTap: enabled ? onTap : null,
    );
  }
}
