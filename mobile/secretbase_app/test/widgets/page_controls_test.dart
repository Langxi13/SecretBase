import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/theme/app_theme.dart';
import 'package:secretbase/src/core/widgets/paged_scroll.dart';
import 'package:secretbase/src/core/widgets/page_controls.dart';

void main() {
  testWidgets('窄屏分页控件会换行且保留每页 50 条选项', (tester) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    var selectedSize = 50;
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light(),
        home: Scaffold(
          body: PageControls(
            page: 2,
            totalPages: 8,
            pageSize: selectedSize,
            onPageChanged: (_) {},
            onPageSizeChanged: (value) => selectedSize = value,
          ),
        ),
      ),
    );

    expect(find.text('2 / 8'), findsOneWidget);
    expect(find.text('每页 50 条'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('分页切换会在异步加载前立即回到列表顶部', (tester) async {
    final controller = ScrollController();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ListView.builder(
            controller: controller,
            itemExtent: 48,
            itemCount: 40,
            itemBuilder: (context, index) => Text('条目 $index'),
          ),
        ),
      ),
    );

    controller.jumpTo(360);
    expect(controller.offset, 360);
    resetPagedScroll(controller);
    expect(controller.offset, 0);

    await tester.pumpWidget(const SizedBox.shrink());
    controller.dispose();
  });
}
