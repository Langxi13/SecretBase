import 'package:flutter/material.dart';
import 'package:secretbase/src/features/sync/mobile_sync_merge.dart';
import 'package:secretbase/src/features/sync/mobile_sync_service.dart';

class MobileSyncConflictView extends StatelessWidget {
  const MobileSyncConflictView({
    required this.conflict,
    required this.resolutions,
    required this.working,
    required this.onResolutionChanged,
    required this.onResolve,
    super.key,
  });

  final MobileSyncConflictSession conflict;
  final Map<String, String> resolutions;
  final bool working;
  final void Function(String conflictId, String value) onResolutionChanged;
  final VoidCallback onResolve;

  bool get _complete => conflict.conflicts.every(
    (item) => resolutions.containsKey(item.conflictId),
  );

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text('需要处理同步冲突', style: TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        const Text('这里只显示标题、状态和变化区块，不显示字段值。'),
        const SizedBox(height: 10),
        for (final item in conflict.conflicts) _item(context, item),
        const SizedBox(height: 8),
        FilledButton(
          onPressed: working || !_complete ? null : onResolve,
          child: Text(working ? '应用中...' : '应用选择'),
        ),
      ],
    );
  }

  Widget _item(BuildContext context, MobileSyncConflict item) {
    return Card(
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
              initialValue: resolutions[item.conflictId],
              decoration: const InputDecoration(
                labelText: '处理方式',
                isDense: true,
              ),
              items: [
                const DropdownMenuItem(value: 'local', child: Text('保留本机')),
                const DropdownMenuItem(value: 'remote', child: Text('保留远端')),
                if (item.allowBoth)
                  const DropdownMenuItem(value: 'both', child: Text('保留两份')),
              ],
              onChanged: working
                  ? null
                  : (value) {
                      if (value != null) {
                        onResolutionChanged(item.conflictId, value);
                      }
                    },
            ),
          ],
        ),
      ),
    );
  }
}
