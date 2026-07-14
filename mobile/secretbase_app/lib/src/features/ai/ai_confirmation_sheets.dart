import 'package:flutter/material.dart';
import 'package:secretbase/src/rust/mobile/models.dart';

Future<bool> showAiSendConfirmationSheet({
  required BuildContext context,
  required AiStatus? status,
  required AiSendSummary summary,
}) async {
  final target = Uri.tryParse(status?.baseUrl ?? '')?.host;
  return await showModalBottomSheet<bool>(
        context: context,
        useSafeArea: true,
        isScrollControlled: true,
        showDragHandle: true,
        constraints: const BoxConstraints(maxWidth: 620),
        builder: (sheetContext) => _ConfirmationSheet(
          icon: summary.includesFieldValues
              ? Icons.warning_amber_rounded
              : Icons.shield_outlined,
          title: summary.title,
          accent: summary.includesFieldValues
              ? Theme.of(sheetContext).colorScheme.error
              : Theme.of(sheetContext).colorScheme.primary,
          content: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _DestinationRow(
                label: '目标服务',
                value: target?.isNotEmpty == true ? target! : '自定义接口',
              ),
              _DestinationRow(
                label: '模型',
                value: status?.model.isNotEmpty == true ? status!.model : '未记录',
              ),
              if (summary.entryCount > 0)
                _DestinationRow(
                  label: '分析范围',
                  value: '${summary.entryCount} 个条目',
                ),
              if (summary.inputChars > 0)
                _DestinationRow(
                  label: '输入长度',
                  value: '${summary.inputChars} 个字符',
                ),
              const SizedBox(height: 12),
              Text(
                '本轮将发送',
                style: Theme.of(
                  sheetContext,
                ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 7),
              ...summary.categories.map(
                (category) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(
                        Icons.check_circle_outline,
                        size: 17,
                        color: Theme.of(sheetContext).colorScheme.primary,
                      ),
                      const SizedBox(width: 7),
                      Expanded(child: Text(category)),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: summary.includesFieldValues
                      ? Theme.of(sheetContext).colorScheme.errorContainer
                      : Theme.of(sheetContext).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  summary.privacyNote,
                  style: Theme.of(sheetContext).textTheme.bodySmall?.copyWith(
                    color: summary.includesFieldValues
                        ? Theme.of(sheetContext).colorScheme.onErrorContainer
                        : Theme.of(sheetContext).colorScheme.onPrimaryContainer,
                    fontWeight: FontWeight.w700,
                    height: 1.45,
                  ),
                ),
              ),
            ],
          ),
          confirmLabel: '确认并发送一次',
        ),
      ) ??
      false;
}

Future<bool> showAiApplyConfirmationSheet({
  required BuildContext context,
  required int selectedCount,
}) async {
  return await showModalBottomSheet<bool>(
        context: context,
        useSafeArea: true,
        showDragHandle: true,
        constraints: const BoxConstraints(maxWidth: 560),
        builder: (sheetContext) => _ConfirmationSheet(
          icon: Icons.fact_check_outlined,
          title: '应用 AI 操作计划',
          accent: Theme.of(sheetContext).colorScheme.primary,
          content: Text(
            '将原子应用已选的 $selectedCount 项操作。写入前会校验密码库版本并创建本机恢复快照。',
            style: Theme.of(
              sheetContext,
            ).textTheme.bodyMedium?.copyWith(height: 1.5),
          ),
          confirmLabel: '确认应用',
        ),
      ) ??
      false;
}

class _ConfirmationSheet extends StatelessWidget {
  const _ConfirmationSheet({
    required this.icon,
    required this.title,
    required this.accent,
    required this.content,
    required this.confirmLabel,
  });

  final IconData icon;
  final String title;
  final Color accent;
  final Widget content;
  final String confirmLabel;

  @override
  Widget build(BuildContext context) {
    final height = MediaQuery.sizeOf(context).height;
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: accent.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(icon, color: accent, size: 21),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            ConstrainedBox(
              constraints: BoxConstraints(maxHeight: height * 0.56),
              child: SingleChildScrollView(child: content),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.of(context).pop(false),
                    child: const Text('返回检查'),
                  ),
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: FilledButton(
                    onPressed: () => Navigator.of(context).pop(true),
                    child: Text(confirmLabel),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _DestinationRow extends StatelessWidget {
  const _DestinationRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 76,
            child: Text(
              label,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              value,
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}
