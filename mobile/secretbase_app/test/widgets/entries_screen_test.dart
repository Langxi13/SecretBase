import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/theme/app_theme.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/entries/entries_screen.dart';
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/preferences_controller.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('窄屏条目筛选保持单行且不溢出', (tester) async {
    tester.view.physicalSize = const Size(320, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    const query = EntryQuery(page: 1, pageSize: 5, search: '', deleted: false);
    final page = EntryPage(
      items: [],
      page: 1,
      pageSize: 5,
      total: 0,
      totalPages: 1,
      revision: BigInt.zero,
    );
    const tags = [
      TaxonomyRecord(name: '工作', description: '', color: '#006B68', count: 1),
    ];
    const groups = [
      TaxonomyRecord(name: '开发资源', description: '', color: '#315DA8', count: 1),
    ];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(preferences),
          entryPageProvider(query).overrideWith((ref) async => page),
          taxonomyProvider('tags').overrideWith((ref) async => tags),
          taxonomyProvider('groups').overrideWith((ref) async => groups),
        ],
        child: MaterialApp(
          theme: AppTheme.light(),
          home: const EntriesScreen(preset: EntryFilterPreset()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('标签'), findsOneWidget);
    expect(find.text('密码组'), findsOneWidget);
    expect(find.byTooltip('仅显示收藏'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('大字体下长分类、收藏和清除筛选仍保持同一行', (tester) async {
    tester.view.physicalSize = const Size(320, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    SharedPreferences.setMockInitialValues({'text_size': 'large'});
    final preferences = await SharedPreferences.getInstance();
    const tagName = '很长的移动端标签名称';
    const groupName = '很长的移动端密码组名称';
    const baseQuery = EntryQuery(
      page: 1,
      pageSize: 5,
      search: '',
      tag: tagName,
      group: groupName,
      deleted: false,
    );
    const starredQuery = EntryQuery(
      page: 1,
      pageSize: 5,
      search: '',
      tag: tagName,
      group: groupName,
      starred: true,
      deleted: false,
    );
    final page = EntryPage(
      items: const [],
      page: 1,
      pageSize: 5,
      total: 0,
      totalPages: 1,
      revision: BigInt.zero,
    );
    const tags = [
      TaxonomyRecord(
        name: tagName,
        description: '',
        color: '#006B68',
        count: 1,
      ),
    ];
    const groups = [
      TaxonomyRecord(
        name: groupName,
        description: '',
        color: '#315DA8',
        count: 1,
      ),
    ];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(preferences),
          entryPageProvider(baseQuery).overrideWith((ref) async => page),
          entryPageProvider(starredQuery).overrideWith((ref) async => page),
          taxonomyProvider('tags').overrideWith((ref) async => tags),
          taxonomyProvider('groups').overrideWith((ref) async => groups),
        ],
        child: MaterialApp(
          theme: AppTheme.light(textSize: AppTextSize.large),
          home: const EntriesScreen(
            preset: EntryFilterPreset(tag: tagName, group: groupName),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('仅显示收藏'));
    await tester.pumpAndSettle();

    final centers = [
      tester.getCenter(find.text(tagName)),
      tester.getCenter(find.text(groupName)),
      tester.getCenter(find.byTooltip('显示全部条目')),
      tester.getCenter(find.byTooltip('清除筛选')),
    ];
    final firstY = centers.first.dy;
    expect(centers.every((center) => (center.dy - firstY).abs() < 2), isTrue);
    expect(tester.takeException(), isNull);
  });
}
