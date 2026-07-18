//! SecretBase Sync Bundle V2: immutable encrypted snapshot primitives.

use std::io::{Read, Write};

use aes_gcm::{aead::Aead, Aes256Gcm, KeyInit, Nonce};
use flate2::{read::GzDecoder, write::GzEncoder, Compression};
use rand_core::{OsRng, RngCore};
use serde_json::Value;
use sha2::{Digest, Sha256};
use thiserror::Error;
use uuid::Uuid;

pub const SYNC_V2_MAGIC: &[u8; 4] = b"SBS2";
pub const SYNC_V2_VERSION: u8 = 2;
pub const SYNC_V2_KIND_SNAPSHOT: u8 = 1;
pub const SYNC_V2_NONCE_LENGTH: usize = 12;
pub const SYNC_V2_HEADER_LENGTH: usize = 4 + 1 + 1 + SYNC_V2_NONCE_LENGTH;
pub const MAX_SYNC_V2_BUNDLE_BYTES: usize = 64 * 1024 * 1024;
pub const MAX_SYNC_V2_PLAINTEXT_BYTES: usize = 64 * 1024 * 1024;
const RECOVERY_PREFIX: &str = "SBSYNC2";

#[derive(Debug, Error, PartialEq, Eq)]
pub enum SyncBundleV2Error {
    #[error("sync v2 bundle format is invalid: {0}")]
    InvalidFormat(&'static str),
    #[error("sync v2 bundle context is invalid")]
    InvalidContext,
    #[error("sync v2 bundle authentication failed")]
    AuthenticationFailed,
    #[error("sync v2 bundle compression is invalid")]
    InvalidCompression,
    #[error("sync v2 payload is too large")]
    PayloadTooLarge,
    #[error("sync v2 payload is invalid")]
    InvalidPayload,
    #[error("sync v2 recovery code is invalid")]
    InvalidRecoveryCode,
}

impl SyncBundleV2Error {
    pub const fn code(&self) -> &'static str {
        match self {
            Self::InvalidFormat(_) => "SYNC_V2_INVALID_FORMAT",
            Self::InvalidContext => "SYNC_V2_INVALID_CONTEXT",
            Self::AuthenticationFailed => "SYNC_V2_AUTHENTICATION_FAILED",
            Self::InvalidCompression => "SYNC_V2_INVALID_COMPRESSION",
            Self::PayloadTooLarge => "SYNC_V2_PAYLOAD_TOO_LARGE",
            Self::InvalidPayload => "SYNC_V2_INVALID_PAYLOAD",
            Self::InvalidRecoveryCode => "SYNC_V2_INVALID_RECOVERY_CODE",
        }
    }
}

fn context_uuid(value: &str) -> Result<String, SyncBundleV2Error> {
    Uuid::parse_str(value)
        .map(|item| item.to_string())
        .map_err(|_| SyncBundleV2Error::InvalidContext)
}

fn aad(vault_id: &str, space_id: &str, snapshot_id: &str) -> Result<Vec<u8>, SyncBundleV2Error> {
    let vault_id = context_uuid(vault_id)?;
    let space_id = context_uuid(space_id)?;
    let snapshot_id = context_uuid(snapshot_id)?;
    let mut result = Vec::with_capacity(80);
    result.extend_from_slice(b"SecretBase Sync V2\0");
    result.extend_from_slice(vault_id.as_bytes());
    result.push(0);
    result.extend_from_slice(space_id.as_bytes());
    result.push(0);
    result.extend_from_slice(snapshot_id.as_bytes());
    Ok(result)
}

