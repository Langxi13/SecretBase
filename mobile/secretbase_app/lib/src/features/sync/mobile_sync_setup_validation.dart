/// 校验移动端同步空间表单，返回可直接展示给用户的错误信息。
String? validateMobileSyncSetup({
  required String baseUrl,
  required String username,
  required String password,
  String recoveryCode = '',
  bool requireRecovery = false,
}) {
  final missing = <String>[];
  if (baseUrl.trim().isEmpty) missing.add('WebDAV 地址');
  if (username.trim().isEmpty) missing.add('用户名');
  if (password.isEmpty) missing.add('应用密码');
  if (requireRecovery && recoveryCode.trim().isEmpty) {
    missing.add('同步恢复码或配对信息');
  }
  if (missing.isNotEmpty) return '请补充：${missing.join('、')}';

  final uri = Uri.tryParse(baseUrl.trim());
  if (uri == null || uri.scheme.toLowerCase() != 'https' || uri.host.isEmpty) {
    return 'WebDAV 地址必须是有效的 HTTPS 地址';
  }
  return null;
}

bool validateAndReportMobileSyncSetup({
  required String baseUrl,
  required String username,
  required String password,
  required String recoveryCode,
  required bool requireRecovery,
  required void Function(String) onError,
}) {
  final error = validateMobileSyncSetup(
    baseUrl: baseUrl,
    username: username,
    password: password,
    recoveryCode: recoveryCode,
    requireRecovery: requireRecovery,
  );
  if (error == null) return true;
  onError(error);
  return false;
}
