part of 'mobile_sync_service.dart';

extension MobileSyncManagement on MobileSyncCoordinator {
  Future<void> cancelPending() => rust_api.syncCancelPending();

  Future<String> recoveryCode(String password) =>
      rust_api.syncRecoveryCode(password: password);

  Future<rust_models.SyncStatus> disconnect() =>
      MobileSyncGate.run(rust_api.syncDisconnect);

  Future<rust_models.SyncStatus> updateConfig({
    required String baseUrl,
    required String username,
    String? password,
    required String deviceName,
    required bool autoSync,
  }) => MobileSyncGate.run(() async {
    final currentStatus = await rust_api.syncStatus();
    final current = await rust_api.syncConnection();
    final candidatePassword = password?.isNotEmpty == true
        ? password!
        : current.password;
    final connectionChanged =
        baseUrl.trim() != current.baseUrl ||
        username.trim() != current.username ||
        candidatePassword != current.password;
    if (connectionChanged) {
      final client = MobileWebDavClient(
        baseUrl: baseUrl,
        username: username,
        password: candidatePassword,
      );
      try {
        await client.probeV2();
        final graph = await _discover(
          client,
          currentStatus.vaultId,
          currentStatus.spaceId,
          null,
        );
        if (graph.snapshots.isEmpty) {
          throw const MobileSyncException('新的 WebDAV 地址中找不到当前同步空间。');
        }
      } finally {
        client.close();
      }
    }
    return rust_api.syncUpdateConfig(
      baseUrl: baseUrl,
      username: username,
      password: password?.isNotEmpty == true ? password : null,
      deviceName: deviceName,
      autoSync: autoSync,
    );
  });