pub fn encrypt_snapshot(
    payload: &Value,
    key: &[u8],
    vault_id: &str,
    space_id: &str,
    snapshot_id: &str,
) -> Result<Vec<u8>, SyncBundleV2Error> {
    if key.len() != 32 || !payload.is_object() {
        return Err(SyncBundleV2Error::InvalidContext);
    }
    let aad = aad(vault_id, space_id, snapshot_id)?;
    let plaintext = serde_json::to_vec(payload).map_err(|_| SyncBundleV2Error::InvalidPayload)?;
    if plaintext.len() > MAX_SYNC_V2_PLAINTEXT_BYTES {
        return Err(SyncBundleV2Error::PayloadTooLarge);
    }
    let mut compressed = Vec::new();
    {
        let mut encoder = GzEncoder::new(&mut compressed, Compression::new(6));
        encoder
            .write_all(&plaintext)
            .map_err(|_| SyncBundleV2Error::InvalidCompression)?;
        encoder
            .finish()
            .map_err(|_| SyncBundleV2Error::InvalidCompression)?;
    }
    let cipher = Aes256Gcm::new_from_slice(key).map_err(|_| SyncBundleV2Error::InvalidContext)?;
    let mut nonce = [0_u8; SYNC_V2_NONCE_LENGTH];
    OsRng.fill_bytes(&mut nonce);
    let ciphertext = cipher
        .encrypt(
            Nonce::from_slice(&nonce),
            aes_gcm::aead::Payload {
                msg: &compressed,
                aad: &aad,
            },
        )
        .map_err(|_| SyncBundleV2Error::AuthenticationFailed)?;
    let mut result = Vec::with_capacity(SYNC_V2_HEADER_LENGTH + ciphertext.len());
    result.extend_from_slice(SYNC_V2_MAGIC);
    result.push(SYNC_V2_VERSION);
    result.push(SYNC_V2_KIND_SNAPSHOT);
    result.extend_from_slice(&nonce);
    result.extend_from_slice(&ciphertext);
    if result.len() > MAX_SYNC_V2_BUNDLE_BYTES {
        return Err(SyncBundleV2Error::PayloadTooLarge);
    }
    Ok(result)
}

pub fn decrypt_snapshot(
    content: &[u8],
    key: &[u8],
    vault_id: &str,
    space_id: &str,
    snapshot_id: &str,
) -> Result<Value, SyncBundleV2Error> {
    if content.len() < SYNC_V2_HEADER_LENGTH + 16 || content.len() > MAX_SYNC_V2_BUNDLE_BYTES {
        return Err(SyncBundleV2Error::InvalidFormat("invalid length"));
    }
    if &content[..4] != SYNC_V2_MAGIC
        || content[4] != SYNC_V2_VERSION
        || content[5] != SYNC_V2_KIND_SNAPSHOT
        || key.len() != 32
    {
        return Err(SyncBundleV2Error::InvalidFormat("invalid header"));
    }
    let aad = aad(vault_id, space_id, snapshot_id)?;
    let cipher = Aes256Gcm::new_from_slice(key).map_err(|_| SyncBundleV2Error::InvalidContext)?;
    let compressed = cipher
        .decrypt(
            Nonce::from_slice(&content[6..SYNC_V2_HEADER_LENGTH]),
            aes_gcm::aead::Payload {
                msg: &content[SYNC_V2_HEADER_LENGTH..],
                aad: &aad,
            },
        )
        .map_err(|_| SyncBundleV2Error::AuthenticationFailed)?;
    let mut decoder = GzDecoder::new(compressed.as_slice());
    let mut plaintext = Vec::new();
    decoder
        .by_ref()
        .take((MAX_SYNC_V2_PLAINTEXT_BYTES + 1) as u64)
        .read_to_end(&mut plaintext)
        .map_err(|_| SyncBundleV2Error::InvalidCompression)?;
    if plaintext.len() > MAX_SYNC_V2_PLAINTEXT_BYTES {
        return Err(SyncBundleV2Error::PayloadTooLarge);
    }
    let value: Value =
        serde_json::from_slice(&plaintext).map_err(|_| SyncBundleV2Error::InvalidPayload)?;
    if !value.is_object() {
        return Err(SyncBundleV2Error::InvalidPayload);
    }
    Ok(value)
}

