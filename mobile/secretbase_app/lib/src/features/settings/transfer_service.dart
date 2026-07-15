import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:secretbase/src/core/biometric_unlock.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/vault_controller.dart';

Future<String?> exportVaultBackup() async {
  final bytes = await rust_api.exportEncryptedVault();
  final timestamp = DateFormat('yyyyMMdd-HHmmss').format(DateTime.now());
  const channel = MethodChannel('secretbase/security');
  final saved = await channel.invokeMethod<bool>('saveDocument', {
    'filename': 'secretbase-$timestamp.vault',
    'bytes': bytes,
  });
  return saved == true ? '加密备份已导出' : null;
}

Future<String?> importVaultBackup({
  required BuildContext context,
  required WidgetRef ref,
}) async {
  const vaultType = XTypeGroup(
    label: 'SecretBase Vault',
    extensions: ['vault'],
    mimeTypes: ['application/octet-stream'],
  );
  final file = await openFile(acceptedTypeGroups: const [vaultType]);
  if (file == null) return null;
  if (await file.length() > 50 * 1024 * 1024) {
    throw StateError('备份文件不能超过 50 MB');
  }
  final bytes = await file.readAsBytes();
  if (!context.mounted) return null;
  final password = await _requestPassword(
    context,
    title: '输入备份主密码',
    description: '请输入创建该备份时，备份所属密码库使用的主密码。',
    fieldLabel: '备份主密码',
  );
  if (password == null || password.isEmpty) return null;
  final preview = await rust_api.previewImport(
    content: bytes,
    password: password,
  );
  if (!context.mounted) return null;
  final confirmed = await _confirmImport(context, preview);
  if (!confirmed) return null;
  final result = await rust_api.applyImport(token: preview.token);
  await _clearBiometricCredential(ref);
  await ref.read(vaultControllerProvider.notifier).refreshStatus();
  ref.invalidate(entryPageProvider);
  ref.invalidate(taxonomyProvider);
  ref.invalidate(recoverySnapshotsProvider);
  return result.message;
}

Future<String?> restoreRecoverySnapshot({
  required BuildContext context,
  required WidgetRef ref,
  required RecoverySnapshot snapshot,
}) async {
  final password = await _requestPassword(
    context,
    title: '输入恢复记录主密码',
    description: '请输入创建该恢复记录时，本机密码库使用的主密码。',
    fieldLabel: '恢复记录主密码',
  );
  if (password == null || password.isEmpty) return null;
  final preview = await rust_api.previewRecovery(
    id: snapshot.id,
    password: password,
  );
  if (!context.mounted) return null;
  final confirmed = await _confirmImport(context, preview, recovery: true);
  if (!confirmed) return null;
  final result = await rust_api.applyImport(token: preview.token);
  await _clearBiometricCredential(ref);
  await ref.read(vaultControllerProvider.notifier).refreshStatus();
  ref.invalidate(entryPageProvider);
  ref.invalidate(taxonomyProvider);
  ref.invalidate(recoverySnapshotsProvider);
  return result.message;
}

Future<void> _clearBiometricCredential(WidgetRef ref) async {
  try {
    await ref.read(biometricPlatformProvider).deleteCredential();
  } catch (_) {
    // The imported Vault salt still prevents a stale device credential from unlocking.
  }
  ref.invalidate(biometricStatusProvider);
}

Future<String?> _requestPassword(
  BuildContext context, {
  required String title,
  required String description,
  required String fieldLabel,
}) async {
  final controller = TextEditingController();
  var obscure = true;
  final result = await showDialog<String>(
    context: context,
    builder: (context) => StatefulBuilder(
      builder: (context, setState) => AlertDialog(
        title: Text(title),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              description,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 14),
            TextField(
              controller: controller,
              autofocus: true,
              obscureText: obscure,
              decoration: InputDecoration(
                labelText: fieldLabel,
                suffixIcon: IconButton(
                  tooltip: obscure ? '显示主密码' : '隐藏主密码',
                  onPressed: () => setState(() => obscure = !obscure),
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
  return result;
}

Future<bool> _confirmImport(
  BuildContext context,
  ImportPreview preview, {
  bool recovery = false,
}) async {
  return await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(recovery ? '确认恢复密码库' : '确认导入密码库'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _PreviewLine(label: '条目', value: preview.entries),
              _PreviewLine(label: '回收站', value: preview.deletedEntries),
              _PreviewLine(label: '标签', value: preview.tags),
              _PreviewLine(label: '密码组', value: preview.groups),
              const SizedBox(height: 12),
              Text(
                '当前密码库将被替换，并在本机保留恢复副本。',
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: Text(recovery ? '恢复' : '导入并替换'),
            ),
          ],
        ),
      ) ??
      false;
}

String transferErrorMessage(Object error) {
  if (error is StateError) return error.message;
  return mobileErrorMessage(error);
}

class _PreviewLine extends StatelessWidget {
  const _PreviewLine({required this.label, required this.value});

  final String label;
  final int value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Text('$value'),
        ],
      ),
    );
  }
}
