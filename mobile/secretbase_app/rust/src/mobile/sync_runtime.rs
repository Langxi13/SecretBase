// V2 synchronization operations included by the mobile runtime module.

fn ensure_sync_vault_id(runtime: &mut MobileRuntime) -> Result<String, MobileError> {
    let existing = runtime
        .session()?
        .document()
        .as_value()
        .get("vault_id")
        .and_then(Value::as_str)
        .and_then(|value| Uuid::parse_str(value).ok())
        .map(|value| value.to_string());
    if let Some(vault_id) = existing {
        return Ok(vault_id);
    }
    let root = runtime.root()?.to_path_buf();
    let mut value = runtime.session()?.document().as_value().clone();
    let vault_id = Uuid::new_v4().to_string();
    value
        .as_object_mut()
        .ok_or_else(|| MobileError::new("INVALID_PAYLOAD", "Vault 根数据无效"))?
        .insert("vault_id".to_string(), Value::String(vault_id.clone()));
    let document = VaultDocument::from_value(value.clone())?;
    let encrypted = runtime.session()?.encrypted_document_bytes(&document)?;
    storage::persist_vault(&root, &encrypted, true)?;
    runtime
        .session
        .as_mut()
        .ok_or_else(|| MobileError::new("VAULT_LOCKED", "请先解锁密码库"))?
        .replace_document(value)?;
    runtime.revision = runtime.revision.saturating_add(1);
    Ok(vault_id)
}

fn parse_sync_document(value: &str) -> Result<Value, MobileError> {
    let parsed: Value = serde_json::from_str(value)
        .map_err(|_| MobileError::new("SYNC_DOCUMENT_INVALID", "同步密码库格式无效"))?;
    Ok(VaultDocument::from_value(parsed)?.into_value())
}

fn persist_sync_document(
    runtime: &mut MobileRuntime,
    value: Value,
    expected_revision: u64,
) -> Result<u64, MobileError> {
    if expected_revision != runtime.revision {
        return Err(MobileError::retryable(
            "REVISION_CONFLICT",
            "密码库已发生变化，请重新同步",
        ));
    }
    let root = runtime.root()?.to_path_buf();
    let document = VaultDocument::from_value(value.clone())?;
    let encrypted = runtime.session()?.encrypted_document_bytes(&document)?;
    storage::persist_vault(&root, &encrypted, true)?;
    runtime
        .session
        .as_mut()
        .ok_or_else(|| MobileError::new("VAULT_LOCKED", "请先解锁密码库"))?
        .replace_document(value)?;
    runtime.revision = runtime.revision.saturating_add(1);
    runtime.pending_import = None;
    runtime.pending_ai_request = None;
    runtime.pending_ai_assistant = None;
    runtime.pending_ai_preview = None;
    runtime.pending_ai_undo = None;
    Ok(runtime.revision)
}

pub fn sync_status() -> Result<SyncStatus, MobileError> {
    with_runtime(|runtime| {
        sync::status(
            runtime.root()?,
            runtime.session()?,
            "idle",
            "同步已就绪",
            "",
        )
    })
}

pub fn sync_connection() -> Result<SyncConnection, MobileError> {
    with_runtime(|runtime| {
        let config = sync::load_config(runtime.root()?, runtime.session()?)?
            .ok_or_else(|| MobileError::new("SYNC_NOT_CONFIGURED", "尚未配置同步"))?;
        Ok(sync::connection(&config))
    })
}

pub fn sync_update_config(
    base_url: String,
    username: String,
    password: Option<String>,
    device_name: String,
    auto_sync: bool,
) -> Result<SyncStatus, MobileError> {
    with_runtime(|runtime| {
        let root = runtime.root()?.to_path_buf();
        let session = runtime.session()?;
        let mut config = sync::load_config(&root, session)?
            .ok_or_else(|| MobileError::new("SYNC_NOT_CONFIGURED", "尚未配置同步"))?;
        config.base_url = base_url.trim().trim_end_matches('/').to_string();
        config.username = username.trim().to_string();
        if let Some(value) = password.filter(|value| !value.is_empty()) {
            config.password = value;
        }
        config.device_name = sync::device_name(&device_name);
        config.auto_sync = auto_sync;
        sync::save_config(&root, session, &config)?;
        runtime.pending_sync = None;
        sync::status(&root, runtime.session()?, "idle", "同步设置已更新", "")
    })
}

