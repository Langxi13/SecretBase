use std::{fs, path::PathBuf};

use secretbase_vault_core::{
    decrypt_v1, encrypt_v1, encrypt_v1_with_parameters, inspect_header, validate_document,
    VaultDocument, VaultError, VaultSession,
};
use serde::Deserialize;
use serde_json::Value;
use sha2::{Digest, Sha256};

#[derive(Debug, Deserialize)]
struct Manifest {
    test_password: String,
    vectors: Vec<Vector>,
}

#[derive(Debug, Deserialize)]
struct Vector {
    name: String,
    salt_hex: String,
    nonce_hex: String,
    plaintext_file: String,
    encrypted_file: String,
    canonical_plaintext_sha256: String,
    encrypted_sha256: String,
}

fn fixture_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("vault-v1")
}

fn read_manifest() -> Result<Manifest, Box<dyn std::error::Error>> {
    let content = fs::read(fixture_dir().join("manifest.json"))?;
    Ok(serde_json::from_slice(&content)?)
}

fn fixed_array<const N: usize>(value: &str) -> Result<[u8; N], Box<dyn std::error::Error>> {
    let bytes = hex::decode(value)?;
    Ok(bytes
        .try_into()
        .map_err(|_| "invalid fixed vector length")?)
}

fn sha256_hex(content: &[u8]) -> String {
    format!("{:x}", Sha256::digest(content))
}

#[test]
fn python_vectors_decrypt_and_reencrypt_exactly() -> Result<(), Box<dyn std::error::Error>> {
    let manifest = read_manifest()?;
    for vector in manifest.vectors {
        let expected_value: Value =
            serde_json::from_slice(&fs::read(fixture_dir().join(&vector.plaintext_file))?)?;
        let expected_plaintext = serde_json::to_vec(&expected_value)?;
        let encrypted = fs::read(fixture_dir().join(&vector.encrypted_file))?;
        assert_eq!(
            sha256_hex(&expected_plaintext),
            vector.canonical_plaintext_sha256
        );
        assert_eq!(sha256_hex(&encrypted), vector.encrypted_sha256);

        let header = inspect_header(&encrypted)?;
        assert_eq!(hex::encode(header.salt), vector.salt_hex);
        assert_eq!(hex::encode(header.nonce), vector.nonce_hex);

        let document = decrypt_v1(&manifest.test_password, &encrypted)?;
        assert_eq!(
            document.as_value(),
            &expected_value,
            "{} payload",
            vector.name
        );
        let regenerated = encrypt_v1_with_parameters(
            &manifest.test_password,
            &document,
            fixed_array(&vector.salt_hex)?,
            fixed_array(&vector.nonce_hex)?,
        )?;
        assert_eq!(regenerated, encrypted, "{} encrypted bytes", vector.name);
    }
    Ok(())
}

#[test]
fn random_rust_encryption_round_trips() -> Result<(), Box<dyn std::error::Error>> {
    let manifest = read_manifest()?;
    let vector = manifest.vectors.first().ok_or("missing fixture vector")?;
    let document =
        VaultDocument::from_json_bytes(&fs::read(fixture_dir().join(&vector.plaintext_file))?)?;
    let encrypted = encrypt_v1(&manifest.test_password, &document)?;
    assert_ne!(
        encrypted,
        fs::read(fixture_dir().join(&vector.encrypted_file))?
    );
    assert_eq!(decrypt_v1(&manifest.test_password, &encrypted)?, document);
    Ok(())
}

#[test]
fn vault_session_reuses_key_and_preserves_candidate_isolation(
) -> Result<(), Box<dyn std::error::Error>> {
    let manifest = read_manifest()?;
    let vector = manifest.vectors.first().ok_or("missing fixture vector")?;
    let document =
        VaultDocument::from_json_bytes(&fs::read(fixture_dir().join(&vector.plaintext_file))?)?;
    let session = VaultSession::create(&manifest.test_password, document.clone())?;

    let mut candidate = document.as_value().clone();
    candidate["future_root"] = serde_json::json!({"mobile": true});
    let candidate = VaultDocument::from_value(candidate)?;
    let encrypted = session.encrypted_document_bytes(&candidate)?;

    assert_eq!(session.document(), &document);
    let unlocked = VaultSession::unlock(&manifest.test_password, &encrypted)?;
    assert_eq!(
        unlocked.document().as_value()["future_root"]["mobile"],
        true
    );
    Ok(())
}

#[test]
fn scoped_encryption_is_purpose_bound_and_rekeyed() -> Result<(), Box<dyn std::error::Error>> {
    let document = validate_document(serde_json::json!({
        "version": "1.0",
        "created_at": "2026-07-12T00:00:00Z",
        "app_name": "SecretBase",
        "entries": [],
        "deleted_entries": [],
        "tags_meta": {},
        "groups_meta": {}
    }))?;
    let mut session = VaultSession::create("old-password", document)?;
    let encrypted_settings = session.encrypt_scoped_bytes("mobile-ai-settings", b"secret")?;

    assert_eq!(
        session.decrypt_scoped_bytes("mobile-ai-settings", &encrypted_settings)?,
        b"secret"
    );
    assert_eq!(
        session.decrypt_scoped_bytes("another-purpose", &encrypted_settings),
        Err(VaultError::AuthenticationFailed)
    );

    session.rekey("new-password");
    let encrypted_vault = session.encrypted_bytes()?;
    assert_eq!(
        VaultSession::unlock("old-password", &encrypted_vault)
            .err()
            .ok_or("old password still works")?,
        VaultError::AuthenticationFailed
    );
    assert!(VaultSession::unlock("new-password", &encrypted_vault).is_ok());
    Ok(())
}

