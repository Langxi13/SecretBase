import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:secretbase/src/core/mobile_error_presenter.dart';
import 'package:secretbase/src/core/widgets/async_content.dart';
import 'package:secretbase/src/core/widgets/page_controls.dart';
import 'package:secretbase/src/core/widgets/responsive_dialog.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart';

class AiScopeSelection {
  const AiScopeSelection(this.entries);

  final Map<String, String> entries;

  bool get isAll => entries.isEmpty;
  List<String> get ids => entries.keys.toList();
}

Future<AiScopeSelection?> showAiScopeDialog({
  required BuildContext context,
  required Map<String, String> selected,
}) {
  return showResponsiveDialog<AiScopeSelection>(
    context: context,
    maxWidth: 760,
    builder: (_) => AiScopeDialog(selected: selected),
  );
}

class AiScopeDialog extends StatefulWidget {
  const AiScopeDialog({required this.selected, super.key});

  final Map<String, String> selected;

  @override
  State<AiScopeDialog> createState() => _AiScopeDialogState();
}

class _AiScopeDialogState extends State<AiScopeDialog> {
  late final Map<String, String> _selected;
  late bool _all;
  int _page = 1;
  int _pageSize = 10;
  late Future<EntryPage> _future;

  @override
  void initState() {
    super.initState();
    _selected = Map.of(widget.selected);
    _all = _selected.isEmpty;
    _future = _load();
  }