pub fn sync_prepare_create(
    base_url: String,
    username: String,
    password: String,
    device_name: String,
    auto_sync: bool,
) -> Result<SyncSetupPlan, MobileError> {
    with_runtime(|runtime| {
        if sync::load_config(runtime.root()?, runtime.session()?)?.is_some() {
            return Err(MobileError::new(
                "SYNC_ALREADY_CONFIGURED",
                "当前 Vault 已配置同步",
            ));
        }
        let vault_id = ensure_sync_vault_id(runtime)?;
        let config = sync::make_config(sync::NewSyncConfig {
            base_url,
            username,
            password,
            vault_id: vault_id.clone(),
            space_id: Uuid::new_v4().to_string(),
            sync_key: {
                let mut key = vec![0_u8; 32];
                use rand_core::RngCore;
                rand_core::OsRng.fill_bytes(&mut key);
                key
            },
            device_name,
            auto_sync,
        })?;
        let value = runtime.session()?.document().as_value().clone();
        let (upload, _payload) = sync::build_snapshot(&config, &value, Vec::new(), 1)?;
        runtime.pending_sync = Some(PendingSync {
            token: upload.token.clone(),
            source_revision: runtime.revision,
            kind: PendingSyncKind::Create,
            config: config.clone(),
            document: value,
            snapshot_id: upload.snapshot_id.clone(),
            generation: upload.generation,
            previous_config: None,
            previous_base: None,
        });
        Ok(SyncSetupPlan {
            token: upload.token,
            vault_id,
            space_id: config.space_id,
            device_id: upload.device_id,
            snapshot_id: upload.snapshot_id,
            generation: upload.generation,
            path: upload.path,
            content: upload.content,
            recovery_code: String::new(),
        })
    })
}

pub fn sync_commit_create(token: String) -> Result<SyncStatus, MobileError> {
    with_runtime(|runtime| {
        let valid = runtime.pending_sync.as_ref().is_some_and(|pending| {
            pending.token == token
                && matches!(pending.kind, PendingSyncKind::Create)
                && pending.source_revision == runtime.revision
        });
        if !valid {
            return Err(MobileError::retryable(
                "SYNC_SETUP_EXPIRED",
                "密码库已变化，请重新创建同步空间",
            ));
        }
        let pending = runtime
            .pending_sync
            .take()
            .ok_or_else(|| MobileError::new("SYNC_SETUP_EXPIRED", "同步创建计划已失效"))?;
        let root = runtime.root()?.to_path_buf();
        let session = runtime.session()?;
        let base = sync::base_for(
            &pending.config,
            vec![pending.snapshot_id],
            pending.generation,
            pending.document,
        );
        if let Err(error) = sync::save_config(&root, session, &pending.config)
            .and_then(|_| sync::save_base(&root, session, &base))
        {
            let _ = sync::clear(&root);
            return Err(error);
        }
        sync::status(&root, session, "synced", "同步空间已创建", "")
    })
}

fn prepare_sync_space_reset(
    runtime: &mut MobileRuntime,
    password: String,
    expected_revision: u64,
    kind: PendingSyncKind,
) -> Result<SyncSetupPlan, MobileError> {
    verify_master_password(runtime, password)?;
    if expected_revision != runtime.revision {
        return Err(MobileError::retryable(
            "REVISION_CONFLICT",
            "密码库已变化，请重新检查同步状态",
        ));
    }
    let root = runtime.root()?.to_path_buf();
    let session = runtime.session()?;
    let old_config = sync::load_config(&root, session)?
        .ok_or_else(|| MobileError::new("SYNC_NOT_CONFIGURED", "尚未配置同步"))?;
    let old_base = sync::load_base(&root, session)?
        .ok_or_else(|| MobileError::new("SYNC_BASE_MISSING", "同步基线缺失，请先同步"))?;
    let value = session.document().as_value().clone();
    if !sync::documents_equal(&value, &old_base.document) {
        return Err(MobileError::new(
            "SYNC_LOCAL_CHANGES",
            "本机还有未同步修改，请先完成同步",
        ));
    }
    let mut new_config = old_config.clone();
    new_config.space_id = Uuid::new_v4().to_string();
    if kind == PendingSyncKind::Rotate {
        let mut key = vec![0_u8; 32];
        use rand_core::RngCore;
        rand_core::OsRng.fill_bytes(&mut key);
        new_config.sync_key = key;
    }
    let (upload, _payload) = sync::build_snapshot(&new_config, &value, Vec::new(), 1)?;
    runtime.pending_sync = Some(PendingSync {
        token: upload.token.clone(),
        source_revision: expected_revision,
        kind,
        config: new_config.clone(),
        document: value,
        snapshot_id: upload.snapshot_id.clone(),
        generation: upload.generation,
        previous_config: Some(old_config),
        previous_base: Some(old_base),
    });
    Ok(SyncSetupPlan {
        token: upload.token,
        vault_id: new_config.vault_id,
        space_id: new_config.space_id,
        device_id: upload.device_id,
        snapshot_id: upload.snapshot_id,
        generation: upload.generation,
        path: upload.path,
        content: upload.content,
        recovery_code: String::new(),
    })
}

