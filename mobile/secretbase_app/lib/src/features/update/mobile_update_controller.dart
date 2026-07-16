import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:secretbase/src/features/update/mobile_update_platform.dart';
import 'package:secretbase/src/features/update/mobile_update_service.dart';
import 'package:secretbase/src/state/preferences_controller.dart';
import 'package:secretbase/src/state/vault_controller.dart';

enum MobileUpdatePhase {
  idle,
  checking,
  available,
  downloading,
  ready,
  installing,
  upToDate,
  unavailable,
  reinstallRequired,
  error,
}

class MobileUpdateState {
  const MobileUpdateState({
    this.phase = MobileUpdatePhase.idle,
    this.application,
    this.asset,
    this.downloadPath,
    this.progress = 0,
    this.message = '',
  });

  final MobileUpdatePhase phase;
  final MobileApplicationInfo? application;
  final MobileUpdateAsset? asset;
  final String? downloadPath;
  final int progress;
  final String message;

  bool get busy => const {
    MobileUpdatePhase.checking,
    MobileUpdatePhase.downloading,
    MobileUpdatePhase.installing,
  }.contains(phase);

  MobileUpdateState copyWith({
    MobileUpdatePhase? phase,
    MobileApplicationInfo? application,
    MobileUpdateAsset? asset,
    String? downloadPath,
    int? progress,
    String? message,
    bool clearAsset = false,
    bool clearDownload = false,
  }) {
    return MobileUpdateState(
      phase: phase ?? this.phase,
      application: application ?? this.application,
      asset: clearAsset ? null : asset ?? this.asset,
      downloadPath: clearDownload ? null : downloadPath ?? this.downloadPath,
      progress: progress ?? this.progress,
      message: message ?? this.message,
    );
  }
}

final mobileUpdatePlatformProvider = Provider<MobileUpdatePlatform>(
  (ref) => const MethodChannelMobileUpdatePlatform(),
);

final mobileUpdateHttpClientProvider = Provider<http.Client>((ref) {
  final client = http.Client();
  ref.onDispose(client.close);
  return client;
});

final mobileUpdateServiceProvider = Provider<MobileUpdateService>((ref) {
  return MobileUpdateService(
    platform: ref.watch(mobileUpdatePlatformProvider),
    client: ref.watch(mobileUpdateHttpClientProvider),
  );
});

final mobileUpdateControllerProvider =
    NotifierProvider<MobileUpdateController, MobileUpdateState>(
      MobileUpdateController.new,
    );

class MobileUpdateController extends Notifier<MobileUpdateState> {
  DownloadCancellation? _cancellation;

  @override
  MobileUpdateState build() => const MobileUpdateState();

  Future<void> maybeCheck() async {
    if (state.busy) return;
    final preferences = ref.read(preferencesProvider);
    if (state.application == null) {
      try {
        final application = await ref
            .read(mobileUpdatePlatformProvider)
            .applicationInfo();
        state = state.copyWith(application: application);
      } catch (_) {
        if (!preferences.updateAutoCheck) return;
      }
    }
    if (!preferences.updateAutoCheck) return;
    final lastCheck = preferences.lastUpdateCheckAt;
    if (lastCheck != null) {
      final elapsed = DateTime.now().difference(lastCheck);
      if (!elapsed.isNegative && elapsed < const Duration(hours: 24)) return;
    }
    await check();
  }

