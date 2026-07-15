import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';

void main() {
  testWidgets('忙碌中的响应式弹窗禁用关闭按钮和系统返回', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: FilledButton(
              onPressed: () => showResponsiveDialog<void>(
                context: context,
                builder: (_) => const DialogFrame(
                  title: '正在保存',
                  canClose: false,
                  child: Center(child: CircularProgressIndicator()),
                ),
              ),
              child: const Text('打开'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('打开'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    final close = tester.widget<IconButton>(
      find.widgetWithIcon(IconButton, Icons.close),
    );
    expect(close.onPressed, isNull);

    await tester.binding.handlePopRoute();
    await tester.pump();
    expect(find.text('正在保存'), findsOneWidget);

    await tester.tapAt(const Offset(4, 4));
    await tester.pump();
    expect(find.text('正在保存'), findsOneWidget);
  });
}
