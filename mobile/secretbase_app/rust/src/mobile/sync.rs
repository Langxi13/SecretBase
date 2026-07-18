//! Mobile-side V2 snapshot metadata, encryption, and encrypted local state.

use std::{collections::HashSet, path::Path};

use chrono::{SecondsFormat, Utc};
use secretbase_vault_core::sync_bundle_v2;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use url::Url;
use uuid::Uuid;

use super::{
    error::MobileError,
    models::{SyncConnection, SyncSnapshotInfo, SyncStatus, SyncUploadPlan},
    storage,
};

const CONFIG_PURPOSE: &str = "webdav-sync-v2-settings";
const BASE_PURPOSE: &str = "webdav-sync-v2-base";
const CONFIG_FILENAME: &str = "sync-settings.vault";
const BASE_FILENAME: &str = "sync-base.vault";
const MAX_PARENTS: usize = 32;
const MAX_DEVICE_NAME_CHARS: usize = 100;
const MAX_USERNAME_CHARS: usize = 512;
const MAX_PASSWORD_CHARS: usize = 4096;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub(crate) struct SyncConfig {
    pub protocol_version: u32,
    pub base_url: String,
    pub username: String,
    pub password: String,
    pub vault_id: String,
    pub space_id: String,
    pub sync_key: Vec<u8>,
    pub device_id: String,
    pub device_name: String,
    pub auto_sync: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub(crate) struct SyncBase {
    pub protocol_version: u32,
    pub space_id: String,
    pub frontier: Vec<String>,
    pub generation: u64,
    pub synced_at: String,
    pub document: Value,
}

pub(crate) struct NewSyncConfig {
    pub base_url: String,
    pub username: String,
    pub password: String,
    pub vault_id: String,
    pub space_id: String,
    pub sync_key: Vec<u8>,
    pub device_name: String,
    pub auto_sync: bool,
}

pub(crate) fn now() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

fn config_path(root: &Path) -> std::path::PathBuf {
    root.join(CONFIG_FILENAME)
}

fn base_path(root: &Path) -> std::path::PathBuf {
    root.join(BASE_FILENAME)
}

fn encode<T: Serialize>(value: &T) -> Result<Vec<u8>, MobileError> {
    serde_json::to_vec(value)
        .map_err(|_| MobileError::new("SYNC_STATE_INVALID", "同步状态无法编码"))
}

fn decode<T: for<'de> Deserialize<'de>>(content: &[u8]) -> Result<T, MobileError> {
    serde_json::from_slice(content)
        .map_err(|_| MobileError::new("SYNC_STATE_INVALID", "同步状态格式无效"))
}

pub(crate) fn load_config(
    root: &Path,
    session: &secretbase_vault_core::VaultSession,
) -> Result<Option<SyncConfig>, MobileError> {
    let path = config_path(root);
    if !path.is_file() {
        return Ok(None);
    }
    let content = std::fs::read(path)?;
    let value: SyncConfig = decode(&session.decrypt_scoped_bytes(CONFIG_PURPOSE, &content)?)?;
    validate_config(&value)?;
    Ok(Some(value))
}

pub(crate) fn save_config(
    root: &Path,
    session: &secretbase_vault_core::VaultSession,
    config: &SyncConfig,
) -> Result<(), MobileError> {
    validate_config(config)?;
    let encrypted = session.encrypt_scoped_bytes(CONFIG_PURPOSE, &encode(config)?)?;
    storage::atomic_write(&config_path(root), &encrypted)
}

pub(crate) fn load_base(
    root: &Path,
    session: &secretbase_vault_core::VaultSession,
) -> Result<Option<SyncBase>, MobileError> {
    let path = base_path(root);
    if !path.is_file() {
        return Ok(None);
    }
    let content = std::fs::read(path)?;
    let value: SyncBase = decode(&session.decrypt_scoped_bytes(BASE_PURPOSE, &content)?)?;
    validate_base(&value)?;
    Ok(Some(value))
}

pub(crate) fn save_base(
    root: &Path,
    session: &secretbase_vault_core::VaultSession,
    base: &SyncBase,
) -> Result<(), MobileError> {
    validate_base(base)?;
    let encrypted = session.encrypt_scoped_bytes(BASE_PURPOSE, &encode(base)?)?;
    storage::atomic_write(&base_path(root), &encrypted)
}

pub(crate) fn clear(root: &Path) -> Result<(), MobileError> {
    for path in [config_path(root), base_path(root)] {
        if path.exists() {
            std::fs::remove_file(path)?;
        }
    }
    Ok(())
}

fn validate_config(config: &SyncConfig) -> Result<(), MobileError> {
    let secure_url = Url::parse(config.base_url.trim()).is_ok_and(|value| {
        value.scheme() == "https"
            && value.host_str().is_some()
            && value.username().is_empty()
            && value.password().is_none()
            && value.query().is_none()
            && value.fragment().is_none()
    });
    if config.protocol_version != 2
        || !secure_url
        || config.username.trim().is_empty()
        || config.username.chars().count() > MAX_USERNAME_CHARS
        || config.password.is_empty()
        || config.password.chars().count() > MAX_PASSWORD_CHARS
        || config.device_name.chars().count() > MAX_DEVICE_NAME_CHARS
        || config.sync_key.len() != 32
        || Uuid::parse_str(&config.vault_id).is_err()
        || Uuid::parse_str(&config.space_id).is_err()
        || Uuid::parse_str(&config.device_id).is_err()
    {
        return Err(MobileError::new("SYNC_STATE_INVALID", "同步设置格式无效"));
    }
    Ok(())
}

fn validate_base(base: &SyncBase) -> Result<(), MobileError> {
    let unique_frontier = base.frontier.iter().collect::<HashSet<_>>();
    if base.protocol_version != 2
        || Uuid::parse_str(&base.space_id).is_err()
        || base.frontier.is_empty()
        || base.frontier.len() > MAX_PARENTS
        || base.frontier.len() != unique_frontier.len()
        || base
            .frontier
            .iter()
            .any(|item| Uuid::parse_str(item).is_err())
        || base.generation < 1
        || !base.document.is_object()
    {
        return Err(MobileError::new("SYNC_STATE_INVALID", "同步基线格式无效"));
    }
    Ok(())
}

pub(crate) fn connection(config: &SyncConfig) -> SyncConnection {
    SyncConnection {
        base_url: config.base_url.clone(),
        username: config.username.clone(),
        password: config.password.clone(),
        device_name: config.device_name.clone(),
        auto_sync: config.auto_sync,
    }
}

pub(crate) fn username_mask(username: &str) -> String {
    let characters = username.chars().collect::<Vec<_>>();
    if characters.len() <= 2 {
        return "*".repeat(characters.len());
    }
    format!("{}***{}", characters[0], characters[characters.len() - 1])
}

pub(crate) fn device_name(value: &str) -> String {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        "Android 设备".to_string()
    } else {
        trimmed.chars().take(MAX_DEVICE_NAME_CHARS).collect()
    }
}

