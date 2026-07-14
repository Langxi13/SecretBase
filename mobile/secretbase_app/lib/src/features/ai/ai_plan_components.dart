part of 'ai_plan_panel.dart';

class _PlanSummary extends StatelessWidget {
  const _PlanSummary({
    required this.preview,
    required this.selectedCount,
    required this.allSelected,
    required this.onSelectAll,
  });

  final AiPreview preview;
  final int selectedCount;
  final bool allSelected;
  final ValueChanged<bool>? onSelectAll;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.fromLTRB(11, 10, 8, 10),
      decoration: BoxDecoration(
        color: scheme.primaryContainer.withValues(alpha: 0.48),
        border: Border.all(color: scheme.primary.withValues(alpha: 0.24)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(Icons.fact_check_outlined, size: 20, color: scheme.primary),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      preview.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    Text(
                      '${preview.items.length} 项建议 · 已选 $selectedCount 项',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              Checkbox(
                value: allSelected,
                onChanged: onSelectAll == null
                    ? null
                    : (value) => onSelectAll!(value ?? false),
              ),
            ],
          ),
          const SizedBox(height: 5),
          Text(
            preview.privacyNote,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: scheme.onSurfaceVariant,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }
}

class _PlanGroup extends StatelessWidget {
  const _PlanGroup({
    required this.label,
    required this.items,
    required this.selected,
    required this.revealed,
    required this.expanded,
    required this.onSelectionChanged,
    required this.onReveal,
    required this.onExpanded,
  });

  final String label;
  final List<AiPreviewItem> items;
  final Set<String> selected;
  final Set<String> revealed;
  final Set<String> expanded;
  final void Function(String id, bool value) onSelectionChanged;
  final ValueChanged<String> onReveal;
  final ValueChanged<String> onExpanded;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final color = _colorFor(scheme);
    final selectedCount = items
        .where((item) => selected.contains(item.id))
        .length;
    final allSelected = selectedCount == items.length;
    final checkboxValue = allSelected
        ? true
        : selectedCount == 0
        ? false
        : null;
    return Container(
      decoration: BoxDecoration(
        border: Border(left: BorderSide(color: color, width: 3)),
      ),
      child: Padding(
        padding: const EdgeInsets.only(left: 7),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              constraints: const BoxConstraints(minHeight: 40),
              padding: const EdgeInsets.fromLTRB(4, 2, 8, 2),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(7),
              ),
              child: Row(
                children: [
                  Checkbox(
                    tristate: true,
                    value: checkboxValue,
                    onChanged: (value) {
                      final next = value != false;
                      for (final item in items) {
                        onSelectionChanged(item.id, next);
                      }
                    },
                  ),
                  Icon(_iconFor(), size: 17, color: color),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      label,
                      style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  Text(
                    '$selectedCount / ${items.length}',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 6),
            ...items.map(
              (item) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: _PlanItem(
                  item: item,
                  selected: selected.contains(item.id),
                  expanded: expanded.contains(item.id),
                  revealed: revealed,
                  onSelected: (value) => onSelectionChanged(item.id, value),
                  onExpanded: () => onExpanded(item.id),
                  onReveal: onReveal,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Color _colorFor(ColorScheme scheme) {
    return switch (label) {
      '密码组' => scheme.tertiary,
      '标签' => scheme.primary,
      '条目结构' => scheme.secondary,
      '条目创建' => const Color(0xFF26834A),
      _ => scheme.onSurfaceVariant,
    };
  }

  IconData _iconFor() {
    return switch (label) {
      '密码组' => Icons.folder_outlined,
      '标签' => Icons.sell_outlined,
      '条目结构' => Icons.view_list_outlined,
      '条目创建' => Icons.add_box_outlined,
      _ => Icons.tune,
    };
  }
}

class _PlanItem extends StatelessWidget {
  const _PlanItem({
    required this.item,
    required this.selected,
    required this.expanded,
    required this.revealed,
    required this.onSelected,
    required this.onExpanded,
    required this.onReveal,
  });

  final AiPreviewItem item;
  final bool selected;
  final bool expanded;
  final Set<String> revealed;
  final ValueChanged<bool> onSelected;
  final VoidCallback onExpanded;
  final ValueChanged<String> onReveal;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final highImpact = aiPreviewItemIsHighImpact(item);
    return Container(
      decoration: BoxDecoration(
        color: selected ? scheme.surface : scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: highImpact
              ? scheme.error.withValues(alpha: 0.45)
              : scheme.outlineVariant,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          InkWell(
            borderRadius: BorderRadius.circular(8),
            onTap: () => onSelected(!selected),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(5, 6, 4, 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Checkbox(
                    value: selected,
                    onChanged: (value) => onSelected(value ?? false),
                  ),
                  const SizedBox(width: 3),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                item.title,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: Theme.of(context).textTheme.titleSmall
                                    ?.copyWith(fontWeight: FontWeight.w800),
                              ),
                            ),
                            if (highImpact)
                              Container(
                                margin: const EdgeInsets.only(left: 6),
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 5,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: scheme.errorContainer,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  '高影响',
                                  style: Theme.of(context).textTheme.labelSmall
                                      ?.copyWith(
                                        color: scheme.onErrorContainer,
                                        fontWeight: FontWeight.w800,
                                      ),
                                ),
                              ),
                          ],
                        ),
                        if (item.subtitle.isNotEmpty) ...[
                          const SizedBox(height: 2),
                          Text(
                            item.subtitle,
                            style: Theme.of(context).textTheme.labelSmall
                                ?.copyWith(color: scheme.onSurfaceVariant),
                          ),
                        ],
                      ],
                    ),
                  ),
                  if (item.details.isNotEmpty)
                    IconButton(
                      tooltip: expanded ? '收起建议详情' : '展开建议详情',
                      onPressed: onExpanded,
                      icon: Icon(
                        expanded ? Icons.expand_less : Icons.expand_more,
                      ),
                    ),
                ],
              ),
            ),
          ),
          if (expanded && item.details.isNotEmpty) ...[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.fromLTRB(11, 7, 7, 9),
              child: Column(
                children: item.details.asMap().entries.map((entry) {
                  final key = '${item.id}:${entry.key}';
                  final detail = entry.value;
                  return _DetailRow(
                    detail: detail,
                    revealed: !detail.sensitive || revealed.contains(key),
                    onReveal: detail.sensitive ? () => onReveal(key) : null,
                  );
                }).toList(),
              ),
            ),
          ],
        ],
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
      'add' => const Color(0xFF26834A),
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
            width: 68,
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
        borderRadius: BorderRadius.circular(8),
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
