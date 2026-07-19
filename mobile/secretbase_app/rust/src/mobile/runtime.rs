use std::{
    fs,
    path::{Path, PathBuf},
    sync::{Mutex, OnceLock},
};

use chrono::{SecondsFormat, Utc};
use secretbase_vault_core::{VaultDocument, VaultSession};
use serde_json::Value;
use uuid::Uuid;
use zeroize::Zeroizing;

use super::{
    ai::{self, PendingAiPreview, PendingAiRequest, PendingAssistantRequest},
    autofill, document,
    error::MobileError,
    models::{
        AiApplyResult, AiAssistantRequestPlan, AiAssistantTurnResult, AiConversation,
        AiConversationSummary, AiHttpRequest, AiPreview, AiRequestPlan, AiStatus, AiUndoState,
        EntryDraft, EntryPage, EntryRecord, ImportPreview, OperationResult, RecoverySnapshot,
        SyncConnection, SyncLocalState, SyncSetupPlan, SyncSnapshotInfo, SyncStatus,
        SyncUploadPlan, TaxonomyRecord, VaultStatus,
    },
    storage, sync,
};

struct PendingImport {
    token: String,
    source_revision: u64,
    session: VaultSession,
    preview: ImportPreview,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum PendingSyncKind {
    Create,
    Join,
    Upload,
    Compact,
    Rotate,
    DeleteRemote,
}

#[derive(Clone)]
struct PendingSync {
    token: String,
    source_revision: u64,
    kind: PendingSyncKind,
    config: sync::SyncConfig,
    document: Value,
    snapshot_id: String,
    generation: u64,
    previous_config: Option<sync::SyncConfig>,
    previous_base: Option<sync::SyncBase>,
}

#[derive(Debug, Clone)]
struct PendingAiUndo {
    token: String,
    source_revision: u64,
    document: Value,
    conversation_id: Option<String>,
    applied_count: u32,
    message: String,
}

#[derive(Default)]
struct MobileRuntime {
    root: Option<PathBuf>,
    session: Option<VaultSession>,
    revision: u64,
    pending_import: Option<PendingImport>,
    pending_ai_request: Option<PendingAiRequest>,
    pending_ai_assistant: Option<PendingAssistantRequest>,
    pending_ai_preview: Option<PendingAiPreview>,
    pending_ai_undo: Option<PendingAiUndo>,
    pending_sync: Option<PendingSync>,
}

static RUNTIME: OnceLock<Mutex<MobileRuntime>> = OnceLock::new();

fn global_runtime() -> &'static Mutex<MobileRuntime> {
    RUNTIME.get_or_init(|| Mutex::new(MobileRuntime::default()))
}

fn with_runtime<T>(
    callback: impl FnOnce(&mut MobileRuntime) -> Result<T, MobileError>,
) -> Result<T, MobileError> {
    let mut runtime = global_runtime()
        .lock()
        .map_err(|_| MobileError::retryable("RUNTIME_BUSY", "密码库运行状态暂时不可用"))?;
    callback(&mut runtime)
}

fn now() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

impl MobileRuntime {
    fn root(&self) -> Result<&Path, MobileError> {
        self.root
            .as_deref()
            .ok_or_else(|| MobileError::new("RUNTIME_NOT_INITIALIZED", "移动运行环境尚未初始化"))
    }

    fn session(&self) -> Result<&VaultSession, MobileError> {
        self.session
            .as_ref()
            .ok_or_else(|| MobileError::new("VAULT_LOCKED", "请先解锁密码库"))
    }

    fn transaction(
        &mut self,
        expected_revision: u64,
        mutation: impl FnOnce(&mut Value) -> Result<String, MobileError>,
    ) -> Result<OperationResult, MobileError> {
        if expected_revision != self.revision {
            return Err(MobileError::retryable(
                "REVISION_CONFLICT",
                "密码库已发生变化，请刷新后重试",
            ));
        }
        let root_path = self.root()?.to_path_buf();
        let session = self.session()?;
        let mut candidate = session.document().as_value().clone();
        let message = mutation(&mut candidate)?;
        let document = VaultDocument::from_value(candidate.clone())?;
        let encrypted = session.encrypted_document_bytes(&document)?;
        storage::persist_vault(&root_path, &encrypted, true)?;
        self.session
            .as_mut()
            .ok_or_else(|| MobileError::new("VAULT_LOCKED", "请先解锁密码库"))?
            .replace_document(candidate)?;
        self.revision = self.revision.saturating_add(1);
        self.pending_import = None;
        self.pending_ai_request = None;
        self.pending_ai_assistant = None;
        self.pending_ai_preview = None;
        self.pending_ai_undo = None;
        self.pending_sync = None;
        Ok(OperationResult {
            revision: self.revision,
            message,
        })
    }
}

fn verify_master_password(runtime: &MobileRuntime, password: String) -> Result<(), MobileError> {
    if password.is_empty() {
        return Err(MobileError::new("VALIDATION_FAILED", "请输入当前主密码"));
    }
    let password = Zeroizing::new(password);
    let content = storage::read_vault(runtime.root()?)?;
    VaultSession::unlock(password.as_str(), &content)
        .map(|_| ())
        .map_err(|_| MobileError::new("AUTH_FAILED", "主密码错误"))
}