pub(crate) fn document_has_content(value: &Value) -> bool {
    ["entries", "deleted_entries"].iter().any(|key| {
        value
            .get(key)
            .and_then(Value::as_array)
            .is_some_and(|items| !items.is_empty())
    }) || ["tags_meta", "groups_meta"].iter().any(|key| {
        value
            .get(key)
            .and_then(Value::as_object)
            .is_some_and(|items| !items.is_empty())
    })
}

pub(crate) fn documents_equal(left: &Value, right: &Value) -> bool {
    fn canonical(value: &Value) -> Value {
        let mut result = value.clone();
        let Some(root) = result.as_object_mut() else {
            return result;
        };
        for collection in ["entries", "deleted_entries"] {
            let Some(items) = root.get_mut(collection).and_then(Value::as_array_mut) else {
                continue;
            };
            items.sort_by(|left, right| {
                let left_id = left.get("id").and_then(Value::as_str).unwrap_or_default();
                let right_id = right.get("id").and_then(Value::as_str).unwrap_or_default();
                left_id.cmp(right_id)
            });
        }
        result
    }

    canonical(left) == canonical(right)
}

pub(crate) fn status(
    root: &Path,
    session: &secretbase_vault_core::VaultSession,
    phase: &str,
    message: &str,
    last_error: &str,
) -> Result<SyncStatus, MobileError> {
    let Some(config) = load_config(root, session)? else {
        return Ok(SyncStatus {
            configured: false,
            protocol_version: 2,
            phase: "disabled".to_string(),
            message: "尚未配置同步".to_string(),
            last_error: last_error.to_string(),
            auto_sync: true,
            base_url: String::new(),
            username_mask: String::new(),
            device_name: String::new(),
            vault_id: String::new(),
            space_id: String::new(),
            generation: 0,
            frontier: Vec::new(),
        });
    };
    let base = load_base(root, session)?;
    let username_mask = username_mask(&config.username);
    Ok(SyncStatus {
        configured: true,
        protocol_version: 2,
        phase: phase.to_string(),
        message: message.to_string(),
        last_error: last_error.to_string(),
        auto_sync: config.auto_sync,
        base_url: config.base_url.clone(),
        username_mask,
        device_name: config.device_name.clone(),
        vault_id: config.vault_id.clone(),
        space_id: config.space_id.clone(),
        generation: base.as_ref().map_or(0, |item| item.generation),
        frontier: base.map_or_else(Vec::new, |item| item.frontier),
    })
}

