import 'package:flutter/material.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/rust/mobile/models.dart';

class AiPlanPanel extends StatelessWidget {
  const AiPlanPanel({
    required this.preview,
    required this.selected,
    required this.revealed,
    required this.working,
    required this.onSelectionChanged,
    required this.onSelectAll,
    required this.onReveal,
    required this.onApply,
    super.key,
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
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLow,
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(
                Icons.fact_check_outlined,
                size: 20,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  preview.title,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
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
            const SizedBox(height: 9),
            _WarningBand(warnings: preview.warnings),
          ],
          const SizedBox(height: 10),
          if (preview.items.isEmpty)
            const EmptyView(icon: Icons.task_alt_outlined, title: '没有需要应用的建议')
          else
            ...preview.items.map(
              (item) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _PlanItem(
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
      ),
    );
  }
}

class _PlanItem extends StatelessWidget {
  const _PlanItem({
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
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 9, 10, 10),
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
                const SizedBox(width: 5),
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
              const SizedBox(height: 8),
              ...item.details.asMap().entries.map((entry) {
                final key = '${item.id}:${entry.key}';
                final detail = entry.value;
                return _DetailRow(
                  detail: detail,
                  revealed: !detail.sensitive || revealed.contains(key),
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

class _DetailRow extends StatelessWidget {
  const _DetailRow({
    required this.detail,
    required this.revealed,
    required this.onReveal,
  });

  final AiPreviewDetail detail;
  final bool revealed;
  final VoidCallback? onReveal;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final changeColor = switch (detail.changeType) {
      'add' => scheme.primary,
      'remove' => scheme.error,
      'update' => scheme.tertiary,
      _ => scheme.onSurfaceVariant,
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 3,
            height: 18,
            margin: const EdgeInsets.only(top: 1),
            decoration: BoxDecoration(
              color: changeColor,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 74,
            child: Text(
              detail.label,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              revealed ? detail.value : '••••••••',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
          if (onReveal != null)
            IconButton(
              tooltip: revealed ? '隐藏内容' : '显示内容',
              onPressed: onReveal,
              visualDensity: VisualDensity.compact,
              iconSize: 18,
              icon: Icon(
                revealed
                    ? Icons.visibility_off_outlined
                    : Icons.visibility_outlined,
              ),
            ),
        ],
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
      padding: const EdgeInsets.all(9),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(5),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.warning_amber_rounded, size: 18, color: scheme.error),
          const SizedBox(width: 7),
          Expanded(
            child: Text(
              warnings.join('\n'),
              style: Theme.of(
                context,
              ).textTheme.bodySmall?.copyWith(color: scheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }
}
