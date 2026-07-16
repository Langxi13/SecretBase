import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/autofill_service.dart';

void main() {
  test('autofill status decodes native settings', () {
    final status = AutofillStatus.fromMap({
      'supported': true,
      'enabled': true,
      'savePromptsEnabled': false,
      'inlineSuggestionsEnabled': true,
      'blockedTargetCount': 3,
    });

    expect(status.supported, isTrue);
    expect(status.enabled, isTrue);
    expect(status.savePromptsEnabled, isFalse);
    expect(status.inlineSuggestionsEnabled, isTrue);
    expect(status.blockedTargetCount, 3);
  });

  test(
    'autofill status keeps privacy-safe defaults for old native bridges',
    () {
      final status = AutofillStatus.fromMap(const {});

      expect(status.supported, isFalse);
      expect(status.enabled, isFalse);
      expect(status.savePromptsEnabled, isTrue);
      expect(status.inlineSuggestionsEnabled, isTrue);
      expect(status.blockedTargetCount, 0);
    },
  );
}