pub fn initialize_runtime(data_root: String) -> Result<VaultStatus, MobileError> {
    with_runtime(|runtime| {
        let root = PathBuf::from(data_root);
        if !root.is_absolute() {
            return Err(MobileError::new(
                "INVALID_PATH",
                "移动数据目录必须是绝对路径",
            ));
        }
        fs::create_dir_all(&root)?;
        if runtime.session.is_some() && runtime.root.as_ref() != Some(&root) {
            return Err(MobileError::new(
                "RUNTIME_ACTIVE",
                "密码库已解锁，不能切换数据目录",
            ));
        }
        runtime.root = Some(root);
        runtime.pending_ai_request = None;
        runtime.pending_ai_assistant = None;
        runtime.pending_ai_preview = None;
        runtime.pending_ai_undo = None;
        runtime.pending_sync = None;
        status(runtime)
    })
}

fn status(runtime: &MobileRuntime) -> Result<VaultStatus, MobileError> {
    let initialized = storage::vault_path(runtime.root()?).is_file();
    let (entry_count, deleted_count) = if let Some(session) = &runtime.session {
        let (entries, deleted, _, _) = document::summary(session.document().as_value())?;
        (entries, deleted)
    } else {
        (0, 0)
    };
    Ok(VaultStatus {
        initialized,
        unlocked: runtime.session.is_some(),
        revision: runtime.revision,
        entry_count,
        deleted_count,
    })
}

pub fn vault_status() -> Result<VaultStatus, MobileError> {
    with_runtime(|runtime| status(runtime))
}

fn validate_new_password(password: &str) -> Result<(), MobileError> {
    let length = password.chars().count();
    if !(8..=128).contains(&length) {
        return Err(MobileError::new(
            "VALIDATION_FAILED",
            "主密码必须为 8 到 128 个字符",
        ));
    }
    Ok(())
}

fn activate_session(
    runtime: &mut MobileRuntime,
    mut session: VaultSession,
) -> Result<VaultStatus, MobileError> {
    let root = runtime.root()?.to_path_buf();
    let mut value = session.document().as_value().clone();
    if document::prepare_for_mobile(&mut value, &now())? {
        let migrated = VaultDocument::from_value(value.clone())?;
        storage::persist_vault(&root, &session.encrypted_document_bytes(&migrated)?, true)?;
        session.replace_document(value)?;
    }
    runtime.session = Some(session);
    runtime.revision = runtime.revision.saturating_add(1).max(1);
    runtime.pending_import = None;
    runtime.pending_ai_request = None;
    runtime.pending_ai_assistant = None;
    runtime.pending_ai_preview = None;
    runtime.pending_ai_undo = None;
    runtime.pending_sync = None;
    status(runtime)
}

pub fn create_vault(password: String) -> Result<VaultStatus, MobileError> {
    validate_new_password(&password)?;
    with_runtime(|runtime| {
        let root = runtime.root()?.to_path_buf();
        if storage::vault_path(&root).exists() {
            return Err(MobileError::new("VAULT_EXISTS", "本机密码库已经存在"));
        }
        storage::delete_secure_settings(&root)?;
        sync::clear(&root)?;
        storage::delete_ai_history(&root)?;
        storage::delete_autofill_settings(&root)?;
        let document = VaultDocument::from_value(document::new_document(&now()))?;
        let session = VaultSession::create(&password, document)?;
        storage::persist_vault(&root, &session.encrypted_bytes()?, false)?;
        runtime.session = Some(session);
        runtime.revision = 1;
        runtime.pending_import = None;
        runtime.pending_ai_request = None;
        runtime.pending_ai_assistant = None;
        runtime.pending_ai_preview = None;
        runtime.pending_ai_undo = None;
        runtime.pending_sync = None;
        status(runtime)
    })
}

pub fn unlock_vault(password: String) -> Result<VaultStatus, MobileError> {
    if password.is_empty() {
        return Err(MobileError::new("VALIDATION_FAILED", "请输入主密码"));
    }
    let password = Zeroizing::new(password);
    with_runtime(|runtime| {
        let root = runtime.root()?.to_path_buf();
        let content = storage::read_vault(&root)?;
        let session = VaultSession::unlock(password.as_str(), &content)?;
        activate_session(runtime, session)
    })
}

pub fn prepare_device_unlock_credential(password: String) -> Result<Vec<u8>, MobileError> {
    if password.is_empty() {
        return Err(MobileError::new("VALIDATION_FAILED", "请输入当前主密码"));
    }
    let password = Zeroizing::new(password);
    with_runtime(|runtime| {
        let _ = runtime.session()?;
        let content = storage::read_vault(runtime.root()?)?;
        let session = VaultSession::unlock(password.as_str(), &content)?;
        Ok(session.device_unlock_credential().to_vec())
    })
}

pub fn unlock_vault_with_device_credential(
    credential: Vec<u8>,
) -> Result<VaultStatus, MobileError> {
    let credential = Zeroizing::new(credential);
    with_runtime(|runtime| {
        let content = storage::read_vault(runtime.root()?)?;
        let session =
            VaultSession::unlock_with_device_credential(&credential, &content).map_err(|_| {
                MobileError::new(
                    "BIOMETRIC_CREDENTIAL_INVALID",
                    "指纹解锁凭据已失效，请使用主密码并重新开启指纹解锁",
                )
            })?;
        activate_session(runtime, session)
    })
}

