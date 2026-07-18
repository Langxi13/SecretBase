use secretbase_vault_core::sync_bundle_v2::{
    decode_recovery_code, decrypt_snapshot, encode_recovery_code, encrypt_snapshot,
};
use serde_json::json;

const VAULT_ID: &str = "11111111-1111-4111-8111-111111111111";
const SPACE_ID: &str = "22222222-2222-4222-8222-222222222222";
const SNAPSHOT_ID: &str = "33333333-3333-4333-8333-333333333333";

#[test]
fn v2_bundle_and_recovery_round_trip() {
    let key = [0x42_u8; 32];
    let payload = json!({
        "schema_version": 2,
        "protocol": "snapshot-dag",
        "vault_id": VAULT_ID,
        "space_id": SPACE_ID,
        "snapshot_id": SNAPSHOT_ID,
        "generation": 1,
        "parents": [],
        "document": {"secret": "never-plaintext"}
    });
    let encrypted = encrypt_snapshot(&payload, &key, VAULT_ID, SPACE_ID, SNAPSHOT_ID)
        .unwrap_or_else(|error| panic!("encrypt failed: {error}"));
    assert!(!encrypted
        .windows("never-plaintext".len())
        .any(|window| window == b"never-plaintext"));
    let decrypted = decrypt_snapshot(&encrypted, &key, VAULT_ID, SPACE_ID, SNAPSHOT_ID)
        .unwrap_or_else(|error| panic!("decrypt failed: {error}"));
    assert_eq!(decrypted, payload);

    let code = encode_recovery_code(VAULT_ID, SPACE_ID, &key)
        .unwrap_or_else(|error| panic!("encode recovery failed: {error}"));
    let decoded = decode_recovery_code(&code)
        .unwrap_or_else(|error| panic!("decode recovery failed: {error}"));
    assert_eq!(decoded.0, VAULT_ID);
    assert_eq!(decoded.1, SPACE_ID);
    assert_eq!(decoded.2, key);
}

#[test]
fn v2_bundle_is_bound_to_space_and_snapshot() {
    let key = [7_u8; 32];
    let payload = json!({"document": {}});
    let encrypted = encrypt_snapshot(&payload, &key, VAULT_ID, SPACE_ID, SNAPSHOT_ID)
        .unwrap_or_else(|error| panic!("encrypt failed: {error}"));
    assert!(decrypt_snapshot(
        &encrypted,
        &key,
        VAULT_ID,
        "44444444-4444-4444-8444-444444444444",
        SNAPSHOT_ID,
    )
    .is_err());
}
