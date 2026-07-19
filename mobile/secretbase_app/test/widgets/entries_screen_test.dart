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
      tester.getCenter(find.text(groupName).last),
      tester.getCenter(find.byTooltip('显示全部条目')),
      tester.getCenter(find.byTooltip('清除筛选')),
    ];
    final firstY = centers.first.dy;
    expect(centers.every((center) => (center.dy - firstY).abs() < 2), isTrue);
    expect(tester.takeException(), isNull);
  });

  testWidgets('从密码组进入条目后返回来源页而不是清成全部条目', (tester) async {
    tester.view.physicalSize = const Size(320, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    const groupName = '工作账号';
    const query = EntryQuery(
      page: 1,
      pageSize: 5,
      search: '',
      group: groupName,
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
    const groups = [
      TaxonomyRecord(
        name: groupName,
        description: '',
        color: '#315DA8',
        count: 0,
      ),
    ];
    var returned = false;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(preferences),
          entryPageProvider(query).overrideWith((ref) async => page),
          taxonomyProvider('tags').overrideWith((ref) async => const []),
          taxonomyProvider('groups').overrideWith((ref) async => groups),
        ],
        child: MaterialApp(
          theme: AppTheme.light(),
          home: EntriesScreen(
            preset: const EntryFilterPreset(
              group: groupName,
              origin: EntryFilterOrigin.groups,
            ),
            onExitPreset: () => returned = true,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text(groupName), findsWidgets);
    expect(find.text('密码组 · 共 0 条'), findsOneWidget);
    expect(find.byTooltip('返回密码组'), findsNWidgets(2));
    await tester.tap(find.byTooltip('返回密码组').last);
    await tester.pump();

    expect(returned, isTrue);
    expect(tester.takeException(), isNull);
  });

  testWidgets('从密码组进入后切换到另一个密码组会更新标题和返回行为', (tester) async {
    tester.view.physicalSize = const Size(360, 760);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    const firstGroup = '工作账号';
    const secondGroup = '个人账号';
    const firstQuery = EntryQuery(
      page: 1,
      pageSize: 5,
      search: '',
      group: firstGroup,
      deleted: false,
    );
    const secondQuery = EntryQuery(
      page: 1,
      pageSize: 5,
      search: '',
      group: secondGroup,
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
    const groups = [
      TaxonomyRecord(
        name: firstGroup,
        description: '',
        color: '#315DA8',
        count: 0,
      ),
      TaxonomyRecord(
        name: secondGroup,
        description: '',
        color: '#7C3AED',
        count: 0,
      ),
    ];

    var returned = false;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(preferences),
          entryPageProvider(firstQuery).overrideWith((ref) async => page),
          entryPageProvider(secondQuery).overrideWith((ref) async => page),
          taxonomyProvider('tags').overrideWith((ref) async => const []),
          taxonomyProvider('groups').overrideWith((ref) async => groups),
        ],
        child: MaterialApp(
          theme: AppTheme.light(),
          home: EntriesScreen(
            preset: const EntryFilterPreset(
              group: firstGroup,
              origin: EntryFilterOrigin.groups,
            ),
            onExitPreset: () => returned = true,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip(firstGroup));
    await tester.pumpAndSettle();
    await tester.tap(find.text(secondGroup).last);
    await tester.pumpAndSettle();

    expect(find.text(secondGroup), findsWidgets);
    expect(find.text('密码组 · 共 0 条'), findsOneWidget);
    expect(find.byTooltip('返回密码组'), findsNothing);
    expect(find.byTooltip('清除筛选'), findsOneWidget);
    await tester.tap(find.byTooltip('清除筛选'));
    await tester.pump();
    expect(returned, isFalse);
    expect(tester.takeException(), isNull);
  });

  testWidgets('从标签进入条目后返回标签页', (tester) async {
    tester.view.physicalSize = const Size(320, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    const tagName = '重要';
    const query = EntryQuery(
      page: 1,
      pageSize: 5,
      search: '',
      tag: tagName,
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
        count: 0,
      ),
    ];
    var returned = false;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(preferences),
          entryPageProvider(query).overrideWith((ref) async => page),
          taxonomyProvider('tags').overrideWith((ref) async => tags),
          taxonomyProvider('groups').overrideWith((ref) async => const []),
        ],
        child: MaterialApp(
          theme: AppTheme.light(),
          home: EntriesScreen(
            preset: const EntryFilterPreset(
              tag: tagName,
              origin: EntryFilterOrigin.tags,
            ),
            onExitPreset: () => returned = true,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('标签 · 共 0 条'), findsOneWidget);
    await tester.tap(find.byTooltip('返回标签').last);
    await tester.pump();

    expect(returned, isTrue);
    expect(tester.takeException(), isNull);
  });
}