pub(crate) fn make_config(input: NewSyncConfig) -> Result<SyncConfig, MobileError> {
    let config = SyncConfig {
        protocol_version: 2,
        base_url: input.base_url,
        username: input.username,
        password: input.password,
        vault_id: input.vault_id,
        space_id: input.space_id,
        sync_key: input.sync_key,
        device_id: Uuid::new_v4().to_string(),
        device_name: device_name(&input.device_name),
        auto_sync: input.auto_sync,
    };
    validate_config(&config)?;
    Ok(config)
}

pub(crate) fn build_snapshot(
    config: &SyncConfig,
    document: &Value,
    parents: Vec<String>,
    generation: u64,
) -> Result<(SyncUploadPlan, Value), MobileError> {
    let unique_parents = parents.iter().collect::<HashSet<_>>();
    if parents.len() > MAX_PARENTS
        || parents.iter().any(|item| Uuid::parse_str(item).is_err())
        || parents.len() != unique_parents.len()
    {
        return Err(MobileError::new(
            "SYNC_GRAPH_INVALID",
            "同步 parent 关系无效",
        ));
    }
    if generation < 1 {
        return Err(MobileError::new(
            "SYNC_GRAPH_INVALID",
            "同步 generation 无效",
        ));
    }
    if parents.is_empty() && generation != 1 {
        return Err(MobileError::new(
            "SYNC_GRAPH_INVALID",
            "同步根快照 generation 必须为 1",
        ));
    }
    if !document.is_object()
        || document.get("vault_id").and_then(Value::as_str) != Some(config.vault_id.as_str())
    {
        return Err(MobileError::new(
            "SYNC_DOCUMENT_INVALID",
            "同步文档与当前 Vault 不一致",
        ));
    }
    let snapshot_id = Uuid::new_v4().to_string();
    let payload = json!({
        "schema_version": 2,
        "protocol": "snapshot-dag",
        "vault_id": config.vault_id,
        "space_id": config.space_id,
        "snapshot_id": snapshot_id,
        "generation": generation,
        "parents": parents,
        "created_at": now(),
        "device_id": config.device_id,
        "device_name": config.device_name,
        "document": document,
    });
    let content = sync_bundle_v2::encrypt_snapshot(
        &payload,
        &config.sync_key,
        &config.vault_id,
        &config.space_id,
        &snapshot_id,
    )
    .map_err(|error| MobileError::new(error.code(), "无法加密同步快照"))?;
    let path = snapshot_path(
        &config.vault_id,
        &config.space_id,
        &config.device_id,
        generation,
        &snapshot_id,
    );
    let token = Uuid::new_v4().to_string();
    Ok((
        SyncUploadPlan {
            token,
            snapshot_id,
            generation,
            device_id: config.device_id.clone(),
            path,
            content,
        },
        payload,
    ))
}

