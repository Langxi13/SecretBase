import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/biometric_unlock.dart';
import 'package:secretbase/src/features/auth/vault_gate.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class _LockedVaultController extends VaultController {
  @override
  VaultUiState build() => const VaultUiState(phase: VaultPhase.locked);
}

class _SetupVaultController extends VaultController {
  @override
  VaultUiState build() => const VaultUiState(phase: VaultPhase.setup);
}

class _UnavailableBiometricPlatform implements BiometricPlatform {
  @override
  Future<bool> deleteCredential() async => false;

  @override
  Future<Uint8List> readCredential() {
    throw StateError('biometric unavailable');
  }

  @override
  Future<BiometricStatus> status() async {
    return const BiometricStatus.unsupported();
  }

  @override
  Future<void> storeCredential(Uint8List credential) async {}
}

void main() {
  testWidgets('锁定页等待自动指纹时不会抢占软键盘焦点', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          vaultControllerProvider.overrideWith(_LockedVaultController.new),
          biometricPlatformProvider.overrideWithValue(
            _UnavailableBiometricPlatform(),
          ),
        ],
        child: const MaterialApp(home: VaultGate()),
      ),
    );
    await tester.pumpAndSettle();

    final password = tester.widget<TextField>(find.byType(TextField).first);
    expect(password.autofocus, isFalse);
    expect(tester.testTextInput.isVisible, isFalse);
  });

  testWidgets('首次创建密码库仍可自动聚焦主密码', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          vaultControllerProvider.overrideWith(_SetupVaultController.new),
          biometricPlatformProvider.overrideWithValue(
            _UnavailableBiometricPlatform(),
          ),
        ],
        child: const MaterialApp(home: VaultGate()),
      ),
    );
    await tester.pump();

    final password = tester.widget<TextField>(find.byType(TextField).first);
    expect(password.autofocus, isTrue);
  });
}