  Future<List<MobileSyncHistoryItem>> history() => MobileSyncGate.run(() async {
    final status = await rust_api.syncStatus();
    final connection = await rust_api.syncConnection();
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
      final items =
          graph.snapshots.values
              .map(
                (snapshot) => MobileSyncHistoryItem(
                  snapshotId: snapshot.info.snapshotId,
                  generation: snapshot.info.generation.toInt(),
                  createdAt: snapshot.info.createdAt,
                  deviceName: snapshot.info.deviceName,
                  frontier: graph.frontier.contains(snapshot.info.snapshotId),
                ),
              )
              .toList()
            ..sort(
              (a, b) => b.generation != a.generation
                  ? b.generation.compareTo(a.generation)
                  : b.snapshotId.compareTo(a.snapshotId),
            );
      return items.take(50).toList();
    } finally {
      client.close();
    }
  });

  Future<MobileSyncResult> restore(String snapshotId) =>
      MobileSyncGate.run(() async {
        final currentStatus = await rust_api.syncStatus();
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
            currentStatus.vaultId,
            currentStatus.spaceId,
            null,
          );
          _validateRemoteProgress(graph, local.frontier);
          final selected = graph.snapshots[snapshotId];
          if (selected == null) {
            throw const MobileSyncException('所选历史快照已经不存在，请刷新后重试。');
          }
          await _upload(
            client,
            selected.document,
            graph.frontier,
            graph.maxGeneration + 1,
            local.revision,
          );
          return const MobileSyncResult(
            action: 'restored',
            message: '历史版本已恢复并发布为最新快照。',
          );
        } finally {
          client.close();
        }
      });

  Future<MobileSyncResult> compactHistory({
    required String password,
  }) => MobileSyncGate.run(() async {
    final currentStatus = await rust_api.syncStatus();
    if (!currentStatus.configured) {
      throw const MobileSyncException('尚未配置同步。');
    }
    final connection = await rust_api.syncConnection();
    final local = await rust_api.syncLocalState();
    final localDocument = _asMap(jsonDecode(local.currentDocumentJson));
    final baseDocument = _asMap(jsonDecode(local.baseDocumentJson));
    if (!documentsEqual(localDocument, baseDocument)) {
      throw const MobileSyncException('本机还有未同步修改，请先完成同步。');
    }
    final client = MobileWebDavClient(
      baseUrl: connection.baseUrl,
      username: connection.username,
      password: connection.password,
    );
    try {
      final graph = await _discover(
        client,
        currentStatus.vaultId,
        currentStatus.spaceId,
        null,
      );
      final remote = _remoteDocument(graph, ancestorHint: baseDocument);
      if (remote.conflictPlan != null ||
          !_sameSet(local.frontier, graph.frontier) ||
          !documentsEqual(remote.document, baseDocument)) {
        throw const MobileSyncException('检测到仍有设备未同步，请在所有设备完成同步后重试。');
      }
      final plan = await rust_api.syncPrepareCompact(
        password: password,
        expectedRevision: local.revision,
      );
      await client.ensureV2Layout(plan.vaultId, plan.spaceId, plan.deviceId);
      await client.put(plan.path, Uint8List.fromList(plan.content));
      await client.verifyStored(plan.path, Uint8List.fromList(plan.content));
      await rust_api.syncCommitCompact(token: plan.token);
      try {
        await client.deleteV2Space(
          currentStatus.vaultId,
          currentStatus.spaceId,
        );
      } on MobileWebDavException {
        return const MobileSyncResult(
          action: 'compacted',
          message: '同步历史已压缩，但旧空间清理未完成，请稍后重试或手动清理。',
        );
      }
      return const MobileSyncResult(
        action: 'compacted',
        message: '同步历史已压缩；其他设备需要使用新的恢复码重新加入。',
      );
    } finally {
      client.close();
    }
  });

  Future<MobileSyncResult> rotateKey({
    required String password,
  }) => MobileSyncGate.run(() async {
    final currentStatus = await rust_api.syncStatus();
    if (!currentStatus.configured) {
      throw const MobileSyncException('尚未配置同步。');
    }
    final connection = await rust_api.syncConnection();
    final local = await rust_api.syncLocalState();
    final localDocument = _asMap(jsonDecode(local.currentDocumentJson));
    final baseDocument = _asMap(jsonDecode(local.baseDocumentJson));
    if (!documentsEqual(localDocument, baseDocument)) {
      throw const MobileSyncException('本机还有未同步修改，请先完成同步。');
    }
    final client = MobileWebDavClient(
      baseUrl: connection.baseUrl,
      username: connection.username,
      password: connection.password,
    );
    try {
      final graph = await _discover(
        client,
        currentStatus.vaultId,
        currentStatus.spaceId,
        null,
      );
      _validateRemoteProgress(graph, local.frontier);
      final remote = _remoteDocument(graph, ancestorHint: baseDocument);
      if (remote.conflictPlan != null ||
          !_sameSet(local.frontier, graph.frontier) ||
          !documentsEqual(remote.document, baseDocument)) {
        throw const MobileSyncException('检测到仍有设备未同步，请先完成同步再轮换密钥。');
      }
      final plan = await rust_api.syncPrepareRotate(
        password: password,
        expectedRevision: local.revision,
      );
      await client.ensureV2Layout(plan.vaultId, plan.spaceId, plan.deviceId);
      await client.put(plan.path, Uint8List.fromList(plan.content));
      await client.verifyStored(plan.path, Uint8List.fromList(plan.content));
      await rust_api.syncCommitRotate(token: plan.token);
      try {
        await client.deleteV2Space(
          currentStatus.vaultId,
          currentStatus.spaceId,
        );
      } on MobileWebDavException {
        return const MobileSyncResult(
          action: 'rotated',
          message: '同步密钥已轮换，但旧空间清理未完成；旧设备仍需使用新恢复码重新加入。',
        );
      }
      return const MobileSyncResult(
        action: 'rotated',
        message: '同步密钥已轮换；其他设备需要使用新恢复码重新加入。',
      );
    } finally {
      client.close();
    }
  });

  Future<rust_models.SyncStatus> deleteRemote({
    required String password,
  }) => MobileSyncGate.run(() async {
    final currentStatus = await rust_api.syncStatus();
    if (!currentStatus.configured) {
      throw const MobileSyncException('尚未配置同步。');
    }
    final connection = await rust_api.syncConnection();
    final token = await rust_api.syncPrepareRemoteDelete(password: password);
    final client = MobileWebDavClient(
      baseUrl: connection.baseUrl,
      username: connection.username,
      password: connection.password,
    );
    try {
      await client.deleteV2Space(currentStatus.vaultId, currentStatus.spaceId);
      return rust_api.syncCommitRemoteDelete(token: token);
    } finally {
      client.close();
    }
  });
}
