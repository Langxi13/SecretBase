import 'dart:convert';
import 'dart:typed_data';

import 'package:secretbase/src/features/sync/mobile_sync_merge.dart';
import 'package:secretbase/src/features/sync/mobile_sync_gate.dart';
import 'package:secretbase/src/features/sync/mobile_webdav.dart';
import 'package:secretbase/src/rust/api/mobile.dart' as rust_api;
import 'package:secretbase/src/rust/mobile/models.dart' as rust_models;

part 'mobile_sync_conflict_session.dart';
part 'mobile_sync_conflict_transport.dart';
part 'mobile_sync_graph.dart';
part 'mobile_sync_management_service.dart';

// Conflict graph types are intentionally private implementation details.
// ignore_for_file: library_private_types_in_public_api

class MobileSyncException implements Exception {
  const MobileSyncException(this.message);

  final String message;

  @override
  String toString() => message;
}

class MobileSyncResult {
  const MobileSyncResult({
    required this.action,
    required this.message,
    this.conflictSession,
  });

  final String action;
  final String message;
  final MobileSyncConflictSession? conflictSession;

  bool get hasConflicts => conflictSession != null;
}

class MobileSyncHistoryItem {
  const MobileSyncHistoryItem({
    required this.snapshotId,
    required this.generation,
    required this.createdAt,
    required this.deviceName,
    required this.frontier,
  });

  final String snapshotId;
  final int generation;
  final String createdAt;
  final String deviceName;
  final bool frontier;
}

class MobileSyncCoordinator {
  static const _maxRemoteSnapshots = 1000;
  static const _maxRemoteHistoryBytes = 256 * 1024 * 1024;
  static const _maxRemoteDocumentBytes = 256 * 1024 * 1024;

  Future<rust_models.SyncStatus> status() => rust_api.syncStatus();

  Future<rust_models.SyncConnection> connection() => rust_api.syncConnection();

  Future<void> testConnection({
    required String baseUrl,
    required String username,
    required String password,
  }) => MobileSyncGate.run(() async {
    final client = MobileWebDavClient(
      baseUrl: baseUrl,
      username: username,
      password: password,
    );
    try {
      await client.probeV2();
    } finally {
      client.close();
    }
  });

  Future<rust_models.SyncStatus> create({
    required String baseUrl,
    required String username,
    required String password,
    required String deviceName,
    bool autoSync = true,
  }) => MobileSyncGate.run(() async {
    final plan = await rust_api.syncPrepareCreate(
      baseUrl: baseUrl,
      username: username,
      password: password,
      deviceName: deviceName,
      autoSync: autoSync,
    );
    final client = MobileWebDavClient(
      baseUrl: baseUrl,
      username: username,
      password: password,
    );
    try {
      await client.ensureV2Layout(plan.vaultId, plan.spaceId, plan.deviceId);
      final root = [
        'secretbase-sync-v2',
        plan.vaultId,
        plan.spaceId,
        'snapshots',
      ];
      final existing = await client.listChildren(root);
      if (existing.isNotEmpty) {
        throw const MobileSyncException('远端已经存在快照，请改用加入同步空间。');
      }
      await client.put(plan.path, plan.content);
      await client.verifyStored(plan.path, plan.content);
      return rust_api.syncCommitCreate(token: plan.token);
    } finally {
      client.close();
    }
  });

  Future<rust_models.SyncSetupPlan> _prepareJoin({
    required String baseUrl,
    required String username,
    required String password,
    required String recoveryCode,
    required String deviceName,
    bool autoSync = true,
    bool mergeExisting = false,
  }) {
    return rust_api.syncPrepareJoin(
      baseUrl: baseUrl,
      username: username,
      password: password,
      recoveryCode: recoveryCode,
      deviceName: deviceName,
      autoSync: autoSync,
      mergeExisting: mergeExisting,
    );
  }

