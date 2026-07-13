use std::collections::HashMap;

use serde::{Deserialize, Serialize};
use zeroize::Zeroize;

use crate::mobile::models::{AiHttpRequest, AiPreview, AiSendSummary};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AiKind {
    Parse,
    EntryTags,
    Groups,
    TagGovernance,
    Actions,
}

impl AiKind {
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "parse" => Some(Self::Parse),
            "entry_tags" => Some(Self::EntryTags),
            "groups" => Some(Self::Groups),
            "tag_governance" => Some(Self::TagGovernance),
            "actions" => Some(Self::Actions),
            _ => None,
        }
    }

    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Parse => "parse",
            Self::EntryTags => "entry_tags",
            Self::Groups => "groups",
            Self::TagGovernance => "tag_governance",
            Self::Actions => "actions",
        }
    }

    pub const fn title(self) -> &'static str {
        match self {
            Self::Parse => "文本解析建议",
            Self::EntryTags => "单条目标签建议",
            Self::Groups => "密码组整理建议",
            Self::TagGovernance => "标签治理建议",
            Self::Actions => "操作计划",
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AiConfig {
    pub base_url: String,
    pub api_key: String,
    pub model: String,
    pub saved_at: String,
}

impl Drop for AiConfig {
    fn drop(&mut self) {
        self.api_key.zeroize();
    }
}

#[derive(Debug, Clone)]
pub struct PendingAiRequest {
    pub token: String,
    pub kind: AiKind,
    pub source_revision: u64,
    pub input_chars: u32,
    pub input_lines: u32,
    pub entry_aliases: HashMap<String, String>,
}

#[derive(Debug, Clone)]
pub struct FieldAlias {
    pub entry_id: String,
    pub index: usize,
    pub name: String,
}

#[derive(Debug, Clone)]
pub struct PendingAssistantRequest {
    pub token: String,
    pub source_revision: u64,
    pub conversation_id: String,
    pub user_message: String,
    pub mode: String,
    pub input_chars: u32,
    pub input_lines: u32,
    pub entry_aliases: HashMap<String, String>,
    pub field_aliases: HashMap<String, FieldAlias>,
}

#[derive(Debug, Clone)]
pub struct PreparedAssistantRequest {
    pub conversation_id: String,
    pub token: String,
    pub request: AiHttpRequest,
    pub summary: AiSendSummary,
    pub mode: String,
    pub pending: PendingAssistantRequest,
}

#[derive(Debug, Clone)]
pub struct PendingAiPreview {
    pub preview: AiPreview,
    pub data: PreviewData,
}

#[derive(Debug, Clone)]
pub enum PreviewData {
    Parsed(Vec<ParsedEntry>),
    Organize(Vec<OrganizeSuggestion>),
    Governance(Vec<TagGovernanceSuggestion>),
    Actions(Vec<ActionPlan>),
    Assistant(Vec<AssistantAction>),
}

#[derive(Debug, Clone)]
pub struct AssistantAction {
    pub id: String,
    pub action_type: String,
    pub entry_ids: Vec<String>,
    pub entry_id: Option<String>,
    pub source_entry_id: Option<String>,
    pub field_index: Option<usize>,
    pub field_name: Option<String>,
    pub name: Option<String>,
    pub new_name: Option<String>,
    pub title: Option<String>,
    pub description: String,
    pub color: Option<String>,
    pub source_tags: Vec<String>,
    pub target_tag: Option<String>,
    pub add: Vec<String>,
    pub remove: Vec<String>,
    pub tags: Vec<String>,
    pub groups: Vec<String>,
    pub fields: Vec<ParsedField>,
    pub copyable: Option<bool>,
    pub hidden: Option<bool>,
    pub reason: String,
}

#[derive(Debug, Clone)]
pub struct NormalizedAssistantResponse {
    pub message: String,
    pub preview: Option<PendingAiPreview>,
    pub warnings: Vec<String>,
    pub navigation_entry_id: Option<String>,
    pub navigation_entry_title: Option<String>,
}

#[derive(Debug, Clone)]
pub struct ParsedEntry {
    pub id: String,
    pub title: String,
    pub url: String,
    pub fields: Vec<ParsedField>,
    pub tags: Vec<String>,
    pub groups: Vec<String>,
    pub remarks: String,
}

#[derive(Debug, Clone)]
pub struct ParsedField {
    pub name: String,
    pub value: String,
    pub copyable: bool,
    pub hidden: bool,
}

#[derive(Debug, Clone)]
pub struct OrganizeSuggestion {
    pub id: String,
    pub entry_id: String,
    pub add_tags: Vec<String>,
    pub remove_tags: Vec<String>,
    pub add_groups: Vec<String>,
    pub remove_groups: Vec<String>,
    pub group_descriptions: Vec<(String, String)>,
    pub reason: String,
}

#[derive(Debug, Clone)]
pub struct TagGovernanceSuggestion {
    pub id: String,
    pub action: String,
    pub tag: Option<String>,
    pub new_tag: Option<String>,
    pub source_tags: Vec<String>,
    pub target_tag: Option<String>,
    pub entry_ids: Vec<String>,
    pub description: String,
    pub color: Option<String>,
    pub reason: String,
}

#[derive(Debug, Clone)]
pub struct ActionPlan {
    pub id: String,
    pub action_type: String,
    pub group: Option<String>,
    pub group_new: Option<String>,
    pub description: String,
    pub title: Option<String>,
    pub url: Option<String>,
    pub tags: Vec<String>,
    pub groups: Vec<String>,
    pub remarks: String,
    pub fields: Vec<ParsedField>,
    pub entry_id: Option<String>,
    pub source_entry_id: Option<String>,
    pub field_index: Option<usize>,
    pub field_name: Option<String>,
    pub field_name_new: Option<String>,
    pub add_tags: Vec<String>,
    pub remove_tags: Vec<String>,
    pub add_groups: Vec<String>,
    pub remove_groups: Vec<String>,
    pub reason: String,
}
