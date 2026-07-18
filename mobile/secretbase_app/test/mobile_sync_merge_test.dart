import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/features/sync/mobile_sync_merge.dart';

Map<String, dynamic> entry(String id, String title) => {
  'id': id,
  'title': title,
  'url': '',
  'starred': false,
  'tags': <String>[],
  'groups': <String>[],
  'fields': <Map<String, dynamic>>[],
  'remarks': '',
  'updated_at': '2026-01-01T00:00:00Z',
  'deleted': false,
};

Map<String, dynamic> document() => {
  'version': '1.0',
  'vault_id': '11111111-1111-4111-8111-111111111111',
  'entries': <dynamic>[],
  'deleted_entries': <dynamic>[],
  'tags_meta': <String, dynamic>{},
  'groups_meta': <String, dynamic>{},
};

void main() {
  test('文档比较忽略条目集合顺序但保留字段顺序', () {
    final left = document()
      ..['entries'] = [entry('b', '第二条'), entry('a', '第一条')];
    final right = document()
      ..['entries'] = [entry('a', '第一条'), entry('b', '第二条')];
    left['entries'][0]['fields'] = [
      {'name': '字段一', 'value': '值一'},
      {'name': '字段二', 'value': '值二'},
    ];
    right['entries'][1]['fields'] = [
      {'name': '字段一', 'value': '值一'},
      {'name': '字段二', 'value': '值二'},
    ];
    expect(documentsEqual(left, right), isTrue);
    right['entries'][1]['fields'] = [
      {'name': '字段二', 'value': '值二'},
      {'name': '字段一', 'value': '值一'},
    ];
    expect(documentsEqual(left, right), isFalse);
  });

  test('不同条目可以无冲突合并', () {
    final base = document();
    final local = jsonDecode(jsonEncode(base)) as Map<String, dynamic>;
    final remote = jsonDecode(jsonEncode(base)) as Map<String, dynamic>;
    local['entries'] = [entry('local', '本机')];
    remote['entries'] = [entry('remote', '远端')];
    final result = mergeDocuments(base, local, remote);
    expect(result.conflicts, isEmpty);
    expect(
      (result.document['entries'] as List).map((item) => item['id']).toSet(),
      {'local', 'remote'},
    );
  });

  test('同一条目冲突不暴露字段值且可保留两份', () {
    final base = document()..['entries'] = [entry('same', '原始')];
    final local = jsonDecode(jsonEncode(base)) as Map<String, dynamic>;
    final remote = jsonDecode(jsonEncode(base)) as Map<String, dynamic>;
    local['entries'][0]['title'] = '本机';
    local['entries'][0]['fields'] = [
      {'name': '密码', 'value': 'local-secret'},
    ];
    remote['entries'][0]['title'] = '远端';
    remote['entries'][0]['fields'] = [
      {'name': '密码', 'value': 'remote-secret'},
    ];
    final plan = MobileSyncMergePlan(base: base, local: local, remote: remote);
    final preview = plan.preview();
    expect(preview.conflicts, hasLength(1));
    final publicConflictText = preview.conflicts
        .map(
          (item) =>
              '${item.label} ${item.changedSections.join(' ')} ${item.local} ${item.remote}',
        )
        .join(' ');
    expect(publicConflictText, isNot(contains('local-secret')));
    expect(publicConflictText, isNot(contains('remote-secret')));
    final merged = plan.resolve({'entry:same': 'both'});
    expect((merged['entries'] as List), hasLength(2));
  });
}