  Future<MobileSyncResult> join({
    required String baseUrl,
    required String username,
    required String password,
    required String recoveryCode,
    required String deviceName,
    bool autoSync = true,
    bool mergeExisting = false,
  }) => MobileSyncGate.run(() async {
    final setup = await _prepareJoin(
      baseUrl: baseUrl,
      username: username,
      password: password,
      recoveryCode: recoveryCode,
      deviceName: deviceName,
      autoSync: autoSync,
      mergeExisting: mergeExisting,
    );
    final client = MobileWebDavClient(
      baseUrl: baseUrl,
      username: username,
      password: password,
    );
    try {
      final graph = await _discover(
        client,
        setup.vaultId,
        setup.spaceId,
        setup.token,
      );
      final localJson = await rust_api.syncCurrentDocumentJson();
      final localDocument = _asMap(jsonDecode(localJson));
      final expectedRevision = (await rust_api.vaultStatus()).revision;
      final remoteResult = _remoteDocument(graph);
      if (remoteResult.conflictPlan != null) {
        return MobileSyncResult(
          action: 'conflict',
          message: '加入前发现远端分支冲突',
          conflictSession: MobileSyncConflictSession(
            plan: remoteResult.conflictPlan!,
            graph: graph,
            baseFrontier: const [],
            expectedRevision: expectedRevision,
            remoteDocument: remoteResult.document,
            joinToken: setup.token,
            remoteContinuation: remoteResult.continuation,
            localDocument: localDocument,
            mergeExisting: mergeExisting,
            joinVaultId: setup.vaultId,
            joinSpaceId: setup.spaceId,
            joinConnection: rust_models.SyncConnection(
              baseUrl: baseUrl,
              username: username,
              password: password,
              deviceName: deviceName,
              autoSync: autoSync,
            ),
          ),
        );
      }
      final remoteDocument = remoteResult.document;
      final merged = mergeExisting
          ? mergeDocuments(
              _seed(remoteDocument),
              _joinLocal(remoteDocument, localDocument),
              remoteDocument,
            )
          : MobileSyncMergeResult(
              document: remoteDocument,
              conflicts: const [],
            );
      if (merged.hasConflicts) {
        return MobileSyncResult(
          action: 'conflict',
          message: '加入前发现本机与远端冲突',
          conflictSession: MobileSyncConflictSession(
            plan: MobileSyncMergePlan(
              base: _seed(remoteDocument),
              local: _joinLocal(remoteDocument, localDocument),
              remote: remoteDocument,
            ),
            graph: graph,
            baseFrontier: const [],
            expectedRevision: expectedRevision,
            remoteDocument: remoteDocument,
            joinToken: setup.token,
            localDocument: localDocument,
            mergeExisting: mergeExisting,
            joinVaultId: setup.vaultId,
            joinSpaceId: setup.spaceId,
            joinConnection: rust_models.SyncConnection(
              baseUrl: baseUrl,
              username: username,
              password: password,
              deviceName: deviceName,
              autoSync: autoSync,
            ),
          ),
        );
      }
      final joined = await rust_api.syncCommitJoin(
        token: setup.token,
        documentJson: jsonEncode(merged.document),
        frontier: graph.frontier,
        generation: BigInt.from(graph.maxGeneration),
        expectedRevision: expectedRevision,
      );
      if (!documentsEqual(merged.document, remoteDocument) ||
          graph.frontier.length > 1) {
        final session = MobileSyncConflictSession(
          plan: MobileSyncMergePlan(
            base: remoteDocument,
            local: merged.document,
            remote: remoteDocument,
          ),
          graph: graph,
          baseFrontier: graph.frontier,
          expectedRevision: (await rust_api.vaultStatus()).revision,
          remoteDocument: remoteDocument,
          joinToken: null,
        );
        try {
          await session._uploadMerged(
            merged.document,
            graph.frontier,
            graph.maxGeneration + 1,
            joined.revision,
          );
        } catch (_) {
          await rust_api.syncCancelPending();
          return const MobileSyncResult(
            action: 'downloaded',
            message: '已加入同步空间；本机合并将在下次同步时继续上传。',
          );
        }
      }
      return const MobileSyncResult(action: 'downloaded', message: '已加入同步空间');
    } finally {
      client.close();
    }
  });

