import 'package:flutter/material.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/rust/mobile/models.dart';

part 'ai_plan_components.dart';

bool aiPreviewItemIsHighImpact(AiPreviewItem item) {
  return const {'标签删除', '标签合并', '删除标签', '合并标签'}.contains(item.subtitle) ||
      item.title.startsWith('删除标签') ||
      item.title.startsWith('合并到');
}

class AiPlanPanel extends StatelessWidget {
  const AiPlanPanel({
    required this.preview,
    required this.selected,
    required this.revealed,
    required this.expanded,
    required this.working,
    required this.onSelectionChanged,
    required this.onSelectAll,
    required this.onReveal,
    required this.onExpanded,
    required this.onApply,
    super.key,
  });

  final AiPreview preview;
  final Set<String> selected;
  final Set<String> revealed;
  final Set<String> expanded;
  final bool working;
  final void Function(String id, bool value) onSelectionChanged;
  final ValueChanged<bool> onSelectAll;
  final ValueChanged<String> onReveal;
  final ValueChanged<String> onExpanded;
  final VoidCallback onApply;

  @override
  Widget build(BuildContext context) {
    final ids = preview.items.map((item) => item.id).toSet();
    final selectedCount = selected.intersection(ids).length;
    final allSelected = ids.isNotEmpty && selectedCount == ids.length;
    final groups = <String, List<AiPreviewItem>>{};
    for (final item in preview.items) {
      final category = preview.kind == 'parse' ? '条目创建' : _categoryFor(item);
      groups.putIfAbsent(category, () => []).add(item);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _PlanSummary(
          preview: preview,
          selectedCount: selectedCount,
          allSelected: allSelected,
          onSelectAll: preview.items.isEmpty ? null : onSelectAll,
        ),
        if (preview.warnings.isNotEmpty) ...[
          const SizedBox(height: 8),
          _WarningBand(warnings: preview.warnings),
        ],
        const SizedBox(height: 10),
        if (preview.items.isEmpty)
          const EmptyView(icon: Icons.task_alt_outlined, title: '没有需要应用的建议')
        else
          ...groups.entries.map(
            (entry) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _PlanGroup(
                label: entry.key,
                items: entry.value,
                selected: selected,
                revealed: revealed,
                expanded: expanded,
                onSelectionChanged: onSelectionChanged,
                onReveal: onReveal,
                onExpanded: onExpanded,
              ),
            ),
          ),
        if (preview.items.isNotEmpty)
          FilledButton.icon(
            onPressed: selectedCount == 0 || working ? null : onApply,
            icon: const Icon(Icons.done_all, size: 18),
            label: Text('应用已选计划（$selectedCount）'),
          ),
      ],
    );
  }

  static String _categoryFor(AiPreviewItem item) {
    final text = '${item.subtitle} ${item.title}';
    if (text.contains('密码组')) return '密码组';
    if (text.contains('标签')) return '标签';
    if (text.contains('本机复制') || text.contains('条目模板')) return '条目创建';
    if (text.contains('字段') || text.contains('条目结构')) return '条目结构';
    if (text.contains('条目') || text.contains('AI 新建')) return '条目创建';
    return '其他操作';
  }
}
