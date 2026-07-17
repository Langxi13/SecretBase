import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class SecurityLifecycleGuard extends ConsumerStatefulWidget {
  const SecurityLifecycleGuard({
    required this.child,
    this.backgroundLockDelay = Duration.zero,
    super.key,
  });

  final Widget child;
  final Duration backgroundLockDelay;

  @override
  ConsumerState<SecurityLifecycleGuard> createState() =>
      _SecurityLifecycleGuardState();
}

class _SecurityLifecycleGuardState extends ConsumerState<SecurityLifecycleGuard>
    with WidgetsBindingObserver {
  static const _channel = MethodChannel('secretbase/security');

  DateTime? _backgroundedAt;
  bool _obscured = false;
  bool _locking = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _channel.setMethodCallHandler(_handleNativeEvent);
  }

  @override
  void dispose() {
    _channel.setMethodCallHandler(null);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.inactive:
        _setObscured(true);
      case AppLifecycleState.hidden:
      case AppLifecycleState.paused:
        _backgroundedAt ??= DateTime.now();
        _setObscured(true);
      case AppLifecycleState.detached:
        unawaited(_lockNow());
      case AppLifecycleState.resumed:
        final backgroundedAt = _backgroundedAt;
        _backgroundedAt = null;
        if (backgroundedAt != null &&
            (widget.backgroundLockDelay == Duration.zero ||
                DateTime.now().difference(backgroundedAt) >=
                    widget.backgroundLockDelay)) {
          unawaited(_lockNow());
        } else {
          _setObscured(false);
        }
    }
  }

  Future<void> _handleNativeEvent(MethodCall call) async {
    if (call.method == 'deviceLocked') {
      _setObscured(true);
      await _lockNow();
    }
  }

  Future<void> _lockNow() async {
    if (_locking) return;
    if (ref.read(vaultControllerProvider).phase != VaultPhase.unlocked) {
      _showUnlockRoute();
      return;
    }
    _locking = true;
    try {
      await ref.read(vaultControllerProvider.notifier).lock();
      _showUnlockRoute();
    } finally {
      _locking = false;
      if (mounted) {
        _setObscured(false);
      }
    }
  }

  void _showUnlockRoute() {
    if (!mounted) return;
    GoRouter.maybeOf(context)?.go('/');
    _setObscured(false);
  }

  void _setObscured(bool value) {
    if (mounted && _obscured != value) {
      setState(() => _obscured = value);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        widget.child,
        if (_obscured)
          ColoredBox(
            color: Theme.of(context).colorScheme.surface,
            child: Center(
              child: Semantics(
                label: 'SecretBase 内容已保护',
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.shield_outlined,
                      size: 42,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      '内容已保护',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}