  Future<MobileSyncResult> run() => MobileSyncGate.run(() async {
    final status = await rust_api.syncStatus();
    if (!status.configured) throw const MobileSyncException('尚未配置同步。');
    final connection = await rust_api.syncConnection();
    final local = await rust_api.syncLocalState();
    final client = MobileWebDavClient(
      baseUrl: connection.baseUrl,
      username: connection.username,
      password: connection.password,
    );
    try {
      final graph = await _discover(
        client,
        status.vaultId,
        status.spaceId,
        null,
      );
      _validateRemoteProgress(graph, local.frontier);
      final localDocument = _asMap(jsonDecode(local.currentDocumentJson));
      final baseDocument = _asMap(jsonDecode(local.baseDocumentJson));
      final remoteResult = _remoteDocument(graph, ancestorHint: baseDocument);
      if (remoteResult.conflictPlan != null) {
        return MobileSyncResult(
          action: 'conflict',
          message: '发现多端修改冲突',
          conflictSession: MobileSyncConflictSession(
            plan: remoteResult.conflictPlan!,
            graph: graph,
            baseFrontier: local.frontier,
            expectedRevision: local.revision,
            remoteDocument: remoteResult.document,
            joinToken: null,
            remoteContinuation: remoteResult.continuation,
            localDocument: localDocument,
            baseDocument: baseDocument,
          ),
        );
      }
      final remoteChanged = !_sameSet(local.frontier, graph.frontier);
      final localChanged = !documentsEqual(localDocument, baseDocument);
      if (!localChanged && !remoteChanged) {
        return const MobileSyncResult(action: 'none', message: '密码库已是最新版本');
      }
      if (!localChanged && remoteChanged) {
        await rust_api.syncApplyRemote(
          documentJson: jsonEncode(remoteResult.document),
          frontier: graph.frontier,
          generation: BigInt.from(graph.maxGeneration),
          expectedRevision: local.revision,
        );
        return const MobileSyncResult(action: 'downloaded', message: '远端修改已应用');
      }
      if (localChanged && !remoteChanged) {
        await _upload(
          client,
          localDocument,
          local.frontier,
          local.generation.toInt() + 1,
          local.revision,
        );
        return const MobileSyncResult(action: 'uploaded', message: '本地修改已上传');
      }
      final merged = mergeDocuments(
        baseDocument,
        localDocument,
        remoteResult.document,
      );
      if (merged.hasConflicts) {
        return MobileSyncResult(
          action: 'conflict',
          message: '发现多端修改冲突',
          conflictSession: MobileSyncConflictSession(
            plan: MobileSyncMergePlan(
              base: baseDocument,
              local: localDocument,
              remote: remoteResult.document,
            ),
            graph: graph,
            baseFrontier: local.frontier,
            expectedRevision: local.revision,
            remoteDocument: remoteResult.document,
            joinToken: null,
            localDocument: localDocument,
            baseDocument: baseDocument,
          ),
        );
      }
      final parents = _minimalParents(graph, [
        ...local.frontier,
        ...graph.frontier,
      ]);
      await _upload(
        client,
        merged.document,
        parents,
        max(local.generation.toInt(), graph.maxGeneration) + 1,
        local.revision,
      );
      return const MobileSyncResult(action: 'merged', message: '多端修改已自动合并');
    } finally {
      client.close();
    }
  });

  Future<void> _upload(
    MobileWebDavClient client,
    Map<String, dynamic> document,
    List<String> parents,
    int generation,
    BigInt revision,
  ) async {
    final plan = await rust_api.syncPrepareUpload(
      documentJson: jsonEncode(document),
      parents: parents,
      generation: BigInt.from(generation),
      expectedRevision: revision,
    );
    await client.ensureV2Layout(plan.path[1], plan.path[2], plan.deviceId);
    await client.put(plan.path, plan.content);
    await client.verifyStored(plan.path, plan.content);
    await rust_api.syncCommitUpload(token: plan.token);
  }