pub fn lock_vault() -> Result<VaultStatus, MobileError> {
    with_runtime(|runtime| {
        runtime.session = None;
        runtime.pending_import = None;
        runtime.pending_ai_request = None;
        runtime.pending_ai_assistant = None;
        runtime.pending_ai_preview = None;
        runtime.pending_ai_undo = None;
        runtime.pending_sync = None;
        runtime.revision = runtime.revision.saturating_add(1);
        status(runtime)
    })
}

// Kept in the runtime module so synchronization can use private pending state
// without widening the mobile core's internal API.
include!("sync_runtime.rs");

#[allow(clippy::too_many_arguments)]
pub fn list_entries(
    page: u32,
    page_size: u32,
    search: String,
    tag: Option<String>,
    group: Option<String>,
    starred: Option<bool>,
    deleted: bool,
) -> Result<EntryPage, MobileError> {
    with_runtime(|runtime| {
        document::list_entries(
            runtime.session()?.document().as_value(),
            page,
            page_size,
            &search,
            tag.as_deref(),
            group.as_deref(),
            starred,
            deleted,
            runtime.revision,
        )
    })
}

pub fn get_entry(id: String) -> Result<EntryRecord, MobileError> {
    with_runtime(|runtime| document::get_entry(runtime.session()?.document().as_value(), &id))
}

pub fn save_entry(
    id: Option<String>,
    draft: EntryDraft,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    with_runtime(|runtime| {
        let is_new = id.is_none();
        runtime.transaction(expected_revision, |value| {
            document::save_entry(value, id.as_deref(), &draft, &now())?;
            Ok(if is_new {
                "条目已新建".to_string()
            } else {
                "条目已更新".to_string()
            })
        })
    })
}

#[cfg(target_os = "android")]
pub fn save_autofill_entry_with_device_credential(
    data_root: String,
    credential: Vec<u8>,
    draft: EntryDraft,
) -> Result<OperationResult, MobileError> {
    let credential = Zeroizing::new(credential);
    save_autofill_entry(data_root, draft, |content| {
        VaultSession::unlock_with_device_credential(&credential, content).map_err(|_| {
            MobileError::new(
                "BIOMETRIC_CREDENTIAL_INVALID",
                "指纹解锁凭据已失效，请使用主密码并重新开启指纹解锁",
            )
        })
    })
}

#[cfg(target_os = "android")]
pub fn save_autofill_entry_with_password(
    data_root: String,
    password: String,
    draft: EntryDraft,
) -> Result<OperationResult, MobileError> {
    if password.is_empty() {
        return Err(MobileError::new("VALIDATION_FAILED", "请输入主密码"));
    }
    let password = Zeroizing::new(password);
    save_autofill_entry(data_root, draft, |content| {
        Ok(VaultSession::unlock(password.as_str(), content)?)
    })
}

#[cfg(target_os = "android")]
fn save_autofill_entry(
    data_root: String,
    draft: EntryDraft,
    authenticate: impl FnOnce(&[u8]) -> Result<VaultSession, MobileError>,
) -> Result<OperationResult, MobileError> {
    let root = PathBuf::from(data_root);
    if !root.is_absolute() {
        return Err(MobileError::new(
            "INVALID_PATH",
            "自动填充数据目录必须是绝对路径",
        ));
    }
    with_runtime(|runtime| {
        let content = storage::read_vault(&root)?;
        let mut authenticated = authenticate(&content)?;
        let mut authenticated_value = authenticated.document().as_value().clone();
        if document::prepare_for_mobile(&mut authenticated_value, &now())? {
            authenticated.replace_document(authenticated_value)?;
        }

        if runtime.session.is_some() {
            if runtime.root.as_ref() != Some(&root) {
                return Err(MobileError::new(
                    "RUNTIME_ACTIVE",
                    "当前解锁会话与自动填充密码库不一致",
                ));
            }
            let revision = runtime.revision;
            return runtime.transaction(revision, |value| {
                document::save_entry(value, None, &draft, &now())?;
                Ok("登录信息已保存为新条目".to_string())
            });
        }

        let mut candidate = authenticated.document().as_value().clone();
        document::save_entry(&mut candidate, None, &draft, &now())?;
        let document = VaultDocument::from_value(candidate)?;
        let encrypted = authenticated.encrypted_document_bytes(&document)?;
        storage::persist_vault(&root, &encrypted, true)?;
        runtime.root = Some(root);
        runtime.revision = runtime.revision.saturating_add(1).max(1);
        runtime.pending_import = None;
        runtime.pending_ai_request = None;
        runtime.pending_ai_assistant = None;
        runtime.pending_ai_preview = None;
        runtime.pending_ai_undo = None;
        runtime.pending_sync = None;
        Ok(OperationResult {
            revision: runtime.revision,
            message: "登录信息已保存为新条目".to_string(),
        })
    })
}

