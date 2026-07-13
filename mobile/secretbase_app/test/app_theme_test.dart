import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/theme/app_theme.dart';

void main() {
  test('标准字体模式比大字体模式更紧凑', () {
    final standard = AppTheme.light(textSize: AppTextSize.standard);
    final large = AppTheme.light(textSize: AppTextSize.large);

    expect(
      standard.textTheme.bodyMedium!.fontSize!,
      lessThan(large.textTheme.bodyMedium!.fontSize!),
    );
    expect(
      standard.navigationBarTheme.height!,
      lessThan(large.navigationBarTheme.height!),
    );
  });
}