fn commit_sync_space_reset(
    runtime: &mut MobileRuntime,
    token: String,
    kind: PendingSyncKind,
    message: &str,
) -> Result<SyncStatus, MobileError> {
    let valid = runtime.pending_sync.as_ref().is_some_and(|pending| {
        pending.token == token
            && pending.kind == kind
            && pending.source_revision == runtime.revision
    });
    if !valid {
        return Err(MobileError::retryable(
            "SYNC_SETUP_EXPIRED",
            "密码库已变化，请重新检查同步状态",
        ));
    }
    let pending = runtime
        .pending_sync
        .take()
        .ok_or_else(|| MobileError::new("SYNC_SETUP_EXPIRED", "同步重置计划已失效"))?;
    let root = runtime.root()?.to_path_buf();
    let session = runtime.session()?;
    if let Err(error) = sync::save_config(&root, session, &pending.config).and_then(|_| {
        sync::save_base(
            &root,
            session,
            &sync::base_for(
                &pending.config,
                vec![pending.snapshot_id.clone()],
                pending.generation,
                pending.document.clone(),
            ),
        )
    }) {
        let restored = pending
            .previous_config
            .as_ref()
            .ok_or_else(|| MobileError::new("SYNC_STATE_INVALID", "旧同步设置缺失"))
            .and_then(|previous| sync::save_config(&root, session, previous))
            .and_then(|_| {
                pending
                    .previous_base
                    .as_ref()
                    .ok_or_else(|| MobileError::new("SYNC_STATE_INVALID", "旧同步基线缺失"))
                    .and_then(|previous| sync::save_base(&root, session, previous))
            });
        if restored.is_err() {
            return Err(MobileError::new(
                "SYNC_ROLLBACK_FAILED",
                "同步设置更新失败，且旧设置无法恢复；请先导出备份并重新配置同步",
            ));
        }
        return Err(error);
    }
    sync::status(&root, session, "synced", message, "")
}

pub fn sync_prepare_compact(
    password: String,
    expected_revision: u64,
) -> Result<SyncSetupPlan, MobileError> {
    with_runtime(|runtime| {
        prepare_sync_space_reset(
            runtime,
            password,
            expected_revision,
            PendingSyncKind::Compact,
        )
    })
}

pub fn sync_commit_compact(token: String) -> Result<SyncStatus, MobileError> {
    with_runtime(|runtime| {
        commit_sync_space_reset(
            runtime,
            token,
            PendingSyncKind::Compact,
            "同步历史已压缩；其他设备需要重新加入",
        )
    })
}

pub fn sync_prepare_rotate(
    password: String,
    expected_revision: u64,
) -> Result<SyncSetupPlan, MobileError> {
    with_runtime(|runtime| {
        prepare_sync_space_reset(
            runtime,
            password,
            expected_revision,
            PendingSyncKind::Rotate,
        )
    })
}

pub fn sync_commit_rotate(token: String) -> Result<SyncStatus, MobileError> {
    with_runtime(|runtime| {
        commit_sync_space_reset(
            runtime,
            token,
            PendingSyncKind::Rotate,
            "同步密钥已轮换；其他设备需要使用新恢复码重新加入",
        )
    })
}

