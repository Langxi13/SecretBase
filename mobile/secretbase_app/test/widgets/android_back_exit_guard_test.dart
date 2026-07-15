import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/widgets/android_back_exit_guard.dart';

void main() {
  testWidgets('Android 根页面连续返回两次才退出', (tester) async {
    var exitCalls = 0;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (call) async {
          if (call.method == 'SystemNavigator.pop') exitCalls += 1;
          return null;
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null),
    );

    await tester.pumpWidget(
      const MaterialApp(
        home: AndroidBackExitGuard(child: Scaffold(body: Text('条目首页'))),
      ),
    );

    await tester.binding.handlePopRoute();
    await tester.pump();
    expect(find.text('再按一次退出'), findsOneWidget);
    expect(exitCalls, 0);

    await tester.binding.handlePopRoute();
    await tester.pump();
    expect(exitCalls, 1);
  });

  testWidgets('确认退出前先执行安全锁定回调', (tester) async {
    var exitCalls = 0;
    var lockCalls = 0;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (call) async {
          if (call.method == 'SystemNavigator.pop') exitCalls += 1;
          return null;
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AndroidBackExitGuard(
          onExit: () async {
            lockCalls += 1;
            return true;
          },
          child: const Scaffold(body: Text('条目首页')),
        ),
      ),
    );

    await tester.binding.handlePopRoute();
    await tester.pump();
    expect(lockCalls, 0);

    await tester.binding.handlePopRoute();
    await tester.pump();
    expect(lockCalls, 1);
    expect(exitCalls, 1);
  });

  testWidgets('安全锁定失败时不会退出', (tester) async {
    var exitCalls = 0;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (call) async {
          if (call.method == 'SystemNavigator.pop') exitCalls += 1;
          return null;
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null),
    );

    await tester.pumpWidget(
      const MaterialApp(
        home: AndroidBackExitGuard(
          onExit: _denyExit,
          child: Scaffold(body: Text('条目首页')),
        ),
      ),
    );

    await tester.binding.handlePopRoute();
    await tester.pump();
    await tester.binding.handlePopRoute();
    await tester.pump();
    expect(exitCalls, 0);
  });

  testWidgets('页面返回逻辑优先于退出提示', (tester) async {
    var consumed = 0;

    await tester.pumpWidget(
      MaterialApp(
        home: AndroidBackExitGuard(
          onBeforeExit: () {
            consumed += 1;
            return true;
          },
          child: const Scaffold(body: Text('设置')),
        ),
      ),
    );

    await tester.binding.handlePopRoute();
    await tester.pump();
    expect(consumed, 1);
    expect(find.text('再按一次退出'), findsNothing);
  });
}

bool _denyExit() => false;
