import 'package:flutter/material.dart';

class PageControls extends StatelessWidget {
  const PageControls({
    required this.page,
    required this.totalPages,
    required this.pageSize,
    required this.onPageChanged,
    required this.onPageSizeChanged,
    this.showPageSize = true,
    super.key,
  });

  final int page;
  final int totalPages;
  final int pageSize;
  final ValueChanged<int> onPageChanged;
  final ValueChanged<int> onPageSizeChanged;
  final bool showPageSize;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
      child: Wrap(
        alignment: WrapAlignment.center,
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 8,
        runSpacing: 8,
        children: [
          IconButton.outlined(
            tooltip: '上一页',
            onPressed: page > 1 ? () => onPageChanged(page - 1) : null,
            icon: const Icon(Icons.chevron_left),
          ),
          SizedBox(
            width: 92,
            child: Text(
              '$page / $totalPages',
              textAlign: TextAlign.center,
              style: Theme.of(
                context,
              ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w700),
            ),
          ),
          IconButton.outlined(
            tooltip: '下一页',
            onPressed: page < totalPages ? () => onPageChanged(page + 1) : null,
            icon: const Icon(Icons.chevron_right),
          ),
          if (showPageSize) ...[
            const SizedBox(width: 4),
            DropdownButton<int>(
              value: pageSize,
              underline: const SizedBox.shrink(),
              borderRadius: BorderRadius.circular(6),
              onChanged: (value) {
                if (value != null) onPageSizeChanged(value);
              },
              items: const [5, 10, 20, 50]
                  .map(
                    (value) => DropdownMenuItem(
                      value: value,
                      child: Text('每页 $value 条'),
                    ),
                  )
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }
}
