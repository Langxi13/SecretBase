import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/core/widgets/paged_scroll.dart';
import 'package:secretbase/src/core/widgets/page_controls.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/state/preferences_controller.dart';

class AiEntrySelection {
  const AiEntrySelection(this.id, this.title);

  final String id;
  final String title;
}

Future<AiEntrySelection?> showAiEntryPickerDialog(BuildContext context) {
  return showResponsiveDialog<AiEntrySelection>(
    context: context,
    maxWidth: 720,
    builder: (_) => const _AiEntryPickerDialog(),
  );
}

class _AiEntryPickerDialog extends ConsumerStatefulWidget {
  const _AiEntryPickerDialog();

  @override
  ConsumerState<_AiEntryPickerDialog> createState() =>
      _AiEntryPickerDialogState();
}

class _AiEntryPickerDialogState extends ConsumerState<_AiEntryPickerDialog> {
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();
  Timer? _debounce;
  int _page = 1;
  String _search = '';

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pageSize = ref.watch(
      preferencesProvider.select((preferences) => preferences.entryPageSize),
    );
    final query = EntryQuery(
      page: _page,
      pageSize: pageSize,
      search: _search,
      deleted: false,
    );
    final entries = ref.watch(entryPageProvider(query));
    return DialogFrame(
      title: '选择条目',
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _searchController,
              onChanged: _onSearchChanged,
              decoration: const InputDecoration(
                isDense: true,
                hintText: '搜索条目名称',
                prefixIcon: Icon(Icons.search, size: 20),
                prefixIconConstraints: BoxConstraints(
                  minWidth: 40,
                  minHeight: 40,
                ),
              ),
            ),
          ),
          Expanded(
            child: entries.when(
              loading: () => const LoadingView(),
              error: (error, stackTrace) => ErrorView(
                message: mobileErrorMessage(error),
                onRetry: () => ref.invalidate(entryPageProvider(query)),
              ),
              data: (page) => ListView.builder(
                controller: _scrollController,
                itemCount: page.items.isEmpty ? 1 : page.items.length + 1,
                itemBuilder: (context, index) {
                  if (page.items.isEmpty) {
                    return const EmptyView(
                      icon: Icons.search_off,
                      title: '没有匹配的条目',
                    );
                  }
                  if (index == page.items.length) {
                    return PageControls(
                      page: page.page,
                      totalPages: page.totalPages,
                      pageSize: pageSize,
                      showPageSize: false,
                      onPageChanged: (value) {
                        setState(() => _page = value);
                        resetPagedScroll(_scrollController);
                      },
                      onPageSizeChanged: (_) {},
                    );
                  }
                  final entry = page.items[index];
                  return ListTile(
                    leading: const Icon(Icons.key_outlined),
                    title: Text(
                      entry.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: entry.url.isEmpty
                        ? null
                        : Text(
                            _displayHost(entry.url),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(
                      context,
                    ).pop(AiEntrySelection(entry.id, entry.title)),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _onSearchChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 280), () {
      if (!mounted) return;
      setState(() {
        _search = value.trim();
        _page = 1;
      });
      resetPagedScroll(_scrollController);
    });
  }

  String _displayHost(String value) {
    final host = Uri.tryParse(value)?.host;
    return host?.isNotEmpty == true ? host! : value;
  }
}
