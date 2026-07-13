import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:secretbase/src/features/auth/vault_gate.dart';
import 'package:secretbase/src/features/shell/app_shell.dart';
import 'package:secretbase/src/features/trash/trash_screen.dart';

final appRouterProvider = Provider<GoRouter>((ref) {
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(path: '/', builder: (context, state) => const VaultGate()),
      GoRoute(path: '/vault', builder: (context, state) => const AppShell()),
      GoRoute(path: '/trash', builder: (context, state) => const TrashScreen()),
    ],
  );
  ref.onDispose(router.dispose);
  return router;
});