  Future<EntryPage> _load() {
    return rust_api.listEntries(
      page: _page,
      pageSize: _pageSize,
      search: '',
      deleted: false,
    );
  }

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    return DialogFrame(
      title: 'AI 分析范围',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
            child: SegmentedButton<bool>(
              segments: const [
                ButtonSegment(
                  value: true,
                  icon: Icon(Icons.select_all, size: 18),
                  label: Text('全部条目'),
                ),
                ButtonSegment(
                  value: false,
                  icon: Icon(Icons.checklist_outlined, size: 18),
                  label: Text('指定条目'),
                ),
              ],
              selected: {_all},
              onSelectionChanged: (values) => setState(() {
                _all = values.first;
                if (_all) _selected.clear();
              }),
            ),
          ),
          if (_all)
            const Expanded(
              child: EmptyView(
                icon: Icons.library_books_outlined,
                title: '将分析当前密码库中的全部条目',
              ),
            )
          else
            Expanded(
              child: FutureBuilder<EntryPage>(
                future: _future,
                builder: (context, snapshot) {
                  if (snapshot.connectionState != ConnectionState.done) {
                    return const LoadingView(label: '正在读取条目');
                  }
                  if (snapshot.hasError || snapshot.data == null) {
                    return ErrorView(
                      message: snapshot.error == null
                          ? '无法读取条目'
                          : mobileErrorMessage(snapshot.error!),
                      onRetry: _reload,
                    );
                  }
                  final page = snapshot.data!;
                  if (page.items.isEmpty) {
                    return const EmptyView(
                      icon: Icons.key_off_outlined,
                      title: '暂无可选条目',
                    );
                  }
                  return Column(
                    children: [
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                '已选择 ${_selected.length} 项',
                                style: Theme.of(context).textTheme.labelLarge,
                              ),
                            ),
                            TextButton(
                              onPressed: _selected.isEmpty
                                  ? null
                                  : () => setState(_selected.clear),
                              child: const Text('清空'),
                            ),
                          ],
                        ),
                      ),
                      const Divider(height: 1),
                      Expanded(
                        child: ListView.separated(
                          itemCount: page.items.length,
                          separatorBuilder: (_, _) => const Divider(height: 1),
                          itemBuilder: (context, index) {
                            final entry = page.items[index];
                            final checked = _selected.containsKey(entry.id);
                            return CheckboxListTile(
                              value: checked,
                              dense: true,
                              controlAffinity: ListTileControlAffinity.leading,
                              title: Text(
                                entry.title,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              subtitle: Text(
                                [
                                  if (entry.groups.isNotEmpty)
                                    entry.groups.join('、'),
                                  if (entry.tags.isNotEmpty)
                                    entry.tags.join('、'),
                                ].join(' · '),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              onChanged: (value) => setState(() {
                                if (value == true) {
                                  _selected[entry.id] = entry.title;
                                } else {
                                  _selected.remove(entry.id);
                                }
                              }),
                            );
                          },
                        ),
                      ),
                      const Divider(height: 1),
                      PageControls(
                        page: page.page,
                        totalPages: page.totalPages,
                        pageSize: page.pageSize,
                        onPageChanged: (value) {
                          _page = value;
                          _reload();
                        },
                        onPageSizeChanged: (value) {
                          _page = 1;
                          _pageSize = value;
                          _reload();
                        },
                      ),
                    ],
                  );
                },
              ),
            ),
          const Divider(height: 1),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('取消'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    onPressed: !_all && _selected.isEmpty
                        ? null
                        : () => Navigator.of(
                            context,
                          ).pop(AiScopeSelection(Map.of(_selected))),
                    child: const Text('确认范围'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

Future<String?> showAiHistoryDialog({required BuildContext context}) {
  return showResponsiveDialog<String>(
    context: context,
    maxWidth: 720,
    builder: (_) => const AiHistoryDialog(),
  );
}

class AiHistoryDialog extends StatefulWidget {
  const AiHistoryDialog({super.key});

  @override
  State<AiHistoryDialog> createState() => _AiHistoryDialogState();
}

class _AiHistoryDialogState extends State<AiHistoryDialog> {
  late Future<List<AiConversationSummary>> _future;
  bool _working = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _future = rust_api.listAiConversations();
  }

  void _reload() => setState(() => _future = rust_api.listAiConversations());

  Future<void> _delete(AiConversationSummary conversation) async {
    if (_working) return;
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      await rust_api.deleteAiConversation(id: conversation.id);
      if (mounted) {
        setState(() => _working = false);
        _reload();
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _working = false;
          _error = mobileErrorMessage(error);
        });
      }
    }
  }

  Future<void> _clear() async {
    if (_working) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('清除对话历史'),
        content: const Text('确认清除本机加密保存的全部 AI 对话？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('清除'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _working = true);
    try {
      await rust_api.clearAiConversations();
      if (mounted) Navigator.of(context).pop('');
    } catch (error) {
      if (mounted) {
        setState(() {
          _working = false;
          _error = mobileErrorMessage(error);
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return DialogFrame(
      title: 'AI 对话历史',
      canClose: !_working,
      actions: [
        IconButton(
          tooltip: '清除全部历史',
          onPressed: _working ? null : _clear,
          icon: const Icon(Icons.delete_sweep_outlined),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_working) const LinearProgressIndicator(minHeight: 2),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
              child: Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          Expanded(
            child: FutureBuilder<List<AiConversationSummary>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const LoadingView(label: '正在读取对话历史');
                }
                if (snapshot.hasError) {
                  return ErrorView(
                    message: mobileErrorMessage(snapshot.error!),
                    onRetry: _reload,
                  );
                }
                final conversations = snapshot.data ?? [];
                if (conversations.isEmpty) {
                  return const EmptyView(
                    icon: Icons.forum_outlined,
                    title: '暂无对话历史',
                  );
                }
                return ListView.separated(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  itemCount: conversations.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final conversation = conversations[index];
                    return ListTile(
                      leading: const Icon(Icons.chat_bubble_outline),
                      title: Text(
                        conversation.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      subtitle: Text(
                        '${conversation.messageCount} 条消息 · ${_formatTime(conversation.updatedAt)}',
                      ),
                      trailing: IconButton(
                        tooltip: '删除对话',
                        onPressed: _working
                            ? null
                            : () => _delete(conversation),
                        icon: const Icon(Icons.delete_outline),
                      ),
                      onTap: _working
                          ? null
                          : () => Navigator.of(context).pop(conversation.id),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  String _formatTime(String value) {
    final parsed = DateTime.tryParse(value)?.toLocal();
    return parsed == null ? '' : DateFormat('MM-dd HH:mm').format(parsed);
  }
}
