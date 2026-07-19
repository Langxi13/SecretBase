import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/secure_clipboard.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';
import 'package:secretbase/src/features/sync/mobile_sync_auto.dart';
import 'package:secretbase/src/features/sync/mobile_sync_configured_view.dart';
import 'package:secretbase/src/features/sync/mobile_sync_conflict_view.dart';
import 'package:secretbase/src/features/sync/mobile_sync_management_dialogs.dart';
import 'package:secretbase/src/features/sync/mobile_sync_pairing.dart';
import 'package:secretbase/src/features/sync/mobile_sync_pairing_scanner.dart';
import 'package:secretbase/src/features/sync/mobile_sync_setup_form.dart';
import 'package:secretbase/src/features/sync/mobile_sync_service.dart';
import 'package:secretbase/src/features/sync/mobile_sync_feedback.dart';
import 'package:secretbase/src/features/sync/mobile_sync_setup_validation.dart';
import 'package:secretbase/src/features/sync/mobile_webdav.dart';
import 'package:secretbase/src/rust/mobile/models.dart' as rust_models;
import 'package:secretbase/src/state/vault_controller.dart';

Future<void> showMobileSyncDialog(BuildContext context) async {
  await showResponsiveDialog<void>(
    context: context,
    maxWidth: 720,
    builder: (_) => const _MobileSyncDialog(),
  );
}

class _MobileSyncDialog extends ConsumerStatefulWidget {
  const _MobileSyncDialog();

  @override
  ConsumerState<_MobileSyncDialog> createState() => _MobileSyncDialogState();
}

