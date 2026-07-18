import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/features/sync/mobile_sync_setup_form.dart';

void main() {
  testWidgets('同步表单在必填信息完整前禁用网络操作', (tester) async {
    final url = TextEditingController();
    final username = TextEditingController();
    final password = TextEditingController();
    final recovery = TextEditingController();
    final device = TextEditingController();
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
              onTestConnection: () {},
              onSubmit: () {},
            ),
          ),
        ),
      ),
    );

    final testButton = find.widgetWithText(OutlinedButton, '测试连接');
    final joinButton = find.widgetWithText(FilledButton, '加入并同步');
    expect(tester.widget<OutlinedButton>(testButton).onPressed, isNull);
    expect(tester.widget<FilledButton>(joinButton).onPressed, isNull);

    final fields = find.byType(TextField);
    await tester.enterText(fields.at(0), 'https://dav.example.test/secretbase');
    await tester.enterText(fields.at(1), 'tester');
    await tester.enterText(fields.at(2), 'app-password');
    await tester.pump();
    expect(tester.widget<OutlinedButton>(testButton).onPressed, isNotNull);
    expect(tester.widget<FilledButton>(joinButton).onPressed, isNull);

    await tester.enterText(fields.at(4), 'SBSYNC2-RECOVERY');
    await tester.pump();
    expect(tester.widget<FilledButton>(joinButton).onPressed, isNotNull);
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
}
