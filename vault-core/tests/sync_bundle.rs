use std::{fs, path::PathBuf};

use secretbase_vault_core::sync_bundle::{decrypt_sync_bundle, SyncBundleError, SyncBundleKind};
use serde::Deserialize;
use serde_json::Value;
use sha2::{Digest, Sha256};

#[derive(Debug, Deserialize)]
struct Manifest {
    schema_version: u8,
    vectors: Vec<Vector>,
}

#[derive(Debug, Deserialize)]
struct Vector {
    name: String,
    kind: u8,
    key_hex: String,
    nonce_hex: String,
    vault_id: String,
    object_id: String,
    bundle_sha256: String,
    bundle_hex: String,
    payload: Value,
}

fn fixture_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("sync-v1")
        .join("manifest.json")
}

#[test]
fn python_sync_vectors_decrypt_in_rust() -> Result<(), Box<dyn std::error::Error>> {
    let manifest: Manifest = serde_json::from_slice(&fs::read(fixture_path())?)?;
    assert_eq!(manifest.schema_version, 1);
    for vector in manifest.vectors {
        let key = hex::decode(&vector.key_hex)?;
        let bundle = hex::decode(&vector.bundle_hex)?;
        let kind = SyncBundleKind::try_from(vector.kind)?;
        assert_eq!(&bundle[6..18], hex::decode(&vector.nonce_hex)?);
        assert_eq!(
            format!("{:x}", Sha256::digest(&bundle)),
            vector.bundle_sha256
        );
        assert_eq!(
            decrypt_sync_bundle(&bundle, &key, kind, &vector.vault_id, &vector.object_id)?,
            vector.payload,
            "{}",
            vector.name
        );

        let mut damaged = bundle.clone();
        let last = damaged.len() - 1;
        damaged[last] ^= 1;
        assert_eq!(
            decrypt_sync_bundle(&damaged, &key, kind, &vector.vault_id, &vector.object_id),
            Err(SyncBundleError::AuthenticationFailed)
        );
        assert_eq!(
            decrypt_sync_bundle(&bundle, &key, kind, &vector.vault_id, "wrong-object"),
            Err(SyncBundleError::AuthenticationFailed)
        );
    }
    Ok(())
}
