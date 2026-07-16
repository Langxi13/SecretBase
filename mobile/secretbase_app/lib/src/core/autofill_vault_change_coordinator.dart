import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class AutofillVaultChangeCoordinator extends ConsumerStatefulWidget {
  const AutofillVaultChangeCoordinator({required this.child, super.key});

  final Widget child;

  @override
  ConsumerState<AutofillVaultChangeCoordinator> createState() =>
      _AutofillVaultChangeCoordinatorState();
}

class _AutofillVaultChangeCoordinatorState
    extends ConsumerState<AutofillVaultChangeCoordinator>
    with WidgetsBindingObserver {
  static const _channel = MethodChannel('secretbase/platform');
  bool _checking = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    scheduleMicrotask(_refreshIfChanged);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(_refreshIfChanged());
    }
  }

  Future<void> _refreshIfChanged() async {
    if (_checking) return;
    _checking = true;
    try {
      final changed = await _channel.invokeMethod<bool>(
        'consumeAutofillVaultChanged',
      );
      if (changed != true) return;
      final phase = ref.read(vaultControllerProvider).phase;
      if (phase != VaultPhase.booting && phase != VaultPhase.failed) {
        await ref.read(vaultControllerProvider.notifier).refreshStatus();
      }
      ref.invalidate(entryPageProvider);
      ref.invalidate(taxonomyProvider);
    } on MissingPluginException {
      // Non-Android tests and future platforms do not expose this bridge.
    } on PlatformException {
      // The native activity may finish while Flutter is still resuming.
    } finally {
      _checking = false;
    }
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
