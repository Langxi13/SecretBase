import 'package:flutter/material.dart';

class AiManagerComposer extends StatelessWidget {
  const AiManagerComposer({
    required this.controller,
    required this.mode,
    required this.selectedEntryCount,
    required this.working,
    required this.onModeChanged,
    required this.onScope,
    required this.onPrompt,
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
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final prompts = [
      ('分类', '统计当前范围内未分组和未加标签的条目'),
      ('标签', '检查当前范围内重复、近义、过细或无效的标签，只生成标签管理计划'),
      ('密码组', '检查当前范围内密码组的分类是否合理，只生成密码组管理计划'),
      ('字段', '检查当前范围内字段命名是否统一，只生成字段结构调整计划'),
    ];
    final scheme = Theme.of(context).colorScheme;
    return SafeArea(
      top: false,
      child: Material(
        color: scheme.surfaceContainerLowest,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: prompts
                    .map(
                      (prompt) => Expanded(
                        child: Padding(
                          padding: EdgeInsets.only(
                            right: prompt == prompts.last ? 0 : 5,
                          ),
                          child: _QuickPromptButton(
                            label: prompt.$1,
                            enabled: !working,
                            onPressed: () => onPrompt(prompt.$2),
                          ),
                        ),
                      ),
                    )
                    .toList(),
              ),
              const SizedBox(height: 7),
              Row(
                children: [
                  Expanded(
                    flex: 3,
                    child: _ModeToggle(
                      mode: mode,
                      enabled: !working,
                      onChanged: onModeChanged,
                    ),
                  ),
                  const SizedBox(width: 7),
                  Expanded(
                    flex: 2,
                    child: _ScopeButton(
                      enabled: !working && mode == 'assistant',
                      count: selectedEntryCount,
                      onPressed: onScope,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 5),
              Row(
                children: [
                  Icon(
                    mode == 'sensitive_create'
                        ? Icons.warning_amber_rounded
                        : Icons.shield_outlined,
                    size: 15,
                    color: mode == 'sensitive_create'
                        ? scheme.error
                        : scheme.primary,
                  ),
                  const SizedBox(width: 5),
                  Expanded(
                    child: Text(
                      mode == 'sensitive_create'
                          ? '将发送本轮完整输入；已有字段值仍不会发送'
                          : '发送前确认 · 不含已有字段值、备注和完整网址',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: mode == 'sensitive_create'
                            ? scheme.error
                            : scheme.onSurfaceVariant,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 7),
              Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Expanded(
                    child: TextField(
                      controller: controller,
                      enabled: !working,
                      minLines: 1,
                      maxLines: mode == 'sensitive_create' ? 6 : 4,
                      maxLength: 6000,
                      textInputAction: TextInputAction.newline,
                      decoration: InputDecoration(
                        hintText: mode == 'sensitive_create'
                            ? '描述需要新建的条目'
                            : '输入整理、定位或结构调整需求',
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
}

class _QuickPromptButton extends StatelessWidget {
  const _QuickPromptButton({
    required this.label,
    required this.enabled,
    required this.onPressed,
  });

  final String label;
  final bool enabled;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surfaceContainerLow,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(7),
        side: BorderSide(color: scheme.outlineVariant),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: enabled ? onPressed : null,
        child: SizedBox(
          height: 36,
          child: Center(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                color: enabled ? scheme.onSurface : scheme.outline,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _ModeToggle extends StatelessWidget {
  const _ModeToggle({
    required this.mode,
    required this.enabled,
    required this.onChanged,
  });

  final String mode;
  final bool enabled;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      height: 38,
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Row(
        children: [
          _ModeOption(
            label: '管家',
            icon: Icons.auto_awesome_outlined,
            selected: mode == 'assistant',
            enabled: enabled,
            onTap: () => onChanged('assistant'),
          ),
          _ModeOption(
            label: 'AI 新建',
            icon: Icons.add_box_outlined,
            selected: mode == 'sensitive_create',
            enabled: enabled,
            onTap: () => onChanged('sensitive_create'),
          ),
        ],
      ),
    );
  }
}

class _ModeOption extends StatelessWidget {
  const _ModeOption({
    required this.label,
    required this.icon,
    required this.selected,
    required this.enabled,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Expanded(
      child: Material(
        color: selected ? scheme.primaryContainer : Colors.transparent,
        borderRadius: BorderRadius.circular(6),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: enabled ? onTap : null,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 15,
                color: selected
                    ? scheme.onPrimaryContainer
                    : scheme.onSurfaceVariant,
              ),
              const SizedBox(width: 4),
              Flexible(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: selected
                        ? scheme.onPrimaryContainer
                        : scheme.onSurfaceVariant,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ScopeButton extends StatelessWidget {
  const _ScopeButton({
    required this.enabled,
    required this.count,
    required this.onPressed,
  });

  final bool enabled;
  final int count;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surfaceContainerLow,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(color: scheme.outlineVariant),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: enabled ? onPressed : null,
        child: SizedBox(
          height: 38,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.filter_alt_outlined,
                size: 16,
                color: enabled ? scheme.primary : scheme.outline,
              ),
              const SizedBox(width: 5),
              Flexible(
                child: Text(
                  count == 0 ? '全部条目' : '已选 $count 项',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: enabled ? scheme.onSurface : scheme.outline,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
