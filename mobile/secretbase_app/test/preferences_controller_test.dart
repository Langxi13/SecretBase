import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/state/preferences_controller.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('分页与主题偏好会从本机存储恢复并继续保存', () async {
    SharedPreferences.setMockInitialValues({
      'theme_mode': 'dark',
      'entry_page_size': 50,
      'taxonomy_page_size': 10,
      'clipboard_clear_seconds': 60,
    });
    final preferences = await SharedPreferences.getInstance();
    final container = ProviderContainer(
      overrides: [sharedPreferencesProvider.overrideWithValue(preferences)],
    );
    addTearDown(container.dispose);

    final initial = container.read(preferencesProvider);
    expect(initial.themeMode, ThemeMode.dark);
    expect(initial.entryPageSize, 50);
    expect(initial.taxonomyPageSize, 10);
    expect(initial.clipboardClearSeconds, 60);

    await container.read(preferencesProvider.notifier).setTaxonomyPageSize(20);
    expect(container.read(preferencesProvider).taxonomyPageSize, 20);
    expect(preferences.getInt('taxonomy_page_size'), 20);
  });

  test('非法分页数量不会进入应用状态', () async {
    SharedPreferences.setMockInitialValues({
      'entry_page_size': 999,
      'taxonomy_page_size': 0,
    });
    final preferences = await SharedPreferences.getInstance();
    final container = ProviderContainer(
      overrides: [sharedPreferencesProvider.overrideWithValue(preferences)],
    );
    addTearDown(container.dispose);

    final state = container.read(preferencesProvider);
    expect(state.entryPageSize, 20);
    expect(state.taxonomyPageSize, 20);
  });
}