  Future<void> check() async {
    if (state.busy) return;
    state = state.copyWith(
      phase: MobileUpdatePhase.checking,
      progress: 0,
      message: '',
      clearAsset: true,
      clearDownload: true,
    );
    try {
      final platform = ref.read(mobileUpdatePlatformProvider);
      final application = state.application ?? await platform.applicationInfo();
      final asset = await ref
          .read(mobileUpdateServiceProvider)
          .checkForUpdate(application);
      await ref
          .read(preferencesProvider.notifier)
          .setLastUpdateCheckAt(DateTime.now());
      if (asset == null) {
        state = state.copyWith(
          phase: MobileUpdatePhase.upToDate,
          application: application,
          message: '当前已是最新正式版本',
        );
        return;
      }
      state = state.copyWith(
        phase: MobileUpdatePhase.available,
        application: application,
        asset: asset,
        message: asset.notes,
      );
      final preferences = ref.read(preferencesProvider);
      if (!preferences.updateAutoDownload) return;
      final network = await platform.networkType();
      if (network == MobileNetworkType.unmetered ||
          (network == MobileNetworkType.metered &&
              preferences.updateAllowMeteredDownload)) {
        await download();
      } else if (network == MobileNetworkType.metered) {
        state = state.copyWith(message: '已发现新版本，当前设置为仅在 Wi-Fi 下自动下载');
      }
    } on MobileUpdateUnavailable catch (error) {
      await ref
          .read(preferencesProvider.notifier)
          .setLastUpdateCheckAt(DateTime.now());
      state = state.copyWith(
        phase: MobileUpdatePhase.unavailable,
        message: error.message,
      );
    } on MobileUpdateReinstallRequired catch (error) {
      await ref
          .read(preferencesProvider.notifier)
          .setLastUpdateCheckAt(DateTime.now());
      state = state.copyWith(
        phase: MobileUpdatePhase.reinstallRequired,
        message: error.message,
      );
    } catch (error) {
      await ref
          .read(preferencesProvider.notifier)
          .setLastUpdateCheckAt(DateTime.now());
      state = state.copyWith(
        phase: MobileUpdatePhase.error,
        message: error is MobileUpdateException
            ? error.message
            : '检查更新失败，请稍后重试',
      );
    }
  }

  Future<void> download() async {
    final asset = state.asset;
    final application = state.application;
    if (asset == null || application == null || state.busy) return;
    _cancellation = DownloadCancellation();
    state = state.copyWith(
      phase: MobileUpdatePhase.downloading,
      progress: 0,
      message: '正在下载更新',
      clearDownload: true,
    );
    try {
      final path = await ref
          .read(mobileUpdateServiceProvider)
          .download(
            asset,
            application,
            cancellation: _cancellation!,
            onProgress: (downloaded, total) {
              state = state.copyWith(
                progress: total <= 0 ? 0 : (downloaded * 100 / total).floor(),
              );
            },
          );
      state = state.copyWith(
        phase: MobileUpdatePhase.ready,
        downloadPath: path,
        progress: 100,
        message: '更新已下载，确认后由 Android 系统完成安装',
      );
    } catch (error) {
      final cancelled = _cancellation?.cancelled == true;
      state = state.copyWith(
        phase: cancelled
            ? MobileUpdatePhase.available
            : MobileUpdatePhase.error,
        message: cancelled
            ? '更新下载已取消'
            : error is MobileUpdateException
            ? error.message
            : '更新下载失败，请稍后重试',
      );
    } finally {
      _cancellation = null;
    }
  }

  void cancelDownload() => _cancellation?.cancel();

  Future<void> install() async {
    final path = state.downloadPath;
    final asset = state.asset;
    final application = state.application;
    if (path == null || asset == null || application == null || state.busy) {
      return;
    }
    final platform = ref.read(mobileUpdatePlatformProvider);
    try {
      await ref
          .read(mobileUpdateServiceProvider)
          .validatePackage(path, asset, application);
      if (!await platform.canInstallPackages()) {
        await platform.openInstallPermission();
        state = state.copyWith(
          phase: MobileUpdatePhase.ready,
          message: '请允许 SecretBase 安装未知应用，返回后再次点击安装',
        );
        return;
      }
      if (ref.read(vaultControllerProvider).phase == VaultPhase.unlocked) {
        await ref.read(vaultControllerProvider.notifier).lock();
      }
      state = state.copyWith(
        phase: MobileUpdatePhase.installing,
        message: '正在打开 Android 系统安装界面',
      );
      await platform.installPackage(path);
    } catch (error) {
      state = state.copyWith(
        phase: MobileUpdatePhase.error,
        message: error is MobileUpdateException
            ? error.message
            : '无法启动系统安装，请重试',
      );
    }
  }
}
