use crate::mobile::{
    error::MobileError,
    models::{
        AiApplyResult, AiAssistantRequestPlan, AiAssistantTurnResult, AiConversation,
        AiConversationSummary, AiHttpRequest, AiPreview, AiRequestPlan, AiStatus, AiUndoState,
        EntryDraft, EntryPage, EntryRecord, ImportPreview, OperationResult, RecoverySnapshot,
        SyncConnection, SyncLocalState, SyncSetupPlan, SyncSnapshotInfo, SyncStatus,
        SyncUploadPlan, TaxonomyRecord, VaultStatus,
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

pub fn sync_status() -> Result<SyncStatus, MobileError> {
    runtime::sync_status()
}

pub fn sync_connection() -> Result<SyncConnection, MobileError> {
    runtime::sync_connection()
}

pub fn sync_update_config(
    base_url: String,
    username: String,
    password: Option<String>,
    device_name: String,
    auto_sync: bool,
) -> Result<SyncStatus, MobileError> {
    runtime::sync_update_config(base_url, username, password, device_name, auto_sync)
}

pub fn sync_prepare_create(
    base_url: String,
    username: String,
    password: String,
    device_name: String,
    auto_sync: bool,
) -> Result<SyncSetupPlan, MobileError> {
    runtime::sync_prepare_create(base_url, username, password, device_name, auto_sync)
}

pub fn sync_commit_create(token: String) -> Result<SyncStatus, MobileError> {
    runtime::sync_commit_create(token)
}

pub fn sync_prepare_compact(
    password: String,
    expected_revision: u64,
) -> Result<SyncSetupPlan, MobileError> {
    runtime::sync_prepare_compact(password, expected_revision)
}

pub fn sync_commit_compact(token: String) -> Result<SyncStatus, MobileError> {
    runtime::sync_commit_compact(token)
}

pub fn sync_prepare_rotate(
    password: String,
    expected_revision: u64,
) -> Result<SyncSetupPlan, MobileError> {
    runtime::sync_prepare_rotate(password, expected_revision)
}

pub fn sync_commit_rotate(token: String) -> Result<SyncStatus, MobileError> {
    runtime::sync_commit_rotate(token)
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
    runtime::sync_prepare_join(
        base_url,
        username,
        password,
        recovery_code,
        device_name,
        auto_sync,
        merge_existing,
    )
}

pub fn sync_decode_snapshot(
    content: Vec<u8>,
    snapshot_id: String,
    setup_token: Option<String>,
) -> Result<SyncSnapshotInfo, MobileError> {
    runtime::sync_decode_snapshot(content, snapshot_id, setup_token)
}

pub fn sync_commit_join(
    token: String,
    document_json: String,
    frontier: Vec<String>,
    generation: u64,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    runtime::sync_commit_join(
        token,
        document_json,
        frontier,
        generation,
        expected_revision,
    )
}

pub fn sync_local_state() -> Result<SyncLocalState, MobileError> {
    runtime::sync_local_state()
}

pub fn sync_current_document_json() -> Result<String, MobileError> {
    runtime::sync_current_document_json()
}

pub fn sync_prepare_upload(
    document_json: Option<String>,
    parents: Vec<String>,
    generation: u64,
    expected_revision: u64,
) -> Result<SyncUploadPlan, MobileError> {
    runtime::sync_prepare_upload(document_json, parents, generation, expected_revision)
}

pub fn sync_commit_upload(token: String) -> Result<OperationResult, MobileError> {
    runtime::sync_commit_upload(token)
}

pub fn sync_apply_remote(
    document_json: String,
    frontier: Vec<String>,
    generation: u64,
    expected_revision: u64,
) -> Result<OperationResult, MobileError> {
    runtime::sync_apply_remote(document_json, frontier, generation, expected_revision)
}

pub fn sync_recovery_code(password: String) -> Result<String, MobileError> {
    runtime::sync_recovery_code(password)
}

pub fn sync_prepare_remote_delete(password: String) -> Result<String, MobileError> {
    runtime::sync_prepare_remote_delete(password)
}

pub fn sync_commit_remote_delete(token: String) -> Result<SyncStatus, MobileError> {
    runtime::sync_commit_remote_delete(token)
}

pub fn sync_disconnect() -> Result<SyncStatus, MobileError> {
    runtime::sync_disconnect()
}

pub fn sync_cancel_pending() -> Result<(), MobileError> {
    runtime::sync_cancel_pending()
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

pub fn cancel_ai_pending() -> Result<(), MobileError> {
    runtime::cancel_ai_pending()
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