pub fn sync_prepare_join(
    base_url: String,
    username: String,
    password: String,
    recovery_code: String,
    device_name: String,
    auto_sync: bool,
    merge_existing: bool,
) -> Result<SyncSetupPlan, MobileError> {
    with_runtime(|runtime| {
        if sync::load_config(runtime.root()?, runtime.session()?)?.is_some() {
            return Err(MobileError::new(
                "SYNC_ALREADY_CONFIGURED",
                "当前 Vault 已配置同步",
            ));
        }
        let local = runtime.session()?.document().as_value().clone();
        if sync::document_has_content(&local) && !merge_existing {
            return Err(MobileError::new(
                "LOCAL_VAULT_NOT_EMPTY",
                "当前密码库已有数据，请明确勾选合并现有数据",
            ));
        }
        let (vault_id, space_id, key) = sync::parse_recovery(&recovery_code)?;
        let config = sync::make_config(sync::NewSyncConfig {
            base_url,
            username,
            password,
            vault_id: vault_id.clone(),
            space_id: space_id.clone(),
            sync_key: key,
            device_name,
            auto_sync,
        })?;
        let token = Uuid::new_v4().to_string();
        runtime.pending_sync = Some(PendingSync {
            token: token.clone(),
            source_revision: runtime.revision,
            kind: PendingSyncKind::Join,
            config: config.clone(),
            document: local,
            snapshot_id: String::new(),
            generation: 0,
            previous_config: None,
            previous_base: None,
        });
        Ok(SyncSetupPlan {
            token,
            vault_id,
            space_id,
            device_id: config.device_id,
            snapshot_id: String::new(),
            generation: 0,
            path: Vec::new(),
            content: Vec::new(),
            recovery_code: String::new(),
        })
    })
}

pub fn sync_decode_snapshot(
    content: Vec<u8>,
    snapshot_id: String,
    setup_token: Option<String>,
) -> Result<SyncSnapshotInfo, MobileError> {
    with_runtime(|runtime| {
        let pending_config = setup_token.as_ref().and_then(|token| {
            runtime
                .pending_sync
                .as_ref()
                .filter(|pending| pending.token == *token)
                .map(|pending| pending.config.clone())
        });
        let config = match pending_config {
            Some(value) => value,
            None => sync::load_config(runtime.root()?, runtime.session()?)?
                .ok_or_else(|| MobileError::new("SYNC_NOT_CONFIGURED", "尚未配置同步"))?,
        };
        sync::decode_snapshot(&config, &content, &snapshot_id).map(|item| item.0)
    })
}

pub fn sync_commit_join(
    token: String,
    document_json: String,
    frontier: Vec<String>,
    generation: u64,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    with_runtime(|runtime| {
        let valid = runtime.pending_sync.as_ref().is_some_and(|pending| {
            pending.token == token
                && matches!(pending.kind, PendingSyncKind::Join)
                && pending.source_revision == runtime.revision
                && expected_revision == runtime.revision
        });
        if !valid {
            return Err(MobileError::retryable(
                "SYNC_SETUP_EXPIRED",
                "密码库已变化，请重新加入同步空间",
            ));
        }
        let pending = runtime
            .pending_sync
            .take()
            .ok_or_else(|| MobileError::new("SYNC_SETUP_EXPIRED", "同步加入计划已失效"))?;
        let value = parse_sync_document(&document_json)?;
        if value.get("vault_id").and_then(Value::as_str) != Some(pending.config.vault_id.as_str()) {
            return Err(MobileError::new(
                "SYNC_DOCUMENT_INVALID",
                "远端 Vault 身份不一致",
            ));
        }
        let original = pending.document.clone();
        let revision = persist_sync_document(runtime, value.clone(), expected_revision)?;
        let root = runtime.root()?.to_path_buf();
        let session = runtime.session()?;
        let base = sync::base_for(&pending.config, frontier, generation, value);
        if let Err(error) = sync::save_config(&root, session, &pending.config)
            .and_then(|_| sync::save_base(&root, session, &base))
        {
            let _ = sync::clear(&root);
            if persist_sync_document(runtime, original, revision).is_err() {
                return Err(MobileError::new(
                    "SYNC_ROLLBACK_FAILED",
                    "加入同步失败，且本机密码库无法恢复；请立即导出当前加密备份",
                ));
            }
            return Err(error);
        }
        Ok(OperationResult {
            revision,
            message: "已加入加密快照同步空间".to_string(),
        })
    })
}

