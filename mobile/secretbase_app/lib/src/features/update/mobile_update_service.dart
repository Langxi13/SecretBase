import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:cryptography/cryptography.dart';
import 'package:http/http.dart' as http;
import 'package:secretbase/src/features/update/mobile_update_download.dart';
import 'package:secretbase/src/features/update/mobile_update_platform.dart';

export 'package:secretbase/src/features/update/mobile_update_download.dart'
    show DownloadCancellation;

const mobileUpdateManifestUrl =
    'https://github.com/Langxi13/SecretBase/releases/latest/download/secretbase-update-v1.json';
const mobileUpdateSignatureUrl = '$mobileUpdateManifestUrl.sig';
const mobileUpdatePublicKeys = {
  '1c9180b8f11c8c43': 'BAED+Er+yGF73nPHdj2SlkxkC1E6g5Rnw0muCqw77B4=',
};
const mobileProductionSignerSha256 =
    '1597489d9e88d47313792e6883cd295c72268a1ce9330138a81e3c3d038c1c64';
const mobileUpdateRequestTimeout = Duration(seconds: 20);
const mobileUpdateCheckMaxAttempts = 3;
const mobileUpdateMaxSignatureBytes = 4096;

class MobileUpdateException implements Exception {
  const MobileUpdateException(this.message);

  final String message;

  @override
  String toString() => message;
}

class MobileUpdateReinstallRequired extends MobileUpdateException {
  const MobileUpdateReinstallRequired(super.message);
}

class MobileUpdateUnavailable extends MobileUpdateException {
  const MobileUpdateUnavailable(super.message);
}

class MobileUpdateAsset {
  const MobileUpdateAsset({
    required this.version,
    required this.versionCode,
    required this.filename,
    required this.url,
    required this.size,
    required this.sha256,
    required this.packageId,
    required this.signerSha256,
    required this.releaseUrl,
    required this.notes,
  });

  final String version;
  final int versionCode;
  final String filename;
  final Uri url;
  final int size;
  final String sha256;
  final String packageId;
  final String signerSha256;
  final Uri releaseUrl;
  final String notes;
}

class MobileUpdateService {
  MobileUpdateService({
    required this.platform,
    http.Client? client,
    this.publicKeys = mobileUpdatePublicKeys,
    this.expectedSignerSha256 = mobileProductionSignerSha256,
    this.checkMaxAttempts = mobileUpdateCheckMaxAttempts,
    Uri? manifestUri,
    Uri? signatureUri,
  }) : assert(checkMaxAttempts > 0),
       client = client ?? http.Client(),
       manifestUri = manifestUri ?? Uri.parse(mobileUpdateManifestUrl),
       signatureUri = signatureUri ?? Uri.parse(mobileUpdateSignatureUrl);

  final MobileUpdatePlatform platform;
  final http.Client client;
  final Map<String, String> publicKeys;
  final String expectedSignerSha256;
  final int checkMaxAttempts;
  final Uri manifestUri;
  final Uri signatureUri;

  late final MobileUpdateDownloader _downloader = MobileUpdateDownloader(
    client: client,
  );

  Future<MobileUpdateAsset?> checkForUpdate(
    MobileApplicationInfo current,
  ) async {
    late final List<http.Response> responses;
    try {
      responses = await Future.wait([
        _getWithRetry(
          manifestUri,
          headers: const {'Accept': 'application/json'},
        ),
        _getWithRetry(signatureUri),
      ]);
    } on TimeoutException {
      throw const MobileUpdateException('获取正式版本信息超时，请稍后重试');
    } on HandshakeException {
      throw const MobileUpdateException('HTTPS 证书验证失败，请检查系统时间、VPN 或代理证书');
    } on SocketException {
      throw const MobileUpdateException('无法连接 GitHub 更新服务，请检查网络、DNS 或 VPN');
    } on http.ClientException {
      throw const MobileUpdateException('更新服务连接失败，请检查网络后重试');
    }
    if (responses[0].statusCode == 404) {
      throw const MobileUpdateUnavailable(
        '当前暂无支持自动更新的正式版本；正式 Release 发布后即可检查更新',
      );
    }
    if (responses[0].statusCode != 200) {
      throw MobileUpdateException('无法获取正式版本信息：HTTP ${responses[0].statusCode}');
    }
    if (responses[1].statusCode == 404) {
      throw const MobileUpdateException('正式更新清单缺少签名文件');
    }
    if (responses[1].statusCode != 200) {
      throw MobileUpdateException('无法获取正式版本签名：HTTP ${responses[1].statusCode}');
    }
    final manifestBytes = responses[0].bodyBytes;
    if (manifestBytes.isEmpty || manifestBytes.length > 512 * 1024) {
      throw const MobileUpdateException('更新清单大小无效');
    }
    final signatureBytes = responses[1].bodyBytes;
    if (signatureBytes.isEmpty ||
        signatureBytes.length > mobileUpdateMaxSignatureBytes) {
      throw const MobileUpdateException('更新清单签名大小无效');
    }
    final untrusted = _decodeObject(manifestBytes);
    final keyId = untrusted['key_id'] as String? ?? '';
    final encodedKey = publicKeys[keyId];
    if (encodedKey == null) {
      throw const MobileUpdateException('更新清单使用了未知签名密钥');
    }
    final signature = _decodeBase64(
      responses[1].body.trim(),
      '更新清单签名无效',
      expectedLength: 64,
    );
    final verified = await Ed25519().verify(
      manifestBytes,
      signature: Signature(
        signature,
        publicKey: SimplePublicKey(
          _decodeBase64(encodedKey, '更新公钥无效', expectedLength: 32),
          type: KeyPairType.ed25519,
        ),
      ),
    );
    if (!verified) throw const MobileUpdateException('更新清单签名校验失败');
    return _validateManifest(untrusted, current);
  }

