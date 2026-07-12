from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from crypto import DecryptionError, decrypt_vault, parse_vault_header  # noqa: E402
from models import VaultData  # noqa: E402
from vault_document import VaultDocumentError, decode_vault_document, encode_vault_document  # noqa: E402


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "vault-v1"


def canonical_json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def deterministic_encrypt(password: str, plaintext: bytes, salt: bytes, nonce: bytes) -> bytes:
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600000, 32)
    ciphertext_with_tag = AESGCM(key).encrypt(nonce, plaintext, None)
    return b"SB01" + b"\x01" + salt + nonce + ciphertext_with_tag[-16:] + ciphertext_with_tag[:-16]


def expect_error(callback, error_type) -> None:
    try:
        callback()
    except error_type:
        return
    raise AssertionError(f"Expected {error_type.__name__}")


def main() -> None:
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    checksums = {
        filename: digest
        for line in (FIXTURE_DIR / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines()
        for digest, filename in (line.split("  ", 1),)
    }
    assert manifest["magic_ascii"] == "SB01"
    assert manifest["header_length"] == 65
    assert manifest["pbkdf2"]["iterations"] == 600000
    password = manifest["test_password"]

    rich_vault = None
    for vector in manifest["vectors"]:
        source = json.loads((FIXTURE_DIR / vector["plaintext_file"]).read_text(encoding="utf-8"))
        expected_plaintext = canonical_json_bytes(source)
        encrypted = (FIXTURE_DIR / vector["encrypted_file"]).read_bytes()
        assert hashlib.sha256((FIXTURE_DIR / vector["plaintext_file"]).read_bytes()).hexdigest() == checksums[vector["plaintext_file"]]
        assert hashlib.sha256(encrypted).hexdigest() == checksums[vector["encrypted_file"]]
        assert hashlib.sha256(expected_plaintext).hexdigest() == vector["canonical_plaintext_sha256"]
        assert hashlib.sha256(encrypted).hexdigest() == vector["encrypted_sha256"]

        header = parse_vault_header(encrypted)
        assert header["salt"].hex() == vector["salt_hex"]
        assert header["nonce"].hex() == vector["nonce_hex"]
        assert decrypt_vault(password, encrypted) == expected_plaintext
        assert deterministic_encrypt(password, expected_plaintext, header["salt"], header["nonce"]) == encrypted

        document = decode_vault_document(expected_plaintext)
        assert json.loads(encode_vault_document(document)) == source
        if vector["name"] == "unicode-rich":
            rich_vault = encrypted
            dumped = document.model_dump()
            assert dumped["future_root"]["enabled"] is True
            assert dumped["entries"][0]["future_entry"]["flags"][-1] == "测试"
            assert dumped["entries"][0]["fields"][0]["future_field"]["retain"] == "字段扩展"
            document.entries[0].remarks = "修改已知字段后仍需保留扩展"
            changed = decode_vault_document(encode_vault_document(document)).model_dump()
            assert changed["future_root"]["enabled"] is True
            assert changed["entries"][0]["future_entry"]["flags"][-1] == "测试"
            assert changed["entries"][0]["fields"][0]["future_field"]["retain"] == "字段扩展"

    assert rich_vault is not None
    expect_error(lambda: decrypt_vault("wrong-password", rich_vault), DecryptionError)
    expect_error(lambda: parse_vault_header(rich_vault[:64]), DecryptionError)
    expect_error(lambda: parse_vault_header(b"NOPE" + rich_vault[4:]), DecryptionError)
    expect_error(lambda: parse_vault_header(rich_vault[:4] + b"\x02" + rich_vault[5:]), DecryptionError)

    tampered = bytearray(rich_vault)
    tampered[49] ^= 0x01
    expect_error(lambda: decrypt_vault(password, bytes(tampered)), DecryptionError)
    expect_error(lambda: decode_vault_document(b"[]"), VaultDocumentError)
    expect_error(lambda: decode_vault_document(b"\xff"), VaultDocumentError)
    try:
        VaultData(version="2.0")
    except ValidationError:
        pass
    else:
        raise AssertionError("Vault payload major version 2 must be rejected")

    print("PASS Vault V1 Python compatibility vectors")


if __name__ == "__main__":
    main()
