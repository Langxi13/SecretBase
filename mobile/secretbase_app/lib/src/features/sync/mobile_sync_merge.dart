import 'dart:convert';

class MobileSyncConflict {
  const MobileSyncConflict({
    required this.conflictId,
    required this.kind,
    required this.label,
    required this.changedSections,
    required this.local,
    required this.remote,
    required this.allowBoth,
  });

  final String conflictId;
  final String kind;
  final String label;
  final List<String> changedSections;
  final Map<String, Object?> local;
  final Map<String, Object?> remote;
  final bool allowBoth;
}

class MobileSyncMergeResult {
  const MobileSyncMergeResult({
    required this.document,
    required this.conflicts,
  });

  final Map<String, dynamic> document;
  final List<MobileSyncConflict> conflicts;
  bool get hasConflicts => conflicts.isNotEmpty;
}

class MobileSyncMergePlan {
  MobileSyncMergePlan({
    required this.base,
    required this.local,
    required this.remote,
  });

  final Map<String, dynamic> base;
  final Map<String, dynamic> local;
  final Map<String, dynamic> remote;

  MobileSyncMergeResult preview() => mergeDocuments(base, local, remote);

  Map<String, dynamic> resolve(Map<String, String> resolutions) {
    final result = _merge(base, local, remote, resolutions);
    if (result.conflicts.isNotEmpty) {
      throw StateError('仍有未处理的同步冲突');
    }
    return result.document;
  }
}

MobileSyncMergeResult mergeDocuments(
  Map<String, dynamic> base,
  Map<String, dynamic> local,
  Map<String, dynamic> remote,
) {
  return _merge(base, local, remote, const {});
}

