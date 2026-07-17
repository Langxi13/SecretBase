//! SecretBase Vault V1 cross-language reference implementation.

pub mod sync_bundle;

use std::collections::HashSet;

use aes_gcm::{
    aead::{Aead, KeyInit},
    Aes256Gcm, Nonce,
};
use pbkdf2::pbkdf2_hmac;
use rand_core::{OsRng, RngCore};
use serde_json::{Map, Value};
use sha2::Sha256;
use thiserror::Error;
use uuid::Uuid;
use zeroize::Zeroizing;

pub const MAGIC_BYTES: &[u8; 4] = b"SB01";
pub const ENVELOPE_VERSION: u8 = 1;
pub const HEADER_LENGTH: usize = 65;
pub const PBKDF2_ITERATIONS: u32 = 600_000;
pub const SALT_LENGTH: usize = 32;
pub const NONCE_LENGTH: usize = 12;
pub const AUTH_TAG_LENGTH: usize = 16;
pub const PURPOSE_KEY_ITERATIONS: u32 = 100_000;
pub const DEVICE_UNLOCK_CREDENTIAL_LENGTH: usize = 69;

const DEVICE_UNLOCK_MAGIC: &[u8; 4] = b"SBUK";
const DEVICE_UNLOCK_VERSION: u8 = 1;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HeaderInfo {
    pub envelope_version: u8,
    pub salt: [u8; SALT_LENGTH],
    pub nonce: [u8; NONCE_LENGTH],
    pub ciphertext_len: usize,
}

