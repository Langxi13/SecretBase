import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/theme/app_theme.dart';
import 'package:secretbase/src/features/entries/entry_card.dart';
import 'package:secretbase/src/rust/mobile/models.dart';

void main() {
  testWidgets('条目卡片限制字段预览数量并再次保护隐藏字段', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final entry = EntryRecord(
      id: 'entry-1',
      title: '用于窄屏测试的超长条目名称',
      url: 'https://example.test/path',
      starred: true,
      tags: const ['测试', '移动端'],
      groups: const ['开发资源'],
      fields: const [
        FieldRecord(
          name: '非常长的字段名称需要合理换行',
          value: 'visible-value',
          copyable: true,
          hidden: false,
        ),
        FieldRecord(
          name: '密码',
          value: 'must-not-render',
          copyable: true,
          hidden: true,
        ),
        FieldRecord(name: '环境', value: '测试', copyable: false, hidden: false),
        FieldRecord(name: '端口', value: '443', copyable: true, hidden: false),
        FieldRecord(
          name: '区域',
          value: 'cn-test',
          copyable: false,
          hidden: false,
        ),
      ],
      remarks: '',
      createdAt: '2026-07-12T00:00:00Z',
      updatedAt: '2026-07-12T00:00:00Z',
      deleted: false,
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light(),
        home: Scaffold(
          body: Padding(
            padding: const EdgeInsets.all(8),
            child: EntryCard(entry: entry, onTap: () {}),
          ),
        ),
      ),
    );

    expect(find.text('还有 2 个字段'), findsOneWidget);
    expect(find.text('must-not-render'), findsNothing);
    expect(find.text('••••••'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
