import 'package:flutter/services.dart';

enum MobileNetworkType { offline, unmetered, metered }

class MobileApplicationInfo {
  const MobileApplicationInfo({
    required this.packageId,
    required this.versionName,
    required this.versionCode,
    required this.signerSha256,
    required this.cacheRoot,
  });

  final String packageId;
  final String versionName;
  final int versionCode;
  final String signerSha256;
  final String cacheRoot;

  factory MobileApplicationInfo.fromMap(Map<Object?, Object?> value) {
    return MobileApplicationInfo(
      packageId: value['packageId'] as String? ?? '',
      versionName: value['versionName'] as String? ?? '',
      versionCode: (value['versionCode'] as num?)?.toInt() ?? 0,
      signerSha256: (value['signerSha256'] as String? ?? '').toLowerCase(),
      cacheRoot: value['cacheRoot'] as String? ?? '',
    );
  }
}

class MobilePackageInfo {
  const MobilePackageInfo({
    required this.packageId,
    required this.versionName,
    required this.versionCode,
    required this.signerSha256,
  });

  final String packageId;
  final String versionName;
  final int versionCode;
  final String signerSha256;

  factory MobilePackageInfo.fromMap(Map<Object?, Object?> value) {
    return MobilePackageInfo(
      packageId: value['packageId'] as String? ?? '',
      versionName: value['versionName'] as String? ?? '',
      versionCode: (value['versionCode'] as num?)?.toInt() ?? 0,
      signerSha256: (value['signerSha256'] as String? ?? '').toLowerCase(),
    );
  }
}

abstract class MobileUpdatePlatform {
  Future<MobileApplicationInfo> applicationInfo();

  Future<MobileNetworkType> networkType();

  Future<MobilePackageInfo> inspectPackage(String path);

  Future<bool> canInstallPackages();

  Future<void> openInstallPermission();

  Future<void> installPackage(String path);
}

class MethodChannelMobileUpdatePlatform implements MobileUpdatePlatform {
  const MethodChannelMobileUpdatePlatform();

  static const _channel = MethodChannel('secretbase/platform');

  @override
  Future<MobileApplicationInfo> applicationInfo() async {
    final value = await _channel.invokeMapMethod<Object?, Object?>(
      'getApplicationInfo',
    );
    if (value == null) throw StateError('无法读取应用版本信息');
    return MobileApplicationInfo.fromMap(value);
  }

  @override
  Future<bool> canInstallPackages() async {
    return await _channel.invokeMethod<bool>('canInstallPackages') ?? false;
  }

  @override
  Future<void> installPackage(String path) {
    return _channel.invokeMethod<void>('installUpdatePackage', {'path': path});
  }

  @override
  Future<MobilePackageInfo> inspectPackage(String path) async {
    final value = await _channel.invokeMapMethod<Object?, Object?>(
      'inspectUpdatePackage',
      {'path': path},
    );
    if (value == null) throw StateError('无法读取更新包信息');
    return MobilePackageInfo.fromMap(value);
  }

  @override
  Future<MobileNetworkType> networkType() async {
    final value = await _channel.invokeMethod<String>('getNetworkType');
    return switch (value) {
      'unmetered' => MobileNetworkType.unmetered,
      'metered' => MobileNetworkType.metered,
      _ => MobileNetworkType.offline,
    };
  }

  @override
  Future<void> openInstallPermission() {
    return _channel.invokeMethod<void>('openInstallPermission');
  }
}
