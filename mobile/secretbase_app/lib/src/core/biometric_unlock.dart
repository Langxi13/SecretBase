import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class BiometricStatus {
  const BiometricStatus({
    required this.supported,
    required this.enrolled,
    required this.credentialStored,
    required this.hardwareBacked,
  });

  const BiometricStatus.unsupported()
    : supported = false,
      enrolled = false,
      credentialStored = false,
      hardwareBacked = false;

  final bool supported;
  final bool enrolled;
  final bool credentialStored;
  final bool hardwareBacked;

  factory BiometricStatus.fromMap(Map<Object?, Object?> value) {
    return BiometricStatus(
      supported: value['supported'] == true,
      enrolled: value['enrolled'] == true,
      credentialStored: value['credentialStored'] == true,
      hardwareBacked: value['hardwareBacked'] == true,
    );
  }
}

class BiometricException implements Exception {
  const BiometricException(this.code, this.message);

  final String code;
  final String message;

  bool get canceled => code == 'BIOMETRIC_CANCELED';

  @override
  String toString() => message;
}

abstract interface class BiometricPlatform {
  Future<BiometricStatus> status();

  Future<void> storeCredential(Uint8List credential);

  Future<Uint8List> readCredential();

  Future<bool> deleteCredential();
}

class MethodChannelBiometricPlatform implements BiometricPlatform {
  const MethodChannelBiometricPlatform();

  static const _channel = MethodChannel('secretbase/security');

  @override
  Future<BiometricStatus> status() async {
    try {
      final value = await _channel.invokeMethod<Map<Object?, Object?>>(
        'biometricStatus',
      );
      return value == null
          ? const BiometricStatus.unsupported()
          : BiometricStatus.fromMap(value);
    } on MissingPluginException {
      return const BiometricStatus.unsupported();
    } on PlatformException catch (error) {
      throw BiometricException(error.code, error.message ?? '无法读取生物识别状态');
    }
  }

  @override
  Future<void> storeCredential(Uint8List credential) async {
    await _invoke<void>('storeBiometricCredential', {'credential': credential});
  }

  @override
  Future<Uint8List> readCredential() async {
    final value = await _invoke<Uint8List>('readBiometricCredential');
    if (value == null || value.isEmpty) {
      throw const BiometricException(
        'BIOMETRIC_CREDENTIAL_INVALID',
        '指纹解锁凭据已失效',
      );
    }
    return value;
  }

  @override
  Future<bool> deleteCredential() async {
    return await _invoke<bool>('deleteBiometricCredential') ?? false;
  }

  Future<T?> _invoke<T>(String method, [Object? arguments]) async {
    try {
      return await _channel.invokeMethod<T>(method, arguments);
    } on PlatformException catch (error) {
      throw BiometricException(error.code, error.message ?? '生物识别操作失败');
    } on MissingPluginException {
      throw const BiometricException('BIOMETRIC_UNAVAILABLE', '当前平台不支持生物识别');
    }
  }
}

final biometricPlatformProvider = Provider<BiometricPlatform>(
  (ref) => const MethodChannelBiometricPlatform(),
);

final biometricStatusProvider = FutureProvider<BiometricStatus>(
  (ref) => ref.watch(biometricPlatformProvider).status(),
);

void clearSensitiveBytes(Uint8List bytes) {
  bytes.fillRange(0, bytes.length, 0);
}

String biometricErrorMessage(Object error) {
  if (error is BiometricException) return error.message;
  return '生物识别操作失败，请使用主密码';
}