pub fn trash_entry(id: String, expected_revision: u64) -> Result<OperationResult, MobileError> {
    with_runtime(|runtime| {
        runtime.transaction(expected_revision, |value| {
            document::trash_entry(value, &id, &now())?;
            Ok("条目已移入回收站".to_string())
        })
    })
}

pub fn restore_entry(id: String, expected_revision: u64) -> Result<OperationResult, MobileError> {
    with_runtime(|runtime| {
        runtime.transaction(expected_revision, |value| {
            document::restore_entry(value, &id, &now())?;
            Ok("条目已恢复".to_string())
        })
    })
}

pub fn purge_entry(id: String, expected_revision: u64) -> Result<OperationResult, MobileError> {
    with_runtime(|runtime| {
        runtime.transaction(expected_revision, |value| {
            document::purge_entry(value, &id, &now())?;
            Ok("条目已彻底删除".to_string())
        })
    })
}

pub fn list_taxonomy(kind: String) -> Result<Vec<TaxonomyRecord>, MobileError> {
    with_runtime(|runtime| document::list_taxonomy(runtime.session()?.document().as_value(), &kind))
}

#[allow(clippy::too_many_arguments)]
pub fn save_taxonomy(
    kind: String,
    old_name: Option<String>,
    name: String,
    description: String,
    color: Option<String>,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    with_runtime(|runtime| {
        runtime.transaction(expected_revision, |value| {
            document::save_taxonomy(
                value,
                &kind,
                old_name.as_deref(),
                &name,
                &description,
                color.as_deref(),
                &now(),
            )?;
            Ok(if kind == "tags" {
                "标签已保存".to_string()
            } else {
                "密码组已保存".to_string()
            })
        })
    })
}

pub fn delete_taxonomy(
    kind: String,
    name: String,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    with_runtime(|runtime| {
        runtime.transaction(expected_revision, |value| {
            document::delete_taxonomy(value, &kind, &name, &now())?;
            Ok(if kind == "tags" {
                "标签已删除".to_string()
            } else {
                "密码组已删除".to_string()
            })
        })
    })
}

pub fn delete_taxonomies(
    kind: String,
    names: Vec<String>,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    with_runtime(|runtime| {
        runtime.transaction(expected_revision, |value| {
            let count = document::delete_taxonomies(value, &kind, &names, &now())?;
            Ok(if kind == "tags" {
                format!("已删除 {count} 个标签")
            } else {
                format!("已删除 {count} 个密码组")
            })
        })
    })
}

pub fn save_group_order(
    names: Vec<String>,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    with_runtime(|runtime| {
        runtime.transaction(expected_revision, |value| {
            document::save_group_order(value, &names, &now())?;
            Ok(if names.is_empty() {
                "已恢复默认排序".to_string()
            } else {
                "密码组排序已更新".to_string()
            })
        })
    })
}

pub fn export_encrypted_vault() -> Result<Vec<u8>, MobileError> {
    with_runtime(|runtime| {
        let _ = runtime.session()?;
        storage::read_vault(runtime.root()?)
    })
}

fn preview_import_bytes(
    runtime: &mut MobileRuntime,
    content: Vec<u8>,
    password: &str,
) -> Result<ImportPreview, MobileError> {
    if runtime.session.is_none() && storage::vault_path(runtime.root()?).exists() {
        return Err(MobileError::new("VAULT_LOCKED", "请先解锁当前密码库再导入"));
    }
    let mut session = VaultSession::unlock(password, &content)?;
    let mut value = session.document().as_value().clone();
    if document::prepare_for_mobile(&mut value, &now())? {
        session.replace_document(value)?;
    }
    let (entries, deleted_entries, tags, groups) =
        document::summary(session.document().as_value())?;
    let token = Uuid::new_v4().to_string();
    let preview = ImportPreview {
        token: token.clone(),
        entries,
        deleted_entries,
        tags,
        groups,
        source_revision: runtime.revision,
    };
    runtime.pending_import = Some(PendingImport {
        token,
        source_revision: runtime.revision,
        session,
        preview: preview.clone(),
    });
    Ok(preview)
}

pub fn preview_import(content: Vec<u8>, password: String) -> Result<ImportPreview, MobileError> {
    if password.is_empty() {
        return Err(MobileError::new("VALIDATION_FAILED", "请输入备份主密码"));
    }
    with_runtime(|runtime| preview_import_bytes(runtime, content, &password))
}

pub fn apply_import(token: String) -> Result<OperationResult, MobileError> {
    with_runtime(|runtime| {
        let pending = runtime
            .pending_import
            .take()
            .ok_or_else(|| MobileError::new("IMPORT_PREVIEW_MISSING", "导入预览已失效"))?;
        if pending.token != token || pending.source_revision != runtime.revision {
            return Err(MobileError::retryable(
                "REVISION_CONFLICT",
                "密码库已发生变化，请重新预览导入文件",
            ));
        }
        let root = runtime.root()?.to_path_buf();
        let value = pending.session.document().as_value().clone();
        if let Some(current) = runtime.session.as_mut() {
            let document = VaultDocument::from_value(value.clone())?;
            let encrypted = current.encrypted_document_bytes(&document)?;
            storage::persist_vault(&root, &encrypted, true)?;
            current.replace_document(value)?;
        } else {
            storage::persist_vault(&root, &pending.session.encrypted_bytes()?, false)?;
            runtime.session = Some(pending.session);
        }
        runtime.revision = runtime.revision.saturating_add(1).max(1);
        runtime.pending_ai_request = None;
        runtime.pending_ai_assistant = None;
        runtime.pending_ai_preview = None;
        runtime.pending_ai_undo = None;
        runtime.pending_sync = None;
        storage::delete_ai_history(&root)?;
        autofill::clear_settings(&root)?;
        Ok(OperationResult {
            revision: runtime.revision,
            message: "加密密码库已导入".to_string(),
        })
    })
}

