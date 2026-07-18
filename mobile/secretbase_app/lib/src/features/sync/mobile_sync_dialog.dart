import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';
import 'package:secretbase/src/features/sync/mobile_sync_auto.dart';
import 'package:secretbase/src/features/sync/mobile_sync_management_dialogs.dart';
import 'package:secretbase/src/features/sync/mobile_sync_service.dart';
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

  Future<void> _load() async {
    try {
      final status = await _coordinator.status();
      final connection = status.configured
          ? await _coordinator.connection()
          : null;
      if (!mounted) return;
      setState(() {
        _status = status;
        _autoSync = status.autoSync;
        if (connection != null) {
          _url.text = connection.baseUrl;
          _username.text = connection.username;
          _device.text = connection.deviceName;
        }
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = mobileErrorMessage(error);
        _loading = false;
      });
    }
  }

  Future<void> _create() async {
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
        _conflict = result.conflictSession;
        _resolutions = {};
      });
      if (result.conflictSession == null) {
        await _refreshVault();
        await _load();
        _showMessage(result.message);
      }
    });
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
      if (result.conflictSession == null &&
          (result.action == 'downloaded' || result.action == 'merged')) {
        await _refreshVault();
      }
      await _load();
      _showMessage(result.message);
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
        await _refreshVault();
        await _load();
        _showMessage(result.message);
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
        });
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
      final code = await _coordinator.recoveryCode(input.password);
      final status = await _coordinator.status();
      if (!mounted) return;
      setState(() {
        _status = status;
        _recoveryCode = code;
      });
      _showMessage(result.message);
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
      await _refreshVault();
      await _load();
      _showMessage(result.message);
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
      final code = await _coordinator.recoveryCode(input.password);
      final status = await _coordinator.status();
      if (!mounted) return;
      setState(() {
        _status = status;
        _recoveryCode = code;
      });
      _showMessage(result.message);
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
      });
      ref.read(mobileSyncAutoStateProvider.notifier).reset();
      _showMessage('远端同步数据已删除');
    });
  }

  Future<void> _refreshVault() =>
      ref.read(vaultControllerProvider.notifier).refreshStatus();

  void _showMessage(String message) {
    if (!mounted || message.isEmpty) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _run(Future<void> Function() operation) async {
    if (_working) return;
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      await operation();
    } on MobileWebDavException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (error) {
      if (mounted) setState(() => _error = mobileErrorMessage(error));
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  @override
  Widget build(BuildContext context) {
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
    if (_error != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _errorPanel(_error!),
          const SizedBox(height: 12),
          if (_status?.configured != true)
            _setupForm(context)
          else
            _configuredView(context),
        ],
      );
    }
    if (_conflict != null) return _conflictView(context);
    return _status?.configured == true
        ? _configuredView(context)
        : _setupForm(context);
  }

  Widget _setupForm(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SegmentedButton<bool>(
          segments: const [
            ButtonSegment(
              value: false,
              label: Text('创建空间'),
              icon: Icon(Icons.add_link_outlined),
            ),
            ButtonSegment(
              value: true,
              label: Text('加入空间'),
              icon: Icon(Icons.login_outlined),
            ),
          ],
          selected: {_joining},
          onSelectionChanged: _working
              ? null
              : (value) => setState(() => _joining = value.first),
        ),
        const SizedBox(height: 14),
        _field(_url, 'WebDAV 地址', 'https://dav.example/secretbase'),
        _field(_username, '用户名', 'WebDAV 用户名'),
        _field(_password, '应用密码', '不会上传到 AI 或写入界面偏好', obscure: true),
        _field(_device, '设备名称', '例如：我的 Android 手机'),
        if (_joining) ...[
          _field(_recovery, 'SBSYNC2 恢复码', '从已配置设备复制', maxLines: 3),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            dense: true,
            value: _mergeExisting,
            onChanged: _working
                ? null
                : (value) => setState(() => _mergeExisting = value ?? false),
            title: const Text('当前 Vault 有数据时尝试合并'),
          ),
        ],
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          dense: true,
          value: _autoSync,
          onChanged: _working
              ? null
              : (value) => setState(() => _autoSync = value),
          title: const Text('自动同步'),
        ),
        const SizedBox(height: 8),
        Text(
          '使用不可变加密快照，不要求 WebDAV 提供 ETag；密码字段和值不会以明文上传。',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 14),
        FilledButton.icon(
          onPressed: _working ? null : (_joining ? _join : _create),
          icon: Icon(_joining ? Icons.login : Icons.cloud_upload_outlined),
          label: Text(
            _working
                ? '处理中...'
                : _joining
                ? '加入并同步'
                : '创建并上传',
          ),
        ),
      ],
    );
  }

  Widget _configuredView(BuildContext context) {
    final status = _status;
    final automatic = ref.watch(mobileSyncAutoStateProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (status != null) ...[
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: automatic.running
                ? const SizedBox.square(
                    dimension: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Icon(
                    automatic.conflict || automatic.lastError.isNotEmpty
                        ? Icons.cloud_off_outlined
                        : Icons.cloud_done_outlined,
                  ),
            title: Text(status.phase == 'error' ? '同步异常' : '已配置快照同步'),
            subtitle: Text(
              '${status.baseUrl}\n${status.usernameMask} · 第 ${status.generation} 代 · '
              '${status.frontier.length} 个分支 · ${status.autoSync ? '自动' : '手动'}',
            ),
          ),
          if (automatic.lastError.isNotEmpty) ...[
            Material(
              color: Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Text(automatic.lastError),
              ),
            ),
            const SizedBox(height: 10),
          ],
          const Divider(),
        ],
        if (_recoveryCode != null) ...[
          const Text('新设备恢复码', style: TextStyle(fontWeight: FontWeight.w700)),
          SelectableText(
            _recoveryCode!,
            style: const TextStyle(fontFamily: 'monospace'),
          ),
          const SizedBox(height: 10),
        ],
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            FilledButton.icon(
              onPressed: _working ? null : _syncNow,
              icon: const Icon(Icons.sync),
              label: const Text('立即同步'),
            ),
            OutlinedButton.icon(
              onPressed: _working ? null : _showRecoveryCode,
              icon: const Icon(Icons.key_outlined),
              label: const Text('恢复码'),
            ),
            OutlinedButton.icon(
              onPressed: _working ? null : _showHistory,
              icon: const Icon(Icons.history),
              label: const Text('历史'),
            ),
            OutlinedButton.icon(
              onPressed: _working ? null : _editConfig,
              icon: const Icon(Icons.tune),
              label: const Text('设置'),
            ),
            PopupMenuButton<String>(
              enabled: !_working,
              tooltip: '更多同步操作',
              icon: const Icon(Icons.more_horiz),
              onSelected: (value) {
                switch (value) {
                  case 'disconnect':
                    _disconnect();
                  case 'compact':
                    _compactHistory();
                  case 'rotate':
                    _rotateKey();
                  case 'delete':
                    _deleteRemote();
                }
              },
              itemBuilder: (context) => const [
                PopupMenuItem(
                  value: 'disconnect',
                  child: ListTile(
                    leading: Icon(Icons.link_off),
                    title: Text('断开本机'),
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
                PopupMenuItem(
                  value: 'compact',
                  child: ListTile(
                    leading: Icon(Icons.cleaning_services_outlined),
                    title: Text('压缩历史'),
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
                PopupMenuItem(
                  value: 'rotate',
                  child: ListTile(
                    leading: Icon(Icons.vpn_key_outlined),
                    title: Text('轮换密钥'),
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
                PopupMenuItem(
                  value: 'delete',
                  child: ListTile(
                    leading: Icon(Icons.delete_forever_outlined),
                    title: Text('删除远端数据'),
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
              ],
            ),
          ],
        ),
      ],
    );
  }

  Widget _conflictView(BuildContext context) {
    final conflict = _conflict!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text('需要处理同步冲突', style: TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        const Text('这里只显示标题、状态和变化区块，不显示字段值。'),
        const SizedBox(height: 10),
        for (final item in conflict.conflicts) ...[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    item.label,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  Text(
                    item.changedSections.join('、'),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 6),
                  DropdownButtonFormField<String>(
                    initialValue: _resolutions[item.conflictId],
                    decoration: const InputDecoration(
                      labelText: '处理方式',
                      isDense: true,
                    ),
                    items: [
                      const DropdownMenuItem(
                        value: 'local',
                        child: Text('保留本机'),
                      ),
                      const DropdownMenuItem(
                        value: 'remote',
                        child: Text('保留远端'),
                      ),
                      if (item.allowBoth)
                        const DropdownMenuItem(
                          value: 'both',
                          child: Text('保留两份'),
                        ),
                    ],
                    onChanged: _working
                        ? null
                        : (value) => setState(
                            () => _resolutions[item.conflictId] = value ?? '',
                          ),
                  ),
                ],
              ),
            ),
          ),
        ],
        const SizedBox(height: 8),
        FilledButton(
          onPressed:
              _working ||
                  conflict.conflicts.any(
                    (item) => !_resolutions.containsKey(item.conflictId),
                  )
              ? null
              : _resolve,
          child: Text(_working ? '应用中...' : '应用选择'),
        ),
      ],
    );
  }

  Widget _field(
    TextEditingController controller,
    String label,
    String hint, {
    bool obscure = false,
    int maxLines = 1,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextField(
        controller: controller,
        obscureText: obscure,
        maxLines: obscure ? 1 : maxLines,
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          border: const OutlineInputBorder(),
          isDense: true,
        ),
      ),
    );
  }

  Widget _errorPanel(String message) => Material(
    color: Theme.of(context).colorScheme.errorContainer,
    child: Padding(padding: const EdgeInsets.all(10), child: Text(message)),
  );
}
