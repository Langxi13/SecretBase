"""Vault V1 JSON payload codec without storage or encryption side effects."""

from __future__ import annotations

import json

from pydantic import ValidationError

from models import VaultData


class VaultDocumentError(ValueError):
    """Raised when decrypted vault payload bytes do not match Vault V1."""


def decode_vault_document(content: bytes) -> VaultData:
    """Decode and validate a UTF-8 Vault V1 JSON payload."""
    try:
        payload = json.loads(content.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Vault payload 根节点必须是对象")
        return VaultData.model_validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError, ValueError) as error:
        raise VaultDocumentError("Vault payload 无效") from error


def encode_vault_document(vault: VaultData) -> bytes:
    """Serialize Vault V1 while retaining allowed unknown JSON fields."""
    if not isinstance(vault, VaultData):
        try:
            vault = VaultData.model_validate(vault)
        except (ValidationError, TypeError, ValueError) as error:
            raise VaultDocumentError("Vault payload 无效") from error
    exclude = {"vault_id"} if vault.vault_id is None else None
    return vault.model_dump_json(exclude=exclude).encode("utf-8")
