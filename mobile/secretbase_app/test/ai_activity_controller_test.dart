import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/features/ai/ai_activity_controller.dart';

void main() {
  test('旧 AI 请求释放时不会解除新请求的全局锁', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final activity = container.read(aiActivityControllerProvider.notifier);

    final first = activity.acquire();
    expect(first, isNotNull);
    expect(activity.acquire(), isNull);
    activity.finish(first);
    expect(container.read(aiActivityControllerProvider), isFalse);

    final second = activity.acquire();
    expect(second, isNotNull);
    activity.finish(first);
    expect(container.read(aiActivityControllerProvider), isTrue);
    activity.finish(second);
    expect(container.read(aiActivityControllerProvider), isFalse);
  });
}
