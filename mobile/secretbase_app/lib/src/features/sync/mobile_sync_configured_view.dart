import 'package:flutter/material.dart';
import 'package:secretbase/src/features/sync/mobile_sync_auto.dart';
import 'package:secretbase/src/rust/mobile/models.dart';

class MobileSyncConfiguredView extends StatelessWidget {
  const MobileSyncConfiguredView({
    required this.status,
    required this.automatic,
    required this.recoveryCode,
    required this.working,
    required this.onSync,
    required this.onShowRecovery,
    required this.onShowHistory,
    required this.onEditConfig,
    required this.onCopyRecovery,
    required this.onCopyPairing,
    required this.onMoreAction,
    super.key,
  });

  final SyncStatus status;
  final MobileSyncAutoState automatic;
  final String? recoveryCode;
  final bool working;
  final VoidCallback onSync;
  final VoidCallback onShowRecovery;
  final VoidCallback onShowHistory;
  final VoidCallback onEditConfig;
  final VoidCallback onCopyRecovery;
  final VoidCallback onCopyPairing;
  final ValueChanged<String> onMoreAction;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
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
        if (recoveryCode != null) ...[
          const Text('新设备恢复码', style: TextStyle(fontWeight: FontWeight.w700)),
          SelectableText(
            recoveryCode!,
            style: const TextStyle(fontFamily: 'monospace'),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              OutlinedButton.icon(
                onPressed: working ? null : onCopyRecovery,
                icon: const Icon(Icons.copy_outlined),
                label: const Text('复制恢复码'),
              ),
              OutlinedButton.icon(
                onPressed: working ? null : onCopyPairing,
                icon: const Icon(Icons.link_outlined),
                label: const Text('复制配对链接'),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            '配对链接不含 WebDAV 应用密码，其他设备仍需手动输入应用密码。',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 10),
        ],
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            FilledButton.icon(
              onPressed: working ? null : onSync,
              icon: const Icon(Icons.sync),
              label: const Text('立即同步'),
            ),
            OutlinedButton.icon(
              onPressed: working ? null : onShowRecovery,
              icon: const Icon(Icons.key_outlined),
              label: const Text('恢复码'),
            ),
            OutlinedButton.icon(
              onPressed: working ? null : onShowHistory,
              icon: const Icon(Icons.history),
              label: const Text('历史'),
            ),
            OutlinedButton.icon(
              onPressed: working ? null : onEditConfig,
              icon: const Icon(Icons.tune),
              label: const Text('设置'),
            ),
            PopupMenuButton<String>(
              enabled: !working,
              tooltip: '更多同步操作',
              icon: const Icon(Icons.more_horiz),
              onSelected: onMoreAction,
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
}
