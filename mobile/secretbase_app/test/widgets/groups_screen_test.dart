import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/theme/app_theme.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/groups/groups_screen.dart';
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/preferences_controller.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('密码组默认每页五条并可切换到下一页', (tester) async {
    tester.view.physicalSize = const Size(320, 760);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    final groups = List.generate(
      7,
      (index) => TaxonomyRecord(
        name: '密码组 ${index + 1}',
        description: '用于验证紧凑卡片和分页行为',
        color: '#315DA8',
        count: index + 1,
      ),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(preferences),
          taxonomyProvider('groups').overrideWith((ref) async => groups),
        ],
        child: MaterialApp(
          theme: AppTheme.light(textSize: AppTextSize.large),
          home: Scaffold(body: GroupsScreen(onOpenGroup: (_) {})),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('密码组 1'), findsOneWidget);
    expect(find.text('密码组 6'), findsNothing);
    await tester.tap(find.byTooltip('密码组操作').first);
    await tester.pumpAndSettle();
    expect(find.text('查看组内条目'), findsOneWidget);
    expect(find.text('编辑密码组'), findsOneWidget);
    expect(find.text('删除密码组'), findsOneWidget);
    Navigator.of(tester.element(find.text('查看组内条目'))).pop();
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.byTooltip('下一页'), 300);
    expect(find.text('1 / 2'), findsOneWidget);

    await tester.tap(find.byTooltip('下一页'));
    await tester.pumpAndSettle();
    expect(find.text('密码组 6'), findsOneWidget);
    expect(find.text('2 / 2'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
