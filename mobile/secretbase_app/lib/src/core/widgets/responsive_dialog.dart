import 'package:flutter/material.dart';

Future<T?> showResponsiveDialog<T>({
  required BuildContext context,
  required WidgetBuilder builder,
  bool dismissible = true,
  double maxWidth = 820,
}) {
  return showDialog<T>(
    context: context,
    barrierDismissible: dismissible,
    builder: (dialogContext) {
      final size = MediaQuery.sizeOf(dialogContext);
      final compact = size.width < 700;
      return Dialog(
        insetPadding: compact ? EdgeInsets.zero : const EdgeInsets.all(24),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(compact ? 0 : 8),
        ),
        clipBehavior: Clip.antiAlias,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: maxWidth,
            maxHeight: compact ? size.height : size.height * 0.92,
          ),
          child: SizedBox(
            width: compact ? size.width : null,
            height: compact ? size.height : null,
            child: builder(dialogContext),
          ),
        ),
      );
    },
  );
}

class DialogFrame extends StatelessWidget {
  const DialogFrame({
    required this.title,
    required this.child,
    this.leading,
    this.actions = const [],
    this.canClose = true,
    this.onClose,
    super.key,
  });

  final String title;
  final Widget child;
  final Widget? leading;
  final List<Widget> actions;
  final bool canClose;
  final VoidCallback? onClose;

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: canClose,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Material(
            color: Theme.of(context).colorScheme.surface,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 8, 10),
              child: Row(
                children: [
                  if (leading != null) ...[leading!, const SizedBox(width: 10)],
                  Expanded(
                    child: Text(
                      title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  ...actions,
                  IconButton(
                    tooltip: '关闭',
                    onPressed: canClose
                        ? onClose ?? () => Navigator.of(context).pop()
                        : null,
                    icon: const Icon(Icons.close),
                  ),
                ],
              ),
            ),
          ),
          const Divider(height: 1),
          Expanded(child: child),
        ],
      ),
    );
  }
}