pub fn sync_local_state() -> Result<SyncLocalState, MobileError> {
    with_runtime(|runtime| {
        let config = sync::load_config(runtime.root()?, runtime.session()?)?
            .ok_or_else(|| MobileError::new("SYNC_NOT_CONFIGURED", "尚未配置同步"))?;
        let base = sync::load_base(runtime.root()?, runtime.session()?)?
            .ok_or_else(|| MobileError::new("SYNC_BASE_MISSING", "同步基线缺失，请重新加入"))?;
        if base.space_id != config.space_id {
            return Err(MobileError::new(
                "SYNC_BASE_INVALID",
                "同步基线不属于当前空间",
            ));
        }
        Ok(SyncLocalState {
            revision: runtime.revision,
            current_document_json: serde_json::to_string(runtime.session()?.document().as_value())
                .map_err(|_| MobileError::new("SYNC_DOCUMENT_INVALID", "本机密码库无法编码"))?,
            base_document_json: serde_json::to_string(&base.document)
                .map_err(|_| MobileError::new("SYNC_BASE_INVALID", "同步基线无法编码"))?,
            frontier: base.frontier,
            generation: base.generation,
        })
    })
}

pub fn sync_current_document_json() -> Result<String, MobileError> {
    with_runtime(|runtime| {
        serde_json::to_string(runtime.session()?.document().as_value())
            .map_err(|_| MobileError::new("SYNC_DOCUMENT_INVALID", "本机密码库无法编码"))
    })
}

pub fn sync_prepare_upload(
    document_json: Option<String>,
    parents: Vec<String>,
    generation: u64,
    expected_revision: u64,
) -> Result<SyncUploadPlan, MobileError> {
    with_runtime(|runtime| {
        if expected_revision != runtime.revision {
            return Err(MobileError::retryable(
                "REVISION_CONFLICT",
                "密码库已变化，请重新同步",
            ));
        }
        let config = sync::load_config(runtime.root()?, runtime.session()?)?
            .ok_or_else(|| MobileError::new("SYNC_NOT_CONFIGURED", "尚未配置同步"))?;
        let value = match document_json {
            Some(raw) => parse_sync_document(&raw)?,
            None => runtime.session()?.document().as_value().clone(),
        };
        if value.get("vault_id").and_then(Value::as_str) != Some(config.vault_id.as_str()) {
            return Err(MobileError::new(
                "SYNC_DOCUMENT_INVALID",
                "同步文档与当前 Vault 不一致",
            ));
        }
        let (upload, _payload) = sync::build_snapshot(&config, &value, parents, generation)?;
        runtime.pending_sync = Some(PendingSync {
            token: upload.token.clone(),
            source_revision: expected_revision,
            kind: PendingSyncKind::Upload,
            config,
            document: value,
            snapshot_id: upload.snapshot_id.clone(),
            generation,
            previous_config: None,
            previous_base: None,
        });
        Ok(upload)
    })
}

pub fn sync_commit_upload(token: String) -> Result<OperationResult, MobileError> {
    with_runtime(|runtime| {
        let valid = runtime.pending_sync.as_ref().is_some_and(|pending| {
            pending.token == token
                && matches!(pending.kind, PendingSyncKind::Upload)
                && pending.source_revision == runtime.revision
        });
        if !valid {
            return Err(MobileError::retryable(
                "SYNC_UPLOAD_EXPIRED",
                "密码库已变化，请重新同步",
            ));
        }
        let pending = runtime
            .pending_sync
            .take()
            .ok_or_else(|| MobileError::new("SYNC_UPLOAD_EXPIRED", "同步上传计划已失效"))?;
        let current = runtime.session()?.document().as_value().clone();
        let revision = if !sync::documents_equal(&current, &pending.document) {
            persist_sync_document(runtime, pending.document.clone(), pending.source_revision)?
        } else {
            runtime.revision
        };
        let root = runtime.root()?.to_path_buf();
        let session = runtime.session()?;
        let result = sync::save_base(
            &root,
            session,
            &sync::base_for(
                &pending.config,
                vec![pending.snapshot_id],
                pending.generation,
                pending.document,
            ),
        );
        if let Err(error) = result {
            if revision != runtime.revision
                && persist_sync_document(runtime, current, revision).is_err()
            {
                return Err(MobileError::new(
                    "SYNC_ROLLBACK_FAILED",
                    "同步快照已上传，但本机状态无法恢复；请立即导出当前加密备份",
                ));
            }
            return Err(error);
        }
        Ok(OperationResult {
            revision,
            message: "同步快照已提交".to_string(),
        })
    })
}