#[test]
fn unknown_fields_survive_json_round_trip() -> Result<(), Box<dyn std::error::Error>> {
    let value: Value = serde_json::from_slice(&fs::read(fixture_dir().join("unicode-rich.json"))?)?;
    let document = validate_document(value.clone())?;
    let round_trip: Value = serde_json::from_slice(&document.to_json_bytes()?)?;
    assert_eq!(round_trip, value);
    assert_eq!(round_trip["future_root"]["enabled"], Value::Bool(true));
    assert_eq!(round_trip["entries"][0]["future_entry"]["flags"][1], "测试");
    assert_eq!(
        round_trip["entries"][0]["fields"][0]["future_field"]["retain"],
        "字段扩展"
    );
    Ok(())
}

#[test]
fn invalid_envelopes_and_authentication_are_rejected() -> Result<(), Box<dyn std::error::Error>> {
    let manifest = read_manifest()?;
    let vector = manifest.vectors.last().ok_or("missing fixture vector")?;
    let encrypted = fs::read(fixture_dir().join(&vector.encrypted_file))?;

    assert_eq!(
        decrypt_v1("wrong-password", &encrypted),
        Err(VaultError::AuthenticationFailed)
    );
    assert_eq!(
        inspect_header(&encrypted[..64]),
        Err(VaultError::InvalidFormat("header is truncated"))
    );

    let mut wrong_magic = encrypted.clone();
    wrong_magic[..4].copy_from_slice(b"NOPE");
    assert_eq!(
        inspect_header(&wrong_magic),
        Err(VaultError::InvalidFormat("magic bytes do not match"))
    );

    let mut wrong_version = encrypted.clone();
    wrong_version[4] = 2;
    assert_eq!(
        inspect_header(&wrong_version),
        Err(VaultError::UnsupportedEnvelopeVersion(2))
    );

    let mut tampered = encrypted;
    tampered[49] ^= 1;
    assert_eq!(
        decrypt_v1(&manifest.test_password, &tampered),
        Err(VaultError::AuthenticationFailed)
    );
    Ok(())
}

#[test]
fn payload_versions_and_shapes_are_validated() -> Result<(), Box<dyn std::error::Error>> {
    let unsupported = br#"{
        "version":"2.0",
        "created_at":"2026-01-01T00:00:00Z",
        "app_name":"SecretBase",
        "entries":[],
        "deleted_entries":[],
        "tags_meta":{},
        "groups_meta":{}
    }"#;
    let error = VaultDocument::from_json_bytes(unsupported)
        .err()
        .ok_or("version 2 accepted")?;
    assert_eq!(error.code(), "UNSUPPORTED_PAYLOAD_VERSION");

    let invalid_root = VaultDocument::from_json_bytes(b"[]")
        .err()
        .ok_or("array root accepted")?;
    assert_eq!(invalid_root.code(), "INVALID_PAYLOAD");

    let invalid_field = br#"{
        "version":"1.0",
        "created_at":"2026-01-01T00:00:00Z",
        "app_name":"SecretBase",
        "entries":[{"title":"demo","fields":[{"name":"password","hidden":"yes"}]}],
        "deleted_entries":[],
        "tags_meta":{},
        "groups_meta":{}
    }"#;
    let error = VaultDocument::from_json_bytes(invalid_field)
        .err()
        .ok_or("invalid hidden field accepted")?;
    assert_eq!(error.code(), "INVALID_PAYLOAD");

    let normalized = br#"{
        "version":"1.0",
        "created_at":"2026-01-01T00:00:00Z",
        "app_name":"SecretBase",
        "entries":[{"title":"demo","tags":[" alpha ","alpha"],"groups":[" group "]}],
        "deleted_entries":[],
        "tags_meta":{},
        "groups_meta":{}
    }"#;
    let normalized = VaultDocument::from_json_bytes(normalized)?;
    assert_eq!(
        normalized.as_value()["entries"][0]["tags"],
        serde_json::json!(["alpha"])
    );
    assert_eq!(
        normalized.as_value()["entries"][0]["groups"],
        serde_json::json!(["group"])
    );

    let invalid_url = br#"{
        "version":"1.0",
        "created_at":"2026-01-01T00:00:00Z",
        "app_name":"SecretBase",
        "entries":[{"title":"demo","url":"ftp://vault.example.com"}],
        "deleted_entries":[],
        "tags_meta":{},
        "groups_meta":{}
    }"#;
    assert_eq!(
        VaultDocument::from_json_bytes(invalid_url)
            .err()
            .ok_or("invalid URL accepted")?
            .code(),
        "INVALID_PAYLOAD"
    );
    Ok(())
}
