import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/features/ai/ai_providers.dart';

void main() {
  test('AI 厂商预设可编辑且不包含 Qwen', () {
    final ids = aiProviderPresets.map((provider) => provider.id).toList();

    expect(ids.toSet().length, ids.length);
    expect(ids, isNot(contains('qwen')));
    expect(aiProviderPresets.last.id, 'custom');
    for (final provider in aiProviderPresets.where(
      (provider) => provider.id != 'custom',
    )) {
      expect(Uri.parse(provider.baseUrl).scheme, 'https');
    }
  });
}