#[derive(Debug, Error, PartialEq, Eq)]
pub enum VaultError {
    #[error("vault format is invalid: {0}")]
    InvalidFormat(&'static str),
    #[error("unsupported vault envelope version: {0}")]
    UnsupportedEnvelopeVersion(u8),
    #[error("vault password is incorrect or encrypted data is corrupt")]
    AuthenticationFailed,
    #[error("vault payload is invalid: {0}")]
    InvalidPayload(String),
    #[error("unsupported vault payload version: {0}")]
    UnsupportedPayloadVersion(String),
    #[error("vault encryption failed")]
    EncryptionFailed,
}

impl VaultError {
    pub const fn code(&self) -> &'static str {
        match self {
            Self::InvalidFormat(_) => "INVALID_FORMAT",
            Self::UnsupportedEnvelopeVersion(_) => "UNSUPPORTED_ENVELOPE_VERSION",
            Self::AuthenticationFailed => "AUTHENTICATION_FAILED",
            Self::InvalidPayload(_) => "INVALID_PAYLOAD",
            Self::UnsupportedPayloadVersion(_) => "UNSUPPORTED_PAYLOAD_VERSION",
            Self::EncryptionFailed => "ENCRYPTION_FAILED",
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct VaultDocument {
    value: Value,
}

impl VaultDocument {
    pub fn from_json_bytes(content: &[u8]) -> Result<Self, VaultError> {
        let value = serde_json::from_slice(content)
            .map_err(|error| VaultError::InvalidPayload(error.to_string()))?;
        Self::from_value(value)
    }

    pub fn from_value(mut value: Value) -> Result<Self, VaultError> {
        normalize_and_validate_document(&mut value)?;
        Ok(Self { value })
    }

    pub fn as_value(&self) -> &Value {
        &self.value
    }

    pub fn into_value(self) -> Value {
        self.value
    }

    pub fn to_json_bytes(&self) -> Result<Vec<u8>, VaultError> {
        serde_json::to_vec(&self.value)
            .map_err(|error| VaultError::InvalidPayload(error.to_string()))
    }
}

pub struct VaultSession {
    document: VaultDocument,
    key: Zeroizing<[u8; 32]>,
    salt: [u8; SALT_LENGTH],
}

impl VaultSession {
    pub fn create(password: &str, document: VaultDocument) -> Result<Self, VaultError> {
        let mut salt = [0_u8; SALT_LENGTH];
        OsRng.fill_bytes(&mut salt);
        Ok(Self {
            document,
            key: derive_key(password, &salt),
            salt,
        })
    }

    pub fn unlock(password: &str, content: &[u8]) -> Result<Self, VaultError> {
        let parsed = parse_header(content)?;
        let key = derive_key(password, &parsed.salt);
        let plaintext = decrypt_bytes_with_key(key.as_ref(), &parsed)?;
        let document = VaultDocument::from_json_bytes(&plaintext)?;
        Ok(Self {
            document,
            key,
            salt: parsed.salt,
        })
    }

    /// Returns a device-only credential that must be wrapped by platform secure storage
    /// before it is persisted. The credential is equivalent to the current vault key and
    /// must never be logged, backed up, or written as plaintext.
    pub fn device_unlock_credential(&self) -> Zeroizing<Vec<u8>> {
        let mut credential = Zeroizing::new(Vec::with_capacity(DEVICE_UNLOCK_CREDENTIAL_LENGTH));
        credential.extend_from_slice(DEVICE_UNLOCK_MAGIC);
        credential.push(DEVICE_UNLOCK_VERSION);
        credential.extend_from_slice(&self.salt);
        credential.extend_from_slice(self.key.as_ref());
        credential
    }

    pub fn unlock_with_device_credential(
        credential: &[u8],
        content: &[u8],
    ) -> Result<Self, VaultError> {
        if credential.len() != DEVICE_UNLOCK_CREDENTIAL_LENGTH
            || &credential[..DEVICE_UNLOCK_MAGIC.len()] != DEVICE_UNLOCK_MAGIC
            || credential[DEVICE_UNLOCK_MAGIC.len()] != DEVICE_UNLOCK_VERSION
        {
            return Err(VaultError::AuthenticationFailed);
        }

        let credential_salt: [u8; SALT_LENGTH] = credential[5..37]
            .try_into()
            .map_err(|_| VaultError::AuthenticationFailed)?;
        let parsed = parse_header(content)?;
        if parsed.salt != credential_salt {
            return Err(VaultError::AuthenticationFailed);
        }

        let key_bytes: [u8; 32] = credential[37..69]
            .try_into()
            .map_err(|_| VaultError::AuthenticationFailed)?;
        let key = Zeroizing::new(key_bytes);
        let plaintext = decrypt_bytes_with_key(key.as_ref(), &parsed)?;
        let document = VaultDocument::from_json_bytes(&plaintext)?;
        Ok(Self {
            document,
            key,
            salt: parsed.salt,
        })
    }

    pub fn document(&self) -> &VaultDocument {
        &self.document
    }

    pub fn replace_document(&mut self, value: Value) -> Result<(), VaultError> {
        self.document = VaultDocument::from_value(value)?;
        Ok(())
    }

    pub fn encrypted_bytes(&self) -> Result<Vec<u8>, VaultError> {
        self.encrypted_document_bytes(&self.document)
    }

    pub fn encrypted_document_bytes(
        &self,
        document: &VaultDocument,
    ) -> Result<Vec<u8>, VaultError> {
        let mut nonce = [0_u8; NONCE_LENGTH];
        OsRng.fill_bytes(&mut nonce);
        encrypt_bytes_with_key(
            self.key.as_ref(),
            self.salt,
            nonce,
            &document.to_json_bytes()?,
        )
    }

    pub fn rekey(&mut self, password: &str) {
        let mut salt = [0_u8; SALT_LENGTH];
        OsRng.fill_bytes(&mut salt);
        self.key = derive_key(password, &salt);
        self.salt = salt;
    }

    pub fn encrypt_scoped_bytes(
        &self,
        purpose: &str,
        plaintext: &[u8],
    ) -> Result<Vec<u8>, VaultError> {
        let key = derive_purpose_key(self.key.as_ref(), &self.salt, purpose);
        let mut nonce = [0_u8; NONCE_LENGTH];
        OsRng.fill_bytes(&mut nonce);
        encrypt_bytes_with_key(key.as_ref(), self.salt, nonce, plaintext)
    }

    pub fn decrypt_scoped_bytes(
        &self,
        purpose: &str,
        content: &[u8],
    ) -> Result<Vec<u8>, VaultError> {
        let parsed = parse_header(content)?;
        if parsed.salt != self.salt {
            return Err(VaultError::AuthenticationFailed);
        }
        let key = derive_purpose_key(self.key.as_ref(), &self.salt, purpose);
        decrypt_bytes_with_key(key.as_ref(), &parsed)
    }
}

pub fn validate_document(value: Value) -> Result<VaultDocument, VaultError> {
    VaultDocument::from_value(value)
}

struct ParsedHeader<'a> {
    salt: [u8; SALT_LENGTH],
    nonce: [u8; NONCE_LENGTH],
    auth_tag: &'a [u8],
    ciphertext: &'a [u8],
}

pub fn inspect_header(content: &[u8]) -> Result<HeaderInfo, VaultError> {
    let parsed = parse_header(content)?;
    Ok(HeaderInfo {
        envelope_version: ENVELOPE_VERSION,
        salt: parsed.salt,
        nonce: parsed.nonce,
        ciphertext_len: parsed.ciphertext.len(),
    })
}

pub fn decrypt_v1(password: &str, content: &[u8]) -> Result<VaultDocument, VaultError> {
    let parsed = parse_header(content)?;
    let key = derive_key(password, &parsed.salt);
    let plaintext = decrypt_bytes_with_key(key.as_ref(), &parsed)?;
    VaultDocument::from_json_bytes(&plaintext)
}

pub fn encrypt_v1(password: &str, document: &VaultDocument) -> Result<Vec<u8>, VaultError> {
    let mut salt = [0_u8; SALT_LENGTH];
    let mut nonce = [0_u8; NONCE_LENGTH];
    OsRng.fill_bytes(&mut salt);
    OsRng.fill_bytes(&mut nonce);
    encrypt_with_parameters(password, document, salt, nonce)
}

#[cfg(feature = "test-vectors")]
pub fn encrypt_v1_with_parameters(
    password: &str,
    document: &VaultDocument,
    salt: [u8; SALT_LENGTH],
    nonce: [u8; NONCE_LENGTH],
) -> Result<Vec<u8>, VaultError> {
    encrypt_with_parameters(password, document, salt, nonce)
}

fn encrypt_with_parameters(
    password: &str,
    document: &VaultDocument,
    salt: [u8; SALT_LENGTH],
    nonce: [u8; NONCE_LENGTH],
) -> Result<Vec<u8>, VaultError> {
    let plaintext = document.to_json_bytes()?;
    let key = derive_key(password, &salt);
    encrypt_bytes_with_key(key.as_ref(), salt, nonce, &plaintext)
}

fn encrypt_bytes_with_key(
    key: &[u8],
    salt: [u8; SALT_LENGTH],
    nonce: [u8; NONCE_LENGTH],
    plaintext: &[u8],
) -> Result<Vec<u8>, VaultError> {
    let cipher = Aes256Gcm::new_from_slice(key).map_err(|_| VaultError::EncryptionFailed)?;
    let ciphertext_with_tag = cipher
        .encrypt(Nonce::from_slice(&nonce), plaintext)
        .map_err(|_| VaultError::EncryptionFailed)?;
    if ciphertext_with_tag.len() < AUTH_TAG_LENGTH {
        return Err(VaultError::EncryptionFailed);
    }
    let tag_start = ciphertext_with_tag.len() - AUTH_TAG_LENGTH;
    let (ciphertext, auth_tag) = ciphertext_with_tag.split_at(tag_start);

    let mut output = Vec::with_capacity(HEADER_LENGTH + ciphertext.len());
    output.extend_from_slice(MAGIC_BYTES);
    output.push(ENVELOPE_VERSION);
    output.extend_from_slice(&salt);
    output.extend_from_slice(&nonce);
    output.extend_from_slice(auth_tag);
    output.extend_from_slice(ciphertext);
    Ok(output)
}

fn decrypt_bytes_with_key(key: &[u8], parsed: &ParsedHeader<'_>) -> Result<Vec<u8>, VaultError> {
    let cipher = Aes256Gcm::new_from_slice(key)
        .map_err(|_| VaultError::InvalidFormat("derived key length"))?;
    let mut ciphertext_with_tag = Vec::with_capacity(parsed.ciphertext.len() + AUTH_TAG_LENGTH);
    ciphertext_with_tag.extend_from_slice(parsed.ciphertext);
    ciphertext_with_tag.extend_from_slice(parsed.auth_tag);
    cipher
        .decrypt(
            Nonce::from_slice(&parsed.nonce),
            ciphertext_with_tag.as_ref(),
        )
        .map_err(|_| VaultError::AuthenticationFailed)
}

fn parse_header(content: &[u8]) -> Result<ParsedHeader<'_>, VaultError> {
    if content.len() < HEADER_LENGTH {
        return Err(VaultError::InvalidFormat("header is truncated"));
    }
    if &content[..MAGIC_BYTES.len()] != MAGIC_BYTES {
        return Err(VaultError::InvalidFormat("magic bytes do not match"));
    }
    let version = content[MAGIC_BYTES.len()];
    if version != ENVELOPE_VERSION {
        return Err(VaultError::UnsupportedEnvelopeVersion(version));
    }