fn base32_encode(bytes: &[u8]) -> String {
    const ALPHABET: &[u8; 32] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
    let mut output = String::new();
    let mut buffer = 0_u16;
    let mut bits = 0_u8;
    for byte in bytes {
        buffer = (buffer << 8) | u16::from(*byte);
        bits += 8;
        while bits >= 5 {
            bits -= 5;
            output.push(ALPHABET[((buffer >> bits) & 31) as usize] as char);
        }
    }
    if bits > 0 {
        output.push(ALPHABET[((buffer << (5 - bits)) & 31) as usize] as char);
    }
    output
}

fn base32_decode(value: &str) -> Result<Vec<u8>, SyncBundleV2Error> {
    let mut output = Vec::new();
    let mut buffer = 0_u32;
    let mut bits = 0_u8;
    for character in value.chars() {
        let upper = character.to_ascii_uppercase();
        let digit = match upper {
            'A'..='Z' => upper as u8 - b'A',
            '2'..='7' => upper as u8 - b'2' + 26,
            _ => return Err(SyncBundleV2Error::InvalidRecoveryCode),
        };
        buffer = (buffer << 5) | u32::from(digit);
        bits += 5;
        if bits >= 8 {
            bits -= 8;
            output.push((buffer >> bits) as u8);
            buffer &= (1_u32 << bits).saturating_sub(1);
        }
    }
    Ok(output)
}

pub fn encode_recovery_code(
    vault_id: &str,
    space_id: &str,
    key: &[u8],
) -> Result<String, SyncBundleV2Error> {
    if key.len() != 32 {
        return Err(SyncBundleV2Error::InvalidContext);
    }
    let vault = Uuid::parse_str(vault_id).map_err(|_| SyncBundleV2Error::InvalidContext)?;
    let space = Uuid::parse_str(space_id).map_err(|_| SyncBundleV2Error::InvalidContext)?;
    let mut payload = vec![SYNC_V2_VERSION];
    payload.extend_from_slice(vault.as_bytes());
    payload.extend_from_slice(space.as_bytes());
    payload.extend_from_slice(key);
    let mut hasher = Sha256::new();
    hasher.update(RECOVERY_PREFIX.as_bytes());
    hasher.update(&payload);
    payload.extend_from_slice(&hasher.finalize()[..4]);
    let encoded = base32_encode(&payload);
    let grouped = encoded
        .as_bytes()
        .chunks(5)
        .map(|chunk| String::from_utf8_lossy(chunk).into_owned())
        .collect::<Vec<_>>()
        .join("-");
    Ok(format!("{RECOVERY_PREFIX}-{grouped}"))
}

pub fn decode_recovery_code(value: &str) -> Result<(String, String, Vec<u8>), SyncBundleV2Error> {
    let normalized: String = value
        .chars()
        .filter(|character| *character != '-' && !character.is_whitespace())
        .map(|character| character.to_ascii_uppercase())
        .collect();
    if !normalized.starts_with(RECOVERY_PREFIX) {
        return Err(SyncBundleV2Error::InvalidRecoveryCode);
    }
    let raw = base32_decode(&normalized[RECOVERY_PREFIX.len()..])?;
    if raw.len() != 1 + 16 + 16 + 32 + 4 || raw[0] != SYNC_V2_VERSION {
        return Err(SyncBundleV2Error::InvalidRecoveryCode);
    }
    let mut hasher = Sha256::new();
    hasher.update(RECOVERY_PREFIX.as_bytes());
    hasher.update(&raw[..raw.len() - 4]);
    if hasher.finalize()[..4] != raw[raw.len() - 4..] {
        return Err(SyncBundleV2Error::InvalidRecoveryCode);
    }
    let vault =
        Uuid::from_slice(&raw[1..17]).map_err(|_| SyncBundleV2Error::InvalidRecoveryCode)?;
    let space =
        Uuid::from_slice(&raw[17..33]).map_err(|_| SyncBundleV2Error::InvalidRecoveryCode)?;
    Ok((vault.to_string(), space.to_string(), raw[33..65].to_vec()))
}
