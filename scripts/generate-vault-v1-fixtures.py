from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "vault-v1"
PASSWORD = "SecretBase-V1-public-test-password"
ITERATIONS = 600000
VECTORS = (
    {
        "name": "empty",
        "salt_hex": "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f",
        "nonce_hex": "202122232425262728292a2b",
    },
    {
        "name": "unicode-rich",
        "salt_hex": "f0e0d0c0b0a090807060504030201000112233445566778899aabbccddeeff01",
        "nonce_hex": "0b1b2b3b4b5b6b7b8b9babbb",
    },
)


def canonical_json_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build_vault(plaintext: bytes, salt: bytes, nonce: bytes) -> bytes:
    key = hashlib.pbkdf2_hmac(
        "sha256",
        PASSWORD.encode("utf-8"),
        salt,
        iterations=ITERATIONS,
        dklen=32,
    )
    ciphertext_with_tag = AESGCM(key).encrypt(nonce, plaintext, None)
    ciphertext = ciphertext_with_tag[:-16]
    auth_tag = ciphertext_with_tag[-16:]
    return b"SB01" + bytes((1,)) + salt + nonce + auth_tag + ciphertext


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def main() -> int:
    manifest_vectors = []
    checksum_lines = []
    for vector in VECTORS:
        name = vector["name"]
        json_path = FIXTURE_DIR / f"{name}.json"
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        plaintext = canonical_json_bytes(payload)
        salt = bytes.fromhex(vector["salt_hex"])
        nonce = bytes.fromhex(vector["nonce_hex"])
        if len(salt) != 32 or len(nonce) != 12:
            raise ValueError(f"{name} 的 salt 或 nonce 长度无效")

        encrypted = build_vault(plaintext, salt, nonce)
        encrypted_name = f"{name}.vault"
        (FIXTURE_DIR / encrypted_name).write_bytes(encrypted)
        manifest_vectors.append({
            **vector,
            "plaintext_file": json_path.name,
            "encrypted_file": encrypted_name,
            "canonical_plaintext_sha256": sha256(plaintext),
            "encrypted_sha256": sha256(encrypted),
        })
        checksum_lines.extend((
            f"{sha256(json_path.read_bytes())}  {json_path.name}",
            f"{sha256(encrypted)}  {encrypted_name}",
        ))

    manifest = {
        "format": "SecretBase Vault V1",
        "magic_ascii": "SB01",
        "envelope_version": 1,
        "header_length": 65,
        "pbkdf2": {
            "hash": "SHA-256",
            "iterations": ITERATIONS,
            "key_length": 32,
        },
        "cipher": "AES-256-GCM",
        "aad": None,
        "test_password": PASSWORD,
        "vectors": manifest_vectors,
    }
    (FIXTURE_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (FIXTURE_DIR / "SHA256SUMS.txt").write_text(
        "\n".join(sorted(checksum_lines)) + "\n",
        encoding="ascii",
    )
    print(f"Generated {len(manifest_vectors)} Vault V1 vectors in {FIXTURE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