    let salt = content[5..37]
        .try_into()
        .map_err(|_| VaultError::InvalidFormat("salt length"))?;
    let nonce = content[37..49]
        .try_into()
        .map_err(|_| VaultError::InvalidFormat("nonce length"))?;
    Ok(ParsedHeader {
        salt,
        nonce,
        auth_tag: &content[49..65],
        ciphertext: &content[65..],
    })
}

fn derive_key(password: &str, salt: &[u8; SALT_LENGTH]) -> Zeroizing<[u8; 32]> {
    let mut key = Zeroizing::new([0_u8; 32]);
    pbkdf2_hmac::<Sha256>(password.as_bytes(), salt, PBKDF2_ITERATIONS, key.as_mut());
    key
}

fn derive_purpose_key(
    vault_key: &[u8],
    salt: &[u8; SALT_LENGTH],
    purpose: &str,
) -> Zeroizing<[u8; 32]> {
    let mut scoped_salt = Vec::with_capacity(12 + salt.len() + purpose.len());
    scoped_salt.extend_from_slice(b"SecretBase:");
    scoped_salt.extend_from_slice(salt);
    scoped_salt.push(b':');
    scoped_salt.extend_from_slice(purpose.as_bytes());
    let mut key = Zeroizing::new([0_u8; 32]);
    pbkdf2_hmac::<Sha256>(
        vault_key,
        &scoped_salt,
        PURPOSE_KEY_ITERATIONS,
        key.as_mut(),
    );
    key
}

fn normalize_and_validate_document(value: &mut Value) -> Result<(), VaultError> {
    let root = value
        .as_object_mut()
        .ok_or_else(|| VaultError::InvalidPayload("root must be an object".to_string()))?;
    normalize_payload_defaults(root);
    validate_payload_version(root)?;
    require_string(root, "created_at", "root")?;
    require_string(root, "app_name", "root")?;
    normalize_optional_vault_id(root)?;
    validate_meta_object(root, "tags_meta")?;
    validate_meta_object(root, "groups_meta")?;
    validate_entries(root, "entries")?;
    validate_entries(root, "deleted_entries")?;
    Ok(())
}

fn normalize_optional_vault_id(root: &mut Map<String, Value>) -> Result<(), VaultError> {
    let Some(value) = root.get_mut("vault_id") else {
        return Ok(());
    };
    if value.is_null() {
        return Ok(());
    }
    let raw = value.as_str().ok_or_else(|| {
        VaultError::InvalidPayload("root.vault_id must be a UUID string or null".to_string())
    })?;
    let normalized = Uuid::parse_str(raw)
        .map_err(|_| VaultError::InvalidPayload("root.vault_id must be a valid UUID".to_string()))?
        .to_string();
    *value = Value::String(normalized);
    Ok(())
}

fn normalize_payload_defaults(root: &mut Map<String, Value>) {
    root.entry("version")
        .or_insert_with(|| Value::String("1.0".to_string()));
    root.entry("app_name")
        .or_insert_with(|| Value::String("SecretBase".to_string()));
    for key in ["entries", "deleted_entries"] {
        root.entry(key).or_insert_with(|| Value::Array(Vec::new()));
    }
    for key in ["tags_meta", "groups_meta"] {
        root.entry(key).or_insert_with(|| Value::Object(Map::new()));
    }
}

fn validate_payload_version(root: &Map<String, Value>) -> Result<(), VaultError> {
    let version = root
        .get("version")
        .and_then(Value::as_str)
        .ok_or_else(|| VaultError::InvalidPayload("version must be a string".to_string()))?;
    let major = version
        .split('.')
        .next()
        .and_then(|part| part.parse::<u32>().ok())
        .ok_or_else(|| VaultError::InvalidPayload("version is invalid".to_string()))?;
    if major != 1 {
        return Err(VaultError::UnsupportedPayloadVersion(version.to_string()));
    }
    Ok(())
}

fn validate_meta_object(root: &Map<String, Value>, key: &str) -> Result<(), VaultError> {
    if root.get(key).is_some_and(Value::is_object) {
        return Ok(());
    }
    Err(VaultError::InvalidPayload(format!(
        "{key} must be an object"
    )))
}

fn validate_entries(root: &mut Map<String, Value>, key: &str) -> Result<(), VaultError> {
    let entries = root
        .get_mut(key)
        .and_then(Value::as_array_mut)
        .ok_or_else(|| VaultError::InvalidPayload(format!("{key} must be an array")))?;
    for (index, entry) in entries.iter_mut().enumerate() {
        validate_entry(entry, key, index)?;
    }
    Ok(())
}

fn validate_entry(entry: &mut Value, collection: &str, index: usize) -> Result<(), VaultError> {
    let path = format!("{collection}[{index}]");
    let object = entry
        .as_object_mut()
        .ok_or_else(|| VaultError::InvalidPayload(format!("{path} must be an object")))?;
    require_bounded_string(object, "title", &path, 1, 200)?;
    for key in ["id", "created_at", "updated_at"] {
        optional_string(object, key, &path)?;
    }
    optional_bounded_string(object, "remarks", &path, 2000)?;
    validate_url(object, &path)?;
    optional_bool(object, "starred", &path)?;
    optional_bool(object, "deleted", &path)?;
    optional_nullable_string(object, "deleted_at", &path)?;
    normalize_name_array(object, "tags", &path)?;
    normalize_name_array(object, "groups", &path)?;
    if let Some(fields) = object.get_mut("fields") {
        let fields = fields
            .as_array_mut()
            .ok_or_else(|| VaultError::InvalidPayload(format!("{path}.fields must be an array")))?;
        let mut field_names = HashSet::new();
        for (field_index, field) in fields.iter_mut().enumerate() {
            let field_name = validate_field(field, &format!("{path}.fields[{field_index}]"))?;
            if !field_names.insert(field_name.clone()) {
                return Err(VaultError::InvalidPayload(format!(
                    "{path}.fields contains duplicate name: {field_name}"
                )));
            }
        }
    }
    Ok(())
}

fn validate_field(field: &mut Value, path: &str) -> Result<String, VaultError> {
    let object = field
        .as_object_mut()
        .ok_or_else(|| VaultError::InvalidPayload(format!("{path} must be an object")))?;
    let name = require_bounded_string(object, "name", path, 1, 100)?.to_string();
    if name.trim().is_empty() {
        return Err(VaultError::InvalidPayload(format!(
            "{path}.name must not be blank"
        )));
    }
    optional_bounded_string(object, "value", path, 10_000)?;
    optional_bool(object, "copyable", path)?;
    if let Some(hidden) = object.get("hidden") {
        if !hidden.is_null() && !hidden.is_boolean() {
            return Err(VaultError::InvalidPayload(format!(
                "{path}.hidden must be a boolean or null"
            )));
        }
    }
    Ok(name)
}

fn require_bounded_string<'a>(
    object: &'a Map<String, Value>,
    key: &str,
    path: &str,
    minimum: usize,
    maximum: usize,
) -> Result<&'a str, VaultError> {
    let value = object
        .get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| VaultError::InvalidPayload(format!("{path}.{key} must be a string")))?;
    let length = value.chars().count();
    if (minimum..=maximum).contains(&length) {
        return Ok(value);
    }
    Err(VaultError::InvalidPayload(format!(
        "{path}.{key} length must be between {minimum} and {maximum}"
    )))
}

