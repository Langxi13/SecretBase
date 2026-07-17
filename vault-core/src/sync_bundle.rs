//! SecretBase Sync Bundle V1 decryption shared by future mobile clients.

use std::io::Read;

use aes_gcm::{
    aead::{Aead, KeyInit, Payload},
    Aes256Gcm, Nonce,
};
use flate2::read::GzDecoder;
use serde_json::Value;
use thiserror::Error;
use uuid::Uuid;

pub const SYNC_MAGIC: &[u8; 4] = b"SBS1";
pub const SYNC_VERSION: u8 = 1;
pub const SYNC_NONCE_LENGTH: usize = 12;
pub const SYNC_HEADER_LENGTH: usize = 18;
pub const MAX_SYNC_BUNDLE_BYTES: usize = 64 * 1024 * 1024;
pub const MAX_SYNC_PLAINTEXT_BYTES: usize = 64 * 1024 * 1024;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum SyncBundleKind {
    Head = 1,
    Snapshot = 2,
}

impl TryFrom<u8> for SyncBundleKind {
    type Error = SyncBundleError;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            1 => Ok(Self::Head),
            2 => Ok(Self::Snapshot),
            _ => Err(SyncBundleError::InvalidFormat("unknown bundle kind")),
        }
    }
}

#[derive(Debug, Error, PartialEq, Eq)]
pub enum SyncBundleError {
    #[error("sync bundle format is invalid: {0}")]
    InvalidFormat(&'static str),
    #[error("unsupported sync bundle version: {0}")]
    UnsupportedVersion(u8),
    #[error("sync bundle kind does not match the requested object")]
    UnexpectedKind,
    #[error("sync bundle context is invalid")]
    InvalidContext,
    #[error("sync bundle authentication failed")]
    AuthenticationFailed,
    #[error("sync bundle compressed payload is invalid")]
    InvalidCompression,
    #[error("sync bundle payload is too large")]
    PayloadTooLarge,
    #[error("sync bundle JSON payload is invalid")]
    InvalidPayload,
}

impl SyncBundleError {
    pub const fn code(&self) -> &'static str {
        match self {
            Self::InvalidFormat(_) => "INVALID_FORMAT",
            Self::UnsupportedVersion(_) => "UNSUPPORTED_VERSION",
            Self::UnexpectedKind => "UNEXPECTED_KIND",
            Self::InvalidContext => "INVALID_CONTEXT",
            Self::AuthenticationFailed => "AUTHENTICATION_FAILED",
            Self::InvalidCompression => "INVALID_COMPRESSION",
            Self::PayloadTooLarge => "PAYLOAD_TOO_LARGE",
            Self::InvalidPayload => "INVALID_PAYLOAD",
        }
    }
}

fn aad(kind: SyncBundleKind, vault_id: &str, object_id: &str) -> Result<Vec<u8>, SyncBundleError> {
    let vault_id = Uuid::parse_str(vault_id)
        .map_err(|_| SyncBundleError::InvalidContext)?
        .to_string();
    let object_id = object_id.trim();
    if object_id.is_empty() || object_id.chars().count() > 100 {
        return Err(SyncBundleError::InvalidContext);
    }
    let mut result = Vec::with_capacity(22 + vault_id.len() + object_id.len());
    result.extend_from_slice(b"SecretBase Sync V1\0");
    result.push(kind as u8);
    result.extend_from_slice(vault_id.as_bytes());
    result.push(0);
    result.extend_from_slice(object_id.as_bytes());
    Ok(result)
}

pub fn decrypt_sync_bundle(
    content: &[u8],
    key: &[u8],
    expected_kind: SyncBundleKind,
    vault_id: &str,
    object_id: &str,
) -> Result<Value, SyncBundleError> {
    if content.len() > MAX_SYNC_BUNDLE_BYTES || content.len() < SYNC_HEADER_LENGTH + 16 {
        return Err(SyncBundleError::InvalidFormat("invalid length"));
    }
    if &content[..4] != SYNC_MAGIC {
        return Err(SyncBundleError::InvalidFormat("invalid magic"));
    }
    if content[4] != SYNC_VERSION {
        return Err(SyncBundleError::UnsupportedVersion(content[4]));
    }
    let kind = SyncBundleKind::try_from(content[5])?;
    if kind != expected_kind {
        return Err(SyncBundleError::UnexpectedKind);
    }
    let cipher = Aes256Gcm::new_from_slice(key).map_err(|_| SyncBundleError::InvalidContext)?;
    let nonce = Nonce::from_slice(&content[6..SYNC_HEADER_LENGTH]);
    let compressed = cipher
        .decrypt(
            nonce,
            Payload {
                msg: &content[SYNC_HEADER_LENGTH..],
                aad: &aad(kind, vault_id, object_id)?,
            },
        )
        .map_err(|_| SyncBundleError::AuthenticationFailed)?;

    let decoder = GzDecoder::new(compressed.as_slice());
    let mut limited = decoder.take((MAX_SYNC_PLAINTEXT_BYTES + 1) as u64);
    let mut plaintext = Vec::new();
    limited
        .read_to_end(&mut plaintext)
        .map_err(|_| SyncBundleError::InvalidCompression)?;
    if plaintext.len() > MAX_SYNC_PLAINTEXT_BYTES {
        return Err(SyncBundleError::PayloadTooLarge);
    }
    let value: Value =
        serde_json::from_slice(&plaintext).map_err(|_| SyncBundleError::InvalidPayload)?;
    if !value.is_object() {
        return Err(SyncBundleError::InvalidPayload);
    }
    Ok(value)
}