  Future<String> download(
    MobileUpdateAsset asset,
    MobileApplicationInfo current, {
    required DownloadCancellation cancellation,
    required void Function(int downloaded, int total) onProgress,
    bool restart = false,
  }) async {
    final updates = Directory('${current.cacheRoot}/updates/${asset.version}');
    await updates.create(recursive: true);
    final target = File('${updates.path}/${asset.filename}');
    final temporary = File('${target.path}.part');
    if (await _validFile(target, asset)) {
      try {
        await validatePackage(target.path, asset, current);
        return target.path;
      } catch (_) {
        await _deleteIfExists(target);
        rethrow;
      }
    }

    for (var integrityAttempt = 0; integrityAttempt < 2; integrityAttempt++) {
      try {
        await _downloader.download(
          url: asset.url,
          temporary: temporary,
          expectedSize: asset.size,
          userAgent: 'SecretBase/${current.versionName}',
          cancellation: cancellation,
          onProgress: onProgress,
          restart: restart || integrityAttempt > 0,
        );
      } on MobileUpdateDownloadFailure catch (error) {
        throw MobileUpdateException(error.message);
      }
      if (await _validFile(temporary, asset)) break;
      await _deleteIfExists(temporary);
      if (integrityAttempt == 1) {
        throw const MobileUpdateException('更新文件完整性校验失败，请重新下载');
      }
    }
    if (cancellation.cancelled) {
      throw const MobileUpdateException('更新下载已暂停');
    }
    await _deleteIfExists(target);
    await temporary.rename(target.path);
    try {
      await validatePackage(target.path, asset, current);
    } catch (_) {
      await _deleteIfExists(target);
      rethrow;
    }
    return target.path;
  }

  Future<void> validatePackage(
    String path,
    MobileUpdateAsset asset,
    MobileApplicationInfo current,
  ) async {
    final package = await platform.inspectPackage(path);
    if (package.packageId != current.packageId ||
        package.packageId != asset.packageId) {
      throw const MobileUpdateException('更新包应用标识不匹配');
    }
    if (package.versionCode != asset.versionCode ||
        package.versionCode <= current.versionCode) {
      throw const MobileUpdateException('更新包版本无效或低于当前版本');
    }
    if (package.signerSha256 != current.signerSha256 ||
        package.signerSha256 != asset.signerSha256) {
      throw const MobileUpdateException('更新包签名与当前应用不一致');
    }
  }

  Future<bool> _validFile(File file, MobileUpdateAsset asset) async {
    if (!await file.exists() || await file.length() != asset.size) return false;
    final digest = await sha256.bind(file.openRead()).first;
    return digest.toString() == asset.sha256;
  }

