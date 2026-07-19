import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/features/sync/mobile_sync_setup_form.dart';

void main() {
  testWidgets('同步表单保持操作可点击并明确提示加入所需恢复码', (tester) async {
    final url = TextEditingController();
    final username = TextEditingController();
    final password = TextEditingController();
    final recovery = TextEditingController();
    final device = TextEditingController();
    var testCalls = 0;
    var submitCalls = 0;
    addTearDown(() {
      url.dispose();
      username.dispose();
      password.dispose();
      recovery.dispose();
      device.dispose();
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: MobileSyncSetupForm(
              url: url,
              username: username,
              password: password,
              recovery: recovery,
              device: device,
              joining: true,
              working: false,
              mergeExisting: false,
              autoSync: true,
              onJoiningChanged: (_) {},
              onMergeChanged: (_) {},
              onAutoSyncChanged: (_) {},
              onScanPairing: () {},
              onPastePairing: () {},
              onTestConnection: () => testCalls += 1,
              onSubmit: () => submitCalls += 1,
            ),
          ),
        ),
      ),
    );

    final testButton = find.widgetWithText(OutlinedButton, '测试连接');
    final joinButton = find.widgetWithText(FilledButton, '加入并同步');
    expect(tester.widget<OutlinedButton>(testButton).onPressed, isNotNull);
    expect(tester.widget<FilledButton>(joinButton).onPressed, isNotNull);
    expect(find.textContaining('测试连接只验证 WebDAV'), findsOneWidget);

    tester.widget<OutlinedButton>(testButton).onPressed!();
    tester.widget<FilledButton>(joinButton).onPressed!();
    expect(testCalls, 1);
    expect(submitCalls, 1);

    final fields = find.byType(TextField);
    await tester.enterText(fields.at(0), 'https://dav.example.test/secretbase');
    await tester.enterText(fields.at(1), 'tester');
    await tester.enterText(fields.at(2), 'app-password');
    await tester.pump();
    expect(tester.widget<OutlinedButton>(testButton).onPressed, isNotNull);
    expect(tester.widget<FilledButton>(joinButton).onPressed, isNotNull);

    await tester.enterText(fields.at(4), 'SBSYNC2-RECOVERY');
    await tester.pump();
    expect(tester.widget<FilledButton>(joinButton).onPressed, isNotNull);
    expect(find.textContaining('测试连接只验证 WebDAV'), findsNothing);
  });

  testWidgets('同步表单支持切换应用密码可见性', (tester) async {
    tester.view.physicalSize = const Size(320, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final controllers = List.generate(5, (_) => TextEditingController());
    addTearDown(() {
      for (final controller in controllers) {
        controller.dispose();
      }
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MobileSyncSetupForm(
            url: controllers[0],
            username: controllers[1],
            password: controllers[2],
            recovery: controllers[3],
            device: controllers[4],
            joining: false,
            working: false,
            mergeExisting: false,
            autoSync: true,
            onJoiningChanged: (_) {},
            onMergeChanged: (_) {},
            onAutoSyncChanged: (_) {},
            onScanPairing: () {},
            onPastePairing: () {},
            onTestConnection: () {},
            onSubmit: () {},
          ),
        ),
      ),
    );

    expect(
      tester.widget<TextField>(find.byType(TextField).at(2)).obscureText,
      isTrue,
    );
    await tester.tap(find.byTooltip('显示密码'));
    await tester.pump();
    expect(
      tester.widget<TextField>(find.byType(TextField).at(2)).obscureText,
      isFalse,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('同步表单在弹窗内保留错误并提供重新读取入口', (tester) async {
    final controllers = List.generate(5, (_) => TextEditingController());
    var reloadCalls = 0;
    addTearDown(() {
      for (final controller in controllers) {
        controller.dispose();
      }
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MobileSyncSetupForm(
            url: controllers[0],
            username: controllers[1],
            password: controllers[2],
            recovery: controllers[3],
            device: controllers[4],
            joining: false,
            working: false,
            mergeExisting: false,
            autoSync: true,
            onJoiningChanged: (_) {},
            onMergeChanged: (_) {},
            onAutoSyncChanged: (_) {},
            onScanPairing: () {},
            onPastePairing: () {},
            onTestConnection: () {},
            onSubmit: () {},
            errorMessage: 'WebDAV 连接失败，请检查网络',
            onReload: () => reloadCalls += 1,
          ),
        ),
      ),
    );

    expect(find.text('WebDAV 连接失败，请检查网络'), findsOneWidget);
    final reload = find.widgetWithText(TextButton, '重新读取');
    expect(reload, findsOneWidget);
    tester.widget<TextButton>(reload).onPressed!();
    expect(reloadCalls, 1);
  });
}
