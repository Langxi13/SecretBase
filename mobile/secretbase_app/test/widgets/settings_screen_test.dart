import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/theme/app_theme.dart';
import 'package:secretbase/src/features/settings/settings_screen.dart';
import 'package:secretbase/src/state/preferences_controller.dart';
import 'package:secretbase/src/state/vault_controller.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _TestVaultController extends VaultController {
  @override
  VaultUiState build() {
    return const VaultUiState(phase: VaultPhase.unlocked);
  }
}

void main() {
  testWidgets('窄屏大字体设置页的外观选项不溢出', (tester) async {
    tester.view.physicalSize = const Size(320, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    SharedPreferences.setMockInitialValues({'text_size': 'large'});
    final preferences = await SharedPreferences.getInstance();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(preferences),
          vaultControllerProvider.overrideWith(_TestVaultController.new),
        ],
        child: MaterialApp(
          theme: AppTheme.light(textSize: AppTextSize.large),
          home: const Scaffold(body: SettingsScreen()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('跟随系统'), findsOneWidget);
    expect(find.text('标准'), findsOneWidget);
    expect(find.text('大字体'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
