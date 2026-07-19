import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/theme/app_theme.dart';
import 'package:secretbase/src/features/ai/ai_plan_panel.dart';
import 'package:secretbase/src/rust/mobile/models.dart';

void main() {
  test('标签删除和合并会被识别为高影响操作', () {
    expect(
      aiPreviewItemIsHighImpact(
        const AiPreviewItem(
          id: 'delete-tag',
          title: '删除标签「临时」',
          subtitle: '标签删除',
          details: [],
        ),
      ),
      isTrue,
    );
    expect(
      aiPreviewItemIsHighImpact(
        const AiPreviewItem(
          id: 'create-group',
          title: '新建密码组「工作」',
          subtitle: '密码组',
          details: [],
        ),
      ),
      isFalse,
    );
  });

  testWidgets('AI 新建计划默认遮蔽敏感值并支持本地查看', (tester) async {
    tester.view.physicalSize = const Size(320, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final preview = AiPreview(
      token: 'preview-token',
      kind: 'assistant',
      title: 'AI 管家操作计划',
      sourceRevision: BigInt.one,
      items: const [
        AiPreviewItem(
          id: 'item-1',
          title: '新建条目「测试账号」',
          subtitle: 'AI 新建',
          details: [
            AiPreviewDetail(
              label: '密码',
              value: 'must-not-show-before-confirmation',
              sensitive: true,
              changeType: 'add',
            ),
          ],
        ),
      ],
      warnings: const [],
      privacyNote: '应用前请核对字段值。',
    );
    final selected = <String>{'item-1'};
    final revealed = <String>{};
    final expanded = <String>{};
    var discarded = false;

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light(textSize: AppTextSize.standard),
        home: Scaffold(
          body: SingleChildScrollView(
            child: StatefulBuilder(
              builder: (context, setState) => AiPlanPanel(
                preview: preview,
                selected: selected,
                revealed: revealed,
                expanded: expanded,
                working: false,
                onSelectionChanged: (id, value) => setState(() {
                  if (value) {
                    selected.add(id);
                  } else {
                    selected.remove(id);
                  }
                }),
                onSelectAll: (_) {},
                onReveal: (key) => setState(() => revealed.add(key)),
                onExpanded: (id) => setState(() => expanded.add(id)),
                onApply: () {},
                onDiscard: () => discarded = true,
              ),
            ),
          ),
        ),
      ),
    );

    expect(find.text('must-not-show-before-confirmation'), findsNothing);
    expect(find.text('••••••••'), findsNothing);
    await tester.tap(find.byTooltip('展开建议详情'));
    await tester.pump();
    expect(find.text('••••••••'), findsOneWidget);
    await tester.tap(find.byTooltip('显示内容'));
    await tester.pump();
    expect(find.text('must-not-show-before-confirmation'), findsOneWidget);
    await tester.tap(find.text('放弃建议'));
    expect(discarded, isTrue);
    expect(tester.takeException(), isNull);
  });
}
