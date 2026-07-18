import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/features/sync/mobile_sync_management_dialogs.dart';
import 'package:secretbase/src/features/sync/mobile_sync_service.dart';

void main() {
  testWidgets('同步历史只对非当前快照提供恢复操作', (tester) async {
    String? selected;
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: FilledButton(
              onPressed: () async {
                selected = await showMobileSyncHistoryPicker(context, const [
                  MobileSyncHistoryItem(
                    snapshotId: 'current',
                    generation: 3,
                    createdAt: '2026-07-18T10:00:00Z',
                    deviceName: '当前设备',
                    frontier: true,
                  ),
                  MobileSyncHistoryItem(
                    snapshotId: 'older',
                    generation: 2,
                    createdAt: '2026-07-17T10:00:00Z',
                    deviceName: '另一设备',
                    frontier: false,
                  ),
                ]);
              },
              child: const Text('打开历史'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('打开历史'));
    await tester.pumpAndSettle();
    expect(find.byTooltip('当前分支'), findsOneWidget);
    expect(find.byTooltip('恢复此版本'), findsOneWidget);
    await tester.tap(find.byTooltip('恢复此版本'));
    await tester.pumpAndSettle();
    expect(selected, 'older');
  });

  testWidgets('高风险同步操作在主密码和确认词完整前保持禁用', (tester) async {
    MobileSyncDangerInput? result;
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: FilledButton(
              onPressed: () async {
                result = await promptSyncDangerConfirmation(
                  context,
                  title: '压缩历史',
                  message: '测试确认',
                  confirmation: 'COMPACT',
                );
              },
              child: const Text('开始'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('开始'));
    await tester.pumpAndSettle();
    final continueButton = find.widgetWithText(FilledButton, '继续');
    expect(tester.widget<FilledButton>(continueButton).onPressed, isNull);

    await tester.enterText(find.byType(TextField).first, 'master-password');
    await tester.enterText(find.byType(TextField).last, 'COMPACT');
    await tester.pump();
    expect(tester.widget<FilledButton>(continueButton).onPressed, isNotNull);
    await tester.tap(continueButton);
    await tester.pumpAndSettle();
    expect(result?.confirmation, 'COMPACT');
    expect(result?.password, 'master-password');
  });
}