fn optional_bounded_string(
    object: &Map<String, Value>,
    key: &str,
    path: &str,
    maximum: usize,
) -> Result<(), VaultError> {
    let Some(value) = object.get(key) else {
        return Ok(());
    };
    let value = value
        .as_str()
        .ok_or_else(|| VaultError::InvalidPayload(format!("{path}.{key} must be a string")))?;
    if value.chars().count() <= maximum {
        return Ok(());
    }
    Err(VaultError::InvalidPayload(format!(
        "{path}.{key} length must not exceed {maximum}"
    )))
}

fn validate_url(object: &Map<String, Value>, path: &str) -> Result<(), VaultError> {
    let Some(url) = object.get("url") else {
        return Ok(());
    };
    let url = url
        .as_str()
        .ok_or_else(|| VaultError::InvalidPayload(format!("{path}.url must be a string")))?;
    if url.chars().count() > 2000 {
        return Err(VaultError::InvalidPayload(format!(
            "{path}.url length must not exceed 2000"
        )));
    }
    if !url.is_empty() && !url.starts_with("http://") && !url.starts_with("https://") {
        return Err(VaultError::InvalidPayload(format!(
            "{path}.url must use http or https"
        )));
    }
    Ok(())
}

fn normalize_name_array(
    object: &mut Map<String, Value>,
    key: &str,
    path: &str,
) -> Result<(), VaultError> {
    let Some(value) = object.get_mut(key) else {
        return Ok(());
    };
    let values = value
        .as_array_mut()
        .ok_or_else(|| VaultError::InvalidPayload(format!("{path}.{key} must be an array")))?;
    let mut normalized = Vec::with_capacity(values.len());
    let mut seen = HashSet::new();
    for value in values.iter() {
        let name = value.as_str().ok_or_else(|| {
            VaultError::InvalidPayload(format!("{path}.{key} must contain strings"))
        })?;
        let name = name.trim();
        if name.is_empty() || name.chars().count() > 50 {
            return Err(VaultError::InvalidPayload(format!(
                "{path}.{key} names must contain 1 to 50 characters"
            )));
        }
        if seen.insert(name.to_string()) {
            normalized.push(Value::String(name.to_string()));
        }
    }
    *values = normalized;
    Ok(())
}

fn require_string(object: &Map<String, Value>, key: &str, path: &str) -> Result<(), VaultError> {
    if object.get(key).is_some_and(Value::is_string) {
        return Ok(());
    }
    Err(VaultError::InvalidPayload(format!(
        "{path}.{key} must be a string"
    )))
}

fn optional_string(object: &Map<String, Value>, key: &str, path: &str) -> Result<(), VaultError> {
    if object.get(key).is_none_or(Value::is_string) {
        return Ok(());
    }
    Err(VaultError::InvalidPayload(format!(
        "{path}.{key} must be a string"
    )))
}

fn optional_nullable_string(
    object: &Map<String, Value>,
    key: &str,
    path: &str,
) -> Result<(), VaultError> {
    if object
        .get(key)
        .is_none_or(|value| value.is_null() || value.is_string())
    {
        return Ok(());
    }
    Err(VaultError::InvalidPayload(format!(
        "{path}.{key} must be a string or null"
    )))
}

fn optional_bool(object: &Map<String, Value>, key: &str, path: &str) -> Result<(), VaultError> {
    if object.get(key).is_none_or(Value::is_boolean) {
        return Ok(());
    }
    Err(VaultError::InvalidPayload(format!(
        "{path}.{key} must be a boolean"
    )))
}