pub fn list_recovery_snapshots() -> Result<Vec<RecoverySnapshot>, MobileError> {
    with_runtime(|runtime| storage::list_recovery(runtime.root()?))
}

pub fn preview_recovery(id: String, password: String) -> Result<ImportPreview, MobileError> {
    with_runtime(|runtime| {
        let content = storage::read_recovery(runtime.root()?, &id)?;
        preview_import_bytes(runtime, content, &password)
    })
}

pub fn change_password(
    new_password: String,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    validate_new_password(&new_password)?;
    with_runtime(|runtime| {
        if expected_revision != runtime.revision {
            return Err(MobileError::retryable(
                "REVISION_CONFLICT",
                "密码库已发生变化，请刷新后重试",
            ));
        }
        let root = runtime.root()?.to_path_buf();
        let old_sync_config = sync::load_config(&root, runtime.session()?).ok().flatten();
        let old_sync_base = sync::load_base(&root, runtime.session()?).ok().flatten();
        let document = VaultDocument::from_value(runtime.session()?.document().as_value().clone())?;
        let replacement = VaultSession::create(&new_password, document)?;
        let autofill_settings_rekeyed =
            autofill::rekey_settings(&root, runtime.session()?, &replacement).unwrap_or_else(
                |_| {
                    let _ = autofill::clear_settings(&root);
                    false
                },
            );
        storage::persist_vault(&root, &replacement.encrypted_bytes()?, true)?;
        let settings_path = storage::secure_settings_path(&root);
        if settings_path.exists() {
            let _ = fs::remove_file(settings_path);
        }
        runtime.session = Some(replacement);
        runtime.pending_import = None;
        runtime.pending_ai_request = None;
        runtime.pending_ai_assistant = None;
        runtime.pending_ai_preview = None;
        runtime.pending_ai_undo = None;
        runtime.pending_sync = None;
        let sync_save_failed = if let Some(config) = old_sync_config {
            if sync::save_config(&root, runtime.session()?, &config).is_err() {
                true
            } else if let Some(base) = old_sync_base {
                sync::save_base(&root, runtime.session()?, &base).is_err()
            } else {
                false
            }
        } else {
            false
        };
        if sync_save_failed {
            let _ = sync::clear(&root);
        }
        storage::delete_ai_history(&root)?;
        runtime.revision = runtime.revision.saturating_add(1);
        Ok(OperationResult {
            revision: runtime.revision,
            message: if autofill_settings_rekeyed {
                "主密码已更新；自动填充绑定已重新加密，本机 AI 设置和对话历史已清除".to_string()
            } else {
                "主密码已更新；本机 AI 设置、对话历史和无效自动填充绑定已清除".to_string()
            },
        })
    })
}

pub fn pending_import_preview() -> Result<Option<ImportPreview>, MobileError> {
    with_runtime(|runtime| {
        Ok(runtime
            .pending_import
            .as_ref()
            .map(|item| item.preview.clone()))
    })
}

pub fn ai_status() -> Result<AiStatus, MobileError> {
    with_runtime(|runtime| {
        let config = ai::load_config(runtime.root()?, runtime.session()?)?;
        Ok(ai::status(config.as_ref()))
    })
}

pub fn prepare_ai_models_request(
    base_url: String,
    api_key: String,
) -> Result<AiHttpRequest, MobileError> {
    with_runtime(|runtime| {
        let config = ai::load_config(runtime.root()?, runtime.session()?)?;
        ai::prepare_models_request(config.as_ref(), &base_url, &api_key)
    })
}

pub fn parse_ai_models_response(content: String) -> Result<Vec<String>, MobileError> {
    ai::parse_models_response(&content)
}

pub fn prepare_ai_verify_request(
    base_url: String,
    api_key: String,
    model: String,
) -> Result<AiHttpRequest, MobileError> {
    with_runtime(|runtime| {
        let config = ai::load_config(runtime.root()?, runtime.session()?)?;
        ai::prepare_verify_request(config.as_ref(), &base_url, &api_key, &model)
    })
}

pub fn verify_ai_response(content: String) -> Result<(), MobileError> {
    ai::verify_response(&content)
}

pub fn save_ai_settings(
    base_url: String,
    api_key: String,
    model: String,
) -> Result<AiStatus, MobileError> {
    with_runtime(|runtime| {
        let root = runtime.root()?.to_path_buf();
        let saved = ai::load_config(&root, runtime.session()?)?;
        let effective_key = if api_key.trim().is_empty()
            && saved.as_ref().is_some_and(|config| {
                config.base_url.trim_end_matches('/') == base_url.trim().trim_end_matches('/')
            }) {
            saved
                .as_ref()
                .map(|config| config.api_key.clone())
                .unwrap_or_default()
        } else {
            api_key
        };
        let status = ai::save_config(&root, runtime.session()?, &base_url, &effective_key, &model)?;
        runtime.pending_ai_request = None;
        runtime.pending_ai_assistant = None;
        runtime.pending_ai_preview = None;
        Ok(status)
    })
}

