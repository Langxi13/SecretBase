use std::{
    fs,
    path::{Path, PathBuf},
    sync::{Mutex, OnceLock},
};

use chrono::{SecondsFormat, Utc};
use secretbase_vault_core::{VaultDocument, VaultSession};
use serde_json::Value;
use uuid::Uuid;

use super::{
    ai::{self, PendingAiPreview, PendingAiRequest},
    document,
    error::MobileError,
    models::{
        AiHttpRequest, AiPreview, AiRequestPlan, AiStatus, EntryDraft, EntryPage, EntryRecord,
        ImportPreview, OperationResult, RecoverySnapshot, TaxonomyRecord, VaultStatus,
    },
    storage,
};

struct PendingImport {
    token: String,
    source_revision: u64,
    session: VaultSession,
    preview: ImportPreview,
}

#[derive(Default)]
struct MobileRuntime {
    root: Option<PathBuf>,
    session: Option<VaultSession>,
    revision: u64,
    pending_import: Option<PendingImport>,
    pending_ai_request: Option<PendingAiRequest>,
    pending_ai_preview: Option<PendingAiPreview>,
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
        self.pending_ai_preview = None;
        Ok(OperationResult {
            revision: self.revision,
            message,
        })
    }
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
        runtime.pending_ai_preview = None;
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

pub fn create_vault(password: String) -> Result<VaultStatus, MobileError> {
    validate_new_password(&password)?;
    with_runtime(|runtime| {
        let root = runtime.root()?.to_path_buf();
        if storage::vault_path(&root).exists() {
            return Err(MobileError::new("VAULT_EXISTS", "本机密码库已经存在"));
        }
        let document = VaultDocument::from_value(document::new_document(&now()))?;
        let session = VaultSession::create(&password, document)?;
        storage::persist_vault(&root, &session.encrypted_bytes()?, false)?;
        runtime.session = Some(session);
        runtime.revision = 1;
        runtime.pending_import = None;
        runtime.pending_ai_request = None;
        runtime.pending_ai_preview = None;
        status(runtime)
    })
}

pub fn unlock_vault(password: String) -> Result<VaultStatus, MobileError> {
    if password.is_empty() {
        return Err(MobileError::new("VALIDATION_FAILED", "请输入主密码"));
    }
    with_runtime(|runtime| {
        let root = runtime.root()?.to_path_buf();
        let content = storage::read_vault(&root)?;
        let mut session = VaultSession::unlock(&password, &content)?;
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
        runtime.pending_ai_preview = None;
        status(runtime)
    })
}

pub fn lock_vault() -> Result<VaultStatus, MobileError> {
    with_runtime(|runtime| {
        runtime.session = None;
        runtime.pending_import = None;
        runtime.pending_ai_request = None;
        runtime.pending_ai_preview = None;
        runtime.revision = runtime.revision.saturating_add(1);
        status(runtime)
    })
}

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
        runtime.pending_ai_preview = None;
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
        let document = VaultDocument::from_value(runtime.session()?.document().as_value().clone())?;
        let replacement = VaultSession::create(&new_password, document)?;
        storage::persist_vault(&root, &replacement.encrypted_bytes()?, true)?;
        let settings_path = storage::secure_settings_path(&root);
        if settings_path.exists() {
            let _ = fs::remove_file(settings_path);
        }
        runtime.session = Some(replacement);
        runtime.pending_import = None;
        runtime.pending_ai_request = None;
        runtime.pending_ai_preview = None;
        runtime.revision = runtime.revision.saturating_add(1);
        Ok(OperationResult {
            revision: runtime.revision,
            message: "主密码已更新；请重新配置本机 AI 设置".to_string(),
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
        runtime.pending_ai_preview = None;
        Ok(status)
    })
}

pub fn clear_ai_settings() -> Result<AiStatus, MobileError> {
    with_runtime(|runtime| {
        let _ = runtime.session()?;
        let root = runtime.root()?.to_path_buf();
        runtime.pending_ai_request = None;
        runtime.pending_ai_preview = None;
        ai::clear_config(&root)
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
        runtime.pending_ai_preview = None;
        Ok(plan)
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
) -> Result<OperationResult, MobileError> {
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
        runtime.transaction(expected_revision, |value| {
            ai::apply_preview(value, &pending, &selected_item_ids, &now())
        })
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
            pending_ai_preview: None,
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
            pending_ai_preview: None,
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
}
