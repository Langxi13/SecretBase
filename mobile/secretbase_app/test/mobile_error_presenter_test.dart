import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/rust/mobile/error.dart';

void main() {
  test('解锁认证失败只提示主密码错误', () {
    const error = MobileError.failure(
      code: 'AUTHENTICATION_FAILED',
      message: '主密码错误或加密文件已损坏',
      retryable: false,
    );

    expect(mobileUnlockErrorMessage(error), '主密码错误');
    expect(mobileErrorMessage(error), '主密码错误或加密文件已损坏');
  });
}
