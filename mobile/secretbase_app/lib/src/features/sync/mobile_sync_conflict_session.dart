part of 'mobile_sync_service.dart';

// Conflict graph types remain private to the sync library.
// ignore_for_file: library_private_types_in_public_api

class MobileSyncConflictSession {
  MobileSyncConflictSession({
    required this.plan,
    required this.graph,
    required this.baseFrontier,
    required this.expectedRevision,
    required this.remoteDocument,
    required this.joinToken,
    this.remoteContinuation,
    this.localDocument,
    this.baseDocument,
    this.mergeExisting = false,
    this.joinVaultId,
    this.joinSpaceId,
    this.joinConnection,
  });

  final MobileSyncMergePlan plan;
  final _MobileSnapshotGraph graph;
  final List<String> baseFrontier;
  final BigInt expectedRevision;
  final Map<String, dynamic> remoteDocument;
  final String? joinToken;
  final _MobileRemoteContinuation? remoteContinuation;
  final Map<String, dynamic>? localDocument;
  final Map<String, dynamic>? baseDocument;
  final bool mergeExisting;
  final String? joinVaultId;
  final String? joinSpaceId;
  final rust_models.SyncConnection? joinConnection;

  List<MobileSyncConflict> get conflicts => plan.preview().conflicts;

  Future<MobileSyncResult> resolve(Map<String, String> resolutions) =>
      MobileSyncGate.run(() async {
        await _ensureFresh();
        var merged = plan.resolve(resolutions);
        final continuation = remoteContinuation;
        if (continuation != null) {
          final next = _foldRemoteDocuments(
            graph,
            ancestor: continuation.ancestor,
            merged: merged,
            frontier: continuation.remainingFrontier,
          );
          if (next.conflictPlan != null) {
            return MobileSyncResult(
              action: 'conflict',
              message: '当前选择已保存，请继续处理剩余分支冲突',
              conflictSession: MobileSyncConflictSession(
                plan: next.conflictPlan!,
                graph: graph,
                baseFrontier: baseFrontier,
                expectedRevision: expectedRevision,
                remoteDocument: next.document,
                joinToken: joinToken,
                remoteContinuation: next.continuation,
                localDocument: localDocument,
                baseDocument: baseDocument,
                mergeExisting: mergeExisting,
                joinVaultId: joinVaultId,
                joinSpaceId: joinSpaceId,
                joinConnection: joinConnection,
              ),
            );
          }
          return _finishRemoteFold(next.document);
        }

        return _commitResolved(merged);
      });

  Future<MobileSyncResult> _finishRemoteFold(
    Map<String, dynamic> remoteMerged,
  ) async {
    if (joinToken != null) {
      late Map<String, dynamic> merged;
      final local = localDocument;
      if (local == null) {
        throw const MobileSyncException('加入同步的本机上下文已失效，请重新加入。');
      }
      if (mergeExisting) {
        final localMerge = mergeDocuments(
          _seedDocument(remoteMerged),
          _joinLocal(remoteMerged, local),
          remoteMerged,
        );
        if (localMerge.hasConflicts) {
          return MobileSyncResult(
            action: 'conflict',
            message: '远端分支已处理，请继续选择本机与远端冲突',
            conflictSession: MobileSyncConflictSession(
              plan: MobileSyncMergePlan(
                base: _seedDocument(remoteMerged),
                local: _joinLocal(remoteMerged, local),
                remote: remoteMerged,
              ),
              graph: graph,
              baseFrontier: baseFrontier,
              expectedRevision: expectedRevision,
              remoteDocument: remoteMerged,
              joinToken: joinToken,
              localDocument: local,
              mergeExisting: true,
              joinVaultId: joinVaultId,
              joinSpaceId: joinSpaceId,
              joinConnection: joinConnection,
            ),
          );
        }
        merged = localMerge.document;
      } else {
        merged = remoteMerged;
      }
      return _commitResolved(merged, forceUpload: true);
    }

    final local = localDocument;
    final base = baseDocument;
    if (local == null || base == null) {
      throw const MobileSyncException('同步冲突上下文已失效，请重新同步。');
    }
    if (documentsEqual(local, base)) {
      await _uploadMerged(
        remoteMerged,
        graph.frontier,
        graph.maxGeneration + 1,
        expectedRevision,
      );
      return const MobileSyncResult(action: 'merged', message: '远端分支冲突已处理并发布');
    }
    final localMerge = mergeDocuments(base, local, remoteMerged);
    if (localMerge.hasConflicts) {
      return MobileSyncResult(
        action: 'conflict',
        message: '远端分支已处理，请继续选择本机与远端冲突',
        conflictSession: MobileSyncConflictSession(
          plan: MobileSyncMergePlan(
            base: base,
            local: local,
            remote: remoteMerged,
          ),
          graph: graph,
          baseFrontier: baseFrontier,
          expectedRevision: expectedRevision,
          remoteDocument: remoteMerged,
          joinToken: null,
          localDocument: local,
          baseDocument: base,
        ),
      );
    }
    final parents = _minimalParents(graph, [
      ...baseFrontier,
      ...graph.frontier,
    ]);
    await _uploadMerged(
      localMerge.document,
      parents,
      graph.maxGeneration + 1,
      expectedRevision,
    );
    return const MobileSyncResult(action: 'merged', message: '多端修改已自动合并');
  }

  Future<MobileSyncResult> _commitResolved(
    Map<String, dynamic> merged, {
    bool forceUpload = false,
  }) async {
    if (joinToken != null) {
      final joined = await rust_api.syncCommitJoin(
        token: joinToken!,
        documentJson: jsonEncode(merged),
        frontier: graph.frontier,
        generation: BigInt.from(graph.maxGeneration),
        expectedRevision: expectedRevision,
      );
      if (forceUpload ||
          !documentsEqual(merged, remoteDocument) ||
          graph.frontier.length > 1) {
        try {
          await _uploadMerged(
            merged,
            graph.frontier,
            graph.maxGeneration + 1,
            joined.revision,
          );
        } catch (_) {
          await rust_api.syncCancelPending();
          return const MobileSyncResult(
            action: 'downloaded',
            message: '已加入同步空间；合并快照将在下次同步时继续上传。',
          );
        }
      }
    } else {
      final parents = _minimalParents(graph, [
        ...baseFrontier,
        ...graph.frontier,
      ]);
      await _uploadMerged(
        merged,
        parents,
        graph.maxGeneration + 1,
        expectedRevision,
      );
    }
    return const MobileSyncResult(action: 'merged', message: '同步冲突已处理');
  }
}