pub fn clear_ai_settings() -> Result<AiStatus, MobileError> {
    with_runtime(|runtime| {
        let _ = runtime.session()?;
        let root = runtime.root()?.to_path_buf();
        runtime.pending_ai_request = None;
        runtime.pending_ai_assistant = None;
        runtime.pending_ai_preview = None;
        ai::clear_config(&root)
    })
}

pub fn cancel_ai_pending() -> Result<(), MobileError> {
    with_runtime(|runtime| {
        let _ = runtime.session()?;
        runtime.pending_ai_request = None;
        runtime.pending_ai_assistant = None;
        runtime.pending_ai_preview = None;
        Ok(())
    })
}

pub fn prepare_ai_request(
    kind: String,
    input: String,
    entry_id: Option<String>,
    user_prompt: String,
) -> Result<AiRequestPlan, MobileError> {
    with_runtime(|runtime| {
        let config = ai::load_config(runtime.root()?, runtime.session()?)?
            .ok_or_else(|| MobileError::new("AI_NOT_CONFIGURED", "请先配置 AI 服务"))?;
        let (plan, pending) = ai::prepare_request(
            runtime.session()?.document().as_value(),
            runtime.revision,
            &config,
            &kind,
            &input,
            entry_id.as_deref(),
            &user_prompt,
        )?;
        runtime.pending_ai_request = Some(pending);
        runtime.pending_ai_assistant = None;
        runtime.pending_ai_preview = None;
        Ok(plan)
    })
}

pub fn list_ai_conversations() -> Result<Vec<AiConversationSummary>, MobileError> {
    with_runtime(|runtime| ai::history::list(runtime.root()?, runtime.session()?))
}

pub fn get_ai_conversation(id: String) -> Result<AiConversation, MobileError> {
    with_runtime(|runtime| {
        ai::history::get(runtime.root()?, runtime.session()?, &id)?
            .ok_or_else(|| MobileError::new("AI_CONVERSATION_NOT_FOUND", "AI 对话不存在"))
    })
}

pub fn create_ai_conversation(title: String) -> Result<AiConversationSummary, MobileError> {
    with_runtime(|runtime| ai::history::create(runtime.root()?, runtime.session()?, &title))
}

pub fn delete_ai_conversation(id: String) -> Result<(), MobileError> {
    with_runtime(|runtime| {
        if !ai::history::delete(runtime.root()?, runtime.session()?, &id)? {
            return Err(MobileError::new(
                "AI_CONVERSATION_NOT_FOUND",
                "AI 对话不存在",
            ));
        }
        Ok(())
    })
}

pub fn clear_ai_conversations() -> Result<(), MobileError> {
    with_runtime(|runtime| {
        let _ = runtime.session()?;
        ai::history::clear(runtime.root()?)
    })
}

pub fn prepare_ai_assistant_request(
    conversation_id: Option<String>,
    message: String,
    mode: String,
    selected_entry_ids: Vec<String>,
) -> Result<AiAssistantRequestPlan, MobileError> {
    with_runtime(|runtime| {
        let root = runtime.root()?.to_path_buf();
        let session = runtime.session()?;
        let conversation_id =
            ai::history::ensure(&root, session, conversation_id.as_deref(), &message)?;
        let context = if mode == "assistant" {
            ai::history::context(&root, session, &conversation_id)?
        } else {
            Vec::new()
        };
        let config = ai::load_config(&root, session)?
            .ok_or_else(|| MobileError::new("AI_NOT_CONFIGURED", "请先配置 AI 服务"))?;
        let prepared = ai::assistant::prepare(
            session.document().as_value(),
            runtime.revision,
            &config,
            conversation_id,
            &message,
            &mode,
            &selected_entry_ids,
            context,
        )?;
        let public = AiAssistantRequestPlan {
            conversation_id: prepared.conversation_id.clone(),
            token: prepared.token.clone(),
            request: prepared.request.clone(),
            summary: prepared.summary.clone(),
            mode: prepared.mode.clone(),
        };
        runtime.pending_ai_request = None;
        runtime.pending_ai_assistant = Some(prepared.pending);
        runtime.pending_ai_preview = None;
        Ok(public)
    })
}

