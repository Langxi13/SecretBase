import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:secretbase/src/core/autofill_service.dart';
import 'package:secretbase/src/core/biometric_unlock.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/theme/app_theme.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/core/widgets/mobile_chrome.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/settings/transfer_service.dart';
import 'package:secretbase/src/features/settings/autofill_settings_dialog.dart';
import 'package:secretbase/src/features/update/mobile_update_controller.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/error.dart';
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/preferences_controller.dart';
import 'package:secretbase/src/state/vault_controller.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  bool _working = false;

  @override
  Widget build(BuildContext context) {
    final preferences = ref.watch(preferencesProvider);
    final vault = ref.watch(vaultControllerProvider);
    final biometric = ref.watch(biometricStatusProvider);
    final autofill = ref.watch(autofillStatusProvider);
    final update = ref.watch(mobileUpdateControllerProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        MobilePageHeader(
          title: '设置',
          subtitle: '外观、安全与本机数据',
          actions: [
            IconButton.outlined(
              tooltip: '立即锁定',
              onPressed: _working ? null : _lock,
              icon: const Icon(Icons.lock_outline),
            ),
          ],
        ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 76),
            children: [
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 920),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _VaultSummary(status: vault.status),
                      const SizedBox(height: 10),
                      _SettingsSection(
                        title: '外观',
                        icon: Icons.palette_outlined,
                        children: [
                          Padding(
                            padding: const EdgeInsets.fromLTRB(16, 6, 16, 14),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text('主题模式'),
                                const SizedBox(height: 10),
                                SegmentedButton<ThemeMode>(
                                  showSelectedIcon: false,
                                  expandedInsets: EdgeInsets.zero,
                                  segments: const [
                                    ButtonSegment(
                                      value: ThemeMode.system,
                                      icon: Icon(
                                        Icons.brightness_auto_outlined,
                                      ),
                                      label: Text('跟随系统'),
                                    ),
                                    ButtonSegment(
                                      value: ThemeMode.light,
                                      icon: Icon(Icons.light_mode_outlined),
                                      label: Text('浅色'),
                                    ),
                                    ButtonSegment(
                                      value: ThemeMode.dark,
                                      icon: Icon(Icons.dark_mode_outlined),
                                      label: Text('深色'),
                                    ),
                                  ],
                                  selected: {preferences.themeMode},
                                  onSelectionChanged: (values) => ref
                                      .read(preferencesProvider.notifier)
                                      .setThemeMode(values.first),
                                ),
                                const Divider(height: 28),
                                const Text('字体大小'),
                                const SizedBox(height: 10),
                                SegmentedButton<AppTextSize>(
                                  showSelectedIcon: false,
                                  expandedInsets: EdgeInsets.zero,
                                  segments: const [
                                    ButtonSegment(
                                      value: AppTextSize.standard,
                                      icon: Icon(Icons.text_fields),
                                      label: Text('标准'),
                                    ),
                                    ButtonSegment(
                                      value: AppTextSize.large,
                                      icon: Icon(Icons.format_size),
                                      label: Text('大字体'),
                                    ),
                                  ],
                                  selected: {preferences.textSize},
                                  onSelectionChanged: (values) => ref
                                      .read(preferencesProvider.notifier)
                                      .setTextSize(values.first),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      _SettingsSection(
                        title: '安全',
                        icon: Icons.security_outlined,
                        children: [
                          ListTile(
                            leading: const Icon(Icons.content_copy_outlined),
                            title: const Text('剪贴板自动清理'),
                            trailing: DropdownButton<int>(
                              value: preferences.clipboardClearSeconds,
                              underline: const SizedBox.shrink(),
                              items: const [15, 30, 60, 120]
                                  .map(
                                    (seconds) => DropdownMenuItem(
                                      value: seconds,
                                      child: Text('$seconds 秒'),
                                    ),
                                  )
                                  .toList(),
                              onChanged: (value) {
                                if (value != null) {
                                  ref
                                      .read(preferencesProvider.notifier)
                                      .setClipboardClearSeconds(value);
                                }
                              },
                            ),
                          ),
                          const Divider(height: 1, indent: 56),
                          ListTile(
                            leading: const Icon(Icons.fingerprint),
                            title: const Text('指纹解锁'),
                            subtitle: Text(_biometricSubtitle(biometric)),
                            trailing: Switch(
                              value: biometric.value?.credentialStored ?? false,
                              onChanged:
                                  _working ||
                                      biometric.isLoading ||
                                      biometric.value?.enrolled != true
                                  ? null
                                  : (value) => value
                                        ? _enableBiometric()
                                        : _disableBiometric(),
                            ),
                          ),
                          const Divider(height: 1, indent: 56),
                          ListTile(
                            leading: const Icon(Icons.password_outlined),
                            title: const Text('系统自动填充'),
                            subtitle: Text(
                              autofill.when(
                                loading: () => '正在读取系统状态',
                                error: (error, stackTrace) => '无法读取系统状态',
                                data: (status) => status.supported
                                    ? status.enabled
                                          ? '已启用 · 本机验证后填充'
                                          : '尚未设为系统自动填充服务'
                                    : '当前系统不支持',
                              ),
                            ),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () async {
                              await showAutofillSettingsDialog(
                                context: context,
                              );
                              ref.invalidate(autofillStatusProvider);
                            },
                          ),
                          const Divider(height: 1, indent: 56),
                          ListTile(
                            leading: const Icon(Icons.password),
                            title: const Text('修改主密码'),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: _working ? null : _changePassword,
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      _SettingsSection(
                        title: '数据',
                        icon: Icons.storage_outlined,
                        children: [
                          ListTile(
                            leading: const Icon(Icons.file_upload_outlined),
                            title: const Text('导出加密备份'),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: _working ? null : _export,
                          ),
                          const Divider(height: 1, indent: 56),
                          ListTile(
                            leading: const Icon(Icons.file_download_outlined),
                            title: const Text('导入加密备份'),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: _working ? null : _import,
                          ),
                          const Divider(height: 1, indent: 56),
                          ListTile(
                            leading: const Icon(Icons.history_outlined),
                            title: const Text('本机恢复记录'),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: _working ? null : _showRecovery,
                          ),
                          const Divider(height: 1, indent: 56),
                          ListTile(
                            leading: const Icon(Icons.delete_outline),
                            title: const Text('回收站'),
                            trailing: Text(
                              '${vault.status?.deletedCount ?? 0} 条',
                            ),
                            onTap: () => context.push('/trash'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      _SettingsSection(
                        title: '版本更新',
                        icon: Icons.system_update_outlined,
                        children: [
                          ListTile(
                            leading: const Icon(Icons.info_outline),
                            title: Text('当前版本 ${_currentVersion(update)}'),
                            subtitle: Text(_updateStatusText(update)),
                            trailing: update.phase == MobileUpdatePhase.checking
                                ? const SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  )
                                : null,
                          ),
                          const Divider(height: 1, indent: 56),
                          SwitchListTile(
                            secondary: const Icon(Icons.sync_outlined),
                            title: const Text('自动检查更新'),
                            subtitle: const Text('每天检查一次稳定版本'),
                            value: preferences.updateAutoCheck,
                            onChanged: (value) => ref
                                .read(preferencesProvider.notifier)
                                .setUpdateAutoCheck(value),
                          ),
                          const Divider(height: 1, indent: 56),
                          SwitchListTile(
                            secondary: const Icon(Icons.download_outlined),
                            title: const Text('自动预下载'),
                            subtitle: const Text('默认仅在 Wi-Fi 下自动下载'),
                            value: preferences.updateAutoDownload,
                            onChanged: (value) => ref
                                .read(preferencesProvider.notifier)
                                .setUpdateAutoDownload(value),
                          ),
                          const Divider(height: 1, indent: 56),
                          SwitchListTile(
                            secondary: const Icon(Icons.network_cell_outlined),
                            title: const Text('允许移动网络自动下载'),
                            subtitle: const Text('可能产生数据流量'),
                            value: preferences.updateAllowMeteredDownload,
                            onChanged: preferences.updateAutoDownload
                                ? (value) => ref
                                      .read(preferencesProvider.notifier)
                                      .setUpdateAllowMeteredDownload(value)
                                : null,
                          ),
                          if (update.phase == MobileUpdatePhase.downloading)
                            Padding(
                              padding: const EdgeInsets.fromLTRB(16, 10, 16, 2),
                              child: LinearProgressIndicator(
                                value: update.progress / 100,
                              ),
                            ),
                          if (update.message.isNotEmpty)
                            Padding(
                              padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
                              child: Text(
                                update.message,
                                style: Theme.of(context).textTheme.bodySmall
                                    ?.copyWith(
                                      color: Theme.of(
                                        context,
                                      ).colorScheme.onSurfaceVariant,
                                    ),
                              ),
                            ),
                          Padding(
                            padding: const EdgeInsets.fromLTRB(16, 12, 16, 14),
                            child: Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              alignment: WrapAlignment.end,
                              children: [
                                OutlinedButton.icon(
                                  onPressed: update.busy
                                      ? null
                                      : () => ref
                                            .read(
                                              mobileUpdateControllerProvider
                                                  .notifier,
                                            )
                                            .check(),
                                  icon: const Icon(Icons.refresh, size: 18),
                                  label: const Text('检查更新'),
                                ),
                                if (update.phase == MobileUpdatePhase.available)
                                  FilledButton.icon(
                                    onPressed: ref
                                        .read(
                                          mobileUpdateControllerProvider
                                              .notifier,
                                        )
                                        .download,
                                    icon: const Icon(
                                      Icons.download_outlined,
                                      size: 18,
                                    ),
                                    label: const Text('下载更新'),
                                  ),
                                if (update.phase ==
                                    MobileUpdatePhase.downloading)
                                  OutlinedButton.icon(
                                    onPressed: ref
                                        .read(
                                          mobileUpdateControllerProvider
                                              .notifier,
                                        )
                                        .cancelDownload,
                                    icon: const Icon(Icons.close, size: 18),
                                    label: const Text('取消下载'),
                                  ),
                                if (update.phase == MobileUpdatePhase.ready)
                                  FilledButton.icon(
                                    onPressed: _confirmInstallUpdate,
                                    icon: const Icon(
                                      Icons.system_update_alt,
                                      size: 18,
                                    ),
                                    label: const Text('安装更新'),
                                  ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      _SettingsSection(
                        title: '关于',
                        icon: Icons.info_outline,
                        children: [
                          ListTile(
                            leading: const Icon(Icons.shield_outlined),
                            title: const Text('SecretBase Android'),
                            subtitle: Text(
                              '版本 ${_currentVersion(update)} · Vault V1',
                            ),
                          ),
                          const Divider(height: 1, indent: 56),
                          const ListTile(
                            leading: Icon(Icons.phonelink_lock_outlined),
                            title: Text('本机私有存储'),
                            subtitle: Text('系统备份已关闭'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
        if (_working) const LinearProgressIndicator(minHeight: 2),
      ],
    );
  }

  Future<void> _lock() async {
    if (_working) return;
    setState(() => _working = true);
    try {
      await ref.read(vaultControllerProvider.notifier).lock();
      if (mounted) context.go('/');
    } catch (error) {
      if (mounted) _showMessage(mobileErrorMessage(error));
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _export() => _run(() => exportVaultBackup());

  Future<void> _import() => _run(
    () => importVaultBackup(context: context, ref: ref),
    transferErrors: true,
  );

  Future<void> _run(
    Future<String?> Function() operation, {
    bool transferErrors = false,
  }) async {
    if (_working) return;
    setState(() => _working = true);
    try {
      final message = await operation();
      if (message != null && mounted) _showMessage(message);
    } catch (error) {
      if (mounted) {
        _showMessage(
          transferErrors
              ? transferErrorMessage(error)
              : mobileErrorMessage(error),
        );
      }
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _changePassword() async {
    final first = TextEditingController();
    final second = TextEditingController();
    final formKey = GlobalKey<FormState>();
    final password = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('修改主密码'),
        content: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: first,
                autofocus: true,
                obscureText: true,
                decoration: const InputDecoration(labelText: '新主密码'),
                validator: (value) => (value ?? '').characters.length < 8
                    ? '主密码至少需要 8 个字符'
                    : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: second,
                obscureText: true,
                decoration: const InputDecoration(labelText: '确认新主密码'),
                validator: (value) => value == first.text ? null : '两次输入不一致',
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () {
              if (formKey.currentState?.validate() ?? false) {
                Navigator.of(context).pop(first.text);
              }
            },
            child: const Text('确认修改'),
          ),
        ],
      ),
    );
    first.dispose();
    second.dispose();
    if (password == null) return;
    await _run(() async {
      final result = await rust_api.changePassword(
        newPassword: password,
        expectedRevision: ref.read(vaultControllerProvider).revision,
      );
      try {
        await ref.read(biometricPlatformProvider).deleteCredential();
      } catch (_) {
        // The rekeyed Vault salt also makes any stale device credential unusable.
      }
      ref.invalidate(biometricStatusProvider);
      await ref.read(vaultControllerProvider.notifier).refreshStatus();
      return '${result.message}；请按需重新开启指纹解锁';
    });
  }

  String _biometricSubtitle(AsyncValue<BiometricStatus> value) {
    return value.when(
      loading: () => '正在检查设备能力',
      error: (error, stackTrace) => '无法读取生物识别状态',
      data: (status) {
        if (!status.supported) return '当前设备不支持强生物识别';
        if (!status.enrolled) return '请先在系统设置中录入指纹';
        if (!status.credentialStored) return '使用 Android Keystore 保护本机解锁密钥';
        return status.hardwareBacked
            ? '已开启 · 安全硬件保护'
            : '已开启 · Android Keystore 保护';
      },
    );
  }

  Future<void> _enableBiometric() async {
    if (_working) return;
    final password = await _requestCurrentMasterPassword();
    if (password == null || password.isEmpty || !mounted) return;
    setState(() => _working = true);
    Uint8List? credential;
    try {
      credential = await rust_api.prepareDeviceUnlockCredential(
        password: password,
      );
      await ref.read(biometricPlatformProvider).storeCredential(credential);
      ref.invalidate(biometricStatusProvider);
      if (mounted) _showMessage('指纹解锁已开启');
    } catch (error) {
      if (error is BiometricException && error.canceled) return;
      if (mounted) {
        _showMessage(
          error is MobileError_Failure
              ? mobileUnlockErrorMessage(error)
              : biometricErrorMessage(error),
        );
      }
    } finally {
      if (credential != null) clearSensitiveBytes(credential);
      if (mounted) setState(() => _working = false);
    }
  }

  Future<void> _disableBiometric() async {
    if (_working) return;
    setState(() => _working = true);
    try {
      await ref.read(biometricPlatformProvider).deleteCredential();
      ref.invalidate(biometricStatusProvider);
      if (mounted) _showMessage('指纹解锁已关闭');
    } catch (error) {
      if (mounted) _showMessage(biometricErrorMessage(error));
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  Future<String?> _requestCurrentMasterPassword() async {
    final controller = TextEditingController();
    var obscure = true;
    final password = await showDialog<String>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('开启指纹解锁'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('请先验证当前主密码。SecretBase 不会保存主密码。'),
              const SizedBox(height: 14),
              TextField(
                controller: controller,
                autofocus: true,
                obscureText: obscure,
                decoration: InputDecoration(
                  labelText: '当前主密码',
                  prefixIcon: const Icon(Icons.lock_outline),
                  suffixIcon: IconButton(
                    tooltip: obscure ? '显示主密码' : '隐藏主密码',
                    onPressed: () => setDialogState(() => obscure = !obscure),
                    icon: Icon(
                      obscure
                          ? Icons.visibility_outlined
                          : Icons.visibility_off_outlined,
                    ),
                  ),
                ),
                onSubmitted: (value) => Navigator.of(context).pop(value),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(controller.text),
              child: const Text('继续'),
            ),
          ],
        ),
      ),
    );
    controller.dispose();
    return password;
  }

  Future<void> _showRecovery() async {
    await showResponsiveDialog<void>(
      context: context,
      maxWidth: 680,
      builder: (_) => _RecoveryDialog(onRestored: _showMessage),
    );
  }

  String _updateStatusText(MobileUpdateState update) {
    return switch (update.phase) {
      MobileUpdatePhase.checking => '正在检查正式版本',
      MobileUpdatePhase.available => '可更新到 ${update.asset?.version ?? ''}',
      MobileUpdatePhase.downloading => '正在下载 ${update.progress}%',
      MobileUpdatePhase.ready => '${update.asset?.version ?? '新版本'} 已准备安装',
      MobileUpdatePhase.installing => '正在打开 Android 系统安装界面',
      MobileUpdatePhase.upToDate => '当前已是最新正式版本',
      MobileUpdatePhase.unavailable => '暂无可用的正式更新清单',
      MobileUpdatePhase.reinstallRequired => '需要迁移到正式签名版本',
      MobileUpdatePhase.error => '更新检查或下载失败',
      MobileUpdatePhase.idle => '每天自动检查稳定版本',
    };
  }

  String _currentVersion(MobileUpdateState update) {
    final version = update.application?.versionName.trim() ?? '';
    return version.isEmpty ? '读取中' : version;
  }

  Future<void> _confirmInstallUpdate() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('安装更新'),
        content: const Text('SecretBase 将先锁定密码库，再打开 Android 系统安装界面。确认继续？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('稍后'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('继续安装'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await ref.read(mobileUpdateControllerProvider.notifier).install();
    }
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }
}

class _VaultSummary extends StatelessWidget {
  const _VaultSummary({required this.status});

  final VaultStatus? status;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: scheme.primaryContainer,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: scheme.primary.withValues(alpha: 0.22)),
      ),
      child: Row(
        children: [
          Icon(
            Icons.verified_user_outlined,
            color: scheme.onPrimaryContainer,
            size: 27,
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '密码库已解锁',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: scheme.onPrimaryContainer,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${status?.entryCount ?? 0} 个条目 · ${status?.deletedCount ?? 0} 个已删除',
                  style: TextStyle(color: scheme.onPrimaryContainer),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingsSection extends StatelessWidget {
  const _SettingsSection({
    required this.title,
    required this.icon,
    required this.children,
  });

  final String title;
  final IconData icon;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(color: scheme.outlineVariant),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 11, 14, 8),
            child: Row(
              children: [
                Icon(icon, size: 19, color: scheme.primary),
                const SizedBox(width: 8),
                Text(
                  title,
                  style: Theme.of(
                    context,
                  ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800),
                ),
              ],
            ),
          ),
          ...children,
        ],
      ),
    );
  }
}

class _RecoveryDialog extends ConsumerStatefulWidget {
  const _RecoveryDialog({required this.onRestored});

  final ValueChanged<String> onRestored;

  @override
  ConsumerState<_RecoveryDialog> createState() => _RecoveryDialogState();
}

class _RecoveryDialogState extends ConsumerState<_RecoveryDialog> {
  String? _restoringId;

  @override
  Widget build(BuildContext context) {
    final snapshots = ref.watch(recoverySnapshotsProvider);
    return DialogFrame(
      title: '本机恢复记录',
      canClose: _restoringId == null,
      child: snapshots.when(
        loading: () => const LoadingView(label: '正在加载恢复记录'),
        error: (error, stackTrace) => ErrorView(
          message: mobileErrorMessage(error),
          onRetry: () => ref.invalidate(recoverySnapshotsProvider),
        ),
        data: (items) {
          if (items.isEmpty) {
            return const EmptyView(
              icon: Icons.history_outlined,
              title: '暂无恢复记录',
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(14),
            itemCount: items.length,
            separatorBuilder: (context, index) => const SizedBox(height: 8),
            itemBuilder: (context, index) {
              final item = items[index];
              final restoring = _restoringId == item.id;
              return Card(
                child: ListTile(
                  leading: const Icon(Icons.restore_page_outlined),
                  title: Text(_formatSnapshotTime(item.createdAt)),
                  subtitle: Text(_formatSize(item.sizeBytes.toInt())),
                  trailing: restoring
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.chevron_right),
                  onTap: _restoringId == null ? () => _restore(item) : null,
                ),
              );
            },
          );
        },
      ),
    );
  }

  Future<void> _restore(RecoverySnapshot snapshot) async {
    if (_restoringId != null) return;
    setState(() => _restoringId = snapshot.id);
    try {
      final message = await restoreRecoverySnapshot(
        context: context,
        ref: ref,
        snapshot: snapshot,
      );
      if (message != null && mounted) {
        Navigator.of(context).pop();
        widget.onRestored(message);
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(transferErrorMessage(error))));
      }
    } finally {
      if (mounted) setState(() => _restoringId = null);
    }
  }

  static String _formatSnapshotTime(String millis) {
    final value = int.tryParse(millis);
    if (value == null) return millis;
    return DateFormat(
      'yyyy-MM-dd HH:mm:ss',
    ).format(DateTime.fromMillisecondsSinceEpoch(value));
  }

  static String _formatSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / 1024 / 1024).toStringAsFixed(1)} MB';
  }
}
