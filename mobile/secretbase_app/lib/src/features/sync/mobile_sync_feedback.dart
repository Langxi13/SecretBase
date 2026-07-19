import 'package:flutter/material.dart';

void _showMobileSyncSnackBar(
  BuildContext context,
  String message, {
  bool error = false,
}) {
  if (message.isEmpty) return;
  final messenger = ScaffoldMessenger.maybeOf(context);
  if (messenger == null) return;
  messenger.hideCurrentSnackBar();
  final scheme = Theme.of(context).colorScheme;
  messenger.showSnackBar(
    SnackBar(
      content: Text(message),
      behavior: SnackBarBehavior.floating,
      backgroundColor: error ? scheme.error : null,
      action: error
          ? SnackBarAction(
              label: '知道了',
              textColor: scheme.onError,
              onPressed: () {},
            )
          : null,
    ),
  );
}

void showMobileSyncMessage(BuildContext context, String message) {
  _showMobileSyncSnackBar(context, message);
}

void showMobileSyncError(BuildContext context, String message) {
  _showMobileSyncSnackBar(context, message, error: true);
}

String mobileSyncResultMessage(String message, bool refreshed) {
  return refreshed ? message : '$message，但界面刷新不完整，请重新读取同步状态。';
}

class MobileSyncErrorPanel extends StatelessWidget {
  const MobileSyncErrorPanel({
    required this.message,
    required this.canReload,
    required this.working,
    this.onReload,
    super.key,
  });

  final String message;
  final bool canReload;
  final bool working;
  final VoidCallback? onReload;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: Text(message)),
            if (canReload && onReload != null) ...[
              const SizedBox(width: 8),
              TextButton(
                onPressed: working ? null : onReload,
                child: const Text('重新读取'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
