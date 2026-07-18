part of 'mobile_sync_service.dart';

class _MobileRemoteMerge {
  const _MobileRemoteMerge({
    required this.document,
    this.conflictPlan,
    this.continuation,
  });

  final Map<String, dynamic> document;
  final MobileSyncMergePlan? conflictPlan;
  final _MobileRemoteContinuation? continuation;
}

class _MobileRemoteContinuation {
  const _MobileRemoteContinuation({
    required this.ancestor,
    required this.remainingFrontier,
  });

  final Map<String, dynamic> ancestor;
  final List<String> remainingFrontier;
}

_MobileRemoteMerge _foldRemoteDocuments(
  _MobileSnapshotGraph graph, {
  required Map<String, dynamic> ancestor,
  required Map<String, dynamic> merged,
  required List<String> frontier,
}) {
  var current = _cloneMap(merged);
  for (var index = 0; index < frontier.length; index++) {
    final branch = graph.snapshots[frontier[index]];
    if (branch == null) {
      throw const MobileSyncException('远端同步历史缺少当前分支。');
    }
    final result = mergeDocuments(ancestor, current, branch.document);
    if (result.hasConflicts) {
      return _MobileRemoteMerge(
        document: result.document,
        conflictPlan: MobileSyncMergePlan(
          base: ancestor,
          local: current,
          remote: branch.document,
        ),
        continuation: _MobileRemoteContinuation(
          ancestor: _cloneMap(ancestor),
          remainingFrontier: frontier.sublist(index + 1),
        ),
      );
    }
    current = result.document;
  }
  return _MobileRemoteMerge(document: _cloneMap(current));
}

class _MobileSnapshot {
  const _MobileSnapshot({
    required this.info,
    required this.document,
    required this.path,
  });

  final rust_models.SyncSnapshotInfo info;
  final Map<String, dynamic> document;
  final List<String> path;
}

class _MobileSnapshotGraph {
  _MobileSnapshotGraph(this.snapshots) {
    final children = <String>{};
    for (final snapshot in snapshots.values) {
      children.addAll(snapshot.info.parents);
    }
    frontier = snapshots.keys.where((id) => !children.contains(id)).toList()
      ..sort();
  }

  final Map<String, _MobileSnapshot> snapshots;
  late final List<String> frontier;

  int get maxGeneration => snapshots.values
      .map((item) => item.info.generation.toInt())
      .fold(0, (a, b) => a > b ? a : b);

  Set<String> ancestors(String id) {
    final result = <String>{};
    final pending = <String>[id];
    while (pending.isNotEmpty) {
      final current = pending.removeLast();
      if (!result.add(current)) continue;
      final snapshot = snapshots[current];
      if (snapshot != null) pending.addAll(snapshot.info.parents);
    }
    return result;
  }

  _MobileSnapshot? commonAncestor(List<String> ids) {
    if (ids.isEmpty) return null;
    Set<String>? common;
    for (final id in ids) {
      common = common == null
          ? ancestors(id)
          : common.intersection(ancestors(id));
    }
    if (common == null || common.isEmpty) return null;
    return common
        .map((id) => snapshots[id])
        .whereType<_MobileSnapshot>()
        .reduce((a, b) {
          final generationOrder = a.info.generation.compareTo(
            b.info.generation,
          );
          if (generationOrder != 0) return generationOrder > 0 ? a : b;
          return a.info.snapshotId.compareTo(b.info.snapshotId) >= 0 ? a : b;
        });
  }

  void validate() {
    for (final snapshot in snapshots.values) {
      if (snapshot.info.parents.isEmpty &&
          snapshot.info.generation != BigInt.one) {
        throw const MobileSyncException('远端根快照版本无效，已停止同步。');
      }
      for (final parent in snapshot.info.parents) {
        final parentSnapshot = snapshots[parent];
        if (parentSnapshot == null ||
            parentSnapshot.info.generation >= snapshot.info.generation) {
          throw const MobileSyncException('远端同步历史关系无效，已停止同步。');
        }
      }
      if (snapshot.info.parents.isNotEmpty) {
        final expectedGeneration =
            snapshot.info.parents
                .map((parent) => snapshots[parent]!.info.generation)
                .reduce((left, right) => left > right ? left : right) +
            BigInt.one;
        if (snapshot.info.generation != expectedGeneration) {
          throw const MobileSyncException('远端同步快照版本跳跃，已停止同步。');
        }
      }
    }
    if (snapshots.isNotEmpty && frontier.isEmpty) {
      throw const MobileSyncException('远端同步历史没有当前分支。');
    }
    if (frontier.length > 32) {
      throw const MobileSyncException('远端同步历史包含过多并发分支，请先在其他设备处理冲突。');
    }
  }
}

Map<String, dynamic> _seedDocument(Map<String, dynamic> value) {
  final result = _cloneMap(value);
  result['entries'] = <dynamic>[];
  result['deleted_entries'] = <dynamic>[];
  result['tags_meta'] = <String, dynamic>{};
  result['groups_meta'] = <String, dynamic>{};
  return result;
}

Map<String, dynamic> _joinLocal(
  Map<String, dynamic> remote,
  Map<String, dynamic> local,
) {
  final result = _cloneMap(remote);
  result['entries'] = _clone(local['entries'] ?? const []);
  result['deleted_entries'] = _clone(local['deleted_entries'] ?? const []);
  result['tags_meta'] = _clone(local['tags_meta'] ?? const {});
  result['groups_meta'] = _clone(local['groups_meta'] ?? const {});
  return result;
}

List<String> _minimalParents(_MobileSnapshotGraph graph, List<String> parents) {
  final normalized = parents.toSet().toList()..sort();
  return normalized
      .where(
        (candidate) => !normalized.any(
          (other) =>
              candidate != other && graph.ancestors(other).contains(candidate),
        ),
      )
      .toList();
}

Map<String, dynamic> _asMap(dynamic value) {
  if (value is! Map) throw const MobileSyncException('同步密码库格式无效。');
  return Map<String, dynamic>.from(value);
}

Map<String, dynamic> _cloneMap(Map<String, dynamic> value) =>
    Map<String, dynamic>.from(_clone(value) as Map);
dynamic _clone(dynamic value) => jsonDecode(jsonEncode(value));

bool _sameSet(List<String> left, List<String> right) =>
    left.toSet().length == right.toSet().length &&
    left.toSet().containsAll(right);

int max(int left, int right) => left > right ? left : right;
