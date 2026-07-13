import 'package:secretbase/src/rust/mobile/error.dart';

String mobileErrorMessage(Object error) {
  if (error is MobileError_Failure) {
    return error.message;
  }
  return '操作失败，请稍后重试';
}

bool isRevisionConflict(Object error) {
  return error is MobileError_Failure && error.code == 'REVISION_CONFLICT';
}