  Future<_MobileSnapshotGraph> _discover(
    MobileWebDavClient client,
    String vaultId,
    String spaceId,
    String? setupToken,
  ) async {
    final root = ['secretbase-sync-v2', vaultId, spaceId, 'snapshots'];
    final devices = await client.listChildren(root);
    final snapshots = <String, _MobileSnapshot>{};
    var encryptedBytes = 0;
    var documentBytes = 0;
    final uuidPattern = RegExp(
      r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
    );
    final namePattern = RegExp(r'^([1-9][0-9]{0,18})-([0-9a-fA-F-]{36})\.sbs$');
    for (final device in devices.where((item) => item.collection)) {
      if (!uuidPattern.hasMatch(device.name)) continue;
      final devicePath = [...root, device.name];
      for (final child in await client.listChildren(devicePath)) {
        if (child.collection) continue;
        final match = namePattern.firstMatch(child.name);
        if (match == null) {
          if (child.name.endsWith('.sbs')) {
            throw const MobileSyncException('远端快照文件名无效。');
          }
          continue;
        }
        final generation = int.tryParse(match.group(1)!) ?? 0;
        final snapshotId = match.group(2)!;
        if (snapshots.containsKey(snapshotId)) {
          throw const MobileSyncException('远端包含重复快照 ID，已停止同步。');
        }
        if (snapshots.length >= _maxRemoteSnapshots) {
          throw const MobileSyncException('远端同步历史过大，请先在已连接设备上压缩历史。');
        }
        final path = [...devicePath, child.name];
        final object = await client.get(path);
        if (object == null) {
          throw const MobileSyncException('远端快照在发现后消失，请重试。');
        }
        encryptedBytes += object.content.length;
        if (encryptedBytes > _maxRemoteHistoryBytes) {
          throw const MobileSyncException('远端同步历史占用过大，请先压缩历史。');
        }
        final info = await rust_api.syncDecodeSnapshot(
          content: object.content,
          snapshotId: snapshotId,
          setupToken: setupToken,
        );
        documentBytes += utf8.encode(info.documentJson).length;
        if (documentBytes > _maxRemoteDocumentBytes) {
          throw const MobileSyncException('远端同步历史解密后过大，请先压缩历史。');
        }
        if (info.generation.toInt() != generation ||
            info.deviceId != device.name) {
          throw const MobileSyncException('远端快照文件名与内容不一致。');
        }
        snapshots[snapshotId] = _MobileSnapshot(
          info: info,
          document: _asMap(jsonDecode(info.documentJson)),
          path: path,
        );
      }
    }
    final graph = _MobileSnapshotGraph(snapshots);
    graph.validate();
    return graph;
  }

  _MobileRemoteMerge _remoteDocument(
    _MobileSnapshotGraph graph, {
    Map<String, dynamic>? ancestorHint,
  }) {
    if (graph.frontier.isEmpty) {
      throw const MobileSyncException('远端同步空间没有可用快照。');
    }
    if (graph.frontier.length == 1) {
      final snapshot = graph.snapshots[graph.frontier.first];
      if (snapshot == null) throw const MobileSyncException('远端同步历史缺少当前分支。');
      return _MobileRemoteMerge(document: _cloneMap(snapshot.document));
    }
    final common = graph.commonAncestor(graph.frontier);
    final ancestor =
        common?.document ??
        ancestorHint ??
        _seed(graph.snapshots[graph.frontier.first]!.document);
    return _foldRemoteDocuments(
      graph,
      ancestor: ancestor,
      merged: ancestor,
      frontier: graph.frontier,
    );
  }

  Map<String, dynamic> _seed(Map<String, dynamic> value) =>
      _seedDocument(value);

  void _validateRemoteProgress(
    _MobileSnapshotGraph graph,
    List<String> baseFrontier,
  ) {
    if (_sameSet(baseFrontier, graph.frontier)) return;
    for (final snapshotId in baseFrontier) {
      if (!graph.snapshots.containsKey(snapshotId) ||
          !graph.frontier.any(
            (frontier) => graph.ancestors(frontier).contains(snapshotId),
          )) {
        throw const MobileSyncException('远端同步历史已压缩、分叉或回退，请使用最新恢复码重新加入。');
      }
    }
  }
}
