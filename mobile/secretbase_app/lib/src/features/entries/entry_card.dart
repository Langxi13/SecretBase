import 'package:flutter/material.dart';
import 'package:secretbase/src/rust/mobile/models.dart';

class EntryCard extends StatelessWidget {
  const EntryCard({required this.entry, required this.onTap, super.key});

  final EntryRecord entry;
  final VoidCallback onTap;

  static const _accentColors = [
    Color(0xFF087F8C),
    Color(0xFF315DA8),
    Color(0xFF6B5B95),
    Color(0xFFB54708),
    Color(0xFF26834A),
    Color(0xFF9F2D55),
  ];

  Color get _accent {
    final hash = entry.title.codeUnits.fold<int>(
      0,
      (value, unit) => value + unit,
    );
    return _accentColors[hash % _accentColors.length];
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final compact = MediaQuery.sizeOf(context).width < 600;
    final previewFields = entry.fields.take(compact ? 2 : 3).toList();
    final remaining = entry.fields.length - previewFields.length;
    final visibleGroups = entry.groups.take(1).toList();
    final visibleTags = entry.tags.take(1).toList();
    final hiddenCategories =
        entry.groups.length +
        entry.tags.length -
        visibleGroups.length -
        visibleTags.length;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Stack(
          children: [
            Positioned.fill(
              right: null,
              child: ColoredBox(
                color: _accent,
                child: const SizedBox(width: 4),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(13, 10, 10, 10),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 32,
                        height: 32,
                        decoration: BoxDecoration(
                          color: _accent.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(7),
                        ),
                        child: Icon(
                          Icons.key_rounded,
                          size: 17,
                          color: _accent,
                        ),
                      ),
                      const SizedBox(width: 9),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              entry.title,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.titleMedium
                                  ?.copyWith(fontWeight: FontWeight.w800),
                            ),
                            if (entry.url.isNotEmpty) ...[
                              const SizedBox(height: 2),
                              Text(
                                _displayUrl(entry.url),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: Theme.of(context).textTheme.bodySmall
                                    ?.copyWith(color: scheme.onSurfaceVariant),
                              ),
                            ],
                          ],
                        ),
                      ),
                      if (entry.starred)
                        Padding(
                          padding: const EdgeInsets.only(left: 8, top: 2),
                          child: Icon(
                            Icons.star_rounded,
                            size: 19,
                            color: scheme.secondary,
                          ),
                        ),
                      Icon(
                        Icons.chevron_right,
                        size: 21,
                        color: scheme.onSurfaceVariant,
                      ),
                    ],
                  ),
                  if (previewFields.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Divider(height: 1, color: scheme.outlineVariant),
                    const SizedBox(height: 6),
                    ...previewFields.map(
                      (field) => Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2),
                        child: _FieldPreviewRow(field: field),
                      ),
                    ),
                    if (remaining > 0)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: Text(
                            '还有 $remaining 个字段',
                            style: Theme.of(context).textTheme.labelMedium
                                ?.copyWith(
                                  color: scheme.primary,
                                  fontWeight: FontWeight.w700,
                                ),
                          ),
                        ),
                      ),
                  ],
                  if (entry.tags.isNotEmpty || entry.groups.isNotEmpty) ...[
                    const SizedBox(height: 7),
                    Wrap(
                      spacing: 5,
                      runSpacing: 4,
                      children: [
                        ...visibleGroups.map(
                          (group) => _MetaLabel(
                            icon: Icons.folder_outlined,
                            label: group,
                            color: scheme.tertiary,
                          ),
                        ),
                        ...visibleTags.map(
                          (tag) => _MetaLabel(
                            icon: Icons.sell_outlined,
                            label: tag,
                            color: scheme.primary,
                          ),
                        ),
                        if (hiddenCategories > 0)
                          _MetaLabel(
                            icon: Icons.more_horiz,
                            label: '+$hiddenCategories',
                            color: scheme.onSurfaceVariant,
                          ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _displayUrl(String value) {
    final uri = Uri.tryParse(value);
    return uri?.host.isNotEmpty == true ? uri!.host : value;
  }
}

class _FieldPreviewRow extends StatelessWidget {
  const _FieldPreviewRow({required this.field});

  final FieldRecord field;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return LayoutBuilder(
      builder: (context, constraints) {
        final keyWidth = (constraints.maxWidth * 0.34).clamp(72.0, 146.0);
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: keyWidth,
              child: Text(
                field.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Text(
                field.hidden ? '••••••' : field.value,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontFamily: field.hidden ? null : 'monospace',
                  fontWeight: field.hidden ? FontWeight.w700 : FontWeight.w500,
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _MetaLabel extends StatelessWidget {
  const _MetaLabel({
    required this.icon,
    required this.label,
    required this.color,
  });

  final IconData icon;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 112),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.09),
        borderRadius: BorderRadius.circular(5),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: color),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: color,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
