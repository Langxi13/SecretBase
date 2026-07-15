import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/theme/app_theme.dart';
import 'package:secretbase/src/features/ai/ai_manager_composer.dart';
import 'package:secretbase/src/features/ai/ai_manager_widgets.dart';
import 'package:secretbase/src/rust/mobile/models.dart';

void main() {
  testWidgets('窄屏大字体 AI 输入区通过加号展开快捷操作', (tester) async {
    tester.view.physicalSize = const Size(320, 760);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final controller = TextEditingController();
    addTearDown(controller.dispose);
    String? selectedPrompt;

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light(textSize: AppTextSize.large),
        home: Scaffold(
          body: Align(
            alignment: Alignment.bottomCenter,
            child: AiManagerComposer(
              controller: controller,
              mode: 'assistant',
              selectedEntryCount: 0,
              working: false,
              onModeChanged: (_) {},
              onScope: () {},
              onPrompt: (value) => selectedPrompt = value,
              onTools: () {},
              onSend: () {},
            ),
          ),
        ),
      ),
    );

    expect(find.byTooltip('更多 AI 操作'), findsOneWidget);
    expect(find.textContaining('管家 · 全部条目'), findsOneWidget);
    expect(find.text('分类'), findsNothing);
    await tester.tap(find.byTooltip('更多 AI 操作'));
    await tester.pumpAndSettle();
    expect(find.text('分类'), findsOneWidget);
    expect(find.text('标签'), findsOneWidget);
    expect(find.text('密码组'), findsOneWidget);
    expect(find.text('字段'), findsOneWidget);
    expect(find.text('全部条目'), findsOneWidget);
    await tester.tap(find.text('密码组'));
    await tester.pump();
    expect(selectedPrompt, contains('密码组的分类是否合理'));
    expect(tester.takeException(), isNull);
  });

  testWidgets('窄屏 AI 标题栏将次要入口收纳到更多菜单', (tester) async {
    tester.view.physicalSize = const Size(320, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light(),
        home: Scaffold(
          body: AiManagerHeader(
            status: const AiStatus(
              configured: true,
              baseUrl: 'https://api.example.test',
              model: 'example-model',
              apiKeyMask: '****',
            ),
            onNewConversation: () {},
            onHistory: () {},
            onTools: () {},
            onSettings: () {},
          ),
        ),
      ),
    );

    expect(find.text('example-model'), findsOneWidget);
    expect(find.byTooltip('更多 AI 功能'), findsOneWidget);
    await tester.tap(find.byTooltip('更多 AI 功能'));
    await tester.pumpAndSettle();
    expect(find.text('专业工具'), findsOneWidget);
    expect(find.text('服务设置'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('AI 应用结果提供紧凑撤回入口', (tester) async {
    var undone = false;
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light(),
        home: Scaffold(
          body: AiUndoBanner(
            state: AiUndoState(
              revision: BigInt.from(2),
              message: '已应用',
              undoToken: 'undo-token',
              appliedCount: 3,
            ),
            onUndo: () => undone = true,
          ),
        ),
      ),
    );

    expect(find.text('已应用 3 项 AI 操作'), findsOneWidget);
    await tester.tap(find.text('撤回'));
    expect(undone, isTrue);
    expect(tester.takeException(), isNull);
  });
}
