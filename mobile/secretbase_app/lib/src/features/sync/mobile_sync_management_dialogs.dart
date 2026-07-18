import 'package:flutter/material.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';
import 'package:secretbase/src/features/sync/mobile_sync_service.dart';
import 'package:secretbase/src/rust/mobile/models.dart';

class MobileSyncConfigDraft {
  const MobileSyncConfigDraft({
    required this.baseUrl,
    required this.username,
    required this.password,
    required this.deviceName,
    required this.autoSync,
  });

  final String baseUrl;
  final String username;
  final String password;
  final String deviceName;
  final bool autoSync;
}

class MobileSyncDangerInput {
  const MobileSyncDangerInput({
    required this.password,
    required this.confirmation,
  });

  final String password;
  final String confirmation;
}

Future<String?> promptSyncMasterPassword(
  BuildContext context, {
  required String title,
  required String message,
}) {
  return showResponsiveDialog<String>(
    context: context,
    maxWidth: 480,
    builder: (_) => _MasterPasswordDialog(title: title, message: message),
  );
}

Future<MobileSyncDangerInput?> promptSyncDangerConfirmation(
  BuildContext context, {
  required String title,
  required String message,
  required String confirmation,
}) {
  return showResponsiveDialog<MobileSyncDangerInput>(
    context: context,
    maxWidth: 520,
    builder: (_) => _DangerConfirmationDialog(
      title: title,
      message: message,
      confirmation: confirmation,
    ),
  );
}

Future<MobileSyncConfigDraft?> showMobileSyncConfigEditor(
  BuildContext context, {
  required SyncConnection connection,
  required bool autoSync,
}) {
  return showResponsiveDialog<MobileSyncConfigDraft>(
    context: context,
    maxWidth: 620,
    builder: (_) =>
        _SyncConfigDialog(connection: connection, autoSync: autoSync),
  );
}

class _MasterPasswordDialog extends StatefulWidget {
  const _MasterPasswordDialog({required this.title, required this.message});

  final String title;
  final String message;

  @override
  State<_MasterPasswordDialog> createState() => _MasterPasswordDialogState();
}

class _MasterPasswordDialogState extends State<_MasterPasswordDialog> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return DialogFrame(
      title: widget.title,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(widget.message),
          const SizedBox(height: 14),
          TextField(
            controller: _controller,
            autofocus: true,
            obscureText: true,
            textInputAction: TextInputAction.done,
            onChanged: (_) => setState(() {}),
            onSubmitted: (_) => _submit(),
            decoration: const InputDecoration(
              labelText: '当前主密码',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _controller.text.isEmpty ? null : _submit,
            child: const Text('验证'),
          ),
        ],
      ),
    );
  }

  void _submit() {
    if (_controller.text.isNotEmpty) Navigator.pop(context, _controller.text);
  }
}

class _DangerConfirmationDialog extends StatefulWidget {
  const _DangerConfirmationDialog({
    required this.title,
    required this.message,
    required this.confirmation,
  });

  final String title;
  final String message;
  final String confirmation;

  @override
  State<_DangerConfirmationDialog> createState() =>
      _DangerConfirmationDialogState();
}

class _DangerConfirmationDialogState extends State<_DangerConfirmationDialog> {
  final _password = TextEditingController();
  final _typed = TextEditingController();

  @override
  void dispose() {
    _password.dispose();
    _typed.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final valid =
        _password.text.isNotEmpty && _typed.text == widget.confirmation;
    return DialogFrame(
      title: widget.title,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(widget.message),
          const SizedBox(height: 14),
          TextField(
            controller: _password,
            obscureText: true,
            onChanged: (_) => setState(() {}),
            decoration: const InputDecoration(
              labelText: '当前主密码',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _typed,
            onChanged: (_) => setState(() {}),
            decoration: InputDecoration(
              labelText: '输入 ${widget.confirmation} 确认',
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: valid
                ? () => Navigator.pop(
                    context,
                    MobileSyncDangerInput(
                      password: _password.text,
                      confirmation: _typed.text,
                    ),
                  )
                : null,
            child: const Text('继续'),
          ),
        ],
      ),
    );
  }
}

class _SyncConfigDialog extends StatefulWidget {
  const _SyncConfigDialog({required this.connection, required this.autoSync});

  final SyncConnection connection;
  final bool autoSync;

  @override
  State<_SyncConfigDialog> createState() => _SyncConfigDialogState();
}

class _SyncConfigDialogState extends State<_SyncConfigDialog> {
  late final TextEditingController _url;
  late final TextEditingController _username;
  late final TextEditingController _password;
  late final TextEditingController _device;
  late bool _automatic;

  @override
  void initState() {
    super.initState();
    _url = TextEditingController(text: widget.connection.baseUrl);
    _username = TextEditingController(text: widget.connection.username);
    _password = TextEditingController();
    _device = TextEditingController(text: widget.connection.deviceName);
    _automatic = widget.autoSync;
  }

  @override
  void dispose() {
    _url.dispose();
    _username.dispose();
    _password.dispose();
    _device.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return DialogFrame(
      title: '同步设置',
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _field(_url, 'WebDAV 地址'),
          _field(_username, '用户名'),
          _field(_password, '新应用密码（留空保持不变）', obscure: true),
          _field(_device, '设备名称'),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            value: _automatic,
            onChanged: (value) => setState(() => _automatic = value),
            title: const Text('自动同步'),
          ),
          const SizedBox(height: 8),
          FilledButton(
            onPressed: () => Navigator.pop(
              context,
              MobileSyncConfigDraft(
                baseUrl: _url.text,
                username: _username.text,
                password: _password.text,
                deviceName: _device.text,
                autoSync: _automatic,
              ),
            ),
            child: const Text('保存设置'),
          ),
        ],
      ),
    );
  }
}

Future<String?> showMobileSyncHistoryPicker(
  BuildContext context,
  List<MobileSyncHistoryItem> items,
) {
  return showResponsiveDialog<String>(
    context: context,
    maxWidth: 720,
    builder: (dialogContext) => DialogFrame(
      title: '加密快照历史',
      child: items.isEmpty
          ? const Center(child: Text('暂无可用历史'))
          : ListView.separated(
              padding: const EdgeInsets.symmetric(vertical: 8),
              itemCount: items.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final item = items[index];
                return ListTile(
                  leading: CircleAvatar(child: Text('${item.generation}')),
                  title: Text(item.deviceName.isEmpty ? '设备' : item.deviceName),
                  subtitle: Text(_historyTime(item.createdAt)),
                  trailing: item.frontier
                      ? const Tooltip(
                          message: '当前分支',
                          child: Icon(Icons.cloud_done_outlined),
                        )
                      : IconButton(
                          tooltip: '恢复此版本',
                          onPressed: () =>
                              Navigator.pop(dialogContext, item.snapshotId),
                          icon: const Icon(Icons.history),
                        ),
                );
              },
            ),
    ),
  );
}

Widget _field(
  TextEditingController controller,
  String label, {
  bool obscure = false,
}) {
  return Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: TextField(
      controller: controller,
      obscureText: obscure,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
        isDense: true,
      ),
    ),
  );
}

String _historyTime(String raw) {
  final value = DateTime.tryParse(raw)?.toLocal();
  if (value == null) return raw.isEmpty ? '时间未知' : raw;
  String two(int number) => number.toString().padLeft(2, '0');
  return '${value.year}-${two(value.month)}-${two(value.day)} '
      '${two(value.hour)}:${two(value.minute)}';
}
