from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sync_crypto import KIND_HEAD, KIND_SNAPSHOT, SyncCryptoError, decrypt_bundle  # noqa: E402


MANIFEST = ROOT / "tests" / "fixtures" / "sync-v1" / "manifest.json"


def expect_crypto_error(callback) -> None:
    try:
        callback()
    except SyncCryptoError:
        return
    raise AssertionError("损坏或上下文不匹配的同步向量必须被拒绝")


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    for vector in manifest["vectors"]:
        key = bytes.fromhex(vector["key_hex"])
        bundle = bytes.fromhex(vector["bundle_hex"])
        kind = KIND_HEAD if vector["kind"] == KIND_HEAD else KIND_SNAPSHOT
        assert bundle[:4] == b"SBS1"
        assert bundle[4] == 1
        assert bundle[5] == kind
        assert bundle[6:18].hex() == vector["nonce_hex"]
        assert hashlib.sha256(bundle).hexdigest() == vector["bundle_sha256"]
        assert decrypt_bundle(
            bundle,
            key,
            kind=kind,
            vault_id=vector["vault_id"],
            object_id=vector["object_id"],
        ) == vector["payload"]

        damaged = bytearray(bundle)
        damaged[-1] ^= 1
        expect_crypto_error(lambda: decrypt_bundle(
            bytes(damaged),
            key,
            kind=kind,
            vault_id=vector["vault_id"],
            object_id=vector["object_id"],
        ))
        expect_crypto_error(lambda: decrypt_bundle(
            bundle,
            bytes(reversed(key)),
            kind=kind,
            vault_id=vector["vault_id"],
            object_id=vector["object_id"],
        ))
        expect_crypto_error(lambda: decrypt_bundle(
            bundle,
            key,
            kind=kind,
            vault_id=vector["vault_id"],
            object_id="55555555-5555-4555-8555-555555555555",
        ))
    print("PASS Sync Bundle V1 Python vectors")


if __name__ == "__main__":
    main()
