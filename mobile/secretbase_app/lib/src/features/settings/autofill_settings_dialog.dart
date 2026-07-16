import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/autofill_service.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';

Future<void> showAutofillSettingsDialog({required BuildContext context}) {
  return showResponsiveDialog<void>(
    context: context,
    maxWidth: 620,
    builder: (_) => const AutofillSettingsDialog(),
  );
}

class AutofillSettingsDialog extends ConsumerStatefulWidget {
  const AutofillSettingsDialog({super.key});

  @override
  ConsumerState<AutofillSettingsDialog> createState() =>
      _AutofillSettingsDialogState();
}

class _AutofillSettingsDialogState extends ConsumerState<AutofillSettingsDialog>
    with WidgetsBindingObserver {
  AutofillStatus? _status;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _reload();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _reload();
  }

  Future<void> _reload() async {
    if (mounted) setState(() => _loading = true);
    try {
      final status = await ref.read(autofillPlatformProvider).status();
      if (mounted) {
        setState(() {
          _status = status;
          _loading = false;
          _error = null;
        });
        ref.invalidate(autofillStatusProvider);
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = '无法读取系统自动填充状态';
        });
      }
    }
  }

  Future<void> _setPreference(String name, bool value) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final status = await ref
          .read(autofillPlatformProvider)
          .setPreference(name, value);
      if (mounted) setState(() => _status = status);
    } catch (_) {
      if (mounted) setState(() => _error = '无法更新自动填充设置');
    } finally {
      if (mounted) setState(() => _loading = false);
      ref.invalidate(autofillStatusProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = _status;
    return DialogFrame(
      title: '系统自动填充',
      child: Column(
        children: [
          if (_loading) const LinearProgressIndicator(minHeight: 2),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(vertical: 8),
              children: [
                ListTile(
                  leading: Icon(
                    status?.enabled == true
                        ? Icons.verified_user
                        : Icons.password_outlined,
                  ),
                  title: Text(status?.enabled == true ? '已启用' : '尚未启用'),
                  subtitle: Text(
                    status?.supported == false
                        ? '当前系统不支持自动填充服务'
                        : '由 Android 系统管理默认自动填充服务',
                  ),
                  trailing: FilledButton(
                    onPressed: status?.supported == false || _loading
                        ? null
                        : () async {
                            final platform = ref.read(autofillPlatformProvider);
                            if (status?.enabled == true) {
                              await platform.openSettings();
                            } else {
                              await platform.requestService();
                            }
                          },
                    child: Text(status?.enabled == true ? '管理' : '启用'),
                  ),
                ),
                const Divider(height: 1, indent: 56),
                SwitchListTile(
                  secondary: const Icon(Icons.save_outlined),
                  title: const Text('保存新登录信息'),
                  subtitle: const Text('登录后由系统询问，再经身份验证保存'),
                  value: status?.savePromptsEnabled ?? true,
                  onChanged: _loading
                      ? null
                      : (value) => _setPreference('savePrompts', value),
                ),
                const Divider(height: 1, indent: 56),
                SwitchListTile(
                  secondary: const Icon(Icons.keyboard_alt_outlined),
                  title: const Text('键盘行内建议'),
                  subtitle: const Text('Android 11 及以上可显示在输入法上方'),
                  value: status?.inlineSuggestionsEnabled ?? true,
                  onChanged: _loading
                      ? null
                      : (value) => _setPreference('inlineSuggestions', value),
                ),
                const Divider(height: 1, indent: 56),
                ListTile(
                  leading: const Icon(Icons.block_outlined),
                  title: const Text('已停用的目标'),
                  subtitle: Text('${status?.blockedTargetCount ?? 0} 个网站或应用'),
                  trailing: TextButton(
                    onPressed:
                        _loading || (status?.blockedTargetCount ?? 0) == 0
                        ? null
                        : () async {
                            setState(() {
                              _loading = true;
                              _error = null;
                            });
                            try {
                              final next = await ref
                                  .read(autofillPlatformProvider)
                                  .clearBlockedTargets();
                              if (mounted) setState(() => _status = next);
                            } catch (_) {
                              if (mounted) {
                                setState(() => _error = '无法清除已停用目标');
                              }
                            } finally {
                              if (mounted) setState(() => _loading = false);
                              ref.invalidate(autofillStatusProvider);
                            }
                          },
                    child: const Text('清除'),
                  ),
                ),
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('完成'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
