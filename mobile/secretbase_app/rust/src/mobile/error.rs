use secretbase_vault_core::VaultError;
use thiserror::Error;

#[derive(Debug, Clone, Error)]
pub enum MobileError {
    #[error("{message}")]
    Failure {
        code: String,
        message: String,
        retryable: bool,
    },
}

impl MobileError {
    pub fn new(code: &str, message: impl Into<String>) -> Self {
        Self::Failure {
            code: code.to_string(),
            message: message.into(),
            retryable: false,
        }
    }

    pub fn retryable(code: &str, message: impl Into<String>) -> Self {
        Self::Failure {
            code: code.to_string(),
            message: message.into(),
            retryable: true,
        }
    }
}

impl From<VaultError> for MobileError {
    fn from(error: VaultError) -> Self {
        let message = match &error {
            VaultError::AuthenticationFailed => "主密码错误或加密文件已损坏".to_string(),
            VaultError::UnsupportedEnvelopeVersion(_)
            | VaultError::UnsupportedPayloadVersion(_) => "该 Vault 版本暂不受支持".to_string(),
            VaultError::InvalidFormat(_) | VaultError::InvalidPayload(_) => {
                "Vault 文件格式无效".to_string()
            }
            VaultError::EncryptionFailed => "无法加密 Vault".to_string(),
        };
        Self::new(error.code(), message)
    }
}

impl From<std::io::Error> for MobileError {
    fn from(_: std::io::Error) -> Self {
        Self::retryable("STORAGE_FAILED", "无法读写本机密码库")
    }
}
