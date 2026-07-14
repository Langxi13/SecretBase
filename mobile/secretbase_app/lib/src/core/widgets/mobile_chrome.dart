import 'package:flutter/material.dart';

class MobilePageHeader extends StatelessWidget {
  const MobilePageHeader({
    required this.title,
    this.subtitle,
    this.leading,
    this.actions = const [],
    super.key,
  });

  final String title;
  final String? subtitle;
  final Widget? leading;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surface,
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
        decoration: BoxDecoration(
          border: Border(bottom: BorderSide(color: scheme.outlineVariant)),
        ),
        child: Row(
          children: [
            if (leading != null) ...[leading!, const SizedBox(width: 4)],
            Expanded(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  if (subtitle?.isNotEmpty == true) ...[
                    const SizedBox(height: 1),
                    Text(
                      subtitle!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            ...actions,
          ],
        ),
      ),
    );
  }
}

class MobileAction {
  const MobileAction({
    required this.label,
    required this.icon,
    required this.onPressed,
    this.color,
    this.subtitle,
  });

  final String label;
  final IconData icon;
  final VoidCallback onPressed;
  final Color? color;
  final String? subtitle;
}

Future<void> showMobileActionSheet({
  required BuildContext context,
  required String title,
  required List<MobileAction> actions,
}) async {
  final selected = await showModalBottomSheet<int>(
    context: context,
    useSafeArea: true,
    showDragHandle: true,
    constraints: const BoxConstraints(maxWidth: 560),
    builder: (sheetContext) {
      final scheme = Theme.of(sheetContext).colorScheme;
      return Padding(
        padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 2, 8, 10),
              child: Text(
                title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(
                  sheetContext,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
              ),
            ),
            ...actions.asMap().entries.map((entry) {
              final action = entry.value;
              final color = action.color ?? scheme.onSurface;
              return Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: ListTile(
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  leading: Icon(action.icon, color: color),
                  title: Text(
                    action.label,
                    style: TextStyle(color: color, fontWeight: FontWeight.w700),
                  ),
                  subtitle: action.subtitle == null
                      ? null
                      : Text(action.subtitle!),
                  onTap: () => Navigator.of(sheetContext).pop(entry.key),
                ),
              );
            }),
          ],
        ),
      );
    },
  );
  if (selected != null && selected >= 0 && selected < actions.length) {
    actions[selected].onPressed();
  }
}
