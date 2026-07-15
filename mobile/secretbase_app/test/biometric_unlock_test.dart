import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/core/biometric_unlock.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('secretbase/security');

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  test('生物识别平台通道读取状态并传递短暂设备凭据', () async {
    Uint8List? stored;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          switch (call.method) {
            case 'biometricStatus':
              return <String, Object>{
                'supported': true,
                'enrolled': true,
                'credentialStored': true,
                'hardwareBacked': true,
              };
            case 'storeBiometricCredential':
              final arguments = call.arguments as Map<Object?, Object?>;
              stored = Uint8List.fromList(
                arguments['credential']! as Uint8List,
              );
              return null;
            case 'readBiometricCredential':
              return Uint8List.fromList([4, 5, 6]);
            case 'deleteBiometricCredential':
              return true;
          }
          return null;
        });

    const platform = MethodChannelBiometricPlatform();
    final status = await platform.status();
    expect(status.supported, isTrue);
    expect(status.enrolled, isTrue);
    expect(status.credentialStored, isTrue);
    expect(status.hardwareBacked, isTrue);

    final outgoing = Uint8List.fromList([1, 2, 3]);
    await platform.storeCredential(outgoing);
    expect(stored, [1, 2, 3]);
    expect(await platform.readCredential(), [4, 5, 6]);
    expect(await platform.deleteCredential(), isTrue);

    clearSensitiveBytes(outgoing);
    expect(outgoing, [0, 0, 0]);
  });

  test('缺少原生插件时状态安全降级为不支持', () async {
    const platform = MethodChannelBiometricPlatform();
    final status = await platform.status();
    expect(status.supported, isFalse);
    expect(status.credentialStored, isFalse);
  });
}
