#[derive(Debug, Clone)]
pub struct VaultStatus {
    pub initialized: bool,
    pub unlocked: bool,
    pub revision: u64,
    pub entry_count: u32,
    pub deleted_count: u32,
}

#[derive(Debug, Clone)]
pub struct FieldRecord {
    pub name: String,
    pub value: String,
    pub copyable: bool,
    pub hidden: bool,
}

#[derive(Debug, Clone)]
pub struct EntryRecord {
    pub id: String,
    pub title: String,
    pub url: String,
    pub starred: bool,
    pub tags: Vec<String>,
    pub groups: Vec<String>,
    pub fields: Vec<FieldRecord>,
    pub remarks: String,
    pub created_at: String,
    pub updated_at: String,
    pub deleted: bool,
    pub deleted_at: Option<String>,
}

#[derive(Debug, Clone)]
pub struct EntryDraft {
    pub title: String,
    pub url: String,
    pub starred: bool,
    pub tags: Vec<String>,
    pub groups: Vec<String>,
    pub fields: Vec<FieldRecord>,
    pub remarks: String,
}

#[derive(Debug, Clone)]
pub struct EntryPage {
    pub items: Vec<EntryRecord>,
    pub page: u32,
    pub page_size: u32,
    pub total: u32,
    pub total_pages: u32,
    pub revision: u64,
}

#[derive(Debug, Clone)]
pub struct TaxonomyRecord {
    pub name: String,
    pub description: String,
    pub color: String,
    pub count: u32,
    pub order_index: Option<i64>,
}

#[derive(Debug, Clone)]
pub struct OperationResult {
    pub revision: u64,
    pub message: String,
}

#[derive(Debug, Clone)]
pub struct ImportPreview {
    pub token: String,
    pub entries: u32,
    pub deleted_entries: u32,
    pub tags: u32,
    pub groups: u32,
    pub source_revision: u64,
}

#[derive(Debug, Clone)]
pub struct RecoverySnapshot {
    pub id: String,
    pub created_at: String,
    pub size_bytes: u64,
}

#[derive(Debug, Clone)]
pub struct AiStatus {
    pub configured: bool,
    pub base_url: String,
    pub model: String,
    pub api_key_mask: String,
}

#[derive(Debug, Clone)]
pub struct AiHttpHeader {
    pub name: String,
    pub value: String,
}

#[derive(Debug, Clone)]
pub struct AiHttpRequest {
    pub method: String,
    pub url: String,
    pub headers: Vec<AiHttpHeader>,
    pub body: String,
    pub timeout_seconds: u32,
}

#[derive(Debug, Clone)]
pub struct AiSendSummary {
    pub title: String,
    pub entry_count: u32,
    pub input_chars: u32,
    pub includes_field_values: bool,
    pub categories: Vec<String>,
    pub privacy_note: String,
}

#[derive(Debug, Clone)]
pub struct AiRequestPlan {
    pub token: String,
    pub request: AiHttpRequest,
    pub summary: AiSendSummary,
}

#[derive(Debug, Clone)]
pub struct AiPreviewDetail {
    pub label: String,
    pub value: String,
    pub sensitive: bool,
    pub change_type: String,
}

#[derive(Debug, Clone)]
pub struct AiPreviewItem {
    pub id: String,
    pub title: String,
    pub subtitle: String,
    pub details: Vec<AiPreviewDetail>,
}

#[derive(Debug, Clone)]
pub struct AiPreview {
    pub token: String,
    pub kind: String,
    pub title: String,
    pub source_revision: u64,
    pub items: Vec<AiPreviewItem>,
    pub warnings: Vec<String>,
    pub privacy_note: String,
}
