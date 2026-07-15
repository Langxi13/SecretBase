import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:secretbase/src/features/shell/app_shell.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class _LockedVaultController extends VaultController {
  @override
  VaultUiState build() => const VaultUiState(phase: VaultPhase.locked);
}

void main() {
  testWidgets('锁定状态误入主界面时自动返回解锁页', (tester) async {
    final router = GoRouter(
      initialLocation: '/vault',
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const Scaffold(body: Text('解锁页')),
        ),
        GoRoute(path: '/vault', builder: (context, state) => const AppShell()),
      ],
    );
    addTearDown(router.dispose);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          vaultControllerProvider.overrideWith(_LockedVaultController.new),
        ],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('解锁页'), findsOneWidget);
  });
}
