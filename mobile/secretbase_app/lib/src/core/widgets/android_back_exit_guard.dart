import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class AndroidBackExitGuard extends StatefulWidget {
  const AndroidBackExitGuard({
    required this.child,
    this.onBeforeExit,
    this.onExit,
    this.resetToken,
    super.key,
  });

  final Widget child;
  final FutureOr<bool> Function()? onBeforeExit;
  final FutureOr<bool> Function()? onExit;
  final Object? resetToken;

  @override
  State<AndroidBackExitGuard> createState() => _AndroidBackExitGuardState();
}

class _AndroidBackExitGuardState extends State<AndroidBackExitGuard> {
  static const _exitWindow = Duration(seconds: 2);

  DateTime? _firstBackAt;
  bool _handling = false;

  @override
  void didUpdateWidget(covariant AndroidBackExitGuard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.resetToken != widget.resetToken) _firstBackAt = null;
  }

  @override
  Widget build(BuildContext context) {
    final android = defaultTargetPlatform == TargetPlatform.android;
    return PopScope(
      canPop: !android,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop && android) unawaited(_handleBack());
      },
      child: widget.child,
    );
  }

  Future<void> _handleBack() async {
    if (_handling) return;
    _handling = true;
    try {
      if (await (widget.onBeforeExit?.call() ?? false)) {
        _firstBackAt = null;
        return;
      }
      if (!mounted) return;
      final now = DateTime.now();
      if (_firstBackAt != null &&
          now.difference(_firstBackAt!) <= _exitWindow) {
        _firstBackAt = null;
        final shouldExit = await (widget.onExit?.call() ?? true);
        if (!mounted || !shouldExit) return;
        await SystemNavigator.pop();
        return;
      }
      _firstBackAt = now;
      final messenger = ScaffoldMessenger.maybeOf(context);
      messenger
        ?..hideCurrentSnackBar()
        ..showSnackBar(
          const SnackBar(content: Text('再按一次退出'), duration: _exitWindow),
        );
    } finally {
      _handling = false;
    }
  }
}