pub fn consume_ai_assistant_response(
    token: String,
    content: String,
) -> Result<AiAssistantTurnResult, MobileError> {
    with_runtime(|runtime| {
        let pending = runtime
            .pending_ai_assistant
            .take()
            .ok_or_else(|| MobileError::new("AI_REQUEST_MISSING", "AI 对话请求已失效"))?;
        if pending.token != token || pending.source_revision != runtime.revision {
            return Err(MobileError::retryable(
                "REVISION_CONFLICT",
                "密码库已发生变化，请重新生成 AI 建议",
            ));
        }
        let normalized = ai::assistant::normalize_response(
            runtime.session()?.document().as_value(),
            &pending,
            &content,
        )?;
        let root = runtime.root()?.to_path_buf();
        ai::history::append_turn(
            &root,
            runtime.session()?,
            &pending.conversation_id,
            &pending.user_message,
            &normalized.message,
            &pending.mode,
        )?;
        let preview = normalized.preview.as_ref().map(ai::public_preview);
        runtime.pending_ai_preview = normalized.preview;
        Ok(AiAssistantTurnResult {
            conversation_id: pending.conversation_id,
            message: normalized.message,
            preview,
            warnings: normalized.warnings,
            navigation_entry_id: normalized.navigation_entry_id,
            navigation_entry_title: normalized.navigation_entry_title,
        })
    })
}

pub fn consume_ai_response(token: String, content: String) -> Result<AiPreview, MobileError> {
    with_runtime(|runtime| {
        let pending = runtime
            .pending_ai_request
            .take()
            .ok_or_else(|| MobileError::new("AI_REQUEST_MISSING", "AI 请求已失效"))?;
        if pending.token != token || pending.source_revision != runtime.revision {
            return Err(MobileError::retryable(
                "REVISION_CONFLICT",
                "密码库已发生变化，请重新生成 AI 建议",
            ));
        }
        let preview = ai::preview_from_response(
            runtime.session()?.document().as_value(),
            &pending,
            &content,
        )?;
        let public = ai::public_preview(&preview);
        runtime.pending_ai_preview = Some(preview);
        Ok(public)
    })
}

pub fn pending_ai_preview() -> Result<Option<AiPreview>, MobileError> {
    with_runtime(|runtime| {
        let _ = runtime.session()?;
        Ok(runtime.pending_ai_preview.as_ref().map(ai::public_preview))
    })
}

pub fn apply_ai_preview(
    token: String,
    selected_item_ids: Vec<String>,
    expected_revision: u64,
) -> Result<AiApplyResult, MobileError> {
    with_runtime(|runtime| {
        let pending = runtime
            .pending_ai_preview
            .take()
            .ok_or_else(|| MobileError::new("AI_PREVIEW_MISSING", "AI 建议预览已失效"))?;
        if pending.preview.token != token
            || pending.preview.source_revision != runtime.revision
            || expected_revision != runtime.revision
        {
            return Err(MobileError::retryable(
                "REVISION_CONFLICT",
                "密码库已发生变化，请重新生成 AI 建议",
            ));
        }
        let previous_document = runtime.session()?.document().as_value().clone();
        let conversation_id = pending.conversation_id.clone();
        let applied_count = u32::try_from(selected_item_ids.len()).unwrap_or(u32::MAX);
        let result = runtime.transaction(expected_revision, |value| {
            ai::apply_preview(value, &pending, &selected_item_ids, &now())
        })?;
        let undo_token = Uuid::new_v4().to_string();
        let message = result.message.clone();
        runtime.pending_ai_undo = Some(PendingAiUndo {
            token: undo_token.clone(),
            source_revision: result.revision,
            document: previous_document,
            conversation_id: conversation_id.clone(),
            applied_count,
            message: message.clone(),
        });
        if let Some(conversation_id) = conversation_id {
            let root = runtime.root()?.to_path_buf();
            if let Ok(session) = runtime.session() {
                let _ = ai::history::append_assistant_message(
                    &root,
                    session,
                    &conversation_id,
                    &format!("已按你的确认应用 {applied_count} 项操作。"),
                );
            }
        }
        Ok(AiApplyResult {
            revision: result.revision,
            message,
            undo_token,
            applied_count,
        })
    })
}

pub fn pending_ai_undo() -> Result<Option<AiUndoState>, MobileError> {
    with_runtime(|runtime| {
        let _ = runtime.session()?;
        Ok(runtime.pending_ai_undo.as_ref().map(|pending| AiUndoState {
            revision: pending.source_revision,
            message: pending.message.clone(),
            undo_token: pending.token.clone(),
            applied_count: pending.applied_count,
        }))
    })
}

pub fn undo_ai_preview(
    undo_token: String,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    with_runtime(|runtime| undo_ai_preview_in_runtime(runtime, &undo_token, expected_revision))
}

