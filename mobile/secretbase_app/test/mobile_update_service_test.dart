import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:cryptography/cryptography.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:secretbase/src/features/update/mobile_update_platform.dart';
import 'package:secretbase/src/features/update/mobile_update_service.dart';

class _FakePlatform implements MobileUpdatePlatform {
  _FakePlatform({required this.current, required this.package});

  final MobileApplicationInfo current;
  final MobilePackageInfo package;
  bool permission = true;
  bool permissionOpened = false;
  String? installedPath;

  @override
  Future<MobileApplicationInfo> applicationInfo() async => current;

  @override
  Future<bool> canInstallPackages() async => permission;

  @override
  Future<void> installPackage(String path) async => installedPath = path;

  @override
  Future<MobilePackageInfo> inspectPackage(String path) async => package;

  @override
  Future<MobileNetworkType> networkType() async => MobileNetworkType.unmetered;

  @override
  Future<void> openInstallPermission() async => permissionOpened = true;
}

class _SignedFixture {
  const _SignedFixture({
    required this.manifest,
    required this.signature,
    required this.publicKeys,
    required this.assetBytes,
    required this.assetUrl,
    required this.arm64AssetUrl,
  });

  final List<int> manifest;
  final String signature;
  final Map<String, String> publicKeys;
  final List<int> assetBytes;
  final Uri assetUrl;
  final Uri arm64AssetUrl;
}

Future<_SignedFixture> _fixture({
  String signer = 'a',
  String version = '5.0.1',
  int versionCode = 5000100,
}) async {
  final assetBytes = utf8.encode('signed-android-apk');
  final signerHash = List.filled(64, signer).join();
  final algorithm = Ed25519();
  final keyPair = await algorithm.newKeyPair();
  final publicKey = await keyPair.extractPublicKey();
  final keyId = sha256.convert(publicKey.bytes).toString().substring(0, 16);
  final assetUrl = Uri.parse(
    'https://github.com/Langxi13/SecretBase/releases/download/'
    'v$version/SecretBase-v$version-android-universal.apk',
  );
  final arm64AssetUrl = Uri.parse(
    'https://github.com/Langxi13/SecretBase/releases/download/'
    'v$version/SecretBase-v$version-android-arm64-v8a.apk',
  );
  Map<String, Object> androidAsset(Uri url, {int? assetVersionCode}) => {
    'filename': url.pathSegments.last,
    'url': url.toString(),
    'size': assetBytes.length,
    'sha256': sha256.convert(assetBytes).toString(),
    'package_id': 'io.github.langxi13.secretbase',
    'version_code': assetVersionCode ?? versionCode,
    'signer_sha256': signerHash,
  };
  final payload = {
    'schema_version': 1,
    'key_id': keyId,
    'channel': 'stable',
    'version': version,
    'published_at': '2026-07-16T00:00:00Z',
    'release_url':
        'https://github.com/Langxi13/SecretBase/releases/tag/v$version',
    'notes': '移动更新测试',
    'assets': {
      'android-universal': androidAsset(assetUrl),
      'android-arm64-v8a': androidAsset(
        arm64AssetUrl,
        assetVersionCode: versionCode + 2000,
      ),
    },
  };
  final manifest = utf8.encode(jsonEncode(payload));
  final signature = await algorithm.sign(manifest, keyPair: keyPair);
  return _SignedFixture(
    manifest: manifest,
    signature: base64Encode(signature.bytes),
    publicKeys: {keyId: base64Encode(publicKey.bytes)},
    assetBytes: assetBytes,
    assetUrl: assetUrl,
    arm64AssetUrl: arm64AssetUrl,
  );
}

