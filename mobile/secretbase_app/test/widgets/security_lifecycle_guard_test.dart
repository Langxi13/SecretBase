import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/security_lifecycle_guard.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class _LockedVaultController extends VaultController {
  @override
  VaultUiState build() => const VaultUiState(phase: VaultPhase.locked);
}

void main() {
  testWidgets('Vault 已锁定时恢复应用会释放内容保护遮罩', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          vaultControllerProvider.overrideWith(_LockedVaultController.new),
        ],
        child: const MaterialApp(
          home: SecurityLifecycleGuard(
            backgroundLockDelay: Duration.zero,
            child: Scaffold(body: Text('主密码解锁页')),
          ),
        ),
      ),
    );

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump();
    expect(find.text('内容已保护'), findsOneWidget);

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    expect(find.text('内容已保护'), findsNothing);
    expect(find.text('主密码解锁页'), findsOneWidget);
  });
}
