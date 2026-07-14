import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/theme/app_theme.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/tags/tags_screen.dart';
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/preferences_controller.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('标签操作在窄屏使用单一入口和底部操作面板', (tester) async {
    tester.view.physicalSize = const Size(320, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    const tags = [
      TaxonomyRecord(
        name: '工作账号',
        description: '用于日常工作相关条目',
        color: '#006B68',
        count: 4,
      ),
    ];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(preferences),
          taxonomyProvider('tags').overrideWith((ref) async => tags),
        ],
        child: MaterialApp(
          theme: AppTheme.light(textSize: AppTextSize.large),
          home: Scaffold(body: TagsScreen(onOpenTag: (_) {})),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byTooltip('标签操作'), findsOneWidget);
    await tester.tap(find.byTooltip('标签操作'));
    await tester.pumpAndSettle();
    expect(find.text('查看标签条目'), findsOneWidget);
    expect(find.text('编辑标签'), findsOneWidget);
    expect(find.text('删除标签'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
