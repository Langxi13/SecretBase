use std::path::Path;

use chrono::{SecondsFormat, Utc};
use secretbase_vault_core::VaultSession;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::mobile::{
    error::MobileError,
    models::{AiConversation, AiConversationMessage, AiConversationSummary},
    storage,
};

const HISTORY_PURPOSE: &str = "mobile-ai-history";
const MAX_CONVERSATIONS: usize = 50;
const MAX_MESSAGES: usize = 200;
const MAX_CONTEXT_MESSAGES: usize = 16;

#[derive(Debug, Default, Serialize, Deserialize)]
struct HistoryFile {
    #[serde(default = "history_version")]
    version: u32,
    #[serde(default)]
    conversations: Vec<ConversationRecord>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ConversationRecord {
    id: String,
    title: String,
    created_at: String,
    updated_at: String,
    #[serde(default)]
    messages: Vec<MessageRecord>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct MessageRecord {
    id: String,
    role: String,
    content: String,
    mode: String,
    created_at: String,
}

fn history_version() -> u32 {
    1
}

fn now() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

fn load(root: &Path, session: &VaultSession) -> Result<HistoryFile, MobileError> {
    let Some(content) = storage::read_ai_history(root)? else {
        return Ok(HistoryFile {
            version: history_version(),
            conversations: Vec::new(),
        });
    };
    let plaintext = session
        .decrypt_scoped_bytes(HISTORY_PURPOSE, &content)
        .map_err(|_| {
            MobileError::new(
                "AI_HISTORY_INVALID",
                "本机 AI 对话历史无法解密，可能属于另一份密码库",
            )
        })?;
    let history: HistoryFile = serde_json::from_slice(&plaintext)
        .map_err(|_| MobileError::new("AI_HISTORY_INVALID", "本机 AI 对话历史格式无效"))?;
    if history.version != history_version() {
        return Err(MobileError::new(
            "AI_HISTORY_INVALID",
            "本机 AI 对话历史版本暂不受支持",
        ));
    }
    Ok(history)
}

fn save(root: &Path, session: &VaultSession, history: &mut HistoryFile) -> Result<(), MobileError> {
    history
        .conversations
        .sort_by(|left, right| right.updated_at.cmp(&left.updated_at));
    history.conversations.truncate(MAX_CONVERSATIONS);
    for conversation in &mut history.conversations {
        if conversation.messages.len() > MAX_MESSAGES {
            conversation.messages = conversation
                .messages
                .split_off(conversation.messages.len() - MAX_MESSAGES);
        }
    }
    let plaintext = serde_json::to_vec(history)
        .map_err(|_| MobileError::new("AI_HISTORY_INVALID", "无法序列化 AI 对话历史"))?;
    let encrypted = session.encrypt_scoped_bytes(HISTORY_PURPOSE, &plaintext)?;
    storage::persist_ai_history(root, &encrypted)
}

fn summary(record: &ConversationRecord) -> AiConversationSummary {
    AiConversationSummary {
        id: record.id.clone(),
        title: record.title.clone(),
        created_at: record.created_at.clone(),
        updated_at: record.updated_at.clone(),
        message_count: u32::try_from(record.messages.len()).unwrap_or(u32::MAX),
    }
}

fn public(record: &ConversationRecord) -> AiConversation {
    AiConversation {
        id: record.id.clone(),
        title: record.title.clone(),
        created_at: record.created_at.clone(),
        updated_at: record.updated_at.clone(),
        messages: record
            .messages
            .iter()
            .map(|message| AiConversationMessage {
                id: message.id.clone(),
                role: message.role.clone(),
                content: message.content.clone(),
                mode: message.mode.clone(),
                created_at: message.created_at.clone(),
            })
            .collect(),
    }
}

pub fn list(
    root: &Path,
    session: &VaultSession,
) -> Result<Vec<AiConversationSummary>, MobileError> {
    Ok(load(root, session)?
        .conversations
        .iter()
        .map(summary)
        .collect())
}

pub fn get(
    root: &Path,
    session: &VaultSession,
    id: &str,
) -> Result<Option<AiConversation>, MobileError> {
    Ok(load(root, session)?
        .conversations
        .iter()
        .find(|conversation| conversation.id == id)
        .map(public))
}

pub fn create(
    root: &Path,
    session: &VaultSession,
    title: &str,
) -> Result<AiConversationSummary, MobileError> {
    let mut history = load(root, session)?;
    let timestamp = now();
    let record = ConversationRecord {
        id: Uuid::new_v4().to_string(),
        title: bounded_title(title),
        created_at: timestamp.clone(),
        updated_at: timestamp,
        messages: Vec::new(),
    };
    let result = summary(&record);
    history.conversations.insert(0, record);
    save(root, session, &mut history)?;
    Ok(result)
}

pub fn ensure(
    root: &Path,
    session: &VaultSession,
    id: Option<&str>,
    first_message: &str,
) -> Result<String, MobileError> {
    if let Some(id) = id.filter(|value| !value.trim().is_empty()) {
        if get(root, session, id)?.is_some() {
            return Ok(id.to_string());
        }
    }
    Ok(create(root, session, first_message)?.id)
}

pub fn append_turn(
    root: &Path,
    session: &VaultSession,
    conversation_id: &str,
    user_message: &str,
    assistant_message: &str,
    mode: &str,
) -> Result<(), MobileError> {
    let mut history = load(root, session)?;
    let conversation = history
        .conversations
        .iter_mut()
        .find(|conversation| conversation.id == conversation_id)
        .ok_or_else(|| MobileError::new("AI_CONVERSATION_NOT_FOUND", "AI 对话不存在"))?;
    let timestamp = now();
    for (role, content) in [("user", user_message), ("assistant", assistant_message)] {
        let content = if role == "user" && mode == "sensitive_create" {
            "已通过 AI 新建模式提交敏感内容（原文未保存）"
        } else {
            content.trim()
        };
        if content.is_empty() {
            continue;
        }
        conversation.messages.push(MessageRecord {
            id: Uuid::new_v4().to_string(),
            role: role.to_string(),
            content: content.chars().take(12_000).collect(),
            mode: mode.to_string(),
            created_at: timestamp.clone(),
        });
    }
    conversation.updated_at = timestamp;
    if conversation.title == "新对话" {
        conversation.title = bounded_title(user_message);
    }
    save(root, session, &mut history)
}

pub fn context(
    root: &Path,
    session: &VaultSession,
    conversation_id: &str,
) -> Result<Vec<serde_json::Value>, MobileError> {
    let Some(conversation) = load(root, session)?
        .conversations
        .into_iter()
        .find(|conversation| conversation.id == conversation_id)
    else {
        return Ok(Vec::new());
    };
    let messages = conversation
        .messages
        .into_iter()
        .filter(|message| message.mode == "assistant")
        .collect::<Vec<_>>();
    Ok(messages
        .into_iter()
        .rev()
        .take(MAX_CONTEXT_MESSAGES)
        .collect::<Vec<_>>()
        .into_iter()
        .rev()
        .map(|message| {
            serde_json::json!({
                "role": message.role,
                "content": message.content.chars().take(4000).collect::<String>()
            })
        })
        .collect())
}

pub fn delete(root: &Path, session: &VaultSession, id: &str) -> Result<bool, MobileError> {
    let mut history = load(root, session)?;
    let original = history.conversations.len();
    history
        .conversations
        .retain(|conversation| conversation.id != id);
    if history.conversations.len() == original {
        return Ok(false);
    }
    save(root, session, &mut history)?;
    Ok(true)
}

pub fn clear(root: &Path) -> Result<(), MobileError> {
    storage::delete_ai_history(root)
}

fn bounded_title(value: &str) -> String {
    let title = value
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .chars()
        .take(32)
        .collect::<String>();
    if title.is_empty() {
        "新对话".to_string()
    } else {
        title
    }
}

#[cfg(test)]
mod tests {
    use secretbase_vault_core::{VaultDocument, VaultSession};

    use super::*;
    use crate::mobile::document;

    #[test]
    fn history_is_encrypted_and_sensitive_turns_are_not_reused_as_context() {
        let directory = tempfile::tempdir().unwrap();
        let session = VaultSession::create(
            "test-password",
            VaultDocument::from_value(document::new_document("2026-07-14T00:00:00.000000Z"))
                .unwrap(),
        )
        .unwrap();
        let conversation = create(directory.path(), &session, "测试").unwrap();
        append_turn(
            directory.path(),
            &session,
            &conversation.id,
            "password: never-send",
            "已创建建议",
            "sensitive_create",
        )
        .unwrap();
        append_turn(
            directory.path(),
            &session,
            &conversation.id,
            "整理标签",
            "已生成建议",
            "assistant",
        )
        .unwrap();

        let bytes = storage::read_ai_history(directory.path()).unwrap().unwrap();
        assert!(!String::from_utf8_lossy(&bytes).contains("never-send"));
        let model_context = context(directory.path(), &session, &conversation.id).unwrap();
        let serialized = serde_json::to_string(&model_context).unwrap();
        assert!(!serialized.contains("never-send"));
        assert!(serialized.contains("整理标签"));
        let saved = get(directory.path(), &session, &conversation.id)
            .unwrap()
            .unwrap();
        assert!(!saved
            .messages
            .iter()
            .any(|message| message.content.contains("never-send")));
    }
}
