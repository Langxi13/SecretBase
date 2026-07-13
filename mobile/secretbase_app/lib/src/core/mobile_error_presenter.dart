import 'package:secretbase/src/rust/mobile/error.dart';

String mobileErrorMessage(Object error) {
  if (error is MobileError_Failure) {
    return error.message;
  }
  return '操作失败，请稍后重试';
}

String mobileUnlockErrorMessage(Object error) {
  if (error is MobileError_Failure && error.code == 'AUTHENTICATION_FAILED') {
    return '主密码错误';
  }
  return mobileErrorMessage(error);
}

bool isRevisionConflict(Object error) {
  return error is MobileError_Failure && error.code == 'REVISION_CONFLICT';
}