pub(crate) fn snapshot_path(
    vault_id: &str,
    space_id: &str,
    device_id: &str,
    generation: u64,
    snapshot_id: &str,
) -> Vec<String> {
    vec![
        "secretbase-sync-v2".to_string(),
        vault_id.to_string(),
        space_id.to_string(),
        "snapshots".to_string(),
        device_id.to_string(),
        format!("{generation}-{snapshot_id}.sbs"),
    ]
}

pub(crate) fn decode_snapshot(
    config: &SyncConfig,
    content: &[u8],
    snapshot_id: &str,
) -> Result<(SyncSnapshotInfo, Value), MobileError> {
    let payload = sync_bundle_v2::decrypt_snapshot(
        content,
        &config.sync_key,
        &config.vault_id,
        &config.space_id,
        snapshot_id,
    )
    .map_err(|error| MobileError::new(error.code(), "远端同步快照校验失败"))?;
    let object = payload
        .as_object()
        .ok_or_else(|| MobileError::new("SYNC_SNAPSHOT_INVALID", "远端同步快照格式无效"))?;
    let payload_snapshot = object
        .get("snapshot_id")
        .and_then(Value::as_str)
        .unwrap_or_default();
    if payload_snapshot != snapshot_id
        || object.get("schema_version").and_then(Value::as_u64) != Some(2)
        || object.get("protocol").and_then(Value::as_str) != Some("snapshot-dag")
        || object.get("vault_id").and_then(Value::as_str) != Some(config.vault_id.as_str())
        || object.get("space_id").and_then(Value::as_str) != Some(config.space_id.as_str())
    {
        return Err(MobileError::new(
            "SYNC_SNAPSHOT_INVALID",
            "远端同步快照身份无效",
        ));
    }
    let generation = object
        .get("generation")
        .and_then(Value::as_u64)
        .ok_or_else(|| MobileError::new("SYNC_SNAPSHOT_INVALID", "远端同步快照版本无效"))?;
    let document = object
        .get("document")
        .cloned()
        .ok_or_else(|| MobileError::new("SYNC_SNAPSHOT_INVALID", "远端同步快照缺少密码库"))?;
    let parents = object
        .get("parents")
        .and_then(Value::as_array)
        .ok_or_else(|| MobileError::new("SYNC_SNAPSHOT_INVALID", "远端同步快照 parent 无效"))?
        .iter()
        .map(|item| {
            item.as_str()
                .ok_or_else(|| {
                    MobileError::new("SYNC_SNAPSHOT_INVALID", "远端同步快照 parent 无效")
                })
                .and_then(|value| {
                    Uuid::parse_str(value)
                        .map(|_| value.to_string())
                        .map_err(|_| {
                            MobileError::new("SYNC_SNAPSHOT_INVALID", "远端同步快照 parent 无效")
                        })
                })
        })
        .collect::<Result<Vec<_>, _>>()?;
    if parents.len() > MAX_PARENTS
        || parents.len() != {
            let unique = parents.iter().collect::<HashSet<_>>();
            unique.len()
        }
        || parents.iter().any(|item| item == snapshot_id)
    {
        return Err(MobileError::new(
            "SYNC_GRAPH_INVALID",
            "远端同步快照 parent 关系无效",
        ));
    }
    let device_id = object
        .get("device_id")
        .and_then(Value::as_str)
        .ok_or_else(|| MobileError::new("SYNC_SNAPSHOT_INVALID", "远端设备身份无效"))?;
    Uuid::parse_str(device_id)
        .map_err(|_| MobileError::new("SYNC_SNAPSHOT_INVALID", "远端设备身份无效"))?;
    let device_name = object
        .get("device_name")
        .and_then(Value::as_str)
        .unwrap_or("设备");
    if device_name.chars().count() > 100 {
        return Err(MobileError::new(
            "SYNC_SNAPSHOT_INVALID",
            "远端设备名称过长",
        ));
    }
    if !document.is_object()
        || document.get("vault_id").and_then(Value::as_str) != Some(config.vault_id.as_str())
    {
        return Err(MobileError::new(
            "SYNC_SNAPSHOT_INVALID",
            "远端密码库格式无效",
        ));
    }
    if generation < 1 {
        return Err(MobileError::new(
            "SYNC_SNAPSHOT_INVALID",
            "远端同步快照版本无效",
        ));
    }
    let info = SyncSnapshotInfo {
        snapshot_id: snapshot_id.to_string(),
        generation,
        parents,
        device_id: device_id.to_string(),
        device_name: device_name.to_string(),
        created_at: object
            .get("created_at")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string(),
        document_json: serde_json::to_string(&document)
            .map_err(|_| MobileError::new("SYNC_SNAPSHOT_INVALID", "远端密码库格式无效"))?,
    };
    Ok((info, document))
}