  MobileUpdateAsset? _validateManifest(
    Map<String, Object?> payload,
    MobileApplicationInfo current,
  ) {
    if (payload['schema_version'] != 1 || payload['channel'] != 'stable') {
      throw const MobileUpdateException('不支持的更新清单');
    }
    final version = payload['version'] as String? ?? '';
    if (!RegExp(r'^\d+\.\d+\.\d+$').hasMatch(version)) {
      throw const MobileUpdateException('正式版本号无效');
    }
    final releaseUrl = _trustedReleaseUri(
      payload['release_url'] as String? ?? '',
    );
    if (!releaseUrl.path.endsWith('/v$version')) {
      throw const MobileUpdateException('版本号与发布地址不一致');
    }
    final assets = payload['assets'];
    if (assets is! Map<String, Object?>) {
      throw const MobileUpdateException('更新清单缺少 Android 文件');
    }
    final rawAsset = _selectAndroidAsset(assets, current.supportedAbis);
    if (rawAsset is! Map<String, Object?>) {
      throw const MobileUpdateException('更新清单缺少 Android 文件');
    }
    final versionCode = (rawAsset['version_code'] as num?)?.toInt() ?? 0;
    final packageId = rawAsset['package_id'] as String? ?? '';
    final signer = (rawAsset['signer_sha256'] as String? ?? '').toLowerCase();
    if (packageId != current.packageId) {
      throw const MobileUpdateException('正式版本应用标识不匹配');
    }
    if (current.signerSha256 != expectedSignerSha256) {
      throw const MobileUpdateReinstallRequired(
        '当前测试版使用临时签名，请先导出加密备份并安装正式签名版本。',
      );
    }
    if (signer != expectedSignerSha256) {
      throw const MobileUpdateException('更新包未使用 SecretBase 正式发布签名');
    }
    if (versionCode <= current.versionCode) return null;
    final filename = rawAsset['filename'] as String? ?? '';
    final size = (rawAsset['size'] as num?)?.toInt() ?? 0;
    final checksum = (rawAsset['sha256'] as String? ?? '').toLowerCase();
    if (filename.isEmpty || filename.contains('/') || filename.contains('\\')) {
      throw const MobileUpdateException('更新文件名无效');
    }
    if (size <= 0 || !RegExp(r'^[0-9a-f]{64}$').hasMatch(checksum)) {
      throw const MobileUpdateException('更新文件完整性信息无效');
    }
    final assetUrl = _trustedAssetUri(rawAsset['url'] as String? ?? '');
    if (!assetUrl.path.endsWith('/v$version/$filename')) {
      throw const MobileUpdateException('更新文件地址与版本不一致');
    }
    return MobileUpdateAsset(
      version: version,
      versionCode: versionCode,
      filename: filename,
      url: assetUrl,
      size: size,
      sha256: checksum,
      packageId: packageId,
      signerSha256: signer,
      releaseUrl: releaseUrl,
      notes: payload['notes'] as String? ?? '',
    );
  }

  static Map<String, Object?> _decodeObject(List<int> bytes) {
    try {
      final value = jsonDecode(utf8.decode(bytes));
      if (value is Map<String, Object?>) return value;
    } catch (_) {
      // Converted to a stable update error below.
    }
    throw const MobileUpdateException('更新清单不是有效 JSON');
  }

  static List<int> _decodeBase64(
    String value,
    String message, {
    int? expectedLength,
  }) {
    try {
      final decoded = base64Decode(value);
      if (expectedLength != null && decoded.length != expectedLength) {
        throw const FormatException('unexpected decoded length');
      }
      return decoded;
    } catch (_) {
      throw MobileUpdateException(message);
    }
  }

  static Future<void> _deleteIfExists(File file) async {
    try {
      if (await file.exists()) await file.delete();
    } catch (_) {
      // Cache cleanup is best effort; the original update error is more useful.
    }
  }

  Future<http.Response> _getWithRetry(
    Uri uri, {
    Map<String, String>? headers,
  }) async {
    for (var attempt = 0; attempt < checkMaxAttempts; attempt++) {
      try {
        final response = await client
            .get(uri, headers: headers)
            .timeout(mobileUpdateRequestTimeout);
        if ((response.statusCode == HttpStatus.tooManyRequests ||
                response.statusCode >= 500) &&
            attempt + 1 < checkMaxAttempts) {
          await _waitBeforeCheckRetry(attempt);
          continue;
        }
        return response;
      } on HandshakeException {
        rethrow;
      } catch (error, stackTrace) {
        final transient =
            error is TimeoutException ||
            error is SocketException ||
            error is http.ClientException;
        if (!transient || attempt + 1 >= checkMaxAttempts) {
          Error.throwWithStackTrace(error, stackTrace);
        }
        await _waitBeforeCheckRetry(attempt);
      }
    }
    throw TimeoutException('update check retries exhausted');
  }

  static Future<void> _waitBeforeCheckRetry(int attempt) {
    return Future<void>.delayed(Duration(seconds: attempt == 0 ? 1 : 3));
  }

  static Object? _selectAndroidAsset(
    Map<String, Object?> assets,
    List<String> supportedAbis,
  ) {
    const keysByAbi = {
      'arm64-v8a': 'android-arm64-v8a',
      'armeabi-v7a': 'android-armeabi-v7a',
      'x86_64': 'android-x86_64',
    };
    for (final abi in supportedAbis) {
      final key = keysByAbi[abi];
      if (key != null && assets.containsKey(key)) return assets[key];
    }
    return assets['android-universal'];
  }

  static Uri _trustedReleaseUri(String value) {
    final uri = Uri.tryParse(value);
    if (uri == null ||
        uri.scheme != 'https' ||
        uri.host != 'github.com' ||
        !uri.path.startsWith('/Langxi13/SecretBase/releases/tag/')) {
      throw const MobileUpdateException('发布页面地址不受信任');
    }
    return uri;
  }

  static Uri _trustedAssetUri(String value) {
    final uri = Uri.tryParse(value);
    if (uri == null ||
        uri.scheme != 'https' ||
        uri.host != 'github.com' ||
        !uri.path.startsWith('/Langxi13/SecretBase/releases/download/')) {
      throw const MobileUpdateException('更新文件地址不受信任');
    }
    return uri;
  }
}