MobileSyncMergeResult _merge(
  Map<String, dynamic> base,
  Map<String, dynamic> local,
  Map<String, dynamic> remote,
  Map<String, String> resolutions,
) {
  final merged = _cloneMap(remote);
  final conflicts = <MobileSyncConflict>[];
  final entryIds = <String>{
    ..._entryStates(base).keys,
    ..._entryStates(local).keys,
    ..._entryStates(remote).keys,
  }.toList()..sort();
  final baseStates = _entryStates(base);
  final localStates = _entryStates(local);
  final remoteStates = _entryStates(remote);
  final entries = <Map<String, dynamic>>[];
  final deleted = <Map<String, dynamic>>[];

  for (final id in entryIds) {
    final baseState = baseStates[id];
    final localState = localStates[id];
    final remoteState = remoteStates[id];
    final choice = _choose(
      baseState?.entry,
      localState?.entry,
      remoteState?.entry,
    );
    Map<String, dynamic>? selected;
    String? selectedLocation;
    if (choice.resolved) {
      selected = choice.value == null ? null : _cloneMap(choice.value!);
      selectedLocation = choice.value == null
          ? null
          : (localState?.entry == choice.value ||
                remoteState?.entry == choice.value)
          ? (localState?.entry == choice.value
                ? localState?.location
                : remoteState?.location)
          : remoteState?.location;
    } else {
      final conflictId = 'entry:$id';
      final resolution = resolutions[conflictId];
      final hasValidResolution =
          resolution == 'local' ||
          resolution == 'remote' ||
          (resolution == 'both' && localState != null && remoteState != null);
      if (!hasValidResolution) {
        conflicts.add(_entryConflict(conflictId, localState, remoteState));
      }
      if (resolution == 'both' && localState != null && remoteState != null) {
        _appendEntry(remoteState.location, remoteState.entry, entries, deleted);
        final duplicate = _cloneMap(localState.entry);
        duplicate['id'] =
            '${duplicate['id']}-${DateTime.now().microsecondsSinceEpoch}';
        duplicate['title'] = '${duplicate['title'] ?? '未命名条目'}（本机冲突副本）';
        _appendEntry(localState.location, duplicate, entries, deleted);
        continue;
      }
      final resolved = _resolveEntry(resolution, localState, remoteState);
      selected = resolved.$1;
      selectedLocation = resolved.$2;
    }
    if (selected != null && selectedLocation != null) {
      if (selectedLocation == 'deleted_entries') {
        deleted.add(selected);
      } else {
        entries.add(selected);
      }
    }
  }
  merged['entries'] = entries;
  merged['deleted_entries'] = deleted;

  for (final kind in const ['tags_meta', 'groups_meta']) {
    final baseMeta = _mapValue(base[kind]);
    final localMeta = _mapValue(local[kind]);
    final remoteMeta = _mapValue(remote[kind]);
    final result = <String, dynamic>{};
    final names = <String>{
      ...baseMeta.keys,
      ...localMeta.keys,
      ...remoteMeta.keys,
    }.toList()..sort();
    for (final name in names) {
      final choice = _choose(baseMeta[name], localMeta[name], remoteMeta[name]);
      dynamic value;
      if (choice.resolved) {
        value = choice.value;
      } else {
        final conflictId = '$kind:$name';
        final resolution = resolutions[conflictId];
        if (resolution != 'local' && resolution != 'remote') {
          conflicts.add(
            MobileSyncConflict(
              conflictId: conflictId,
              kind: kind,
              label: '${kind == 'tags_meta' ? '标签' : '密码组'}：$name',
              changedSections: const ['名称、简介、颜色或排序'],
              local: {
                'state': localMeta.containsKey(name) ? 'present' : 'absent',
              },
              remote: {
                'state': remoteMeta.containsKey(name) ? 'present' : 'absent',
              },
              allowBoth: false,
            ),
          );
        }
        value = resolution == 'local' ? localMeta[name] : remoteMeta[name];
      }
      if (value != null) result[name] = _clone(value);
    }
    merged[kind] = result;
  }

  final excluded = {'entries', 'deleted_entries', 'tags_meta', 'groups_meta'};
  final rootKeys = <String>{
    ...base.keys,
    ...local.keys,
    ...remote.keys,
  }.where((key) => !excluded.contains(key)).toList()..sort();
  for (final key in rootKeys) {
    final choice = _choose(base[key], local[key], remote[key]);
    if (choice.resolved) {
      if (choice.value == null) {
        merged.remove(key);
      } else {
        merged[key] = _clone(choice.value);
      }
    } else {
      final conflictId = 'root:$key';
      final resolution = resolutions[conflictId];
      if (resolution != 'local' && resolution != 'remote') {
        conflicts.add(
          MobileSyncConflict(
            conflictId: conflictId,
            kind: 'root',
            label: 'Vault 扩展字段：$key',
            changedSections: const ['兼容扩展数据'],
            local: const {'state': 'changed'},
            remote: const {'state': 'changed'},
            allowBoth: false,
          ),
        );
      }
      final value = resolution == 'local' ? local[key] : remote[key];
      if (value == null) {
        merged.remove(key);
      } else {
        merged[key] = _clone(value);
      }
    }
  }
  return MobileSyncMergeResult(document: merged, conflicts: conflicts);
}

void _appendEntry(
  String location,
  Map<String, dynamic> entry,
  List<Map<String, dynamic>> entries,
  List<Map<String, dynamic>> deleted,
) {
  if (location == 'deleted_entries') {
    deleted.add(_cloneMap(entry));
  } else {
    entries.add(_cloneMap(entry));
  }
}

class _EntryState {
  const _EntryState(this.location, this.entry);

  final String location;
  final Map<String, dynamic> entry;
}

Map<String, _EntryState> _entryStates(Map<String, dynamic> document) {
  final result = <String, _EntryState>{};
  for (final location in const ['entries', 'deleted_entries']) {
    final values = document[location];
    if (values is! List) continue;
    for (final raw in values) {
      if (raw is Map &&
          raw['id'] is String &&
          (raw['id'] as String).isNotEmpty) {
        result[raw['id'] as String] = _EntryState(
          location,
          _cloneMap(Map<String, dynamic>.from(raw)),
        );
      }
    }
  }
  return result;
}