class _MobileSyncDialogState extends ConsumerState<_MobileSyncDialog> {
  final _coordinator = MobileSyncCoordinator();
  final _url = TextEditingController();
  final _username = TextEditingController();
  final _password = TextEditingController();
  final _recovery = TextEditingController();
  final _device = TextEditingController();
  rust_models.SyncStatus? _status;
  MobileSyncConflictSession? _conflict;
  Map<String, String> _resolutions = {};
  String? _recoveryCode;
  String? _error;
  bool _errorCanReload = false;
  bool _connectionTestPassed = false;
  bool _loading = true;
  bool _working = false;
  bool _joining = false;
  bool _mergeExisting = false;
  bool _autoSync = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    if (_conflict != null) {
      unawaited(_coordinator.cancelPending().onError((_, _) {}));
    }
    _url.dispose();
    _username.dispose();
    _password.dispose();
    _recovery.dispose();
    _device.dispose();
    super.dispose();
  }

  Future<bool> _load({bool showError = true}) async {
    try {
      final status = await _coordinator.status();
      final connection = status.configured
          ? await _coordinator.connection()
          : null;
      if (!mounted) return false;
      setState(() {
        _status = status;
        _autoSync = status.autoSync;
        _error = null;
        _errorCanReload = false;
        if (connection != null) {
          _url.text = connection.baseUrl;
          _username.text = connection.username;
          _device.text = connection.deviceName;
        }
        _loading = false;
      });
      return true;
    } catch (error) {
      if (!mounted) return false;
      setState(() {
        _error = showError
            ? mobileErrorMessage(error)
            : '操作已完成，但同步状态读取失败，请点击“重新读取”。';
        _errorCanReload = true;
        _loading = false;
      });
      showMobileSyncError(context, _error!);
      return false;
    }
  }

  Future<void> _reloadStatus() async {
    if (_loading || _working || !mounted) return;
    setState(() {
      _loading = true;
      _error = null;
      _errorCanReload = false;
    });
    await _load();
  }

  Future<void> _create() async {
    if (!_validateSetup()) return;
    await _run(() async {
      final status = await _coordinator.create(
        baseUrl: _url.text,
        username: _username.text,
        password: _password.text,
        deviceName: _device.text,
        autoSync: _autoSync,
      );
      if (!mounted) return;
      setState(() {
        _status = status;
        _recoveryCode = null;
        _password.clear();
      });
      _showMessage('同步空间已创建，可验证主密码后显示恢复码。');
    });
  }

  Future<void> _join() async {
    if (!_validateSetup(requireRecovery: true)) return;
    await _run(() async {
      final result = await _coordinator.join(
        baseUrl: _url.text,
        username: _username.text,
        password: _password.text,
        recoveryCode: _recovery.text,
        deviceName: _device.text,
        autoSync: _autoSync,
        mergeExisting: _mergeExisting,
      );
      if (!mounted) return;
      setState(() {
        _password.clear();
        _recovery.clear();
        _conflict = result.conflictSession;
        _resolutions = {};
      });
      if (result.conflictSession == null) {
        final refreshed = await _refreshAfterMutation(refreshVault: true);
        _showMessage(mobileSyncResultMessage(result.message, refreshed));
      }
    });
  }

  Future<void> _testConnection() async {
    if (!_validateSetup(requireRecovery: false)) return;
    if (mounted) setState(() => _connectionTestPassed = false);
    await _run(() async {
      await _coordinator.testConnection(
        baseUrl: _url.text,
        username: _username.text,
        password: _password.text,
      );
      if (mounted) setState(() => _connectionTestPassed = true);
      _showMessage('WebDAV 连接测试通过');
    });
  }

  Future<void> _scanPairing() async {
    final pairing = await showMobileSyncPairingScanner(context);
    if (!mounted || pairing == null) return;
    setState(() {
      _joining = true;
      _url.text = pairing.baseUrl;
      _username.text = pairing.username;
      _recovery.text = pairing.recoveryCode;
      _error = null;
      _errorCanReload = false;
      _connectionTestPassed = false;
    });
    _showMessage('已读取配对信息，请输入 WebDAV 应用密码');
  }

  Future<void> _pastePairing() async {
    try {
      final data = await Clipboard.getData(Clipboard.kTextPlain);
      final raw = data?.text?.trim() ?? '';
      if (raw.isEmpty) throw const MobileSyncPairingException('剪贴板没有配对链接');
      final pairing = MobileSyncPairing.parse(raw);
      await _clearClipboardIfMatches(raw);
      if (!mounted) return;
      setState(() {
        _joining = true;
        _url.text = pairing.baseUrl;
        _username.text = pairing.username;
        _recovery.text = pairing.recoveryCode;
        _error = null;
        _errorCanReload = false;
        _connectionTestPassed = false;
      });
      _showMessage('已读取配对信息，请输入 WebDAV 应用密码');
    } on MobileSyncPairingException catch (error) {
      _reportError(error.message);
    } catch (_) {
      _reportError('读取剪贴板失败，请手动粘贴恢复码');
    }
  }

  Future<void> _clearClipboardIfMatches(String value) async {
    try {
      final current = await Clipboard.getData(Clipboard.kTextPlain);
      if (current?.text?.trim() == value.trim()) {
        await Clipboard.setData(const ClipboardData(text: ''));
      }
    } catch (_) {
      // 剪贴板清理失败不影响配对流程，表单仍不会持久化链接。
    }
  }

  void _setJoining(bool value) {
    setState(() {
      _joining = value;
      _error = null;
      _errorCanReload = false;
      _connectionTestPassed = false;
      if (!value) {
        _recovery.clear();
        _mergeExisting = false;
      }
    });
  }

  Future<void> _copyRecoveryCode() async {
    final code = _recoveryCode;
    if (code == null || code.isEmpty) return;
    await copySensitiveValue(ref, code);
    _showMessage('恢复码已复制，将按剪贴板设置自动清理');
  }

  Future<void> _copyPairingUri() async {
    final code = _recoveryCode;
    final status = _status;
    if (code == null || status == null || !status.configured) return;
    try {
      final connection = await _coordinator.connection();
      final pairing = MobileSyncPairing(
        baseUrl: connection.baseUrl,
        username: connection.username,
        recoveryCode: code,
      );
      await copySensitiveValue(ref, pairing.uri.toString());
      _showMessage('配对链接已复制，将按剪贴板设置自动清理');
    } catch (error) {
      _reportError(mobileErrorMessage(error));
    }
  }

  Future<void> _syncNow() async {
    await _run(() async {
      final result = await _coordinator.run();
      if (!mounted) return;
      setState(() {
        _conflict = result.conflictSession;
        _resolutions = {};
      });
      if (result.hasConflicts) {
        ref
            .read(mobileSyncAutoStateProvider.notifier)
            .failure('请完成当前冲突选择。', conflict: true);
      } else {
        ref.read(mobileSyncAutoStateProvider.notifier).success(result.message);
      }
      var refreshed = true;
      if (result.conflictSession == null &&
          (result.action == 'downloaded' || result.action == 'merged')) {
        refreshed = await _refreshVaultSafely();
      }
      refreshed = await _load(showError: false) && refreshed;
      _showMessage(mobileSyncResultMessage(result.message, refreshed));
    });
  }

  Future<void> _resolve() async {
    final conflict = _conflict;
    if (conflict == null ||
        conflict.conflicts.any(
          (item) => !_resolutions.containsKey(item.conflictId),
        )) {
      return;
    }
    await _run(() async {
      final result = await conflict.resolve(_resolutions);
      if (!mounted) return;
      setState(() {
        _conflict = result.conflictSession;
        _resolutions = {};
      });
      if (result.hasConflicts) {
        ref
            .read(mobileSyncAutoStateProvider.notifier)
            .failure('请继续处理剩余冲突。', conflict: true);
      } else {
        ref.read(mobileSyncAutoStateProvider.notifier).success(result.message);
      }
      if (result.conflictSession == null) {
        final refreshed = await _refreshAfterMutation(refreshVault: true);
        _showMessage(mobileSyncResultMessage(result.message, refreshed));
      } else {
        final loaded = await _load(showError: false);
        if (!loaded) {
          _showMessage('冲突已保存，但状态刷新不完整，请重新读取。');
        }
      }
    });
  }

  Future<void> _disconnect() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('断开本机同步'),
        content: const Text('只清除本机保存的同步设置，不删除 WebDAV 上的加密快照。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('断开'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await _run(() async {
      final status = await _coordinator.disconnect();
      if (mounted) {
        setState(() {
          _status = status;
          _recoveryCode = null;
          _url.clear();
          _username.clear();
          _password.clear();
          _recovery.clear();
          _device.clear();
          _joining = false;
          _mergeExisting = false;
          _autoSync = true;
        });
        _showMessage('已断开本机同步');
      }
    });
  }

  Future<void> _compactHistory() async {
    final input = await promptSyncDangerConfirmation(
      context,
      title: '压缩并清理同步历史',
      message: '将创建新的根快照并清理旧历史，其他设备需要使用新恢复码重新加入。',
      confirmation: 'COMPACT',
    );
    if (input == null) return;
    await _run(() async {
      final result = await _coordinator.compactHistory(
        password: input.password,
      );
      var refreshed = true;
      String? code;
      rust_models.SyncStatus? status;
      try {
        code = await _coordinator.recoveryCode(input.password);
      } catch (_) {
        refreshed = false;
      }
      try {
        status = await _coordinator.status();
      } catch (_) {
        refreshed = false;
      }
      if (!mounted) return;
      setState(() {
        if (status != null) _status = status;
        _recoveryCode = code;
      });
      _showMessage(mobileSyncResultMessage(result.message, refreshed));
    });
  }

  Future<void> _showRecoveryCode() async {
    final password = await promptSyncMasterPassword(
      context,
      title: '显示恢复码',
      message: '恢复码可解密整个同步空间，请验证当前主密码。',
    );
    if (password == null) return;
    await _run(() async {
      final code = await _coordinator.recoveryCode(password);
      if (mounted) setState(() => _recoveryCode = code);
    });
  }

  Future<void> _editConfig() async {
    rust_models.SyncConnection? connection;
    await _run(() async => connection = await _coordinator.connection());
    if (!mounted || connection == null) return;
    final draft = await showMobileSyncConfigEditor(
      context,
      connection: connection!,
      autoSync: _status?.autoSync ?? true,
    );
    if (draft == null) return;
    await _run(() async {
      final status = await _coordinator.updateConfig(
        baseUrl: draft.baseUrl,
        username: draft.username,
        password: draft.password,
        deviceName: draft.deviceName,
        autoSync: draft.autoSync,
      );
      if (!mounted) return;
      setState(() {
        _status = status;
        _autoSync = status.autoSync;
      });
      ref.read(mobileSyncAutoStateProvider.notifier).reset();
      _showMessage('同步设置已保存');
    });
  }

  Future<void> _showHistory() async {
    List<MobileSyncHistoryItem>? items;
    await _run(() async => items = await _coordinator.history());
    if (!mounted || items == null) return;
    final snapshotId = await showMobileSyncHistoryPicker(context, items!);
    if (!mounted || snapshotId == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('恢复历史版本'),
        content: const Text('所选版本会作为新的最新快照发布，现有历史不会被改写。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('恢复'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await _run(() async {
      final result = await _coordinator.restore(snapshotId);
      final refreshed = await _refreshAfterMutation(refreshVault: true);
      _showMessage(mobileSyncResultMessage(result.message, refreshed));
    });
  }

  Future<void> _rotateKey() async {
    final input = await promptSyncDangerConfirmation(
      context,
      title: '轮换同步密钥',
      message: '将创建使用新密钥的同步空间，其他设备需要使用新恢复码重新加入。',
      confirmation: 'ROTATE',
    );
    if (input == null) return;
    await _run(() async {
      final result = await _coordinator.rotateKey(password: input.password);
      var refreshed = true;
      String? code;
      rust_models.SyncStatus? status;
      try {
        code = await _coordinator.recoveryCode(input.password);
      } catch (_) {
        refreshed = false;
      }
      try {
        status = await _coordinator.status();
      } catch (_) {
        refreshed = false;
      }
      if (!mounted) return;
      setState(() {
        if (status != null) _status = status;
        _recoveryCode = code;
      });
      _showMessage(mobileSyncResultMessage(result.message, refreshed));
    });
  }

  Future<void> _deleteRemote() async {
    final input = await promptSyncDangerConfirmation(
      context,
      title: '删除远端同步数据',
      message: '将删除当前 WebDAV 同步空间中的加密快照，本机密码库不会删除。',
      confirmation: 'DELETE',
    );
    if (input == null) return;
    await _run(() async {
      final status = await _coordinator.deleteRemote(password: input.password);
      if (!mounted) return;
      setState(() {
        _status = status;
        _recoveryCode = null;
        _url.clear();
        _username.clear();
        _password.clear();
        _recovery.clear();
        _device.clear();
        _joining = false;
        _mergeExisting = false;
        _autoSync = true;
      });
      ref.read(mobileSyncAutoStateProvider.notifier).reset();
      _showMessage('远端同步数据已删除');
    });
  }

  Future<bool> _refreshVaultSafely() async {
    try {
      await ref.read(vaultControllerProvider.notifier).refreshStatus();
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<bool> _refreshAfterMutation({bool refreshVault = false}) async {
    var refreshed = true;
    if (refreshVault) refreshed = await _refreshVaultSafely();
    final loaded = await _load(showError: false);
    return refreshed && loaded;
  }

  bool _validateSetup({bool requireRecovery = false}) {
    return validateAndReportMobileSyncSetup(
      baseUrl: _url.text,
      username: _username.text,
      password: _password.text,
      recoveryCode: _recovery.text,
      requireRecovery: requireRecovery,
      onError: _reportError,
    );
  }

  void _handleMoreAction(String value) {
    if (value == 'disconnect') _disconnect();
    if (value == 'compact') _compactHistory();
    if (value == 'rotate') _rotateKey();
    if (value == 'delete') _deleteRemote();
  }

  void _reportError(String message, {bool canReload = false}) {
    if (!mounted || message.isEmpty) return;
    setState(() {
      _error = message;
      _errorCanReload = canReload;
      _connectionTestPassed = false;
    });
    showMobileSyncError(context, message);
  }

  void _showMessage(String message) => showMobileSyncMessage(context, message);

  Future<void> _run(Future<void> Function() operation) async {
    if (!mounted || _working) return;
    setState(() {
      _working = true;
      _error = null;
      _errorCanReload = false;
    });
    try {
      await operation();
    } on MobileWebDavException catch (error) {
      _reportError(error.message);
    } catch (error) {
      _reportError(mobileErrorMessage(error));
    } finally {
      _password.clear();
      if (mounted) setState(() => _working = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(vaultControllerProvider, (previous, next) {
      if (previous?.phase == VaultPhase.unlocked &&
          next.phase != VaultPhase.unlocked) {
        _clearSensitiveState();
        WidgetsBinding.instance.addPostFrameCallback((_) {
          _closeDialogsAfterLock();
        });
      }
    });
    return DialogFrame(
      title: '加密快照同步',
      canClose: !_working,
      child: _loading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: _body(context),
            ),
    );
  }

  Widget _body(BuildContext context) {
    if (_conflict != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_error != null) ...[
            MobileSyncErrorPanel(
              message: _error!,
              canReload: _errorCanReload,
              working: _working,
              onReload: _reloadStatus,
            ),
            const SizedBox(height: 12),
          ],
          _conflictView(),
        ],
      );
    }
    if (_status?.configured == true) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_error != null) ...[
            MobileSyncErrorPanel(
              message: _error!,
              canReload: _errorCanReload,
              working: _working,
              onReload: _reloadStatus,
            ),
            const SizedBox(height: 12),
          ],
          _configuredView(),
        ],
      );
    }
    return _setupForm();
  }

  Widget _setupForm() {
    return MobileSyncSetupForm(
      url: _url,
      username: _username,
      password: _password,
      recovery: _recovery,
      device: _device,
      joining: _joining,
      working: _working,
      mergeExisting: _mergeExisting,
      autoSync: _autoSync,
      onJoiningChanged: _setJoining,
      onMergeChanged: (value) => setState(() => _mergeExisting = value),
      onAutoSyncChanged: (value) => setState(() => _autoSync = value),
      onScanPairing: _scanPairing,
      onPastePairing: _pastePairing,
      onTestConnection: _testConnection,
      onSubmit: _joining ? _join : _create,
      errorMessage: _error,
      connectionTestPassed: _connectionTestPassed,
      onReload: _errorCanReload ? _reloadStatus : null,
      onInputChanged: () {
        if (_error != null || _connectionTestPassed) {
          setState(() {
            _error = null;
            _errorCanReload = false;
            _connectionTestPassed = false;
          });
        }
      },
    );
  }

  Widget _configuredView() {
    final status = _status;
    if (status == null) return const SizedBox.shrink();
    return MobileSyncConfiguredView(
      status: status,
      automatic: ref.watch(mobileSyncAutoStateProvider),
      recoveryCode: _recoveryCode,
      working: _working,
      onSync: _syncNow,
      onShowRecovery: _showRecoveryCode,
      onShowHistory: _showHistory,
      onEditConfig: _editConfig,
      onCopyRecovery: _copyRecoveryCode,
      onCopyPairing: _copyPairingUri,
      onMoreAction: _handleMoreAction,
    );
  }

  Widget _conflictView() {
    final conflict = _conflict;
    if (conflict == null) return const SizedBox.shrink();
    return MobileSyncConflictView(
      conflict: conflict,
      resolutions: _resolutions,
      working: _working,
      onResolutionChanged: (id, value) {
        setState(() {
          _resolutions[id] = value;
          _error = null;
        });
      },
      onResolve: _resolve,
    );
  }

  void _clearSensitiveState() {
    if (!mounted) return;
    MobileWebDavClient.cancelAll();
    unawaited(_coordinator.cancelPending().onError((_, _) {}));
    setState(() {
      _password.clear();
      _recovery.clear();
      _url.clear();
      _username.clear();
      _device.clear();
      _recoveryCode = null;
      _error = null;
      _errorCanReload = false;
      _connectionTestPassed = false;
      _conflict = null;
      _resolutions = {};
      _working = false;
      _joining = false;
      _mergeExisting = false;
      _autoSync = true;
    });
  }

  Future<void> _closeDialogsAfterLock() async {
    if (!mounted) return;
    final navigator = Navigator.of(context);
    if (navigator.canPop()) navigator.pop();
    await Future<void>.delayed(Duration.zero);
    if (mounted && navigator.canPop()) navigator.pop();
  }
}
