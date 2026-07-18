part of 'mobile_sync_service.dart';

extension _MobileSyncConflictTransport on MobileSyncConflictSession {
  Future<void> _ensureFresh() async {
    final vault = await rust_api.vaultStatus();
    if (vault.revision != expectedRevision) {
      throw const MobileSyncException('密码库已发生变化，请重新同步后处理冲突。');
    }
    late final rust_models.SyncConnection connection;
    late final String vaultId;
    late final String spaceId;
    if (joinToken != null) {
      connection =
          joinConnection ??
          (throw const MobileSyncException('加入同步的连接上下文已失效，请重新加入。'));
      vaultId =
          joinVaultId ??
          (throw const MobileSyncException('加入同步的 Vault 上下文已失效，请重新加入。'));
      spaceId =
          joinSpaceId ??
          (throw const MobileSyncException('加入同步的空间上下文已失效，请重新加入。'));
    } else {
      final status = await rust_api.syncStatus();
      if (!status.configured) {
        throw const MobileSyncException('同步配置已变化，请重新同步。');
      }
      connection = await rust_api.syncConnection();
      vaultId = status.vaultId;
      spaceId = status.spaceId;
    }
    final client = MobileWebDavClient(
      baseUrl: connection.baseUrl,
      username: connection.username,
      password: connection.password,
    );
    try {
      final current = await MobileSyncCoordinator()._discover(
        client,
        vaultId,
        spaceId,
        joinToken,
      );
      if (!_sameSet(current.frontier, graph.frontier)) {
        throw const MobileSyncException('远端同步分支已变化，请重新同步后处理冲突。');
      }
    } finally {
      client.close();
    }
  }

  Future<void> _uploadMerged(
    Map<String, dynamic> document,
    List<String> parents,
    int generation,
    BigInt expectedRevision,
  ) async {
    final plan = await rust_api.syncPrepareUpload(
      documentJson: jsonEncode(document),
      parents: parents,
      generation: BigInt.from(generation),
      expectedRevision: expectedRevision,
    );
    final connection = await rust_api.syncConnection();
    final client = MobileWebDavClient(
      baseUrl: connection.baseUrl,
      username: connection.username,
      password: connection.password,
    );
    try {
      await client.ensureV2Layout(plan.path[1], plan.path[2], plan.deviceId);
      await client.put(plan.path, plan.content);
      await client.verifyStored(plan.path, plan.content);
      await rust_api.syncCommitUpload(token: plan.token);
    } finally {
      client.close();
    }
  }
}
