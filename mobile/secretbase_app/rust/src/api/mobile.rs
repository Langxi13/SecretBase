use crate::mobile::{
    error::MobileError,
    models::{
        AiApplyResult, AiAssistantRequestPlan, AiAssistantTurnResult, AiConversation,
        AiConversationSummary, AiHttpRequest, AiPreview, AiRequestPlan, AiStatus, AiUndoState,
        EntryDraft, EntryPage, EntryRecord, ImportPreview, OperationResult, RecoverySnapshot,
        TaxonomyRecord, VaultStatus,
    },
    runtime,
};

#[flutter_rust_bridge::frb(init)]
pub fn init_app() {
    flutter_rust_bridge::setup_default_user_utils();
}

pub fn initialize_runtime(data_root: String) -> Result<VaultStatus, MobileError> {
    runtime::initialize_runtime(data_root)
}

pub fn vault_status() -> Result<VaultStatus, MobileError> {
    runtime::vault_status()
}

pub fn create_vault(password: String) -> Result<VaultStatus, MobileError> {
    runtime::create_vault(password)
}

pub fn unlock_vault(password: String) -> Result<VaultStatus, MobileError> {
    runtime::unlock_vault(password)
}

pub fn prepare_device_unlock_credential(password: String) -> Result<Vec<u8>, MobileError> {
    runtime::prepare_device_unlock_credential(password)
}

pub fn unlock_vault_with_device_credential(
    credential: Vec<u8>,
) -> Result<VaultStatus, MobileError> {
    runtime::unlock_vault_with_device_credential(credential)
}

pub fn lock_vault() -> Result<VaultStatus, MobileError> {
    runtime::lock_vault()
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
    runtime::list_entries(page, page_size, search, tag, group, starred, deleted)
}

pub fn get_entry(id: String) -> Result<EntryRecord, MobileError> {
    runtime::get_entry(id)
}

pub fn save_entry(
    id: Option<String>,
    draft: EntryDraft,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    runtime::save_entry(id, draft, expected_revision)
}

pub fn trash_entry(id: String, expected_revision: u64) -> Result<OperationResult, MobileError> {
    runtime::trash_entry(id, expected_revision)
}

pub fn restore_entry(id: String, expected_revision: u64) -> Result<OperationResult, MobileError> {
    runtime::restore_entry(id, expected_revision)
}

pub fn purge_entry(id: String, expected_revision: u64) -> Result<OperationResult, MobileError> {
    runtime::purge_entry(id, expected_revision)
}

pub fn list_taxonomy(kind: String) -> Result<Vec<TaxonomyRecord>, MobileError> {
    runtime::list_taxonomy(kind)
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
    runtime::save_taxonomy(kind, old_name, name, description, color, expected_revision)
}

pub fn delete_taxonomy(
    kind: String,
    name: String,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    runtime::delete_taxonomy(kind, name, expected_revision)
}

pub fn delete_taxonomies(
    kind: String,
    names: Vec<String>,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    runtime::delete_taxonomies(kind, names, expected_revision)
}

pub fn save_group_order(
    names: Vec<String>,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    runtime::save_group_order(names, expected_revision)
}

pub fn export_encrypted_vault() -> Result<Vec<u8>, MobileError> {
    runtime::export_encrypted_vault()
}

pub fn preview_import(content: Vec<u8>, password: String) -> Result<ImportPreview, MobileError> {
    runtime::preview_import(content, password)
}

pub fn apply_import(token: String) -> Result<OperationResult, MobileError> {
    runtime::apply_import(token)
}

pub fn pending_import_preview() -> Result<Option<ImportPreview>, MobileError> {
    runtime::pending_import_preview()
}

pub fn list_recovery_snapshots() -> Result<Vec<RecoverySnapshot>, MobileError> {
    runtime::list_recovery_snapshots()
}

pub fn preview_recovery(id: String, password: String) -> Result<ImportPreview, MobileError> {
    runtime::preview_recovery(id, password)
}

pub fn change_password(
    new_password: String,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    runtime::change_password(new_password, expected_revision)
}

pub fn ai_status() -> Result<AiStatus, MobileError> {
    runtime::ai_status()
}

pub fn prepare_ai_models_request(
    base_url: String,
    api_key: String,
) -> Result<AiHttpRequest, MobileError> {
    runtime::prepare_ai_models_request(base_url, api_key)
}

pub fn parse_ai_models_response(content: String) -> Result<Vec<String>, MobileError> {
    runtime::parse_ai_models_response(content)
}

pub fn prepare_ai_verify_request(
    base_url: String,
    api_key: String,
    model: String,
) -> Result<AiHttpRequest, MobileError> {
    runtime::prepare_ai_verify_request(base_url, api_key, model)
}

pub fn verify_ai_response(content: String) -> Result<(), MobileError> {
    runtime::verify_ai_response(content)
}

pub fn save_ai_settings(
    base_url: String,
    api_key: String,
    model: String,
) -> Result<AiStatus, MobileError> {
    runtime::save_ai_settings(base_url, api_key, model)
}

pub fn clear_ai_settings() -> Result<AiStatus, MobileError> {
    runtime::clear_ai_settings()
}

pub fn prepare_ai_request(
    kind: String,
    input: String,
    entry_id: Option<String>,
    user_prompt: String,
) -> Result<AiRequestPlan, MobileError> {
    runtime::prepare_ai_request(kind, input, entry_id, user_prompt)
}

pub fn consume_ai_response(token: String, content: String) -> Result<AiPreview, MobileError> {
    runtime::consume_ai_response(token, content)
}

pub fn pending_ai_preview() -> Result<Option<AiPreview>, MobileError> {
    runtime::pending_ai_preview()
}

pub fn apply_ai_preview(
    token: String,
    selected_item_ids: Vec<String>,
    expected_revision: u64,
) -> Result<AiApplyResult, MobileError> {
    runtime::apply_ai_preview(token, selected_item_ids, expected_revision)
}

pub fn pending_ai_undo() -> Result<Option<AiUndoState>, MobileError> {
    runtime::pending_ai_undo()
}

pub fn undo_ai_preview(
    undo_token: String,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    runtime::undo_ai_preview(undo_token, expected_revision)
}

pub fn list_ai_conversations() -> Result<Vec<AiConversationSummary>, MobileError> {
    runtime::list_ai_conversations()
}

pub fn get_ai_conversation(id: String) -> Result<AiConversation, MobileError> {
    runtime::get_ai_conversation(id)
}

pub fn create_ai_conversation(title: String) -> Result<AiConversationSummary, MobileError> {
    runtime::create_ai_conversation(title)
}

pub fn delete_ai_conversation(id: String) -> Result<(), MobileError> {
    runtime::delete_ai_conversation(id)
}

pub fn clear_ai_conversations() -> Result<(), MobileError> {
    runtime::clear_ai_conversations()
}

pub fn prepare_ai_assistant_request(
    conversation_id: Option<String>,
    message: String,
    mode: String,
    selected_entry_ids: Vec<String>,
) -> Result<AiAssistantRequestPlan, MobileError> {
    runtime::prepare_ai_assistant_request(conversation_id, message, mode, selected_entry_ids)
}

pub fn consume_ai_assistant_response(
    token: String,
    content: String,
) -> Result<AiAssistantTurnResult, MobileError> {
    runtime::consume_ai_assistant_response(token, content)
}
