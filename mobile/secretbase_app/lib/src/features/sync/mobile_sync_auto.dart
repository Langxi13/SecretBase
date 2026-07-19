import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/features/sync/mobile_sync_gate.dart';
import 'package:secretbase/src/features/sync/mobile_sync_service.dart';
import 'package:secretbase/src/features/sync/mobile_webdav.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class MobileSyncAutoState {
  const MobileSyncAutoState({
    this.running = false,
    this.message = '',
    this.lastError = '',
    this.conflict = false,
  });

  final bool running;
  final String message;
  final String lastError;
  final bool conflict;
}

final mobileSyncAutoStateProvider =
    NotifierProvider<MobileSyncAutoController, MobileSyncAutoState>(
      MobileSyncAutoController.new,
    );

class MobileSyncAutoController extends Notifier<MobileSyncAutoState> {
  @override
  MobileSyncAutoState build() => const MobileSyncAutoState();

  void running() {
    state = MobileSyncAutoState(
      running: true,
      message: state.message,
      lastError: '',
    );
  }

  void success(String message) {
    state = MobileSyncAutoState(message: message);
  }

  void failure(String message, {bool conflict = false}) {
    state = MobileSyncAutoState(
      message: conflict ? '需要处理同步冲突' : '自动同步未完成',
      lastError: message,
      conflict: conflict,
    );
  }

  void reset() {
    state = const MobileSyncAutoState();
  }
}

class MobileSyncAutoCoordinator extends ConsumerStatefulWidget {
  const MobileSyncAutoCoordinator({required this.child, super.key});

  final Widget child;

  @override
  ConsumerState<MobileSyncAutoCoordinator> createState() =>
      _MobileSyncAutoCoordinatorState();
}

class _MobileSyncAutoCoordinatorState
    extends ConsumerState<MobileSyncAutoCoordinator> {
  final _coordinator = MobileSyncCoordinator();
  Timer? _timer;
  BigInt? _observedRevision;
  bool _disposed = false;

  @override
  void initState() {
    super.initState();
    _observedRevision = ref.read(vaultRevisionProvider);
    _schedule(const Duration(seconds: 1));
  }

  @override
  void dispose() {
    _disposed = true;
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<BigInt>(vaultRevisionProvider, (previous, next) {
      if (next != _observedRevision) {
        _observedRevision = next;
        _schedule(const Duration(seconds: 5));
      }
    });
    ref.listen<VaultPhase>(
      vaultControllerProvider.select((state) => state.phase),
      (previous, next) {
        if (next != VaultPhase.unlocked) {
          _timer?.cancel();
          MobileWebDavClient.cancelAll();
          ref.read(mobileSyncAutoStateProvider.notifier).reset();
        } else if (previous != VaultPhase.unlocked) {
          _schedule(const Duration(seconds: 1));
        }
      },
    );
    return widget.child;
  }

  void _schedule(Duration delay) {
    if (_disposed) return;
    _timer?.cancel();
    _timer = Timer(delay, () => unawaited(_run()));
  }

  Future<void> _run() async {
    if (_disposed ||
        ref.read(vaultControllerProvider).phase != VaultPhase.unlocked) {
      return;
    }
    if (MobileSyncGate.busy) {
      _schedule(const Duration(seconds: 2));
      return;
    }
    final state = ref.read(mobileSyncAutoStateProvider.notifier);
    try {
      final status = await _coordinator.status();
      if (!status.configured || !status.autoSync) {
        state.reset();
        return;
      }
      state.running();
      final result = await _coordinator.run();
      if (_disposed || !mounted) return;
      if (result.hasConflicts) {
        state.failure('请打开“设置 > 加密快照同步”处理冲突。', conflict: true);
        return;
      }
      var refreshed = true;
      if (result.action == 'downloaded' || result.action == 'merged') {
        try {
          await ref.read(vaultControllerProvider.notifier).refreshStatus();
        } catch (_) {
          refreshed = false;
        }
      }
      if (refreshed) {
        state.success(result.message);
      } else {
        state.success('${result.message}，但本地界面刷新不完整，将稍后重试。');
        _schedule(const Duration(seconds: 10));
      }
    } on MobileSyncBusyException {
      if (!_disposed) _schedule(const Duration(seconds: 2));
    } catch (error) {
      if (!_disposed) state.failure(mobileErrorMessage(error));
    }
  }
}
