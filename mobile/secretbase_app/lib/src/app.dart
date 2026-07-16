import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/security_lifecycle_guard.dart';
import 'package:secretbase/src/core/theme/app_theme.dart';
import 'package:secretbase/src/features/update/mobile_update_widgets.dart';
import 'package:secretbase/src/routing/app_router.dart';
import 'package:secretbase/src/state/preferences_controller.dart';

class SecretBaseApp extends ConsumerWidget {
  const SecretBaseApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final preferences = ref.watch(preferencesProvider);
    final router = ref.watch(appRouterProvider);

    return MaterialApp.router(
      title: 'SecretBase',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(textSize: preferences.textSize),
      darkTheme: AppTheme.dark(textSize: preferences.textSize),
      themeMode: preferences.themeMode,
      locale: const Locale('zh', 'CN'),
      supportedLocales: const [Locale('zh', 'CN')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      routerConfig: router,
      builder: (context, child) => MobileUpdateCoordinator(
        child: SecurityLifecycleGuard(child: child ?? const SizedBox.shrink()),
      ),
    );
  }
}