pub(crate) fn recovery_code(config: &SyncConfig) -> Result<String, MobileError> {
    sync_bundle_v2::encode_recovery_code(&config.vault_id, &config.space_id, &config.sync_key)
        .map_err(|error| MobileError::new(error.code(), "同步恢复码生成失败"))
}

pub(crate) fn parse_recovery(value: &str) -> Result<(String, String, Vec<u8>), MobileError> {
    sync_bundle_v2::decode_recovery_code(value)
        .map_err(|error| MobileError::new(error.code(), "同步恢复码无效"))
}

pub(crate) fn base_for(
    config: &SyncConfig,
    frontier: Vec<String>,
    generation: u64,
    document: Value,
) -> SyncBase {
    SyncBase {
        protocol_version: 2,
        space_id: config.space_id.clone(),
        frontier,
        generation,
        synced_at: now(),
        document,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mobile::document;
    use secretbase_vault_core::{VaultDocument, VaultSession};
    use tempfile::tempdir;

    #[test]
    fn sync_state_can_be_rekeyed_with_the_vault_without_exposing_plaintext() {
        let root = tempdir().unwrap();
        let value = document::new_document(&now());
        let old_session = VaultSession::create(
            "old-master",
            VaultDocument::from_value(value.clone()).unwrap(),
        )
        .unwrap();
        let config = make_config(NewSyncConfig {
            base_url: "https://dav.example.test/root".to_string(),
            username: "user".to_string(),
            password: "application-password".to_string(),
            vault_id: "11111111-1111-4111-8111-111111111111".to_string(),
            space_id: "22222222-2222-4222-8222-222222222222".to_string(),
            sync_key: vec![7; 32],
            device_name: "测试设备".to_string(),
            auto_sync: true,
        })
        .unwrap();
        let base = base_for(
            &config,
            vec!["33333333-3333-4333-8333-333333333333".to_string()],
            1,
            value.clone(),
        );
        save_config(root.path(), &old_session, &config).unwrap();
        save_base(root.path(), &old_session, &base).unwrap();
        let encrypted_config = std::fs::read(config_path(root.path())).unwrap();
        assert!(!String::from_utf8_lossy(&encrypted_config).contains("application-password"));

        let new_session =
            VaultSession::create("new-master", VaultDocument::from_value(value).unwrap()).unwrap();
        save_config(root.path(), &new_session, &config).unwrap();
        save_base(root.path(), &new_session, &base).unwrap();
        assert!(load_config(root.path(), &old_session).is_err());
        assert_eq!(
            load_config(root.path(), &new_session)
                .unwrap()
                .unwrap()
                .space_id,
            config.space_id
        );
        assert_eq!(
            load_base(root.path(), &new_session)
                .unwrap()
                .unwrap()
                .frontier,
            base.frontier
        );
    }

    #[test]
    fn sync_state_rejects_insecure_urls_and_duplicate_frontiers() {
        let error = make_config(NewSyncConfig {
            base_url: "http://dav.example.test/root".to_string(),
            username: "user".to_string(),
            password: "password".to_string(),
            vault_id: "11111111-1111-4111-8111-111111111111".to_string(),
            space_id: "22222222-2222-4222-8222-222222222222".to_string(),
            sync_key: vec![7; 32],
            device_name: "设备".to_string(),
            auto_sync: true,
        })
        .unwrap_err();
        assert!(matches!(
            error,
            MobileError::Failure { ref code, .. } if code == "SYNC_STATE_INVALID"
        ));

        let config = make_config(NewSyncConfig {
            base_url: "https://dav.example.test/root".to_string(),
            username: "user".to_string(),
            password: "password".to_string(),
            vault_id: "11111111-1111-4111-8111-111111111111".to_string(),
            space_id: "22222222-2222-4222-8222-222222222222".to_string(),
            sync_key: vec![7; 32],
            device_name: "设备".to_string(),
            auto_sync: true,
        })
        .unwrap();
        let base = base_for(
            &config,
            vec![
                "33333333-3333-4333-8333-333333333333".to_string(),
                "33333333-3333-4333-8333-333333333333".to_string(),
            ],
            1,
            json!({"vault_id": config.vault_id}),
        );
        let root = tempdir().unwrap();
        let session = VaultSession::create(
            "master",
            VaultDocument::from_value(document::new_document(&now())).unwrap(),
        )
        .unwrap();
        assert!(save_base(root.path(), &session, &base).is_err());
    }

    #[test]
    fn document_comparison_ignores_entry_order_but_preserves_field_order() {
        let mut left = document::new_document(&now());
        left["entries"] = json!([
            {"id": "first", "title": "first", "fields": [{"name": "a"}, {"name": "b"}]},
            {"id": "second", "title": "second", "fields": []}
        ]);
        let mut reordered = left.clone();
        reordered["entries"].as_array_mut().unwrap().reverse();
        assert!(documents_equal(&left, &reordered));

        reordered["entries"][1]["fields"] = json!([{"name": "b"}, {"name": "a"}]);
        assert!(!documents_equal(&left, &reordered));
    }

    #[test]
    fn unicode_usernames_are_masked_without_byte_slicing() {
        assert_eq!(username_mask("张三丰"), "张***丰");
        assert_eq!(username_mask("用户"), "**");
    }

    #[test]
    fn vault_content_detection_matches_join_safety_boundary() {
        let empty = document::new_document(&now());
        assert!(!document_has_content(&empty));
        let mut tagged = empty.clone();
        tagged["tags_meta"] = json!({"工作": {"description": ""}});
        assert!(document_has_content(&tagged));
    }

    #[test]
    fn root_snapshot_requires_generation_one() {
        let config = make_config(NewSyncConfig {
            base_url: "https://dav.example.test/root".to_string(),
            username: "user".to_string(),
            password: "password".to_string(),
            vault_id: "11111111-1111-4111-8111-111111111111".to_string(),
            space_id: "22222222-2222-4222-8222-222222222222".to_string(),
            sync_key: vec![7; 32],
            device_name: "设备".to_string(),
            auto_sync: true,
        })
        .unwrap();
        let document = document::new_document(&now());
        let error = build_snapshot(&config, &document, Vec::new(), 2).unwrap_err();
        assert!(matches!(
            error,
            MobileError::Failure { ref code, .. } if code == "SYNC_GRAPH_INVALID"
        ));
    }
}
