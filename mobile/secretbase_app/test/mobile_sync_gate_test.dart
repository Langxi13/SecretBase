import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/features/sync/mobile_sync_gate.dart';

void main() {
  test('自动与手动同步不能同时进入全局操作区', () async {
    final release = Completer<void>();
    final active = MobileSyncGate.run(() async {
      await release.future;
      return 'done';
    });
    expect(MobileSyncGate.busy, isTrue);
    await expectLater(
      MobileSyncGate.run(() async => 'second'),
      throwsA(isA<MobileSyncBusyException>()),
    );
    release.complete();
    expect(await active, 'done');
    expect(MobileSyncGate.busy, isFalse);
  });
}