fn undo_ai_preview_in_runtime(
    runtime: &mut MobileRuntime,
    undo_token: &str,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    let pending = runtime
        .pending_ai_undo
        .as_ref()
        .ok_or_else(|| MobileError::new("AI_UNDO_MISSING", "没有可撤回的 AI 操作"))?;
    if pending.token != undo_token
        || pending.source_revision != runtime.revision
        || expected_revision != runtime.revision
    {
        return Err(MobileError::retryable(
            "REVISION_CONFLICT",
            "密码库已发生变化，无法撤回之前的 AI 操作",
        ));
    }

    let root = runtime.root()?.to_path_buf();
    let value = pending.document.clone();
    let conversation_id = pending.conversation_id.clone();
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
    runtime.pending_sync = None;

    if let Some(conversation_id) = conversation_id {
        if let Ok(session) = runtime.session() {
            let _ = ai::history::append_assistant_message(
                &root,
                session,
                &conversation_id,
                "已撤回上一轮 AI 操作。",
            );
        }
    }
    Ok(OperationResult {
        revision: runtime.revision,
        message: "已撤回上一轮 AI 操作".to_string(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mobile::models::FieldRecord;

    fn draft(title: &str) -> EntryDraft {
        EntryDraft {
            title: title.to_string(),
            url: String::new(),
            starred: false,
            tags: Vec::new(),
            groups: Vec::new(),
            fields: vec![FieldRecord {
                name: "密码".to_string(),
                value: "test-secret".to_string(),
                copyable: true,
                hidden: true,
            }],
            remarks: String::new(),
        }
    }

    #[test]
    fn transaction_rejects_stale_revision_before_writing() {
        let directory = tempfile::tempdir().unwrap();
        let document = VaultDocument::from_value(document::new_document(&now())).unwrap();
        let session = VaultSession::create("test-password", document).unwrap();
        let original = session.encrypted_bytes().unwrap();
        storage::persist_vault(directory.path(), &original, false).unwrap();
        let mut runtime = MobileRuntime {
            root: Some(directory.path().to_path_buf()),
            session: Some(session),
            revision: 4,
            pending_import: None,
            pending_ai_request: None,
            pending_ai_assistant: None,
            pending_ai_preview: None,
            pending_ai_undo: None,
            pending_sync: None,
        };

        let result = runtime.transaction(3, |value| {
            document::save_entry(value, None, &draft("不应保存"), &now())?;
            Ok("saved".to_string())
        });

        assert!(matches!(
            result,
            Err(MobileError::Failure { ref code, .. }) if code == "REVISION_CONFLICT"
        ));
        assert_eq!(runtime.revision, 4);
        assert_eq!(storage::read_vault(directory.path()).unwrap(), original);
        assert!(storage::list_recovery(directory.path()).unwrap().is_empty());
    }

    #[test]
    fn transaction_commits_valid_document_and_creates_recovery() {
        let directory = tempfile::tempdir().unwrap();
        let document = VaultDocument::from_value(document::new_document(&now())).unwrap();
        let session = VaultSession::create("test-password", document).unwrap();
        storage::persist_vault(directory.path(), &session.encrypted_bytes().unwrap(), false)
            .unwrap();
        let mut runtime = MobileRuntime {
            root: Some(directory.path().to_path_buf()),
            session: Some(session),
            revision: 1,
            pending_import: None,
            pending_ai_request: None,
            pending_ai_assistant: None,
            pending_ai_preview: None,
            pending_ai_undo: None,
            pending_sync: None,
        };

        let result = runtime
            .transaction(1, |value| {
                document::save_entry(value, None, &draft("已保存"), &now())?;
                Ok("saved".to_string())
            })
            .unwrap();

        assert_eq!(result.revision, 2);
        assert_eq!(runtime.revision, 2);
        assert_eq!(storage::list_recovery(directory.path()).unwrap().len(), 1);
        let encrypted = storage::read_vault(directory.path()).unwrap();
        let unlocked = VaultSession::unlock("test-password", &encrypted).unwrap();
        assert_eq!(
            document::summary(unlocked.document().as_value()).unwrap().0,
            1
        );
    }

    #[test]
    fn ai_undo_restores_exact_document_once_and_rejects_stale_revision() {
        let directory = tempfile::tempdir().unwrap();
        let document = VaultDocument::from_value(document::new_document(&now())).unwrap();
        let session = VaultSession::create("test-password", document).unwrap();
        storage::persist_vault(directory.path(), &session.encrypted_bytes().unwrap(), false)
            .unwrap();
        let original = session.document().as_value().clone();
        let mut runtime = MobileRuntime {
            root: Some(directory.path().to_path_buf()),
            session: Some(session),
            revision: 1,
            pending_import: None,
            pending_ai_request: None,
            pending_ai_assistant: None,
            pending_ai_preview: None,
            pending_ai_undo: None,
            pending_sync: None,
        };

        runtime
            .transaction(1, |value| {
                document::save_entry(value, None, &draft("AI 新建"), &now())?;
                Ok("applied".to_string())
            })
            .unwrap();
        runtime.pending_ai_undo = Some(PendingAiUndo {
            token: "undo-token".to_string(),
            source_revision: 2,
            document: original.clone(),
            conversation_id: None,
            applied_count: 1,
            message: "applied".to_string(),
        });

        let stale = undo_ai_preview_in_runtime(&mut runtime, "undo-token", 1);
        assert!(matches!(
            stale,
            Err(MobileError::Failure { ref code, .. }) if code == "REVISION_CONFLICT"
        ));
        assert!(runtime.pending_ai_undo.is_some());

        let result = undo_ai_preview_in_runtime(&mut runtime, "undo-token", 2).unwrap();
        assert_eq!(result.revision, 3);
        assert_eq!(runtime.session().unwrap().document().as_value(), &original);
        assert!(runtime.pending_ai_undo.is_none());
        assert_eq!(storage::list_recovery(directory.path()).unwrap().len(), 2);

        let repeated = undo_ai_preview_in_runtime(&mut runtime, "undo-token", 3);
        assert!(matches!(
            repeated,
            Err(MobileError::Failure { ref code, .. }) if code == "AI_UNDO_MISSING"
        ));
    }
}