MobileSyncConflict _entryConflict(
  String id,
  _EntryState? local,
  _EntryState? remote,
) {
  final localSummary = _summary(local);
  final remoteSummary = _summary(remote);
  return MobileSyncConflict(
    conflictId: id,
    kind: 'entry',
    label: localSummary['title'] as String,
    changedSections: _changedSections(local?.entry, remote?.entry),
    local: localSummary,
    remote: remoteSummary,
    allowBoth: local != null && remote != null,
  );
}

Map<String, Object?> _summary(_EntryState? state) {
  if (state == null) {
    return const {
      'state': 'absent',
      'title': '已彻底删除',
      'updated_at': '',
      'field_count': 0,
    };
  }
  return {
    'state': state.location == 'deleted_entries' ? 'deleted' : 'active',
    'title': (state.entry['title'] as String?)?.isNotEmpty == true
        ? state.entry['title']
        : '未命名条目',
    'updated_at': state.entry['updated_at'] ?? '',
    'field_count': state.entry['fields'] is List
        ? (state.entry['fields'] as List).length
        : 0,
  };
}

List<String> _changedSections(
  Map<String, dynamic>? left,
  Map<String, dynamic>? right,
) {
  if (left == null || right == null) return const ['状态'];
  const labels = {
    'title': '标题',
    'url': '网址',
    'starred': '收藏',
    'tags': '标签',
    'groups': '密码组',
    'fields': '自定义字段',
    'remarks': '备注',
    'deleted': '删除状态',
  };
  final changed = labels.entries
      .where((item) => !_deepEqual(left[item.key], right[item.key]))
      .map((item) => item.value)
      .toList();
  return changed.isEmpty ? const ['条目元数据'] : changed;
}

class _Choice {
  const _Choice(this.resolved, this.value);

  final bool resolved;
  final dynamic value;
}

_Choice _choose(dynamic base, dynamic local, dynamic remote) {
  if (_deepEqual(local, remote)) return _Choice(true, local);
  if (_deepEqual(local, base)) return _Choice(true, remote);
  if (_deepEqual(remote, base)) return _Choice(true, local);
  return const _Choice(false, null);
}

(Map<String, dynamic>?, String?) _resolveEntry(
  String? resolution,
  _EntryState? local,
  _EntryState? remote,
) {
  switch (resolution) {
    case 'local':
      return (local == null ? null : _cloneMap(local.entry), local?.location);
    case 'remote':
      return (
        remote == null ? null : _cloneMap(remote.entry),
        remote?.location,
      );
    case 'both':
      return (remote?.entry, remote?.location);
    default:
      return (remote?.entry, remote?.location);
  }
}

Map<String, dynamic> _cloneMap(Map<String, dynamic> value) =>
    Map<String, dynamic>.from(_clone(value) as Map);

dynamic _clone(dynamic value) => jsonDecode(jsonEncode(value));

Map<String, dynamic> _mapValue(dynamic value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};

bool _deepEqual(dynamic left, dynamic right) {
  if (left is num && right is num) return left == right;
  if (left is Map && right is Map) {
    if (left.length != right.length) return false;
    for (final key in left.keys) {
      if (!right.containsKey(key) || !_deepEqual(left[key], right[key])) {
        return false;
      }
    }
    return true;
  }
  if (left is List && right is List) {
    if (left.length != right.length) return false;
    for (var index = 0; index < left.length; index++) {
      if (!_deepEqual(left[index], right[index])) return false;
    }
    return true;
  }
  return left == right;
}

bool documentsEqual(Map<String, dynamic> left, Map<String, dynamic> right) =>
    _deepEqual(_canonicalDocument(left), _canonicalDocument(right));

Map<String, dynamic> _canonicalDocument(Map<String, dynamic> value) {
  final result = _cloneMap(value);
  for (final collection in const ['entries', 'deleted_entries']) {
    final raw = result[collection];
    if (raw is! List) continue;
    final items = raw.map(_clone).toList();
    items.sort((left, right) {
      final leftId = left is Map ? (left['id']?.toString() ?? '') : '';
      final rightId = right is Map ? (right['id']?.toString() ?? '') : '';
      return leftId.compareTo(rightId);
    });
    result[collection] = items;
  }
  return result;
}
