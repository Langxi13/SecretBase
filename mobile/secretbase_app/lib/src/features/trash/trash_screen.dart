import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/core/widgets/page_controls.dart';
import 'package:secretbase/src/data/vault_providers.dart';
import 'package:secretbase/src/features/entries/entry_card.dart';
import 'package:secretbase/src/features/entries/entry_detail_dialog.dart';
import 'package:secretbase/src/rust/mobile/models.dart';
import 'package:secretbase/src/state/preferences_controller.dart';

class TrashScreen extends ConsumerStatefulWidget {
  const TrashScreen({super.key});

  @override
  ConsumerState<TrashScreen> createState() => _TrashScreenState();
}

class _TrashScreenState extends ConsumerState<TrashScreen> {
  final _searchController = TextEditingController();
  Timer? _debounce;
  int _page = 1;
  String _search = '';

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
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
      deleted: true,
    );
    final entries = ref.watch(entryPageProvider(query));
    return Scaffold(
      appBar: AppBar(title: const Text('回收站')),
      body: Column(
        children: [
          Material(
            color: Theme.of(context).colorScheme.surface,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 920),
                  child: TextField(
                    controller: _searchController,
                    onChanged: _onSearch,
                    decoration: const InputDecoration(
                      hintText: '筛选已删除条目',
                      prefixIcon: Icon(Icons.search),
                    ),
                  ),
                ),
              ),
            ),
          ),
          Expanded(
            child: entries.when(
              loading: () => const LoadingView(label: '正在加载回收站'),
              error: (error, stackTrace) => ErrorView(
                message: mobileErrorMessage(error),
                onRetry: () => ref.invalidate(entryPageProvider(query)),
              ),
              data: (page) => _buildList(page),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildList(EntryPage page) {
    if (page.items.isEmpty) {
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          EmptyView(
            icon: Icons.delete_outline,
            title: _search.isEmpty ? '回收站为空' : '没有匹配的已删除条目',
          ),
        ],
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 34),
      itemCount: page.items.length + 1,
      itemBuilder: (context, index) {
        if (index == page.items.length) {
          return PageControls(
            page: page.page,
            totalPages: page.totalPages,
            pageSize: page.pageSize,
            onPageChanged: (value) => setState(() => _page = value),
            onPageSizeChanged: (value) {
              ref.read(preferencesProvider.notifier).setEntryPageSize(value);
              setState(() => _page = 1);
            },
          );
        }
        final entry = page.items[index];
        return Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 920),
            child: Padding(
              padding: const EdgeInsets.only(bottom: 9),
              child: EntryCard(entry: entry, onTap: () => _openEntry(entry.id)),
            ),
          ),
        );
      },
    );
  }

  void _onSearch(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () {
      if (mounted) {
        setState(() {
          _search = value.trim();
          _page = 1;
        });
      }
    });
  }

  Future<void> _openEntry(String id) async {
    final message = await showEntryDetailDialog(
      context: context,
      ref: ref,
      entryId: id,
    );
    if (message != null && mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
    }
  }
}