void main() {
  test('检查更新断网时返回可操作的网络提示', () async {
    final current = MobileApplicationInfo(
      packageId: 'io.github.langxi13.secretbase',
      versionName: '5.1.0',
      versionCode: 5010000,
      signerSha256: List.filled(64, 'a').join(),
      cacheRoot: Directory.systemTemp.path,
    );
    final service = MobileUpdateService(
      platform: _FakePlatform(
        current: current,
        package: MobilePackageInfo(
          packageId: current.packageId,
          versionName: current.versionName,
          versionCode: current.versionCode,
          signerSha256: current.signerSha256,
        ),
      ),
      client: MockClient((request) async {
        throw const SocketException('offline');
      }),
      checkMaxAttempts: 1,
    );

    expect(
      () => service.checkForUpdate(current),
      throwsA(
        isA<MobileUpdateException>().having(
          (error) => error.message,
          'message',
          allOf(contains('GitHub'), contains('DNS'), contains('VPN')),
        ),
      ),
    );
  });

  test('检查更新证书失败时提示检查系统时间和代理证书', () async {
    final current = MobileApplicationInfo(
      packageId: 'io.github.langxi13.secretbase',
      versionName: '5.1.0',
      versionCode: 5010000,
      signerSha256: List.filled(64, 'a').join(),
      cacheRoot: Directory.systemTemp.path,
    );
    final service = MobileUpdateService(
      platform: _FakePlatform(
        current: current,
        package: MobilePackageInfo(
          packageId: current.packageId,
          versionName: current.versionName,
          versionCode: current.versionCode,
          signerSha256: current.signerSha256,
        ),
      ),
      client: MockClient((request) async {
        throw HandshakeException('certificate rejected');
      }),
      checkMaxAttempts: 1,
    );

    expect(
      () => service.checkForUpdate(current),
      throwsA(
        isA<MobileUpdateException>().having(
          (error) => error.message,
          'message',
          allOf(contains('系统时间'), contains('代理证书')),
        ),
      ),
    );
  });

  test('尚无正式更新清单时返回中性状态而不是网络失败', () async {
    final current = MobileApplicationInfo(
      packageId: 'io.github.langxi13.secretbase',
      versionName: '5.0.0',
      versionCode: 5000000,
      signerSha256: List.filled(64, 'a').join(),
      cacheRoot: Directory.systemTemp.path,
    );
    final service = MobileUpdateService(
      platform: _FakePlatform(
        current: current,
        package: MobilePackageInfo(
          packageId: current.packageId,
          versionName: current.versionName,
          versionCode: current.versionCode,
          signerSha256: current.signerSha256,
        ),
      ),
      client: MockClient((request) async => http.Response('not found', 404)),
    );

    expect(
      () => service.checkForUpdate(current),
      throwsA(
        isA<MobileUpdateUnavailable>().having(
          (error) => error.message,
          'message',
          contains('正式 Release'),
        ),
      ),
    );
  });

  test('签名清单通过后可以下载并复核 Android 包身份', () async {
    final fixture = await _fixture();
    final root = await Directory.systemTemp.createTemp('secretbase-update-');
    addTearDown(() => root.delete(recursive: true));
    final current = MobileApplicationInfo(
      packageId: 'io.github.langxi13.secretbase',
      versionName: '5.0.0',
      versionCode: 5000000,
      signerSha256: List.filled(64, 'a').join(),
      cacheRoot: root.path,
    );
    final platform = _FakePlatform(
      current: current,
      package: MobilePackageInfo(
        packageId: current.packageId,
        versionName: '5.0.1',
        versionCode: 5000100,
        signerSha256: current.signerSha256,
      ),
    );
    final client = MockClient((request) async {
      if (request.url.toString() == mobileUpdateManifestUrl) {
        return http.Response.bytes(fixture.manifest, 200);
      }
      if (request.url.toString() == mobileUpdateSignatureUrl) {
        return http.Response(fixture.signature, 200);
      }
      if (request.url == fixture.assetUrl) {
        return http.Response.bytes(fixture.assetBytes, 200);
      }
      return http.Response('not found', 404);
    });
    final service = MobileUpdateService(
      platform: platform,
      client: client,
      publicKeys: fixture.publicKeys,
      expectedSignerSha256: List.filled(64, 'a').join(),
    );

    final asset = await service.checkForUpdate(current);
    expect(asset?.version, '5.0.1');
    final path = await service.download(
      asset!,
      current,
      cancellation: DownloadCancellation(),
      onProgress: (downloaded, total) {},
    );
    expect(await File(path).readAsBytes(), fixture.assetBytes);
    await service.validatePackage(path, asset, current);
  });

  test('签名清单优先选择当前设备的 ABI 独立包', () async {
    final fixture = await _fixture();
    final current = MobileApplicationInfo(
      packageId: 'io.github.langxi13.secretbase',
      versionName: '5.0.0',
      versionCode: 5000000,
      signerSha256: List.filled(64, 'a').join(),
      cacheRoot: Directory.systemTemp.path,
      supportedAbis: const ['arm64-v8a', 'armeabi-v7a'],
    );
    final service = MobileUpdateService(
      platform: _FakePlatform(
        current: current,
        package: MobilePackageInfo(
          packageId: current.packageId,
          versionName: '5.0.1',
          versionCode: 5000100,
          signerSha256: current.signerSha256,
        ),
      ),
      publicKeys: fixture.publicKeys,
      expectedSignerSha256: List.filled(64, 'a').join(),
      client: MockClient((request) async {
        if (request.url.toString() == mobileUpdateManifestUrl) {
          return http.Response.bytes(fixture.manifest, 200);
        }
        return http.Response(fixture.signature, 200);
      }),
    );

    final asset = await service.checkForUpdate(current);

    expect(asset?.url, fixture.arm64AssetUrl);
    expect(asset?.filename, endsWith('android-arm64-v8a.apk'));
    expect(asset?.versionCode, 5002100);
  });

  test('临时签名测试版会明确要求一次迁移', () async {
    final fixture = await _fixture();
    final current = MobileApplicationInfo(
      packageId: 'io.github.langxi13.secretbase',
      versionName: '5.0.0',
      versionCode: 5000000,
      signerSha256: List.filled(64, 'b').join(),
      cacheRoot: Directory.systemTemp.path,
    );
    final platform = _FakePlatform(
      current: current,
      package: MobilePackageInfo(
        packageId: current.packageId,
        versionName: '5.0.1',
        versionCode: 5000100,
        signerSha256: current.signerSha256,
      ),
    );
    final service = MobileUpdateService(
      platform: platform,
      publicKeys: fixture.publicKeys,
      expectedSignerSha256: List.filled(64, 'a').join(),
      client: MockClient((request) async {
        if (request.url.toString() == mobileUpdateManifestUrl) {
          return http.Response.bytes(fixture.manifest, 200);
        }
        return http.Response(fixture.signature, 200);
      }),
    );

    expect(
      () => service.checkForUpdate(current),
      throwsA(isA<MobileUpdateReinstallRequired>()),
    );
  });

  test('临时签名测试版与正式版版本号相同时仍要求迁移', () async {
    final fixture = await _fixture(version: '5.0.0', versionCode: 5000000);
    final current = MobileApplicationInfo(
      packageId: 'io.github.langxi13.secretbase',
      versionName: '5.0.0',
      versionCode: 5000000,
      signerSha256: List.filled(64, 'b').join(),
      cacheRoot: Directory.systemTemp.path,
    );
    final service = MobileUpdateService(
      platform: _FakePlatform(
        current: current,
        package: MobilePackageInfo(
          packageId: current.packageId,
          versionName: current.versionName,
          versionCode: current.versionCode,
          signerSha256: current.signerSha256,
        ),
      ),
      publicKeys: fixture.publicKeys,
      expectedSignerSha256: List.filled(64, 'a').join(),
      client: MockClient((request) async {
        if (request.url.toString() == mobileUpdateManifestUrl) {
          return http.Response.bytes(fixture.manifest, 200);
        }
        return http.Response(fixture.signature, 200);
      }),
    );

    expect(
      () => service.checkForUpdate(current),
      throwsA(isA<MobileUpdateReinstallRequired>()),
    );
  });

  test('被篡改的更新清单不会进入解析和下载', () async {
    final fixture = await _fixture();
    final tampered = [...fixture.manifest, 32];
    final current = MobileApplicationInfo(
      packageId: 'io.github.langxi13.secretbase',
      versionName: '5.0.0',
      versionCode: 5000000,
      signerSha256: List.filled(64, 'a').join(),
      cacheRoot: Directory.systemTemp.path,
    );
    final platform = _FakePlatform(
      current: current,
      package: MobilePackageInfo(
        packageId: current.packageId,
        versionName: '5.0.1',
        versionCode: 5000100,
        signerSha256: current.signerSha256,
      ),
    );
    final service = MobileUpdateService(
      platform: platform,
      publicKeys: fixture.publicKeys,
      expectedSignerSha256: List.filled(64, 'a').join(),
      client: MockClient((request) async {
        if (request.url.toString() == mobileUpdateManifestUrl) {
          return http.Response.bytes(tampered, 200);
        }
        return http.Response(fixture.signature, 200);
      }),
    );

    expect(
      () => service.checkForUpdate(current),
      throwsA(
        isA<MobileUpdateException>().having(
          (error) => error.message,
          'message',
          contains('签名校验失败'),
        ),
      ),
    );
  });
}
