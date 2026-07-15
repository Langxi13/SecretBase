import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart';

final dataRootProvider = Provider<String>(
  (ref) => throw StateError('移动数据目录尚未初始化'),
);

enum VaultPhase { booting, setup, locked, unlocked, failed }

class VaultUiState {
  const VaultUiState({
    required this.phase,
    this.status,
    this.busy = false,
    this.errorMessage,
  });

  final VaultPhase phase;
  final VaultStatus? status;
  final bool busy;
  final String? errorMessage;

  BigInt get revision => status?.revision ?? BigInt.zero;

  VaultUiState copyWith({
    VaultPhase? phase,
    VaultStatus? status,
    bool? busy,
    String? errorMessage,
    bool clearError = false,
  }) {
    return VaultUiState(
      phase: phase ?? this.phase,
      status: status ?? this.status,
      busy: busy ?? this.busy,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
    );
  }
}

final vaultControllerProvider = NotifierProvider<VaultController, VaultUiState>(
  VaultController.new,
);

final vaultRevisionProvider = Provider<BigInt>(
  (ref) => ref.watch(vaultControllerProvider.select((state) => state.revision)),
);

class VaultController extends Notifier<VaultUiState> {
  @override
  VaultUiState build() {
    Future.microtask(initialize);
    return const VaultUiState(phase: VaultPhase.booting);
  }

  Future<void> initialize() async {
    state = const VaultUiState(phase: VaultPhase.booting);
    try {
      final status = await rust_api.initializeRuntime(
        dataRoot: ref.read(dataRootProvider),
      );
      state = _stateForStatus(status);
    } catch (error) {
      state = VaultUiState(
        phase: VaultPhase.failed,
        errorMessage: error.toString(),
      );
    }
  }

  Future<void> create(String password) async {
    await _runAuth(() => rust_api.createVault(password: password));
  }

  Future<void> unlock(String password) async {
    await _runAuth(() => rust_api.unlockVault(password: password));
  }

  Future<void> unlockWithDeviceCredential(Uint8List credential) async {
    await _runAuth(
      () => rust_api.unlockVaultWithDeviceCredential(credential: credential),
    );
  }

  Future<void> _runAuth(Future<VaultStatus> Function() operation) async {
    state = state.copyWith(busy: true, clearError: true);
    try {
      final status = await operation();
      state = _stateForStatus(status);
    } catch (_) {
      state = state.copyWith(busy: false);
      rethrow;
    }
  }

  Future<void> lock() async {
    if (state.phase != VaultPhase.unlocked) {
      return;
    }
    final status = await rust_api.lockVault();
    state = _stateForStatus(status);
  }

  Future<void> refreshStatus() async {
    final status = await rust_api.vaultStatus();
    state = _stateForStatus(status);
  }

  VaultUiState _stateForStatus(VaultStatus status) {
    final phase = status.unlocked
        ? VaultPhase.unlocked
        : status.initialized
        ? VaultPhase.locked
        : VaultPhase.setup;
    return VaultUiState(phase: phase, status: status);
  }
}
