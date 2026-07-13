import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/theme/app_theme.dart';
import 'package:secretbase/src/features/ai/ai_plan_panel.dart';
import 'package:secretbase/src/rust/mobile/models.dart';

void main() {
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
                onApply: () {},
              ),
            ),
          ),
        ),
      ),
    );

    expect(find.text('must-not-show-before-confirmation'), findsNothing);
    expect(find.text('••••••••'), findsOneWidget);
    await tester.tap(find.byTooltip('显示内容'));
    await tester.pump();
    expect(find.text('must-not-show-before-confirmation'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
