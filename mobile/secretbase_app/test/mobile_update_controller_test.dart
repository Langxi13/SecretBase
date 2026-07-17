import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:secretbase/src/features/update/mobile_update_controller.dart';
import 'package:secretbase/src/features/update/mobile_update_platform.dart';
import 'package:secretbase/src/features/update/mobile_update_service.dart';
import 'package:secretbase/src/state/preferences_controller.dart';
import 'package:secretbase/src/state/vault_controller.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FakePlatform implements MobileUpdatePlatform {
  _FakePlatform({required this.application});

  final MobileApplicationInfo application;
  MobileNetworkType network = MobileNetworkType.unmetered;
  Object? networkError;
  Object? installError;
  String? installedPath;

  @override
  Future<MobileApplicationInfo> applicationInfo() async => application;

  @override
  Future<bool> canInstallPackages() async => true;

  @override
  Future<void> installPackage(String path) async {
    final error = installError;
    if (error != null) throw error;
    installedPath = path;
  }

  @override
  Future<MobilePackageInfo> inspectPackage(String path) async {
    return MobilePackageInfo(
      packageId: application.packageId,
      versionName: '5.1.1',
      versionCode: 5010100,
      signerSha256: application.signerSha256,
    );
  }

  @override
  Future<MobileNetworkType> networkType() async {
    final error = networkError;
    if (error != null) throw error;
    return network;
  }

  @override
  Future<void> openInstallPermission() async {}
}

class _FakeUpdateService extends MobileUpdateService {
  _FakeUpdateService({
    required super.platform,
    required this.asset,
    this.downloadError,
  }) : super(client: MockClient((request) async => http.Response('', 500)));

  final MobileUpdateAsset asset;
  final MobileUpdateException? downloadError;
  final String downloadPath = '/tmp/secretbase-update.apk';

  @override
  Future<MobileUpdateAsset?> checkForUpdate(
    MobileApplicationInfo current,
  ) async => asset;

  @override
  Future<String> download(
    MobileUpdateAsset asset,
    MobileApplicationInfo current, {
    required DownloadCancellation cancellation,
    required void Function(int downloaded, int total) onProgress,
  }) async {
    final error = downloadError;
    if (error != null) throw error;
    onProgress(1, 1);
    return downloadPath;
  }

  @override
  Future<void> validatePackage(
    String path,
    MobileUpdateAsset asset,
    MobileApplicationInfo current,
  ) async {}
}

class _LockedVaultController extends VaultController {
  @override
  VaultUiState build() => const VaultUiState(phase: VaultPhase.locked);
}

MobileApplicationInfo _application() => MobileApplicationInfo(
  packageId: 'io.github.langxi13.secretbase',
  versionName: '5.1.0',
  versionCode: 5010000,
  signerSha256: List.filled(64, 'a').join(),
  cacheRoot: '/tmp',
);

MobileUpdateAsset _asset(MobileApplicationInfo application) =>
    MobileUpdateAsset(
      version: '5.1.1',
      versionCode: 5010100,
      filename: 'SecretBase-v5.1.1-android-universal.apk',
      url: Uri.parse(
        'https://github.com/Langxi13/SecretBase/releases/download/'
        'v5.1.1/SecretBase-v5.1.1-android-universal.apk',
      ),
      size: 1,
      sha256: List.filled(64, 'b').join(),
      packageId: application.packageId,
      signerSha256: application.signerSha256,
      releaseUrl: Uri.parse(
        'https://github.com/Langxi13/SecretBase/releases/tag/v5.1.1',
      ),
      notes: '稳定性更新',
    );

Future<ProviderContainer> _container({
  required _FakePlatform platform,
  required _FakeUpdateService service,
  bool autoDownload = true,
}) async {
  SharedPreferences.setMockInitialValues({
    'update_auto_check': true,
    'update_auto_download': autoDownload,
    'update_allow_metered_download': false,
  });
  final preferences = await SharedPreferences.getInstance();
  return ProviderContainer(
    overrides: [
      sharedPreferencesProvider.overrideWithValue(preferences),
      mobileUpdatePlatformProvider.overrideWithValue(platform),
      mobileUpdateServiceProvider.overrideWithValue(service),
      vaultControllerProvider.overrideWith(_LockedVaultController.new),
    ],
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('发现更新后读取网络状态失败仍保留手动下载入口', () async {
    final application = _application();
    final platform = _FakePlatform(application: application)
      ..networkError = StateError('permission unavailable');
    final service = _FakeUpdateService(
      platform: platform,
      asset: _asset(application),
    );
    final container = await _container(platform: platform, service: service);
    addTearDown(container.dispose);

    await container.read(mobileUpdateControllerProvider.notifier).check();

    final state = container.read(mobileUpdateControllerProvider);
    expect(state.phase, MobileUpdatePhase.available);
    expect(state.asset?.version, '5.1.1');
    expect(state.message, contains('手动下载'));
  });

  test('下载失败后保留更新信息和重试入口', () async {
    final application = _application();
    final platform = _FakePlatform(application: application);
    final service = _FakeUpdateService(
      platform: platform,
      asset: _asset(application),
      downloadError: const MobileUpdateException('测试下载失败'),
    );
    final container = await _container(
      platform: platform,
      service: service,
      autoDownload: false,
    );
    addTearDown(container.dispose);

    final controller = container.read(mobileUpdateControllerProvider.notifier);
    await controller.check();
    await controller.download();

    final state = container.read(mobileUpdateControllerProvider);
    expect(state.phase, MobileUpdatePhase.available);
    expect(state.asset?.version, '5.1.1');
    expect(state.message, '测试下载失败');
    expect(state.progress, 0);
  });

  test('系统安装界面启动失败后仍可再次安装', () async {
    final application = _application();
    final platform = _FakePlatform(application: application)
      ..installError = StateError('installer unavailable');
    final service = _FakeUpdateService(
      platform: platform,
      asset: _asset(application),
    );
    final container = await _container(
      platform: platform,
      service: service,
      autoDownload: false,
    );
    addTearDown(container.dispose);

    final controller = container.read(mobileUpdateControllerProvider.notifier);
    await controller.check();
    await controller.download();
    await controller.install();

    final state = container.read(mobileUpdateControllerProvider);
    expect(state.phase, MobileUpdatePhase.ready);
    expect(state.message, contains('重试'));
  });

  test('打开系统安装界面后不会永久停留在处理中', () async {
    final application = _application();
    final platform = _FakePlatform(application: application);
    final service = _FakeUpdateService(
      platform: platform,
      asset: _asset(application),
    );
    final container = await _container(
      platform: platform,
      service: service,
      autoDownload: false,
    );
    addTearDown(container.dispose);

    final controller = container.read(mobileUpdateControllerProvider.notifier);
    await controller.check();
    await controller.download();
    await controller.install();

    final state = container.read(mobileUpdateControllerProvider);
    expect(platform.installedPath, '/tmp/secretbase-update.apk');
    expect(state.phase, MobileUpdatePhase.ready);
    expect(state.message, contains('若取消安装'));
  });
}
