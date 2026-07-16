#![cfg_attr(not(target_os = "android"), allow(dead_code))]

use std::{
    collections::{HashMap, HashSet},
    path::{Path, PathBuf},
    sync::{Mutex, OnceLock},
    time::{Duration, Instant},
};

use secretbase_vault_core::VaultSession;
use serde::{Deserialize, Serialize};
use url::Url;
use uuid::Uuid;

use super::{
    document,
    error::MobileError,
    models::{EntryDraft, EntryRecord, FieldRecord},
    storage,
};

const SETTINGS_PURPOSE: &str = "mobile-autofill-settings";
const SESSION_TTL: Duration = Duration::from_secs(120);
const MAX_PENDING_SESSIONS: usize = 3;
const MAX_CANDIDATES: usize = 500;

#[derive(Debug, Clone, Deserialize)]
pub struct AutofillTarget {
    pub package_name: String,
    pub web_domain: Option<String>,
    pub web_scheme: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct AutofillFieldOption {
    pub name: String,
    pub hidden: bool,
    pub copyable: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct AutofillCandidate {
    pub entry_id: String,
    pub title: String,
    pub username_preview: String,
    pub username_field: Option<String>,
    pub password_field: String,
    pub fields: Vec<AutofillFieldOption>,
    pub matched: bool,
    pub match_label: String,
    pub mapping_confident: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct AutofillOpenResult {
    pub session_token: String,
    pub target_label: String,
    pub candidates: Vec<AutofillCandidate>,
    pub truncated: bool,
}

#[derive(Debug, Clone, Deserialize)]
pub struct AutofillSelection {
    pub entry_id: String,
    pub username_field: Option<String>,
    pub password_field: String,
    pub remember_binding: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct AutofillFillValues {
    pub title: String,
    pub username: String,
    pub password: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct AutofillSaveDraft {
    pub title: String,
    pub url: String,
    pub username: String,
    pub password: String,
}

impl AutofillSaveDraft {
    pub fn into_entry_draft(self) -> Result<EntryDraft, MobileError> {
        if self.password.is_empty() {
            return Err(MobileError::new(
                "AUTOFILL_SAVE_INVALID",
                "没有可保存的密码",
            ));
        }
        let mut fields = Vec::with_capacity(2);
        if !self.username.is_empty() {
            fields.push(FieldRecord {
                name: "账号".to_string(),
                value: self.username,
                copyable: true,
                hidden: false,
            });
        }
        fields.push(FieldRecord {
            name: "密码".to_string(),
            value: self.password,
            copyable: true,
            hidden: true,
        });
        Ok(EntryDraft {
            title: self.title,
            url: self.url,
            starred: false,
            tags: Vec::new(),
            groups: Vec::new(),
            fields,
            remarks: String::new(),
        })
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
struct AutofillSettings {
    #[serde(default = "settings_version")]
    version: u8,
    #[serde(default)]
    bindings: HashMap<String, String>,
    #[serde(default)]
    field_mappings: HashMap<String, FieldMapping>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct FieldMapping {
    username_field: Option<String>,
    password_field: String,
}

struct PendingAutofillSession {
    created_at: Instant,
    root: PathBuf,
    target: AutofillTarget,
    candidate_entry_ids: HashSet<String>,
    session: VaultSession,
}

static PENDING_SESSIONS: OnceLock<Mutex<HashMap<String, PendingAutofillSession>>> = OnceLock::new();

fn settings_version() -> u8 {
    1
}

fn pending_sessions() -> &'static Mutex<HashMap<String, PendingAutofillSession>> {
    PENDING_SESSIONS.get_or_init(|| Mutex::new(HashMap::new()))
}

fn normalized_root(data_root: &str) -> Result<PathBuf, MobileError> {
    let root = PathBuf::from(data_root);
    if !root.is_absolute() {
        return Err(MobileError::new(
            "INVALID_PATH",
            "自动填充数据目录必须是绝对路径",
        ));
    }
    Ok(root)
}

impl AutofillTarget {
    fn normalize(mut self) -> Result<Self, MobileError> {
        self.package_name = self.package_name.trim().to_ascii_lowercase();
        if self.package_name.is_empty() || self.package_name.len() > 255 {
            return Err(MobileError::new(
                "AUTOFILL_TARGET_INVALID",
                "自动填充目标应用无效",
            ));
        }
        self.web_domain = self.web_domain.and_then(|domain| {
            let normalized = domain.trim().trim_end_matches('.').to_ascii_lowercase();
            (!normalized.is_empty()
                && normalized.len() <= 253
                && !normalized.contains(['/', '\\', ' ', '@']))
            .then_some(normalized)
        });
        self.web_scheme = self.web_scheme.and_then(|scheme| {
            let normalized = scheme.trim().to_ascii_lowercase();
            matches!(normalized.as_str(), "http" | "https").then_some(normalized)
        });
        Ok(self)
    }

    fn key(&self) -> String {
        self.web_domain
            .as_ref()
            .map(|domain| format!("web:{domain}"))
            .unwrap_or_else(|| format!("app:{}", self.package_name))
    }

    fn label(&self) -> String {
        self.web_domain
            .clone()
            .unwrap_or_else(|| self.package_name.clone())
    }
}

pub fn open_with_device_credential(
    data_root: &str,
    credential: &[u8],
    target: AutofillTarget,
) -> Result<AutofillOpenResult, MobileError> {
    let root = normalized_root(data_root)?;
    let content = storage::read_vault(&root)?;
    let session =
        VaultSession::unlock_with_device_credential(credential, &content).map_err(|_| {
            MobileError::new(
                "BIOMETRIC_CREDENTIAL_INVALID",
                "指纹解锁凭据已失效，请使用主密码并重新开启指纹解锁",
            )
        })?;
    open_session(root, session, target)
}

pub fn open_with_password(
    data_root: &str,
    password: &str,
    target: AutofillTarget,
) -> Result<AutofillOpenResult, MobileError> {
    if password.is_empty() {
        return Err(MobileError::new("VALIDATION_FAILED", "请输入主密码"));
    }
    let root = normalized_root(data_root)?;
    let content = storage::read_vault(&root)?;
    let session = VaultSession::unlock(password, &content)?;
    open_session(root, session, target)
}

fn open_session(
    root: PathBuf,
    session: VaultSession,
    target: AutofillTarget,
) -> Result<AutofillOpenResult, MobileError> {
    let target = target.normalize()?;
    let settings = load_or_reset_settings(&root, &session)?;
    let entries = document::active_entry_records(session.document().as_value())?;
    let mut candidates = build_candidates(&entries, &target, &settings);
    let truncated = candidates.len() > MAX_CANDIDATES;
    candidates.truncate(MAX_CANDIDATES);
    let candidate_entry_ids = candidates
        .iter()
        .map(|candidate| candidate.entry_id.clone())
        .collect();
    let token = Uuid::new_v4().to_string();
    let mut sessions = pending_sessions()
        .lock()
        .map_err(|_| MobileError::retryable("AUTOFILL_BUSY", "自动填充暂时不可用"))?;
    cleanup_sessions(&mut sessions);
    if sessions.len() >= MAX_PENDING_SESSIONS {
        if let Some(oldest) = sessions
            .iter()
            .min_by_key(|(_, pending)| pending.created_at)
            .map(|(token, _)| token.clone())
        {
            sessions.remove(&oldest);
        }
    }
    sessions.insert(
        token.clone(),
        PendingAutofillSession {
            created_at: Instant::now(),
            root,
            target: target.clone(),
            candidate_entry_ids,
            session,
        },
    );
    Ok(AutofillOpenResult {
        session_token: token,
        target_label: target.label(),
        candidates,
        truncated,
    })
}

pub fn select(
    session_token: &str,
    selection: AutofillSelection,
) -> Result<AutofillFillValues, MobileError> {
    let mut sessions = pending_sessions()
        .lock()
        .map_err(|_| MobileError::retryable("AUTOFILL_BUSY", "自动填充暂时不可用"))?;
    cleanup_sessions(&mut sessions);
    let pending = sessions
        .remove(session_token)
        .ok_or_else(|| MobileError::new("AUTOFILL_SESSION_EXPIRED", "自动填充会话已过期"))?;
    if !pending.candidate_entry_ids.contains(&selection.entry_id) {
        return Err(MobileError::new(
            "AUTOFILL_SELECTION_INVALID",
            "所选条目不在当前自动填充范围内",
        ));
    }
    let entry = document::get_entry(pending.session.document().as_value(), &selection.entry_id)?;
    let password = field_value(&entry, &selection.password_field)?;
    if password.is_empty() {
        return Err(MobileError::new(
            "AUTOFILL_FIELD_INVALID",
            "所选密码字段没有可填充内容",
        ));
    }
    let username = match selection.username_field.as_deref() {
        Some(name) if !name.is_empty() => field_value(&entry, name)?,
        _ => String::new(),
    };

    let mut settings = load_or_reset_settings(&pending.root, &pending.session)?;
    settings.field_mappings.insert(
        entry.id.clone(),
        FieldMapping {
            username_field: selection.username_field.clone(),
            password_field: selection.password_field,
        },
    );
    if selection.remember_binding {
        settings
            .bindings
            .insert(pending.target.key(), entry.id.clone());
    }
    save_settings(&pending.root, &pending.session, &settings)?;

    Ok(AutofillFillValues {
        title: entry.title,
        username,
        password,
    })
}

pub fn cancel(session_token: &str) {
    if let Ok(mut sessions) = pending_sessions().lock() {
        sessions.remove(session_token);
        cleanup_sessions(&mut sessions);
    }
}

pub fn clear_settings(root: &Path) -> Result<(), MobileError> {
    storage::delete_autofill_settings(root)
}

pub fn rekey_settings(
    root: &Path,
    current: &VaultSession,
    replacement: &VaultSession,
) -> Result<bool, MobileError> {
    let Some(content) = storage::read_autofill_settings(root)? else {
        return Ok(false);
    };
    let plaintext = current
        .decrypt_scoped_bytes(SETTINGS_PURPOSE, &content)
        .map_err(|_| MobileError::new("AUTOFILL_SETTINGS_INVALID", "自动填充设置无法解密"))?;
    let _: AutofillSettings = serde_json::from_slice(&plaintext)
        .map_err(|_| MobileError::new("AUTOFILL_SETTINGS_INVALID", "自动填充设置格式无效"))?;
    let encrypted = replacement.encrypt_scoped_bytes(SETTINGS_PURPOSE, &plaintext)?;
    storage::persist_autofill_settings(root, &encrypted)?;
    Ok(true)
}

fn cleanup_sessions(sessions: &mut HashMap<String, PendingAutofillSession>) {
    sessions.retain(|_, pending| pending.created_at.elapsed() < SESSION_TTL);
}

fn load_settings(root: &Path, session: &VaultSession) -> Result<AutofillSettings, MobileError> {
    let Some(content) = storage::read_autofill_settings(root)? else {
        return Ok(AutofillSettings {
            version: settings_version(),
            ..AutofillSettings::default()
        });
    };
    let plaintext = session
        .decrypt_scoped_bytes(SETTINGS_PURPOSE, &content)
        .map_err(|_| MobileError::new("AUTOFILL_SETTINGS_INVALID", "自动填充设置无法解密"))?;
    let settings: AutofillSettings = serde_json::from_slice(&plaintext)
        .map_err(|_| MobileError::new("AUTOFILL_SETTINGS_INVALID", "自动填充设置格式无效"))?;
    if settings.version != settings_version() {
        return Err(MobileError::new(
            "AUTOFILL_SETTINGS_INVALID",
            "自动填充设置版本不受支持",
        ));
    }
    Ok(settings)
}

fn load_or_reset_settings(
    root: &Path,
    session: &VaultSession,
) -> Result<AutofillSettings, MobileError> {
    match load_settings(root, session) {
        Ok(settings) => Ok(settings),
        Err(_) => {
            storage::delete_autofill_settings(root)?;
            Ok(AutofillSettings {
                version: settings_version(),
                ..AutofillSettings::default()
            })
        }
    }
}

fn save_settings(
    root: &Path,
    session: &VaultSession,
    settings: &AutofillSettings,
) -> Result<(), MobileError> {
    let plaintext = serde_json::to_vec(settings)
        .map_err(|_| MobileError::new("AUTOFILL_SETTINGS_INVALID", "无法保存自动填充设置"))?;
    let encrypted = session.encrypt_scoped_bytes(SETTINGS_PURPOSE, &plaintext)?;
    storage::persist_autofill_settings(root, &encrypted)
}

fn build_candidates(
    entries: &[EntryRecord],
    target: &AutofillTarget,
    settings: &AutofillSettings,
) -> Vec<AutofillCandidate> {
    let bound_entry = settings.bindings.get(&target.key());
    let mut candidates: Vec<(u16, AutofillCandidate)> = entries
        .iter()
        .filter_map(|entry| {
            let saved_mapping = settings.field_mappings.get(&entry.id);
            let mapping = infer_mapping(entry, saved_mapping)?;
            let (score, match_label) = entry_match(entry, target, bound_entry);
            let username_preview = mapping
                .username_field
                .as_deref()
                .and_then(|name| entry.fields.iter().find(|field| field.name == name))
                .map(|field| field.value.clone())
                .unwrap_or_default();
            let fields = entry
                .fields
                .iter()
                .filter(|field| !field.value.is_empty())
                .map(|field| AutofillFieldOption {
                    name: field.name.clone(),
                    hidden: field.hidden,
                    copyable: field.copyable,
                })
                .collect();
            Some((
                score,
                AutofillCandidate {
                    entry_id: entry.id.clone(),
                    title: entry.title.clone(),
                    username_preview,
                    username_field: mapping.username_field,
                    password_field: mapping.password_field,
                    fields,
                    matched: score > 0,
                    match_label,
                    mapping_confident: mapping.confident,
                },
            ))
        })
        .collect();
    candidates.sort_by(|(left_score, left), (right_score, right)| {
        right_score
            .cmp(left_score)
            .then_with(|| left.title.to_lowercase().cmp(&right.title.to_lowercase()))
    });
    candidates
        .into_iter()
        .map(|(_, candidate)| candidate)
        .collect()
}

struct InferredMapping {
    username_field: Option<String>,
    password_field: String,
    confident: bool,
}

fn infer_mapping(entry: &EntryRecord, saved: Option<&FieldMapping>) -> Option<InferredMapping> {
    let non_empty: Vec<&FieldRecord> = entry
        .fields
        .iter()
        .filter(|field| !field.value.is_empty())
        .collect();
    if non_empty.is_empty() {
        return None;
    }
    if let Some(saved) = saved {
        let password_exists = non_empty
            .iter()
            .any(|field| field.name == saved.password_field);
        let username_exists = saved
            .username_field
            .as_ref()
            .is_none_or(|name| non_empty.iter().any(|field| field.name == *name));
        if password_exists && username_exists {
            return Some(InferredMapping {
                username_field: saved.username_field.clone(),
                password_field: saved.password_field.clone(),
                confident: true,
            });
        }
    }

    let (password, password_score) = non_empty
        .iter()
        .map(|field| (*field, password_score(field)))
        .max_by_key(|(_, score)| *score)?;
    if password_score == 0 {
        return None;
    }
    let username = non_empty
        .iter()
        .filter(|field| field.name != password.name)
        .map(|field| (*field, username_score(field)))
        .max_by_key(|(_, score)| *score)
        .filter(|(_, score)| *score > 0);
    Some(InferredMapping {
        username_field: username.map(|(field, _)| field.name.clone()),
        password_field: password.name.clone(),
        confident: password_score >= 100
            && username.is_none_or(|(_, username_score)| username_score >= 100),
    })
}

fn password_score(field: &FieldRecord) -> u16 {
    let name = normalized_field_name(&field.name);
    let explicit = [
        "密码",
        "口令",
        "登录密码",
        "password",
        "passwd",
        "passcode",
        "pwd",
    ]
    .iter()
    .any(|token| name == *token || name.contains(token));
    if explicit {
        100 + u16::from(field.hidden) * 30 + u16::from(field.copyable) * 10
    } else if field.hidden {
        40 + u16::from(field.copyable) * 10
    } else {
        0
    }
}

fn username_score(field: &FieldRecord) -> u16 {
    let name = normalized_field_name(&field.name);
    let explicit = [
        "账号",
        "帐户",
        "账户",
        "用户名",
        "登录名",
        "邮箱",
        "邮件",
        "手机号",
        "username",
        "user",
        "login",
        "email",
        "account",
        "phone",
    ]
    .iter()
    .any(|token| name == *token || name.contains(token));
    if explicit {
        100 + u16::from(!field.hidden) * 20 + u16::from(field.copyable) * 10
    } else if !field.hidden && field.copyable {
        20
    } else {
        0
    }
}

fn normalized_field_name(name: &str) -> String {
    name.chars()
        .filter(|character| character.is_alphanumeric())
        .flat_map(char::to_lowercase)
        .collect()
}

fn entry_match(
    entry: &EntryRecord,
    target: &AutofillTarget,
    bound_entry: Option<&String>,
) -> (u16, String) {
    if bound_entry.is_some_and(|id| id == &entry.id) {
        return (1000, "已绑定到此目标".to_string());
    }
    let Some(target_domain) = target.web_domain.as_deref() else {
        return (0, "可手动选择".to_string());
    };
    let Some(entry_domain) = Url::parse(&entry.url)
        .ok()
        .and_then(|url| url.host_str().map(str::to_ascii_lowercase))
    else {
        return (0, "可手动选择".to_string());
    };
    if entry_domain == target_domain {
        return (900, "网址完全匹配".to_string());
    }
    if domain_is_related(&entry_domain, target_domain) {
        return (800, "同一网站".to_string());
    }
    (0, "可手动选择".to_string())
}

fn domain_is_related(left: &str, right: &str) -> bool {
    left.ends_with(&format!(".{right}")) || right.ends_with(&format!(".{left}"))
}

fn field_value(entry: &EntryRecord, name: &str) -> Result<String, MobileError> {
    entry
        .fields
        .iter()
        .find(|field| field.name == name)
        .map(|field| field.value.clone())
        .ok_or_else(|| MobileError::new("AUTOFILL_FIELD_INVALID", "所选自动填充字段不存在"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mobile::models::{EntryDraft, FieldRecord};
    use secretbase_vault_core::{VaultDocument, VaultSession};

    fn entry(id: &str, title: &str, url: &str, username: &str, password: &str) -> EntryRecord {
        EntryRecord {
            id: id.to_string(),
            title: title.to_string(),
            url: url.to_string(),
            starred: false,
            tags: Vec::new(),
            groups: Vec::new(),
            fields: vec![
                FieldRecord {
                    name: "账号".to_string(),
                    value: username.to_string(),
                    copyable: true,
                    hidden: false,
                },
                FieldRecord {
                    name: "密码".to_string(),
                    value: password.to_string(),
                    copyable: true,
                    hidden: true,
                },
            ],
            remarks: String::new(),
            created_at: String::new(),
            updated_at: String::new(),
            deleted: false,
            deleted_at: None,
        }
    }

    #[test]
    fn exact_domain_candidates_rank_before_unmatched_entries() {
        let target = AutofillTarget {
            package_name: "com.android.chrome".to_string(),
            web_domain: Some("login.example.test".to_string()),
            web_scheme: Some("https".to_string()),
        };
        let entries = vec![
            entry(
                "other",
                "其他",
                "https://other.example.test",
                "other",
                "secret",
            ),
            entry(
                "match",
                "匹配",
                "https://login.example.test/account",
                "owner",
                "secret",
            ),
        ];
        let candidates = build_candidates(&entries, &target, &AutofillSettings::default());
        assert_eq!(candidates[0].entry_id, "match");
        assert!(candidates[0].matched);
        assert!(!candidates[1].matched);
    }

    #[test]
    fn hidden_field_fallback_requires_mapping_confirmation() {
        let mut record = entry("token", "令牌", "", "owner", "secret");
        record.fields[1].name = "API Token".to_string();
        let mapping = infer_mapping(&record, None).unwrap();
        assert_eq!(mapping.password_field, "API Token");
        assert!(!mapping.confident);
    }

    #[test]
    fn related_domains_require_dot_boundary() {
        assert!(domain_is_related("login.example.com", "example.com"));
        assert!(!domain_is_related("evil-example.com", "example.com"));
    }

    #[test]
    fn authenticated_open_does_not_return_password_until_selection() {
        let directory = tempfile::tempdir().unwrap();
        let mut value = document::new_document("2026-07-16T00:00:00Z");
        document::save_entry(
            &mut value,
            None,
            &EntryDraft {
                title: "Example".to_string(),
                url: "https://login.example.test".to_string(),
                starred: false,
                tags: Vec::new(),
                groups: Vec::new(),
                fields: vec![
                    FieldRecord {
                        name: "账号".to_string(),
                        value: "owner@example.test".to_string(),
                        copyable: true,
                        hidden: false,
                    },
                    FieldRecord {
                        name: "密码".to_string(),
                        value: "super-secret-value".to_string(),
                        copyable: true,
                        hidden: true,
                    },
                ],
                remarks: String::new(),
            },
            "2026-07-16T00:00:00Z",
        )
        .unwrap();
        let session = VaultSession::create(
            "correct horse battery staple",
            VaultDocument::from_value(value).unwrap(),
        )
        .unwrap();
        storage::persist_vault(directory.path(), &session.encrypted_bytes().unwrap(), false)
            .unwrap();

        let opened = open_with_password(
            directory.path().to_str().unwrap(),
            "correct horse battery staple",
            AutofillTarget {
                package_name: "com.android.chrome".to_string(),
                web_domain: Some("login.example.test".to_string()),
                web_scheme: Some("https".to_string()),
            },
        )
        .unwrap();
        let open_json = serde_json::to_string(&opened).unwrap();
        assert!(!open_json.contains("super-secret-value"));
        assert_eq!(opened.candidates.len(), 1);

        let candidate = &opened.candidates[0];
        let filled = select(
            &opened.session_token,
            AutofillSelection {
                entry_id: candidate.entry_id.clone(),
                username_field: candidate.username_field.clone(),
                password_field: candidate.password_field.clone(),
                remember_binding: true,
            },
        )
        .unwrap();
        assert_eq!(filled.username, "owner@example.test");
        assert_eq!(filled.password, "super-secret-value");
        assert!(storage::autofill_settings_path(directory.path()).is_file());
    }
}
