import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/security_lifecycle_guard.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class _LockedVaultController extends VaultController {
  @override
  VaultUiState build() => const VaultUiState(phase: VaultPhase.locked);
}

class _UnlockedVaultController extends VaultController {
  int lockCount = 0;

  @override
  VaultUiState build() => const VaultUiState(phase: VaultPhase.unlocked);

  @override
  Future<void> lock() async {
    lockCount += 1;
    state = const VaultUiState(phase: VaultPhase.locked);
  }
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

  testWidgets('进入后台后恢复会立即锁定密码库', (tester) async {
    final controller = _UnlockedVaultController();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [vaultControllerProvider.overrideWith(() => controller)],
        child: const MaterialApp(
          home: SecurityLifecycleGuard(child: Scaffold(body: Text('密码库内容'))),
        ),
      ),
    );

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump();
    expect(find.text('内容已保护'), findsOneWidget);

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();
    expect(controller.lockCount, 1);
    expect(controller.state.phase, VaultPhase.locked);
    expect(find.text('内容已保护'), findsNothing);
  });

  testWidgets('系统指纹弹窗造成的短暂 inactive 不会锁定密码库', (tester) async {
    final controller = _UnlockedVaultController();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [vaultControllerProvider.overrideWith(() => controller)],
        child: const MaterialApp(
          home: SecurityLifecycleGuard(child: Scaffold(body: Text('密码库内容'))),
        ),
      ),
    );

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    await tester.pump();
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();

    expect(controller.lockCount, 0);
    expect(find.text('密码库内容'), findsOneWidget);
  });

  testWidgets('进入后台时会清除输入焦点并隐藏软键盘', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          vaultControllerProvider.overrideWith(_LockedVaultController.new),
        ],
        child: const MaterialApp(
          home: SecurityLifecycleGuard(child: Scaffold(body: TextField())),
        ),
      ),
    );
    await tester.showKeyboard(find.byType(TextField));
    expect(tester.testTextInput.isVisible, isTrue);

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump();

    expect(tester.testTextInput.isVisible, isFalse);
    final editable = tester.widget<EditableText>(find.byType(EditableText));
    expect(editable.focusNode.hasFocus, isFalse);
  });
}