pub fn sync_apply_remote(
    document_json: String,
    frontier: Vec<String>,
    generation: u64,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    with_runtime(|runtime| {
        let config = sync::load_config(runtime.root()?, runtime.session()?)?
            .ok_or_else(|| MobileError::new("SYNC_NOT_CONFIGURED", "尚未配置同步"))?;
        let value = parse_sync_document(&document_json)?;
        if value.get("vault_id").and_then(Value::as_str) != Some(config.vault_id.as_str()) {
            return Err(MobileError::new(
                "SYNC_DOCUMENT_INVALID",
                "远端 Vault 身份不一致",
            ));
        }
        let original = runtime.session()?.document().as_value().clone();
        let revision = persist_sync_document(runtime, value.clone(), expected_revision)?;
        let root = runtime.root()?.to_path_buf();
        let session = runtime.session()?;
        let result = sync::save_base(
            &root,
            session,
            &sync::base_for(&config, frontier, generation, value),
        );
        if let Err(error) = result {
            if persist_sync_document(runtime, original, revision).is_err() {
                return Err(MobileError::new(
                    "SYNC_ROLLBACK_FAILED",
                    "应用远端修改失败，且本机密码库无法恢复；请立即导出当前加密备份",
                ));
            }
            return Err(error);
        }
        Ok(OperationResult {
            revision,
            message: "远端修改已应用".to_string(),
        })
    })
}

pub fn sync_recovery_code(password: String) -> Result<String, MobileError> {
    with_runtime(|runtime| {
        verify_master_password(runtime, password)?;
        let config = sync::load_config(runtime.root()?, runtime.session()?)?
            .ok_or_else(|| MobileError::new("SYNC_NOT_CONFIGURED", "尚未配置同步"))?;
        sync::recovery_code(&config)
    })
}

pub fn sync_prepare_remote_delete(password: String) -> Result<String, MobileError> {
    with_runtime(|runtime| {
        verify_master_password(runtime, password)?;
        let root = runtime.root()?.to_path_buf();
        let session = runtime.session()?;
        let config = sync::load_config(&root, session)?
            .ok_or_else(|| MobileError::new("SYNC_NOT_CONFIGURED", "尚未配置同步"))?;
        let token = Uuid::new_v4().to_string();
        runtime.pending_sync = Some(PendingSync {
            token: token.clone(),
            source_revision: runtime.revision,
            kind: PendingSyncKind::DeleteRemote,
            config,
            document: session.document().as_value().clone(),
            snapshot_id: String::new(),
            generation: 0,
            previous_config: None,
            previous_base: None,
        });
        Ok(token)
    })
}

pub fn sync_commit_remote_delete(token: String) -> Result<SyncStatus, MobileError> {
    with_runtime(|runtime| {
        let valid = runtime.pending_sync.as_ref().is_some_and(|pending| {
            pending.token == token
                && pending.kind == PendingSyncKind::DeleteRemote
                && pending.source_revision == runtime.revision
        });
        if !valid {
            return Err(MobileError::retryable(
                "SYNC_SETUP_EXPIRED",
                "密码库已变化，请重新确认删除远端同步数据",
            ));
        }
        sync::clear(runtime.root()?)?;
        runtime.pending_sync = None;
        sync::status(
            runtime.root()?,
            runtime.session()?,
            "disabled",
            "远端同步数据已删除",
            "",
        )
    })
}

pub fn sync_disconnect() -> Result<SyncStatus, MobileError> {
    with_runtime(|runtime| {
        sync::clear(runtime.root()?)?;
        runtime.pending_sync = None;
        sync::status(
            runtime.root()?,
            runtime.session()?,
            "disabled",
            "已断开本机同步",
            "",
        )
    })
}

pub fn sync_cancel_pending() -> Result<(), MobileError> {
    with_runtime(|runtime| {
        runtime.pending_sync = None;
        Ok(())
    })
}
