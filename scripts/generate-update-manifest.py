from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization


REPOSITORY = "Langxi13/SecretBase"
EXPECTED_UPDATE_KEY_ID = "1c9180b8f11c8c43"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and sign the SecretBase update manifest.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--assets-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--private-key-file")
    parser.add_argument("--published-at")
    parser.add_argument("--notes", default="")
    parser.add_argument("--expected-key-id", default=EXPECTED_UPDATE_KEY_ID)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def asset_payload(path: Path, *, version: str) -> dict[str, str | int]:
    return {
        "filename": path.name,
        "url": f"https://github.com/{REPOSITORY}/releases/download/v{version}/{path.name}",
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def read_private_key(path: str | None):
    if path:
        pem = Path(path).read_bytes()
    else:
        encoded = os.environ.get("UPDATE_SIGNING_PRIVATE_KEY_PEM_BASE64", "")
        if not encoded:
            raise RuntimeError("UPDATE_SIGNING_PRIVATE_KEY_PEM_BASE64 is required")
        pem = base64.b64decode(encoded, validate=True)
    return serialization.load_pem_private_key(pem, password=None)


def require_asset(root: Path, filename: str) -> Path:
    path = root / filename
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def main() -> int:
    args = parse_args()
    version = args.version.strip()
    if not version or any(not part.isdigit() for part in version.split(".")) or len(version.split(".")) != 3:
        raise ValueError("version must use major.minor.patch")

    assets_dir = Path(args.assets_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    windows = require_asset(assets_dir, f"SecretBase-v{version}-windows-x64-setup.exe")
    macos = require_asset(assets_dir, f"SecretBase-v{version}-macos-arm64.dmg")
    android_assets = {
        "android-universal": require_asset(
            assets_dir, f"SecretBase-v{version}-android-universal.apk"
        ),
        "android-arm64-v8a": require_asset(
            assets_dir, f"SecretBase-v{version}-android-arm64-v8a.apk"
        ),
        "android-armeabi-v7a": require_asset(
            assets_dir, f"SecretBase-v{version}-android-armeabi-v7a.apk"
        ),
        "android-x86_64": require_asset(
            assets_dir, f"SecretBase-v{version}-android-x86_64.apk"
        ),
    }
    android_metadata = json.loads(require_asset(assets_dir, "ANDROID-METADATA.json").read_text(encoding="utf-8"))
    if android_metadata.get("version_name") != version:
        raise ValueError("Android metadata version does not match release version")
    android_version_codes = android_metadata.get("version_codes", {})
    if not isinstance(android_version_codes, dict):
        raise ValueError("Android metadata version_codes must be an object")

    private_key = read_private_key(args.private_key_file)
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = hashlib.sha256(public_raw).hexdigest()[:16]
    if key_id != args.expected_key_id:
        raise ValueError("update signing key does not match the public key embedded in clients")
    android_payloads = {}
    for key, path in android_assets.items():
        current_payload = asset_payload(path, version=version)
        current_payload.update({
            "package_id": android_metadata["package_id"],
            "version_code": int(
                android_version_codes.get(key, android_metadata["version_code"])
            ),
            "signer_sha256": str(android_metadata["signer_sha256"]).lower(),
        })
        android_payloads[key] = current_payload
    published_at = args.published_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    payload = {
        "schema_version": 1,
        "key_id": key_id,
        "channel": "stable",
        "version": version,
        "published_at": published_at,
        "release_url": f"https://github.com/{REPOSITORY}/releases/tag/v{version}",
        "notes": args.notes.strip() or f"SecretBase {version} 正式版本",
        "assets": {
            "windows-x64-installer": asset_payload(windows, version=version),
            "macos-arm64-dmg": asset_payload(macos, version=version),
            **android_payloads,
        },
    }
    manifest_bytes = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    signature = private_key.sign(manifest_bytes)
    manifest_path = output_dir / "secretbase-update-v1.json"
    signature_path = output_dir / "secretbase-update-v1.json.sig"
    manifest_path.write_bytes(manifest_bytes)
    signature_path.write_text(base64.b64encode(signature).decode("ascii") + "\n", encoding="ascii")
    print(f"Update manifest: {manifest_path}")
    print(f"Update signature: {signature_path}")
    print(f"Update key id: {key_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
